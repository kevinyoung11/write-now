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
    expect(apiClient).toContain("X-Dev-User-Id");
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
});
