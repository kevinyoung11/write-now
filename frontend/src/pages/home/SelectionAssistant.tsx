import React, { useEffect, useRef, useState } from "react";
import { Check, Loader2, Sparkles, X } from "lucide-react";
import { rewriteWithStream, type WritingStyle } from "../../services/api";
import { getCaretCoordinates } from "./caretPosition";
import "./SelectionAssistant.css";

interface Target {
  start: number;
  end: number;
  text: string;
  anchorTop: number;
  anchorLeft: number;
}

interface SelectionAssistantProps {
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  fullText: string;
  onApply: (nextFullText: string) => void;
  styles: WritingStyle[];
  selectedStyleId: number | undefined;
  onSelectStyleId: (id: number) => void;
  labels: {
    selectionScope: (count: number) => string;
    wholeDraftScope: string;
    stylePlaceholder: string;
    rewriteAction: string;
    applyAction: string;
    discardAction: string;
    needStyleHint: string;
    shortcutHint: string;
  };
}

export const SelectionAssistant: React.FC<SelectionAssistantProps> = ({
  textareaRef,
  fullText,
  onApply,
  styles,
  selectedStyleId,
  onSelectStyleId,
  labels,
}) => {
  const [target, setTarget] = useState<Target | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [preview, setPreview] = useState("");
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const activeSourceRef = useRef<EventSource | null>(null);

  const reset = () => {
    setTarget(null);
    setChatOpen(false);
    setIsStreaming(false);
    setPreview("");
    activeSourceRef.current?.close();
    activeSourceRef.current = null;
  };

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }

    const showAt = (start: number, end: number) => {
      const text = fullText.slice(start, end);
      if (!text.trim()) {
        return;
      }
      const coords = getCaretCoordinates(textarea, end);
      setTarget({
        start,
        end,
        text,
        anchorTop: coords.top + coords.height,
        anchorLeft: coords.left,
      });
      setChatOpen(false);
      setPreview("");
    };

    const handleSelect = () => {
      if (document.activeElement !== textarea) {
        return;
      }
      const { selectionStart, selectionEnd } = textarea;
      if (selectionStart == null || selectionEnd == null || selectionStart === selectionEnd) {
        return;
      }
      showAt(selectionStart, selectionEnd);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      const isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      if (!isShortcut) {
        return;
      }
      event.preventDefault();
      const { selectionStart, selectionEnd } = textarea;
      if (selectionStart != null && selectionEnd != null && selectionStart !== selectionEnd) {
        showAt(selectionStart, selectionEnd);
      } else {
        showAt(0, textarea.value.length);
      }
    };

    textarea.addEventListener("select", handleSelect);
    textarea.addEventListener("mouseup", handleSelect);
    textarea.addEventListener("keydown", handleKeyDown);
    return () => {
      textarea.removeEventListener("select", handleSelect);
      textarea.removeEventListener("mouseup", handleSelect);
      textarea.removeEventListener("keydown", handleKeyDown);
    };
  }, [textareaRef, fullText]);

  useEffect(() => {
    const handleOutside = (event: MouseEvent) => {
      if (!target) {
        return;
      }
      const wrap = wrapRef.current;
      if (wrap && wrap.contains(event.target as Node)) {
        return;
      }
      if (event.target === textareaRef.current) {
        return;
      }
      reset();
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        reset();
      }
    };
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("keydown", handleEscape);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  useEffect(() => () => activeSourceRef.current?.close(), []);

  if (!target) {
    return null;
  }

  const isWholeDraft = target.start === 0 && target.end === fullText.length;
  const scopeLabel = isWholeDraft
    ? labels.wholeDraftScope
    : labels.selectionScope(target.text.length);

  const handleRewrite = () => {
    if (!selectedStyleId || isStreaming) {
      return;
    }
    setIsStreaming(true);
    setPreview("");
    let buffer = "";
    const source = rewriteWithStream(
      {
        source_article: target.text,
        style_id: selectedStyleId,
        target_words: Math.max(20, target.text.length),
        enable_rag: false,
      },
      (chunk) => {
        buffer += chunk;
        setPreview(buffer);
      },
      () => {
        setIsStreaming(false);
      },
      () => {
        setIsStreaming(false);
      },
    );
    activeSourceRef.current = source;
  };

  const handleApply = () => {
    if (!preview.trim()) {
      return;
    }
    const next = fullText.slice(0, target.start) + preview + fullText.slice(target.end);
    onApply(next);
    reset();
  };

  return (
    <div
      className="sel-assist"
      ref={wrapRef}
      style={{ top: target.anchorTop, left: target.anchorLeft }}
    >
      <button
        type="button"
        className={`sel-assist-btn${chatOpen ? " on" : ""}`}
        onClick={() => setChatOpen((value) => !value)}
      >
        <Sparkles size={13} />
      </button>

      {chatOpen && (
        <div className="sel-assist-pop">
          <div className="sel-assist-head">
            <span>{scopeLabel}</span>
            <button type="button" onClick={reset}><X size={12} /></button>
          </div>

          <select
            className="sel-assist-style"
            value={selectedStyleId ?? ""}
            onChange={(event) => onSelectStyleId(Number(event.target.value))}
          >
            <option value="">{labels.stylePlaceholder}</option>
            {styles.map((style) => (
              <option key={style.id} value={style.id}>{style.name}</option>
            ))}
          </select>

          {preview ? (
            <div className="sel-assist-preview">{preview}</div>
          ) : !selectedStyleId ? (
            <p className="sel-assist-hint">{labels.needStyleHint}</p>
          ) : (
            <p className="sel-assist-hint">{labels.shortcutHint}</p>
          )}

          <div className="sel-assist-actions">
            {!preview || isStreaming ? (
              <button
                type="button"
                className="sel-assist-primary"
                onClick={handleRewrite}
                disabled={!selectedStyleId || isStreaming}
              >
                {isStreaming ? <Loader2 size={13} className="spin" /> : <Sparkles size={13} />}
                {labels.rewriteAction}
              </button>
            ) : (
              <>
                <button type="button" className="sel-assist-ghost" onClick={reset}>
                  {labels.discardAction}
                </button>
                <button type="button" className="sel-assist-primary" onClick={handleApply}>
                  <Check size={13} />
                  {labels.applyAction}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
