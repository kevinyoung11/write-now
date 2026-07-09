import { describe, expect, it } from "vitest";
import {
  buildExportFileName,
  countCjkAwareWords,
  normalizeScriptPlainText,
} from "./documentTransforms";

describe("normalizeScriptPlainText", () => {
  it("collapses markdown syntax into readable script text", () => {
    expect(normalizeScriptPlainText("# 标题\n\n- 第一条\n- 第二条")).toBe(
      "标题\n\n第一条\n第二条",
    );
  });

  it("removes emphasis and quote markers while preserving paragraph breaks", () => {
    expect(
      normalizeScriptPlainText("> **重点**：AI 写作\n\n\n普通段落里的 *强调*。"),
    ).toBe("重点：AI 写作\n\n普通段落里的 强调。");
  });
});

describe("countCjkAwareWords", () => {
  it("counts CJK characters and English words", () => {
    expect(countCjkAwareWords("AI 正在 helping 2 创作者")).toBe(8);
  });
});

describe("buildExportFileName", () => {
  it("builds stable timestamped markdown names", () => {
    expect(
      buildExportFileName("markdown", new Date("2026-07-10T02:03:04+08:00")),
    ).toBe("write-now-20260709-180304.md");
  });

  it("builds stable timestamped script names", () => {
    expect(
      buildExportFileName("script", new Date("2026-07-10T02:03:04+08:00")),
    ).toBe("write-now-script-20260709-180304.txt");
  });
});
