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
    expect(client).toContain("createDocumentVersion");
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
    expect(wordflow).toContain("createDocumentVersion");
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
    expect(chatClient).toContain("EventSource");
    expect(chatClient).toContain("document_version_id");
    expect(agentChat).toContain("wordflow-agent-chat");
    expect(agentChat).toContain("reasoning_trace");
    expect(wordflow).toContain("wordflow-agent-chat");
    expect(wordflow).toContain(".documentId=");
    expect(wordflow).toContain(".documentVersionId=");
  });
});
