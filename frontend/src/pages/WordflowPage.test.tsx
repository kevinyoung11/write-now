import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

describe("WordflowPage", () => {
  it("renders the Wordflow iframe shell", async () => {
    const pages = await import("./index");
    const WordflowPage = pages.WordflowPage;

    expect(WordflowPage).toBeTypeOf("function");

    const html = renderToString(<WordflowPage />);

    expect(html).toContain("<iframe");
    expect(html).toContain('src="/wordflow/index.html"');
    expect(html).toContain('title="Wordflow editor"');
    expect(html).toContain('sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"');
    expect(html).toContain('referrerPolicy="no-referrer"');
  });
});

describe("vendored Wordflow assets", () => {
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

describe("App routes", () => {
  const renderRoute = async (path: string) => {
    const appModule = await import("../App");
    const AppRoutes = appModule.AppRoutes;

    expect(AppRoutes).toBeTypeOf("function");

    return renderToString(
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>,
    );
  };

  it("uses WordflowPage at the root route", async () => {
    const html = await renderRoute("/");

    expect(html).toContain('src="/wordflow/index.html"');
    expect(html).toContain('title="Wordflow editor"');
  });

  it.each([
    "/write-agent",
    "/styles",
    "/materials",
    "/reviews",
    "/covers",
    "/github-trends",
    "/linuxdo-trends",
    "/hot-topics",
    "/xhs-trends",
    "/layout",
  ])("routes legacy path %s to Wordflow", async (path) => {
    const html = await renderRoute(path);

    expect(html).toContain('src="/wordflow/index.html"');
    expect(html).toContain('title="Wordflow editor"');
    expect(html).not.toContain('class="home-v2-page"');
  });
});
