import { useState } from "react";
import { Loader2, Send, Sparkles } from "lucide-react";
import {
  runAIWritingWorkflow,
  type AIWritingReviewSummary,
} from "./aiWritingClient";

type AIWritingPanelProps = {
  markdown: string;
  onApplyResult: (markdown: string) => void;
};

export const AIWritingPanel = ({ markdown, onApplyResult }: AIWritingPanelProps) => {
  const [styleId, setStyleId] = useState(1);
  const [targetWords, setTargetWords] = useState(1200);
  const [enableRag, setEnableRag] = useState(true);
  const [ragTopK, setRagTopK] = useState(3);
  const [status, setStatus] = useState("");
  const [review, setReview] = useState<AIWritingReviewSummary | undefined>();
  const [generatedMarkdown, setGeneratedMarkdown] = useState("");
  const [error, setError] = useState("");
  const [isRunning, setIsRunning] = useState(false);

  const canRun = markdown.trim().length > 0 && styleId > 0 && !isRunning;

  const runWorkflow = async () => {
    if (!canRun) {
      return;
    }
    setIsRunning(true);
    setError("");
    setGeneratedMarkdown("");
    setReview(undefined);
    setStatus("正在启动 AI 工作流");

    try {
      const result = await runAIWritingWorkflow(
        {
          markdown,
          styleId,
          targetWords,
          enableRag,
          ragTopK,
        },
        {
          onContent: setGeneratedMarkdown,
          onReview: setReview,
          onStage: setStatus,
        },
      );
      setGeneratedMarkdown(result.generatedMarkdown);
      setReview(result.review);
      setStatus("AI 工作流已完成");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setStatus("AI 工作流失败");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <aside className="ai-writing-panel" aria-label="AI 审稿与改稿" role="region">
      <div className="workbench-panel-heading">
        <Sparkles size={18} />
        <h2>AI 审稿与改稿</h2>
      </div>

      <label>
        风格 ID
        <input
          min={1}
          onChange={(event) => setStyleId(Number(event.target.value))}
          type="number"
          value={styleId}
        />
      </label>

      <label>
        目标字数
        <input
          min={100}
          onChange={(event) => setTargetWords(Number(event.target.value))}
          step={100}
          type="number"
          value={targetWords}
        />
      </label>

      <div className="ai-writing-panel-row">
        <label className="ai-writing-panel-toggle">
          <input
            checked={enableRag}
            onChange={(event) => setEnableRag(event.target.checked)}
            type="checkbox"
          />
          使用资料库
        </label>
        <label>
          Top K
          <select
            disabled={!enableRag}
            onChange={(event) => setRagTopK(Number(event.target.value))}
            value={ragTopK}
          >
            <option value={1}>1</option>
            <option value={3}>3</option>
            <option value={5}>5</option>
          </select>
        </label>
      </div>

      <button
        aria-label="运行 AI 审稿改稿"
        className="workbench-primary-button"
        disabled={!canRun}
        onClick={runWorkflow}
        type="button"
      >
        {isRunning ? <Loader2 size={16} className="workbench-spin" /> : <Send size={16} />}
        运行 AI 审稿改稿
      </button>

      <div className="ai-writing-panel-status" role="status">
        {error || status || "输入正文后可运行 AI 工作流"}
      </div>

      {review && (
        <div className="ai-writing-panel-review">
          <strong>{review.passed ? "审稿通过" : "需要继续修改"}</strong>
          <span>{review.score ? `${review.score} 分` : "未评分"}</span>
          {review.reason && <p>{review.reason}</p>}
        </div>
      )}

      {generatedMarkdown && (
        <div className="ai-writing-panel-result">
          <div className="ai-writing-panel-result-head">
            <strong>AI 改稿结果</strong>
            <button onClick={() => onApplyResult(generatedMarkdown)} type="button">
              插入正文
            </button>
          </div>
          <pre>{generatedMarkdown}</pre>
        </div>
      )}
    </aside>
  );
};
