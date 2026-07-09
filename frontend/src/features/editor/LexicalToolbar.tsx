import {
  Bold,
  Heading1,
  Italic,
  List,
  ListOrdered,
  Pilcrow,
  Quote,
  Redo2,
  Undo2,
} from "lucide-react";
import { INSERT_ORDERED_LIST_COMMAND, INSERT_UNORDERED_LIST_COMMAND } from "@lexical/list";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { $createHeadingNode, $createQuoteNode } from "@lexical/rich-text";
import { $setBlocksType } from "@lexical/selection";
import {
  $createParagraphNode,
  $getSelection,
  $isRangeSelection,
  CAN_REDO_COMMAND,
  CAN_UNDO_COMMAND,
  FORMAT_TEXT_COMMAND,
  REDO_COMMAND,
  UNDO_COMMAND,
} from "lexical";
import { useEffect, useState } from "react";

const LOW_PRIORITY = 1;

export const LexicalToolbar = () => {
  const [editor] = useLexicalComposerContext();
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  useEffect(() => {
    return editor.registerCommand(
      CAN_UNDO_COMMAND,
      (payload) => {
        setCanUndo(payload);
        return false;
      },
      LOW_PRIORITY,
    );
  }, [editor]);

  useEffect(() => {
    return editor.registerCommand(
      CAN_REDO_COMMAND,
      (payload) => {
        setCanRedo(payload);
        return false;
      },
      LOW_PRIORITY,
    );
  }, [editor]);

  const setBlock = (kind: "paragraph" | "heading" | "quote") => {
    editor.update(() => {
      const selection = $getSelection();
      if (!$isRangeSelection(selection)) {
        return;
      }
      if (kind === "heading") {
        $setBlocksType(selection, () => $createHeadingNode("h2"));
        return;
      }
      if (kind === "quote") {
        $setBlocksType(selection, () => $createQuoteNode());
        return;
      }
      $setBlocksType(selection, () => $createParagraphNode());
    });
  };

  return (
    <div className="lexical-toolbar" aria-label="编辑工具栏">
      <button aria-label="撤销" disabled={!canUndo} onClick={() => editor.dispatchCommand(UNDO_COMMAND, undefined)} type="button">
        <Undo2 size={16} />
      </button>
      <button aria-label="重做" disabled={!canRedo} onClick={() => editor.dispatchCommand(REDO_COMMAND, undefined)} type="button">
        <Redo2 size={16} />
      </button>
      <span className="lexical-toolbar-divider" />
      <button aria-label="正文" onClick={() => setBlock("paragraph")} type="button">
        <Pilcrow size={16} />
      </button>
      <button aria-label="标题" onClick={() => setBlock("heading")} type="button">
        <Heading1 size={16} />
      </button>
      <button aria-label="引用" onClick={() => setBlock("quote")} type="button">
        <Quote size={16} />
      </button>
      <span className="lexical-toolbar-divider" />
      <button aria-label="加粗" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, "bold")} type="button">
        <Bold size={16} />
      </button>
      <button aria-label="斜体" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, "italic")} type="button">
        <Italic size={16} />
      </button>
      <span className="lexical-toolbar-divider" />
      <button aria-label="无序列表" onClick={() => editor.dispatchCommand(INSERT_UNORDERED_LIST_COMMAND, undefined)} type="button">
        <List size={16} />
      </button>
      <button aria-label="有序列表" onClick={() => editor.dispatchCommand(INSERT_ORDERED_LIST_COMMAND, undefined)} type="button">
        <ListOrdered size={16} />
      </button>
    </div>
  );
};
