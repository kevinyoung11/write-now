import { useMemo, useState } from "react";
import { Download, FileText, Library, Lightbulb, ListChecks, ScrollText } from "lucide-react";
import { AIWritingPanel } from "../ai/AIWritingPanel";
import {
  buildExportFileName,
  countCjkAwareWords,
  normalizeScriptPlainText,
} from "../editor/documentTransforms";
import { LexicalWorkbench } from "../editor/LexicalWorkbench";
import type {
  ExternalMarkdownValue,
  MarkdownChangePayload,
} from "../editor/LexicalMarkdownPlugin";
import { useLocalDraft } from "../editor/useLocalDraft";
import "./WorkbenchPage.css";

const downloadText = (fileName: string, content: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
};

export const WorkbenchPage = () => {
  const { saveDraft, snapshot } = useLocalDraft();
  const [editorPayload, setEditorPayload] = useState<MarkdownChangePayload>({
    lexicalJson: snapshot.lexicalJson,
    markdown: snapshot.markdown,
    plainText: snapshot.plainText,
  });
  const [externalMarkdown, setExternalMarkdown] = useState<ExternalMarkdownValue | undefined>();
  const [externalMarkdownRevision, setExternalMarkdownRevision] = useState(0);

  const wordCount = useMemo(
    () => countCjkAwareWords(editorPayload.plainText || editorPayload.markdown),
    [editorPayload],
  );

  const handleMarkdownChange = (payload: MarkdownChangePayload) => {
    setEditorPayload(payload);
    saveDraft(payload);
  };

  const exportMarkdown = () => {
    downloadText(
      buildExportFileName("markdown"),
      editorPayload.markdown,
      "text/markdown;charset=utf-8",
    );
  };

  const exportScript = () => {
    downloadText(
      buildExportFileName("script"),
      normalizeScriptPlainText(editorPayload.markdown),
      "text/plain;charset=utf-8",
    );
  };

  const applyAiResult = (markdown: string) => {
    const nextRevision = externalMarkdownRevision + 1;
    const nextPayload = {
      lexicalJson: "",
      markdown,
      plainText: normalizeScriptPlainText(markdown),
    };
    setExternalMarkdownRevision(nextRevision);
    setExternalMarkdown({
      markdown,
      revision: nextRevision,
    });
    setEditorPayload(nextPayload);
    saveDraft(nextPayload);
  };

  return (
    <main className="workbench-page">
      <header className="workbench-topbar">
        <div>
          <h1>Write Now</h1>
          <span>Lexical AI writing workbench</span>
        </div>
        <div className="workbench-export-actions">
          <button aria-label="导出 Markdown" onClick={exportMarkdown} type="button">
            <FileText size={16} />
            Markdown
          </button>
          <button aria-label="导出口播稿" onClick={exportScript} type="button">
            <Download size={16} />
            口播稿
          </button>
        </div>
      </header>

      <div className="workbench-grid">
        <aside className="workbench-left-rail" aria-label="写作链条">
          <section aria-label="选题 brief" className="workbench-side-section">
            <div className="workbench-panel-heading">
              <ScrollText size={17} />
              <h2>选题 brief</h2>
            </div>
            <textarea
              aria-label="选题 brief 输入"
              placeholder="写下选题、受众、核心问题和输出目标。"
            />
          </section>

          <section aria-label="资料收集" className="workbench-side-section">
            <div className="workbench-panel-heading">
              <Library size={17} />
              <h2>资料收集</h2>
            </div>
            <textarea
              aria-label="资料收集 输入"
              placeholder="粘贴资料、链接摘要、事实和案例。"
            />
          </section>

          <section aria-label="观点池" className="workbench-side-section">
            <div className="workbench-panel-heading">
              <Lightbulb size={17} />
              <h2>观点池</h2>
            </div>
            <textarea
              aria-label="观点池 输入"
              placeholder="沉淀判断、金句、反常识观点和争议点。"
            />
          </section>

          <section aria-label="大纲" className="workbench-side-section">
            <div className="workbench-panel-heading">
              <ListChecks size={17} />
              <h2>大纲</h2>
            </div>
            <textarea aria-label="大纲 输入" placeholder="拆分开头、展开、转折、结尾。" />
          </section>
        </aside>

        <section className="workbench-editor-column" aria-label="段落写作">
          <div className="workbench-editor-meta">
            <span>{wordCount} 字</span>
            <span>{editorPayload.markdown.split(/\n{2,}/).filter(Boolean).length} 段</span>
            {snapshot.updatedAt && <span>已自动保存</span>}
          </div>
          <LexicalWorkbench
            externalMarkdown={externalMarkdown}
            initialMarkdown={snapshot.markdown}
            onMarkdownChange={handleMarkdownChange}
          />
        </section>

        <AIWritingPanel markdown={editorPayload.markdown} onApplyResult={applyAiResult} />
      </div>
    </main>
  );
};
