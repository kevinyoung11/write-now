import { $convertFromMarkdownString } from "@lexical/markdown";
import { AutoFocusPlugin } from "@lexical/react/LexicalAutoFocusPlugin";
import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { LexicalErrorBoundary } from "@lexical/react/LexicalErrorBoundary";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { ListPlugin } from "@lexical/react/LexicalListPlugin";
import { MarkdownShortcutPlugin } from "@lexical/react/LexicalMarkdownShortcutPlugin";
import { RichTextPlugin } from "@lexical/react/LexicalRichTextPlugin";
import { HeadingNode, QuoteNode } from "@lexical/rich-text";
import { ListItemNode, ListNode } from "@lexical/list";
import type { InitialConfigType } from "@lexical/react/LexicalComposer";
import {
  LexicalMarkdownPlugin,
  type ExternalMarkdownValue,
  type MarkdownChangePayload,
} from "./LexicalMarkdownPlugin";
import { LexicalToolbar } from "./LexicalToolbar";
import { WORKBENCH_MARKDOWN_TRANSFORMERS } from "./markdownTransformers";
import "./LexicalWorkbench.css";

export type LexicalWorkbenchProps = {
  initialMarkdown?: string;
  externalMarkdown?: ExternalMarkdownValue;
  onMarkdownChange: (payload: MarkdownChangePayload) => void;
};

const theme = {
  heading: {
    h1: "lexical-heading-one",
    h2: "lexical-heading-two",
  },
  list: {
    listitem: "lexical-list-item",
    nested: {
      listitem: "lexical-nested-list-item",
    },
    ol: "lexical-list-ordered",
    ul: "lexical-list-unordered",
  },
  paragraph: "lexical-paragraph",
  quote: "lexical-quote",
  text: {
    bold: "lexical-text-bold",
    italic: "lexical-text-italic",
    strikethrough: "lexical-text-strikethrough",
  },
};

export const LexicalWorkbench = ({
  initialMarkdown = "",
  externalMarkdown,
  onMarkdownChange,
}: LexicalWorkbenchProps) => {
  const initialConfig: InitialConfigType = {
    namespace: "WriteNowWorkbench",
    nodes: [HeadingNode, QuoteNode, ListNode, ListItemNode],
    onError(error) {
      throw error;
    },
    editorState: () => {
      if (initialMarkdown.trim()) {
        $convertFromMarkdownString(initialMarkdown, WORKBENCH_MARKDOWN_TRANSFORMERS);
      }
    },
    theme,
  };

  return (
    <LexicalComposer initialConfig={initialConfig}>
      <section className="lexical-workbench" aria-label="写作编辑器">
        <LexicalToolbar />
        <div className="lexical-editor-shell">
          <RichTextPlugin
            contentEditable={
              <ContentEditable
                aria-label="正文编辑器"
                className="lexical-content-editable"
                role="textbox"
                spellCheck={false}
              />
            }
            ErrorBoundary={LexicalErrorBoundary}
            placeholder={
              <div className="lexical-placeholder">从这里开始写正文...</div>
            }
          />
          <HistoryPlugin />
          <ListPlugin />
          <AutoFocusPlugin />
          <MarkdownShortcutPlugin transformers={WORKBENCH_MARKDOWN_TRANSFORMERS} />
          <LexicalMarkdownPlugin
            externalMarkdown={externalMarkdown}
            onMarkdownChange={onMarkdownChange}
          />
        </div>
      </section>
    </LexicalComposer>
  );
};
