import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppTopNav } from "../components/AppTopNav";
import { LanguageProvider } from "../i18n";

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

describe("AppTopNav", () => {
  it("keeps the rewrite navigation item pointed at the write agent route", () => {
    const html = renderToString(
      <LanguageProvider>
        <MemoryRouter>
          <AppTopNav />
        </MemoryRouter>
      </LanguageProvider>,
    );

    expect(html).toContain('href="/write-agent"');
  });
});

describe("App routes", () => {
  const renderRoute = async (path: string) => {
    const appModule = await import("../App");
    const AppRoutes = appModule.AppRoutes;

    expect(AppRoutes).toBeTypeOf("function");

    return renderToString(
      <LanguageProvider>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </LanguageProvider>,
    );
  };

  it("uses WordflowPage at the root route", async () => {
    const html = await renderRoute("/");

    expect(html).toContain('src="/wordflow/index.html"');
    expect(html).toContain('title="Wordflow editor"');
  });

  it("keeps the existing writing agent on /write-agent", async () => {
    const html = await renderRoute("/write-agent");

    expect(html).toContain('class="home-v2-page"');
    expect(html).not.toContain('src="/wordflow/index.html"');
  });

  it.each([
    ["/styles", 'class="styles-v2-page"'],
    ["/materials", 'class="materials-v2-page"'],
    ["/reviews", 'class="reviews-v2-page"'],
    ["/covers", 'class="covers-v2-page"'],
    ["/github-trends", 'class="github-trends-page"'],
    ["/linuxdo-trends", 'class="linuxdo-trends-page"'],
    ["/hot-topics", 'class="xhs-trends-page"'],
    ["/xhs-trends", 'class="xhs-trends-page"'],
    ["/layout", "Loading layout..."],
  ])("keeps the existing route %s", async (path, expectedMarker) => {
    const html = await renderRoute(path);

    expect(html).toContain(expectedMarker);
    expect(html).not.toContain('src="/wordflow/index.html"');
  });
});
