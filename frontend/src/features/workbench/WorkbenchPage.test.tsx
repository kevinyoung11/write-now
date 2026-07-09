import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../../App";
import { WorkbenchPage } from "./WorkbenchPage";

describe("WorkbenchPage", () => {
  it("renders the full writing chain regions", () => {
    render(<WorkbenchPage />);

    expect(screen.getByRole("region", { name: "选题 brief" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资料收集" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "观点池" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "大纲" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 审稿与改稿" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "正文编辑器" })).toBeInTheDocument();
  });

  it("renders export actions", () => {
    render(<WorkbenchPage />);

    expect(screen.getByRole("button", { name: "导出 Markdown" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出口播稿" })).toBeInTheDocument();
  });

  it("names each workflow note field for assistive technology", () => {
    render(<WorkbenchPage />);

    expect(screen.getByRole("textbox", { name: "选题 brief 输入" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "资料收集 输入" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "观点池 输入" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "大纲 输入" })).toBeInTheDocument();
  });

  it("routes / to the workbench", () => {
    window.history.pushState({}, "", "/");

    render(<App />);

    expect(screen.getByRole("heading", { name: "Write Now" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 审稿与改稿" })).toBeInTheDocument();
  });
});
