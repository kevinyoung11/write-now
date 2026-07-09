export type ExportKind = "markdown" | "script";

const MARKDOWN_LINE_PREFIX = /^\s{0,3}(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+[.)]\s+)/;
const EMPHASIS_MARKERS = /[*_~`]+/g;

export const normalizeScriptPlainText = (markdown: string): string => {
  return markdown
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) =>
      line
        .replace(MARKDOWN_LINE_PREFIX, "")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
        .replace(EMPHASIS_MARKERS, "")
        .trimEnd(),
    )
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
};

export const countCjkAwareWords = (text: string): number => {
  const cjkMatches = text.match(/[\u3400-\u9fff]/g) ?? [];
  const nonCjkText = text.replace(/[\u3400-\u9fff]/g, " ");
  const wordMatches = nonCjkText.match(/[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*/g) ?? [];
  return cjkMatches.length + wordMatches.length;
};

const pad = (value: number): string => String(value).padStart(2, "0");

export const buildExportFileName = (kind: ExportKind, now = new Date()): string => {
  const timestamp = [
    now.getUTCFullYear(),
    pad(now.getUTCMonth() + 1),
    pad(now.getUTCDate()),
    "-",
    pad(now.getUTCHours()),
    pad(now.getUTCMinutes()),
    pad(now.getUTCSeconds()),
  ].join("");

  if (kind === "script") {
    return `write-now-script-${timestamp}.txt`;
  }
  return `write-now-${timestamp}.md`;
};
