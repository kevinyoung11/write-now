import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { LexicalWorkbench } from "./LexicalWorkbench";

describe("LexicalWorkbench", () => {
  it("renders an editable writing area with placeholder", () => {
    render(<LexicalWorkbench onMarkdownChange={vi.fn()} />);

    expect(screen.getByRole("textbox", { name: "正文编辑器" })).toBeInTheDocument();
    expect(screen.getByText("从这里开始写正文...")).toBeInTheDocument();
  });

  it("renders toolbar buttons with accessible labels", () => {
    render(<LexicalWorkbench onMarkdownChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "标题" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "正文" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "加粗" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "无序列表" })).toBeInTheDocument();
  });

  it("calls onMarkdownChange after text input", async () => {
    const onMarkdownChange = vi.fn();
    render(<LexicalWorkbench onMarkdownChange={onMarkdownChange} />);

    const editor = screen.getByRole("textbox", { name: "正文编辑器" });
    await waitFor(() => {
      expect(editor).toHaveAttribute("data-lexical-editor", "true");
    });
    editor.textContent = "第一段内容";
    fireEvent(
      editor,
      new InputEvent("input", {
        bubbles: true,
        data: "第一段内容",
        inputType: "insertText",
      }),
    );

    await waitFor(() => {
      expect(onMarkdownChange).toHaveBeenCalledWith(
        expect.objectContaining({
          plainText: expect.stringContaining("第一段内容"),
        }),
      );
    });
  });

  it("re-applies the same external markdown when the revision changes", async () => {
    const Harness = () => {
      const [revision, setRevision] = useState(0);
      return (
        <>
          <button onClick={() => setRevision((value) => value + 1)} type="button">
            插入同一结果
          </button>
          <LexicalWorkbench
            externalMarkdown={{
              markdown: "## AI 结果",
              revision,
            }}
            onMarkdownChange={vi.fn()}
          />
        </>
      );
    };

    render(<Harness />);
    const editor = screen.getByRole("textbox", { name: "正文编辑器" });

    await waitFor(() => {
      expect(editor).toHaveTextContent("AI 结果");
    });

    editor.textContent = "用户手动修改";
    fireEvent(
      editor,
      new InputEvent("input", {
        bubbles: true,
        data: "用户手动修改",
        inputType: "insertText",
      }),
    );

    screen.getByRole("button", { name: "插入同一结果" }).click();

    await waitFor(() => {
      expect(editor).toHaveTextContent("AI 结果");
    });
  });
});
