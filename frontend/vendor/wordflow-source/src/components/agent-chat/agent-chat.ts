import { LitElement, css, html, PropertyValues, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import {
  sendChatMessage,
  streamChatRunEvents,
  type ChatSelectionPayload,
  type ChatEventStream,
  type ChatRunEventPayload
} from '../../product/chat-client';

import componentCSS from './agent-chat.css?inline';

interface ChatDisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  reasoning?: string[];
}

@customElement('wordflow-agent-chat')
export class WordflowAgentChat extends LitElement {
  @property({ type: Number })
  documentId: number | null = null;

  @property({ type: Number })
  documentVersionId: number | null = null;

  @property({ attribute: false })
  selection: ChatSelectionPayload | null = null;

  @state()
  messages: ChatDisplayMessage[] = [];

  @state()
  draft = '';

  @state()
  isStreaming = false;

  @state()
  statusText = 'Document chat';

  eventSource: ChatEventStream | null = null;

  willUpdate(changedProperties: PropertyValues<this>) {}

  disconnectedCallback() {
    super.disconnectedCallback();
    this.eventSource?.close();
  }

  async sendMessage() {
    const content = this.draft.trim();
    if (!content || this.documentId === null || this.isStreaming) return;

    this.messages = [
      ...this.messages,
      { role: 'user', content },
      { role: 'assistant', content: '', reasoning: [] }
    ];
    this.draft = '';
    this.isStreaming = true;
    this.statusText = 'Thinking';

    try {
      const payload = {
        content,
        selection: this.selection,
        document_version_id: this.documentVersionId
      };
      const run = await sendChatMessage(this.documentId, payload);
      this.eventSource = streamChatRunEvents(run.run_id, {
        onEvent: event => this.handleRunEvent(event),
        onError: () => {
          this.statusText = 'Reconnecting';
        },
        onDone: () => {
          this.statusText = 'Document chat';
          this.isStreaming = false;
        }
      });
    } catch (error) {
      this.statusText = 'Chat unavailable';
      this.isStreaming = false;
      this.appendAssistantDelta(this.formatChatError(error));
    }
  }

  formatChatError(error: unknown) {
    const fallback = 'AI chat is unavailable. Please try again.';
    const raw = error instanceof Error ? error.message : '';
    if (!raw) return fallback;

    try {
      const payload = JSON.parse(raw);
      const detail = payload.detail;
      if (typeof detail === 'string' && !detail.includes('{')) return detail;
      if (detail?.error_code || detail?.node_id) return fallback;
    } catch (_) {
      // Keep the readable raw message fallback below.
    }

    if (raw.includes('Internal Server Error') || raw.includes('E_UNHANDLED')) {
      return fallback;
    }
    return raw;
  }

  handleRunEvent(event: ChatRunEventPayload) {
    if (event.event_type === 'message_delta') {
      this.appendAssistantDelta(String(event.delta ?? event.content ?? ''));
    } else if (event.event_type === 'reasoning_trace') {
      this.appendReasoningTrace(
        String(event.content ?? event.summary ?? 'reasoning_trace')
      );
    } else if (event.event_type === 'runtime_update') {
      this.statusText = String(event.stage ?? event.current_stage ?? 'Working');
    } else if (event.event_type === 'run_failed') {
      this.statusText = 'Run failed';
      this.isStreaming = false;
    } else if (event.event_type === 'run_cancelled') {
      this.statusText = 'Run cancelled';
      this.isStreaming = false;
    }
  }

  appendAssistantDelta(delta: string) {
    if (!delta) return;
    const messages = [...this.messages];
    const last = messages[messages.length - 1];
    if (last?.role === 'assistant') {
      messages[messages.length - 1] = {
        ...last,
        content: `${last.content}${delta}`
      };
    } else {
      messages.push({ role: 'assistant', content: delta, reasoning: [] });
    }
    this.messages = messages;
  }

  appendReasoningTrace(content: string) {
    if (!content) return;
    const messages = [...this.messages];
    const last = messages[messages.length - 1];
    if (last?.role === 'assistant') {
      messages[messages.length - 1] = {
        ...last,
        reasoning: [...(last.reasoning ?? []), content]
      };
    }
    this.messages = messages;
  }

  keydownHandler(event: KeyboardEvent) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      void this.sendMessage();
    }
  }

  renderMessage(message: ChatDisplayMessage) {
    return html`
      <div class="message ${message.role}">
        <div class="bubble">${message.content || '...'}</div>
        ${(message.reasoning ?? []).map(
          reasoning => html`<div class="reasoning">${reasoning}</div>`
        )}
      </div>
    `;
  }

  render() {
    const hasDocument = this.documentId !== null;
    return html`
      <section class="agent-chat" aria-label="Document chat">
        <div class="header">
          <span class="title">AI</span>
          <span class="status">${hasDocument ? this.statusText : 'Saving document'}</span>
        </div>
        <div class="messages">
          ${this.messages.length === 0
            ? html`<div class="message assistant">
                <div class="bubble">
                  ${this.selection?.text
                    ? 'Ask about the selected text.'
                    : 'Ask about the current script.'}
                </div>
              </div>`
            : this.messages.map(message => this.renderMessage(message))}
        </div>
        <div class="composer">
          <textarea
            .value=${this.draft}
            ?disabled=${!hasDocument || this.isStreaming}
            @input=${(event: InputEvent) => {
              this.draft = (event.target as HTMLTextAreaElement).value;
            }}
            @keydown=${(event: KeyboardEvent) => this.keydownHandler(event)}
          ></textarea>
          <div class="actions">
            <button
              ?disabled=${!hasDocument || this.isStreaming || !this.draft.trim()}
              @click=${() => void this.sendMessage()}
            >
              Send
            </button>
          </div>
        </div>
      </section>
    `;
  }

  static styles = css`
    ${unsafeCSS(componentCSS)}
  `;
}
