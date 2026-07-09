import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkflowStreamCallbacks, WorkflowStreamEvent } from "../../services/api";
import { runWorkflowWithStream } from "../../services/api";
import { runAIWritingWorkflow } from "./aiWritingClient";

vi.mock("../../services/api", () => ({
  runWorkflowWithStream: vi.fn(),
}));

const mockedRunWorkflow = vi.mocked(runWorkflowWithStream);

describe("runAIWritingWorkflow", () => {
  beforeEach(() => {
    mockedRunWorkflow.mockReset();
  });

  it("accumulates workflow content events into generated markdown", async () => {
    mockedRunWorkflow.mockImplementation(async (_request, callbacks = {}) => {
      callbacks.onContent?.({ type: "content", delta: "第一段" });
      callbacks.onContent?.({ type: "content", delta: "\n\n第二段" });
      callbacks.onDone?.({ type: "done", rewrite_id: 12 });
      return [
        { type: "content", delta: "第一段" },
        { type: "content", delta: "\n\n第二段" },
        { type: "done", rewrite_id: 12 },
      ] as WorkflowStreamEvent[];
    });

    const result = await runAIWritingWorkflow({
      markdown: "原稿",
      styleId: 3,
      targetWords: 800,
      enableRag: true,
      ragTopK: 3,
    });

    expect(result.generatedMarkdown).toBe("第一段\n\n第二段");
    expect(result.rewriteId).toBe(12);
    expect(mockedRunWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({
        source_article: "原稿",
        style_id: 3,
        target_words: 800,
        enable_rag: true,
        rag_top_k: 3,
      }),
      expect.any(Object),
      undefined,
    );
  });

  it("reports review summaries from review_done events", async () => {
    const onReview = vi.fn();
    mockedRunWorkflow.mockImplementation(async (_request, callbacks = {}) => {
      callbacks.onReviewDone?.({
        type: "review_done",
        review_id: 9,
        score: 87,
        passed: true,
        reason: "结构清楚",
      });
      return [
        {
          type: "review_done",
          review_id: 9,
          score: 87,
          passed: true,
          reason: "结构清楚",
        },
      ] as WorkflowStreamEvent[];
    });

    const result = await runAIWritingWorkflow(
      { markdown: "原稿", styleId: 3 },
      { onReview },
    );

    expect(onReview).toHaveBeenCalledWith({
      reviewId: 9,
      score: 87,
      passed: true,
      reason: "结构清楚",
    });
    expect(result.review).toEqual({
      reviewId: 9,
      score: 87,
      passed: true,
      reason: "结构清楚",
    });
  });

  it("throws a readable error when the workflow reports an error event", async () => {
    mockedRunWorkflow.mockImplementation(
      async (
        _request,
        callbacks: WorkflowStreamCallbacks = {},
      ): Promise<WorkflowStreamEvent[]> => {
        callbacks.onError?.({ type: "error", message: "模型超时" });
        return [{ type: "error", message: "模型超时" }];
      },
    );

    await expect(
      runAIWritingWorkflow({ markdown: "原稿", styleId: 3 }),
    ).rejects.toThrow("模型超时");
  });
});
