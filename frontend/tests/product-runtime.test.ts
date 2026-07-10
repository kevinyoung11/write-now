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
});

