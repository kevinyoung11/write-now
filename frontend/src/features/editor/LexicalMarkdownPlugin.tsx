import { useEffect, useRef } from "react";
import { $convertFromMarkdownString, $convertToMarkdownString } from "@lexical/markdown";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { $getRoot, type EditorState } from "lexical";
import { WORKBENCH_MARKDOWN_TRANSFORMERS } from "./markdownTransformers";

export type MarkdownChangePayload = {
  lexicalJson: string;
  markdown: string;
  plainText: string;
};

export type ExternalMarkdownValue =
  | string
  | {
      markdown: string;
      revision: number;
    };

type LexicalMarkdownPluginProps = {
  externalMarkdown?: ExternalMarkdownValue;
  onMarkdownChange: (payload: MarkdownChangePayload) => void;
};

const readPayload = (editorState: EditorState): MarkdownChangePayload => {
  let markdown = "";
  let plainText = "";

  editorState.read(() => {
    markdown = $convertToMarkdownString(WORKBENCH_MARKDOWN_TRANSFORMERS);
    plainText = $getRoot().getTextContent();
  });

  return {
    lexicalJson: JSON.stringify(editorState.toJSON()),
    markdown,
    plainText,
  };
};

const unpackExternalMarkdown = (
  externalMarkdown?: ExternalMarkdownValue,
): { markdown: string; key: string } | undefined => {
  if (externalMarkdown === undefined) {
    return undefined;
  }
  if (typeof externalMarkdown === "string") {
    return {
      markdown: externalMarkdown,
      key: externalMarkdown,
    };
  }
  return {
    markdown: externalMarkdown.markdown,
    key: `${externalMarkdown.revision}:${externalMarkdown.markdown}`,
  };
};

const ExternalMarkdownPlugin = ({
  externalMarkdown,
}: {
  externalMarkdown?: ExternalMarkdownValue;
}) => {
  const [editor] = useLexicalComposerContext();
  const lastAppliedRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    const nextExternal = unpackExternalMarkdown(externalMarkdown);
    if (!nextExternal || nextExternal.key === lastAppliedRef.current) {
      return;
    }
    lastAppliedRef.current = nextExternal.key;
    editor.update(() => {
      $convertFromMarkdownString(nextExternal.markdown, WORKBENCH_MARKDOWN_TRANSFORMERS);
    });
  }, [editor, externalMarkdown]);

  return null;
};

const NativeInputFallbackPlugin = ({
  onMarkdownChange,
}: {
  onMarkdownChange: (payload: MarkdownChangePayload) => void;
}) => {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    let currentRootElement: HTMLElement | null = null;
    const emitFallback = () => {
      const plainText = currentRootElement?.textContent || "";
      if (!plainText.trim()) {
        return;
      }
      onMarkdownChange({
        lexicalJson: "",
        markdown: plainText,
        plainText,
      });
    };

    const unregisterRootListener = editor.registerRootListener(
      (rootElement, previousRootElement) => {
      previousRootElement?.removeEventListener("input", emitFallback);
      rootElement?.addEventListener("input", emitFallback);
        currentRootElement = rootElement;
      },
    );

    return () => {
      currentRootElement?.removeEventListener("input", emitFallback);
      unregisterRootListener();
    };
  }, [editor, onMarkdownChange]);

  return null;
};

export const LexicalMarkdownPlugin = ({
  externalMarkdown,
  onMarkdownChange,
}: LexicalMarkdownPluginProps) => {
  return (
    <>
      <ExternalMarkdownPlugin externalMarkdown={externalMarkdown} />
      <NativeInputFallbackPlugin onMarkdownChange={onMarkdownChange} />
      <OnChangePlugin
        ignoreSelectionChange
        onChange={(editorState) => {
          onMarkdownChange(readPayload(editorState));
        }}
      />
    </>
  );
};
