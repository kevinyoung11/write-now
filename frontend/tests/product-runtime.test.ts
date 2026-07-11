import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("product runtime wiring", () => {
  it("defines document endpoints and script text actions", () => {
    const config = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/config/config.ts"),
      "utf-8",
    );
    const actions = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/script-actions.ts"),
      "utf-8",
    );
    const client = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/document-client.ts"),
      "utf-8",
    );

    expect(config).toContain("documentsEndpoint");
    expect(config).toContain("chatMessagesEndpoint");
    expect(config).toContain("supabaseAuth");
    expect(actions).toContain("expand");
    expect(actions).toContain("rewrite");
    expect(actions).toContain("oralize");
    expect(actions).toContain("shorten");
    expect(client).toContain("listDocuments");
    expect(client).toContain("getDocument");
    expect(client).toContain("createDocumentVersion");
  });

  it("uses the same authenticated product client for documents and chat streams", () => {
    const apiClient = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/api-client.ts"),
      "utf-8",
    );
    const documentClient = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/document-client.ts"),
      "utf-8",
    );
    const chatClient = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/chat-client.ts"),
      "utf-8",
    );

    expect(documentClient).toContain("authHeaders");
    expect(apiClient).not.toContain("X-Dev-User-Id");
    expect(apiClient).toContain("Authorization = `Bearer ${accessToken}`");
    expect(chatClient).toContain("authHeaders(false)");
    expect(chatClient).not.toContain("new EventSource");
    expect(chatClient).toContain("ReadableStreamDefaultReader");
    expect(chatClient).toContain("fromSeq = lastSeq");
    expect(chatClient).toContain("reasoning_delta");
    expect(chatClient).toContain("reasoning_completed");
  });

  it("emits accepted AI edit events for version saving", () => {
    const textEditor = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/text-editor/text-editor.ts"),
      "utf-8",
    );
    const wordflow = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/wordflow/wordflow.ts"),
      "utf-8",
    );

    expect(textEditor).toContain("ai-edit-accepted");
    expect(textEditor).toContain("ai-edit-rejected");
    expect(textEditor).toContain("getCleanDocumentSnapshot");
    expect(textEditor).toContain("lastAiEditContext");
    expect(wordflow).toContain("createDocumentVersion");
    expect(wordflow).toContain("restoreCurrentDocument");
    expect(wordflow).toContain("getDocument");
    expect(wordflow).toContain("listDocuments");
    expect(wordflow).toContain("selected_text");
    expect(wordflow).toContain("result_text");
    expect(wordflow).toContain("base_version_id");
    expect(wordflow).toContain("document_id");
    expect(wordflow).toContain("beforeSnapshot.content_text === afterSnapshot.content_text");
    expect(wordflow).toContain("`${editContext.action} ${editContext.scope}`");
  });

  it("wires document-scoped streaming chat into the wordflow shell", () => {
    const chatClient = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/chat-client.ts"),
      "utf-8",
    );
    const agentChat = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/agent-chat/agent-chat.ts"),
      "utf-8",
    );
    const wordflow = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/wordflow/wordflow.ts"),
      "utf-8",
    );

    expect(chatClient).toContain("sendChatMessage");
    expect(chatClient).toContain("streamChatRunEvents");
    expect(chatClient).toContain("document_version_id");
    expect(agentChat).toContain("wordflow-agent-chat");
    expect(agentChat).toContain("reasoning_trace");
    expect(wordflow).toContain("wordflow-agent-chat");
    expect(wordflow).toContain(".documentId=");
    expect(wordflow).toContain(".documentVersionId=");
  });

  it("exposes AI chat as a contextual editor popover", () => {
    const wordflow = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/wordflow/wordflow.ts"),
      "utf-8",
    );
    const wordflowCss = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/wordflow/wordflow.css"),
      "utf-8",
    );
    const textEditor = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/text-editor/text-editor.ts"),
      "utf-8",
    );
    const agentChat = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/agent-chat/agent-chat.ts"),
      "utf-8",
    );

    expect(wordflow).toContain("updateContextualChat");
    expect(wordflow).toContain("contextual-chat");
    expect(wordflow).toContain("contextual-chat-popover");
    expect(wordflow).toContain("wordflow-floating-menu");
    expect(wordflow).toContain("AI Chat");
    expect(wordflow).toContain("currentUserLabel");
    expect(wordflow).toContain("hasAuthToken");
    expect(wordflow).not.toContain("showAgentChat");
    expect(wordflow).not.toContain("chat-entry-button");
    // The tool/prompt toolbar is a persistent, always-visible menu (not
    // gated behind text selection) with the AI Chat icon as one of its
    // buttons.
    expect(wordflow).toContain("floating-menu-box hidden");
    expect(wordflow).toContain("ai-chat-button-clicked");
    expect(wordflowCss).toContain(".contextual-chat");
    expect(wordflowCss).toContain(".contextual-chat[is-visible]");
    expect(wordflowCss).toContain(".floating-menu-box");
    expect(wordflowCss).toContain(".contextual-chat-popover");
    expect(wordflowCss).toContain("position: fixed");
    expect(textEditor).toContain("updateContextualChat");
    expect(textEditor).toContain("notifyContextualChat");
    expect(textEditor).toContain("contextualChatKeydownHandler");
    expect(textEditor).toContain("if (!hasSelection && !open)");
    expect(textEditor).toContain("posToDOMRect");
    // The AI Chat entry is an explicit trigger (persistent toolbar icon or
    // the Cmd/Ctrl+J shortcut) rather than auto-popping on every selection.
    expect(textEditor).not.toContain("onSelectionUpdate: () => this.notifyContextualChat");
    expect(agentChat).toContain("selection");
    expect(agentChat).toContain("selection: this.selection");
    expect(agentChat).toContain("formatChatError");
    expect(agentChat).toContain("JSON.parse");
  });

  it("keeps the mobile writing surface anchored to the top of the screen", () => {
    const wordflowCss = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/wordflow/wordflow.css"),
      "utf-8",
    );
    const textEditorCss = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/text-editor/text-editor.css"),
      "utf-8",
    );

    expect(wordflowCss).toContain("min-height: 100dvh");
    expect(wordflowCss).toContain("grid-template-rows: auto minmax(0, 1fr)");
    expect(wordflowCss).toContain("min-height: calc(100dvh - 48px)");
    expect(textEditorCss).toContain("@media (max-width: 900px)");
    expect(textEditorCss).toContain("min-height: calc(100dvh - 48px)");
    expect(textEditorCss).toContain("padding: 18px 20px 40px");
    expect(textEditorCss).toContain("align-items: flex-start");
  });

  it("requires a Supabase user token before editing or saving documents", () => {
    const apiClient = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/api-client.ts"),
      "utf-8",
    );
    const wordflow = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/wordflow/wordflow.ts"),
      "utf-8",
    );
    const textEditor = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/text-editor/text-editor.ts"),
      "utf-8",
    );

    expect(apiClient).toContain("hasAuthToken");
    expect(apiClient).toContain("clearAuthToken");
    expect(apiClient).toContain("saveAuthSession");
    expect(wordflow).toContain("isUserAuthorized()");
    expect(wordflow).toContain("auth-gate");
    expect(wordflow).toContain("Please sign in before writing");
    expect(wordflow).toContain("signInWithPassword");
    expect(wordflow).toContain("authEmailInput");
    expect(wordflow).toContain("authPasswordInput");
    expect(wordflow).toContain("if (!this.isUserAuthorized()) return");
    expect(wordflow).toContain(".isAuthorized=${this.isUserAuthorized()}");
    expect(wordflow).not.toContain("Supabase access token");
    expect(textEditor).toContain("@property({ type: Boolean })");
    expect(textEditor).toContain("isAuthorized = false");
    expect(textEditor).toContain("this.editor.setEditable(this.isAuthorized)");
    expect(textEditor).toContain("if (!this.isAuthorized)");
    expect(textEditor).toContain("contenteditable=\"false\"");
  });

  it("signs in through Supabase auth before storing a browser session", () => {
    const authClient = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/supabase-auth-client.ts"),
      "utf-8",
    );

    expect(authClient).toContain("signInWithPassword");
    expect(authClient).toContain("/auth/v1/token?grant_type=password");
    expect(authClient).toContain("apikey");
    expect(authClient).toContain("saveAuthSession");
    expect(authClient).toContain("access_token");
  });
});
