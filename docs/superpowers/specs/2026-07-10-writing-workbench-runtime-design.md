# Writing Workbench Runtime Design

Date: 2026-07-10

## Goal

Build the first stable runtime for a video-script writing workbench on top of the current Wordflow-based editor. The runtime must make user documents durable, versioned, and recoverable while allowing AI to interact with selected text, paragraphs, and a document-scoped chat.

The first phase is intentionally narrow: make documents and versions the product source of truth, then attach Wordflow text actions and a DeepAgents-powered streaming chat to that model.

## Current Context

The app currently serves Wordflow directly as the frontend root. Wordflow already supports selection-aware prompt execution, paragraph fallback, replace/append injection modes, loading highlights, diff display, and accept/reject behavior.

The backend already has FastAPI, SQLModel, Supabase/Postgres configuration, Wordflow model proxy routes, and legacy writing workflow tables such as `rewrite_records`, `review_records`, `workflow_jobs`, and `workflow_job_events`.

The missing product layer is user-owned documents, document versions, document-scoped agent chat, and a clean runtime boundary between editor state, AI execution state, and persisted writing history.

## Scope

In scope for the first implementation:

- Supabase-authenticated users.
- User-owned documents.
- Key-change document version history.
- Wordflow-based selection and paragraph AI actions.
- Four built-in text actions: expand, rewrite, oralize, shorten.
- A document-scoped DeepAgents chat runtime.
- LangGraph/DeepAgents streaming events exposed through backend SSE.
- Visible reasoning/runtime traces when the model or runtime exposes them.
- Replayable run events.
- Version creation only when the user accepts or explicitly saves a change.

Out of scope for the first implementation:

- Full research-to-script workflow automation.
- Multi-user collaborative editing.
- Per-keystroke versioning.
- Letting chat silently modify document content.
- Complex tool permissions beyond read-only chat tools.
- Replacing Wordflow with another editor.

## Product Model

The product source of truth is not a chat transcript and not a LangGraph checkpoint. It is the document and its versions.

### Tables

`users`

- `id`
- `supabase_user_id`
- `email`
- `created_at`

`documents`

- `id`
- `user_id`
- `title`
- `current_version_id`
- `status`
- `created_at`
- `updated_at`

`document_versions`

- `id`
- `document_id`
- `user_id`
- `parent_version_id`
- `content_html`
- `content_text`
- `source`
- `reason`
- `created_at`

`agent_threads`

- `id`
- `user_id`
- `document_id`
- `langgraph_thread_id`
- `title`
- `status`
- `created_at`
- `updated_at`

`agent_messages`

- `id`
- `thread_id`
- `run_id`
- `role`
- `content`
- `metadata_json`
- `document_version_id`
- `created_at`

`agent_runs`

- `id`
- `user_id`
- `document_id`
- `thread_id`
- `type`
- `status`
- `current_stage`
- `input_version_id`
- `output_version_id`
- `error_message`
- `created_at`
- `updated_at`

`agent_run_events`

- `id`
- `run_id`
- `seq`
- `event_type`
- `payload_json`
- `created_at`

`agent_reasoning_traces`

- `id`
- `run_id`
- `thread_id`
- `seq`
- `content`
- `summary`
- `visibility`
- `created_at`

## User Boundary

Production access is based on Supabase Auth. The backend resolves the authenticated Supabase user into the local `users` table and applies `user_id` filtering to every document, version, thread, message, and run query.

Development may use an explicit fallback user only in local mode. Production must not rely on anonymous single-user state.

## Version Policy

The first versioning model is key-change versioning.

A new document version is created when:

- A document is created.
- The user explicitly saves.
- The user accepts an AI edit.
- The user imports content.

A new document version is not created when:

- The user is still typing.
- AI is only suggesting text in chat.
- A generated diff is rejected.
- A chat answer discusses the document without being applied.

Rollback is implemented by updating `documents.current_version_id` to an existing version owned by the same user and document. Rollback does not delete later versions.

The primary stored format is `content_html` plus `content_text`. HTML matches the current Wordflow/Tiptap document model. Plain text supports search, AI context construction, and export.

## Wordflow Text Actions

Wordflow remains the editor interaction layer for local text edits. The first AI actions are:

- `expand`
- `rewrite`
- `oralize`
- `shorten`

Interaction flow:

1. User selects text.
2. The floating AI action menu appears.
3. User chooses an action.
4. Wordflow calls the backend text generation route.
5. Wordflow renders a diff in the editor.
6. User accepts or rejects the change.
7. Accept creates a new `document_version`; reject creates no version.

When no text is selected, the same action applies to the current paragraph, preserving Wordflow's existing paragraph fallback behavior.

Wordflow should emit product-level events:

- `ai-edit-start`
- `ai-edit-finished`
- `ai-edit-accepted`
- `ai-edit-rejected`

`ai-edit-accepted` carries enough information for the backend to create a new version:

- `document_id`
- `base_version_id`
- `action`
- `content_html`
- `content_text`
- `selected_text`
- `result_text`

The backend persists accepted AI edits as:

- `document_versions.source = "ai_action"`
- `document_versions.reason = "<action> selection"` or `"<action> paragraph"`
- `document_versions.parent_version_id = base_version_id`

The first implementation saves the accepted full document HTML and text. It does not need server-side patch merging.

## DeepAgents Chat Runtime

Each document has one document-scoped chat thread. The chat uses DeepAgents native runtime capabilities, but the product API and persistence remain ours.

Conceptual flow:

```text
our chat API
  -> create or restore document agent thread
  -> run DeepAgents/LangGraph
  -> normalize streaming events into SSE
  -> persist messages, visible reasoning traces, and run events
```

