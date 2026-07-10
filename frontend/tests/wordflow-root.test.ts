import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function readWordflowBundle() {
  const indexHtml = readFileSync(resolve(process.cwd(), "public/wordflow/index.html"), "utf-8");
  const match = indexHtml.match(/src="\/wordflow\/(assets\/main-[^"]+\.js)"/);

  expect(match?.[1]).toBeDefined();

  return readFileSync(resolve(process.cwd(), "public/wordflow", match![1]), "utf-8");
}

describe("Wordflow root app", () => {
  it("uses Wordflow as the root document without an iframe shell", () => {
    const indexHtml = readFileSync(resolve(process.cwd(), "index.html"), "utf-8");

    expect(indexHtml).toContain("<wordflow-wordflow>");
    expect(indexHtml).toContain('href="/wordflow/global.css"');
    expect(indexHtml).toMatch(/src="\/wordflow\/assets\/main-[^"]+\.js"/);
    expect(indexHtml).not.toContain("<iframe");
    expect(indexHtml).not.toContain("/src/main.tsx");
  });

  it("loads assets from the /wordflow base path without analytics", () => {
    const indexHtml = readFileSync(
      resolve(process.cwd(), "public/wordflow/index.html"),
      "utf-8",
    );

    expect(indexHtml).toContain('href="/wordflow/global.css"');
    expect(indexHtml).toMatch(/src="\/wordflow\/assets\/main-[^"]+\.js"/);
    expect(indexHtml).not.toContain("googletagmanager.com");
    expect(indexHtml).not.toContain("gtag(");
  });

  it("keeps the root index pointed at the published Wordflow bundle", () => {
    const rootIndex = readFileSync(resolve(process.cwd(), "index.html"), "utf-8");
    const publicIndex = readFileSync(
      resolve(process.cwd(), "public/wordflow/index.html"),
      "utf-8",
    );
    const rootBundle = rootIndex.match(/src="\/wordflow\/(assets\/main-[^"]+\.js)"/)?.[1];
    const publicBundle = publicIndex.match(/src="\/wordflow\/(assets\/main-[^"]+\.js)"/)?.[1];

    expect(rootBundle).toBe(publicBundle);
    expect(existsSync(resolve(process.cwd(), "public/wordflow", rootBundle!))).toBe(true);
  });

  it("does not keep the old React/Vite frontend shell", () => {
    expect(existsSync(resolve(process.cwd(), "src"))).toBe(false);
    expect(existsSync(resolve(process.cwd(), "public/vite.svg"))).toBe(false);
    expect(existsSync(resolve(process.cwd(), "public/yanque-logo.svg"))).toBe(false);

    const readme = readFileSync(resolve(process.cwd(), "README.md"), "utf-8");

    expect(readme).not.toMatch(/React|@vitejs\/plugin-react|YanQue|砚雀|write-agent|write_agent/);
  });

  it("routes Wordflow remote calls through this backend", () => {
    const gptSource = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/llms/gpt.ts"),
      "utf-8",
    );
    const configSource = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/config/config.ts"),
      "utf-8",
    );
    const authSource = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/modal-auth/modal-auth.ts"),
      "utf-8",
    );
    const bundle = readWordflowBundle();

    expect(gptSource).toContain("config.urls.textGenEndpoint");
    expect(gptSource).toContain("fetch(textGenEndpoint");
    expect(configSource).toContain("/api/wordflow/text-gen");
    expect(configSource).toContain("/api/wordflow/records");
    expect(configSource).toContain("/api/documents");
    expect(configSource).toContain("/api/chat/runs");
    expect(authSource).toContain("BACKEND_GPT_API_KEY");
    expect(bundle.includes("/api/wordflow/text-gen")).toBe(true);
    expect(bundle.includes("/api/wordflow/records")).toBe(true);
    expect(bundle.includes("/api/documents")).toBe(true);
    expect(bundle.includes("/api/chat/runs")).toBe(true);
    expect(bundle.includes("wordflow-agent-chat")).toBe(true);
    expect(bundle.includes("backend-managed")).toBe(true);
    expect(bundle.includes("https://api.openai.com/v1/responses")).toBe(false);
    expect(bundle.includes("https://generativelanguage.googleapis.com")).toBe(false);
    expect(
      bundle.includes("https://62uqq9jku8.execute-api.us-east-1.amazonaws.com/prod/records"),
    ).toBe(false);
  });

  it("proxies API calls to the backend during local frontend development", () => {
    const viteConfig = readFileSync(resolve(process.cwd(), "vite.config.ts"), "utf-8");

    expect(viteConfig).toContain("'/api'");
    expect(viteConfig).toContain("http://127.0.0.1:8000");
  });
});
