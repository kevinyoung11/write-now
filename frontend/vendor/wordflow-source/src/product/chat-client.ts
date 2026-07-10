import { config } from '../config/config';
import { authHeaders, parseJsonResponse } from './api-client';

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
  onError?: (error: unknown) => void;
  onDone?: () => void;
}

export interface ChatEventStream {
  close: () => void;
}

const TERMINAL_EVENTS = ['run_completed', 'run_failed', 'run_cancelled'];
const RECONNECT_DELAY_MS = 500;

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
): ChatEventStream {
  let closed = false;
  let lastSeq = fromSeq;
  let controller: AbortController | null = null;

  const close = () => {
    closed = true;
    controller?.abort();
  };

  const connect = async () => {
    while (!closed) {
      try {
        controller = new AbortController();
        await readSseStream(
          `${config.urls.chatRunEventsEndpoint}/${runId}/events?from_seq=${lastSeq}`,
          controller,
          event => {
            if (typeof event.seq === 'number') {
              lastSeq = event.seq;
            }
            handlers.onEvent?.(event);
            if (TERMINAL_EVENTS.includes(event.event_type)) {
              close();
              handlers.onDone?.();
            }
          }
        );
      } catch (error) {
        if (!closed) {
          handlers.onError?.(error);
          await sleep(RECONNECT_DELAY_MS);
          fromSeq = lastSeq;
        }
      }
    }
  };

  void connect();
  return { close };
}

async function readSseStream(
  url: string,
  controller: AbortController,
  onEvent: (event: ChatRunEventPayload) => void
) {
  const response = await fetch(url, {
    headers: authHeaders(false),
    signal: controller.signal
  });
  if (!response.ok || response.body === null) {
    throw new Error(await response.text());
  }

  const reader: ReadableStreamDefaultReader<Uint8Array> =
    response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';
    for (const part of parts) {
      const event = parseSseEvent(part);
      if (event !== null) onEvent(event);
    }
  }
}

function parseSseEvent(chunk: string): ChatRunEventPayload | null {
  const eventType = chunk
    .split('\n')
    .find(line => line.startsWith('event: '))
    ?.replace('event: ', '')
    .trim();
  const dataLine = chunk
    .split('\n')
    .find(line => line.startsWith('data: '))
    ?.replace('data: ', '');
  if (!eventType || !dataLine) return null;

  const payload = JSON.parse(dataLine);
  const normalizedEventType =
    eventType === 'reasoning_delta' || eventType === 'reasoning_completed'
      ? 'reasoning_trace'
      : eventType;
  return { ...payload, event_type: normalizedEventType };
}

function sleep(milliseconds: number) {
  return new Promise(resolve => window.setTimeout(resolve, milliseconds));
}