DeepAgents is responsible for:

- Threaded chat execution.
- LangGraph checkpointing.
- Streaming runtime events.
- Tool calling.
- Future subagents.
- Future interrupt/resume flows.

The application is responsible for:

- User authorization.
- Documents.
- Versions.
- Chat messages.
- Reasoning trace storage.
- Run event replay.

First-version chat tools are read-only:

- `read_current_document`
- `read_current_selection`
- `get_version_history`

The chat must not silently edit the document. It can produce suggestions, previews, and action recommendations. Applying a suggestion is a user action that goes through Wordflow diff and version creation.

## Chat API

Create a streaming chat run:

```text
POST /documents/{document_id}/chat/messages
```

Request:

```json
{
  "content": "这段怎么改得更有口播感？",
  "selection": {
    "text": "用户当前选中的文字",
    "context_before": "前文",
    "context_after": "后文"
  },
  "base_version_id": 12
}
```

Response:

```json
{
  "run_id": 88,
  "thread_id": 5,
  "status": "running"
}
```

Stream run events:

```text
GET /chat/runs/{run_id}/events?from_seq=0
```

Fetch persisted chat history:

```text
GET /documents/{document_id}/chat/messages
```

Cancel a run:

```text
POST /chat/runs/{run_id}/cancel
```

## Streaming Events

The backend exposes normalized SSE events:

- `run_started`
- `user_message_saved`
- `reasoning_delta`
- `reasoning_completed`
- `message_delta`
- `message_completed`
- `suggestion`
- `tool_started`
- `tool_completed`
- `run_completed`
- `run_failed`

`reasoning_delta` is only emitted when the model or runtime exposes a visible reasoning summary or trace. The system must not invent hidden reasoning. If no visible reasoning is returned, the UI can show that the model did not provide a visible reasoning trace.

Runtime progress events such as reading the current document, analyzing a selection, starting a tool, or producing a suggestion may be displayed and saved as runtime traces. These are product/runtime events, not fabricated model chain-of-thought.

Persistence rules:

- `reasoning_delta` events are written to `agent_run_events`.
- Completed visible reasoning is stored in `agent_reasoning_traces`.
- `message_delta` events are written to `agent_run_events`.
- Completed assistant messages are stored in `agent_messages`.
- User messages are stored in `agent_messages`.
- Suggestions are written to `agent_run_events` and may also be referenced from assistant message metadata.

Reasoning traces are not automatically injected into future model context. Future context should use final assistant messages and explicit summaries only.

## Runtime Graph

The first chat graph stays small:

```text
load_context
  -> chat_model
  -> persist_message
  -> done
```

`load_context` injects:

- Current document version text.
- Current selected text and nearby context, if provided.
- Recent chat messages.
- User writing style or document goal when available.
- The available first-phase actions: expand, rewrite, oralize, shorten.

`chat_model` streams:

- Assistant response deltas.
- Visible reasoning deltas if provided.
- Structured suggestions when appropriate.

`persist_message` writes final assistant output and trace summaries.

Future versions can extend the graph with review, outline, research, material collection, subagents, and human approval nodes.

## Error Handling

Document save failure:

- Do not update `documents.current_version_id`.
- Preserve the editor content on the frontend.
- Return a clear retryable error.

AI run failure:

- Set `agent_runs.status = "failed"`.
- Write a `run_failed` event with stage and error message.
- Do not create a document version.

SSE disconnect:

- Frontend reconnects with the last seen sequence number.
- Backend replays from `agent_run_events` using `from_seq`.
- If the run is still active, the frontend continues receiving new events.

Cancel:

- Set `agent_runs.status = "cancelled"`.
- Emit a terminal cancellation event.
- First implementation may use logical cancellation even if an in-flight provider request cannot be aborted immediately.

## Testing

Backend tests:

- User A cannot read or mutate User B documents.
- Creating a document creates an initial version.
- Manual save creates a version.
- Rollback updates only `current_version_id`.
- Accepted AI edit creates a version.
- Rejected AI edit creates no version.
- Chat message creates an agent run and run events.
- SSE replay returns events after `from_seq`.
- Failed AI run does not create a version.
- Visible reasoning deltas are persisted when present.
- No reasoning trace is fabricated when absent.

Frontend tests:

- Wordflow remains the root editor.
- Selection actions call the backend.
- Paragraph fallback still works when no text is selected.
- Accepting a diff emits a version-save event.
- Rejecting a diff does not save a version.
- Chat renders streaming message deltas.
- Chat renders visible reasoning traces when present.
- Chat suggestions do not modify the document without user action.

## Acceptance Criteria

The first implementation is complete when a user can:

- Log in.
- Create a script document.
- Write content in Wordflow.
- Save a version.
- Select text and run expand, rewrite, oralize, or shorten.
- See Wordflow diff output.
- Accept an AI edit and get a new document version.
- Reject an AI edit without creating a version.
- View version history.
- Roll back to a previous version.
- Open document-scoped chat.
- Send a message and receive a streaming AI response.
- See and persist visible reasoning/runtime traces when available.
- Refresh the page and recover documents, versions, chat messages, and replayable run events.

## Migration Notes

Existing `rewrite_records`, `review_records`, `workflow_jobs`, and `workflow_job_events` remain for compatibility during the first phase. New product truth should live in `documents`, `document_versions`, `agent_threads`, `agent_messages`, `agent_runs`, `agent_run_events`, and `agent_reasoning_traces`.

The old tables can later be mapped into the new model or retired after the new runtime covers the same workflows.
