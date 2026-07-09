import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  WORKBENCH_DRAFT_STORAGE_KEY,
  readStoredDraft,
  useLocalDraft,
  writeStoredDraft,
} from "./useLocalDraft";

describe("local draft persistence", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("loads the initial value from localStorage", () => {
    writeStoredDraft({
      lexicalJson: "{\"root\":{\"children\":[]}}",
      markdown: "# 已保存标题",
      plainText: "已保存标题",
      updatedAt: "2026-07-10T00:00:00.000Z",
    });

    const { result } = renderHook(() => useLocalDraft());

    expect(result.current.snapshot.markdown).toBe("# 已保存标题");
    expect(result.current.snapshot.plainText).toBe("已保存标题");
  });

  it("saves latest lexical json, markdown, and plain text", () => {
    const { result } = renderHook(() => useLocalDraft());

    act(() => {
      result.current.saveDraft({
        lexicalJson: "{\"root\":{\"children\":[{\"text\":\"新稿\"}]}}",
        markdown: "新稿",
        plainText: "新稿",
      });
    });

    const stored = readStoredDraft();
    expect(stored.lexicalJson).toContain("新稿");
    expect(stored.markdown).toBe("新稿");
    expect(stored.plainText).toBe("新稿");
    expect(stored.updatedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("falls back to an empty draft when stored JSON is corrupt", () => {
    localStorage.setItem(WORKBENCH_DRAFT_STORAGE_KEY, "{broken");

    const { result } = renderHook(() => useLocalDraft());

    expect(result.current.snapshot).toEqual({
      lexicalJson: "",
      markdown: "",
      plainText: "",
      updatedAt: "",
    });
  });

  it("keeps the in-memory draft when localStorage write fails", () => {
    const setItem = vi.spyOn(localStorage, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded");
    });

    const { result } = renderHook(() => useLocalDraft());

    act(() => {
      result.current.saveDraft({
        lexicalJson: "{\"root\":{\"children\":[{\"text\":\"大稿\"}]}}",
        markdown: "大稿",
        plainText: "大稿",
      });
    });

    expect(result.current.snapshot.markdown).toBe("大稿");
    expect(result.current.persistError).toBe("quota exceeded");

    setItem.mockRestore();
  });
});
