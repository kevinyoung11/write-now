import {
  runWorkflowWithStream,
  type WorkflowStreamEvent,
} from "../../services/api";

export type AIWritingRunRequest = {
  markdown: string;
  styleId: number;
  targetWords?: number;
  enableRag?: boolean;
  ragTopK?: number;
};

export type AIWritingReviewSummary = {
  reviewId?: number;
  score?: number;
  passed?: boolean;
  reason?: string;
};

export type AIWritingRunResult = {
  generatedMarkdown: string;
  rewriteId?: number;
  reviewId?: number;
  review?: AIWritingReviewSummary;
  events: WorkflowStreamEvent[];
};

export type AIWritingRunCallbacks = {
  onContent?: (markdown: string) => void;
  onReview?: (review: AIWritingReviewSummary) => void;
  onStage?: (message: string) => void;
};

const errorMessageFromEvent = (event: WorkflowStreamEvent): string => {
  return event.message || event.reason || event.error_code || "AI workflow failed";
};

export const runAIWritingWorkflow = async (
  request: AIWritingRunRequest,
  callbacks: AIWritingRunCallbacks = {},
  signal?: AbortSignal,
): Promise<AIWritingRunResult> => {
  let generatedMarkdown = "";
  let rewriteId: number | undefined;
  let reviewId: number | undefined;
  let review: AIWritingReviewSummary | undefined;
  let errorMessage = "";

  const events = await runWorkflowWithStream(
    {
      source_article: request.markdown,
      style_id: request.styleId,
      target_words: request.targetWords,
      enable_rag: request.enableRag,
      rag_top_k: request.ragTopK,
      max_retries: 1,
      force_new: true,
    },
    {
      onStage: (event) => {
        callbacks.onStage?.(event.message || event.stage || "AI workflow running");
      },
      onProgress: (event) => {
        callbacks.onStage?.(event.message || event.stage || "AI workflow running");
      },
      onContent: (event) => {
        generatedMarkdown += event.delta || "";
        callbacks.onContent?.(generatedMarkdown);
      },
      onReviewDone: (event) => {
        reviewId = event.review_id;
        review = {
          reviewId,
          score: event.score,
          passed: event.passed,
          reason: event.reason,
        };
        callbacks.onReview?.(review);
      },
      onDone: (event) => {
        rewriteId = event.rewrite_id || rewriteId;
        reviewId = event.review_id || reviewId;
      },
      onError: (event) => {
        errorMessage = errorMessageFromEvent(event);
      },
    },
    signal,
  );

  const terminalDone = [...events].reverse().find((event) => event.type === "done");
  const terminalError = [...events].reverse().find((event) => event.type === "error");

  if (terminalError || errorMessage) {
    throw new Error(errorMessage || errorMessageFromEvent(terminalError as WorkflowStreamEvent));
  }

  rewriteId = terminalDone?.rewrite_id || rewriteId;
  reviewId = terminalDone?.review_id || reviewId;

  return {
    generatedMarkdown,
    rewriteId,
    reviewId,
    review,
    events,
  };
};
