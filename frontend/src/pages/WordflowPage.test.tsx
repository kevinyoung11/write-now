import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("vendored Wordflow assets", () => {
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
});
