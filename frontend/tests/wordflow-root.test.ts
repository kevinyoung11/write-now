import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

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

  it("does not keep the old React/Vite frontend shell", () => {
    expect(existsSync(resolve(process.cwd(), "src"))).toBe(false);
    expect(existsSync(resolve(process.cwd(), "public/vite.svg"))).toBe(false);
    expect(existsSync(resolve(process.cwd(), "public/yanque-logo.svg"))).toBe(false);

    const readme = readFileSync(resolve(process.cwd(), "README.md"), "utf-8");

    expect(readme).not.toMatch(/React|@vitejs\/plugin-react|YanQue|砚雀|write-agent|write_agent/);
  });
});
