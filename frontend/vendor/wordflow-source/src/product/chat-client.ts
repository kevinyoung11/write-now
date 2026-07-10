import { config } from '../config/config';

export interface ChatSelectionPayload {
  text: string;
  context_before?: string;
  context_after?: string;
}

export interface ChatMessageRequest {
  content: string;
  selection?: ChatSelectionPayload | null;
  document_version_id?: number | null;
}

export interface ChatRunPayload {
  run_id: number;
  thread_id: number;
  status: string;
}

export interface ChatRunEventPayload {
  seq: number;
  event_type: string;
  [key: string]: unknown;
}

export interface ChatStreamHandlers {
  onEvent?: (event: ChatRunEventPayload) => void;
  onError?: (error: Event) => void;
  onDone?: () => void;
}

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const accessToken = localStorage.getItem('supabase-access-token');
  const devUserId = localStorage.getItem('user-id');

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  } else if (devUserId) {
    headers['X-Dev-User-Id'] = devUserId;
  }

  return headers;
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export async function sendChatMessage(
  documentId: number,
  payload: ChatMessageRequest
): Promise<ChatRunPayload> {
  const response = await fetch(
    `${config.urls.chatMessagesEndpoint}/${documentId}/chat/messages`,
    {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        content: payload.content,
        selection: payload.selection ?? null,
        base_version_id: payload.document_version_id ?? null,
        document_version_id: payload.document_version_id ?? null
      })
    }
  );
  return parseJsonResponse<ChatRunPayload>(response);
}

export function streamChatRunEvents(
  runId: number,
  handlers: ChatStreamHandlers,
  fromSeq = 0
): EventSource {
  const source = new EventSource(
    `${config.urls.chatRunEventsEndpoint}/${runId}/events?from_seq=${fromSeq}`,
    { withCredentials: true }
  );
  const terminalEvents = ['run_completed', 'run_failed', 'run_cancelled'];
  const eventTypes = [
    'run_started',
    'message_delta',
    'reasoning_trace',
    'runtime_update',
    ...terminalEvents
  ];

  for (const eventType of eventTypes) {
    source.addEventListener(eventType, event => {
      const payload = JSON.parse((event as MessageEvent).data);
      handlers.onEvent?.({ ...payload, event_type: eventType });
      if (terminalEvents.includes(eventType)) {
        source.close();
        handlers.onDone?.();
      }
    });
  }

  source.onerror = error => {
    handlers.onError?.(error);
  };

  return source;
}

