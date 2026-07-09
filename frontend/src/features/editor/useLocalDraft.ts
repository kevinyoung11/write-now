import { useMemo, useState } from "react";

export const WORKBENCH_DRAFT_STORAGE_KEY = "write-now:lexical-workbench:draft";

export type WorkbenchDraftSnapshot = {
  lexicalJson: string;
  markdown: string;
  plainText: string;
  updatedAt: string;
};

export type WorkbenchDraftInput = Omit<WorkbenchDraftSnapshot, "updatedAt">;
export type DraftWriteResult = {
  snapshot: WorkbenchDraftSnapshot;
  error?: string;
};

export const EMPTY_DRAFT: WorkbenchDraftSnapshot = {
  lexicalJson: "",
  markdown: "",
  plainText: "",
  updatedAt: "",
};

const isDraftSnapshot = (value: unknown): value is WorkbenchDraftSnapshot => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    typeof record.lexicalJson === "string" &&
    typeof record.markdown === "string" &&
    typeof record.plainText === "string" &&
    typeof record.updatedAt === "string"
  );
};

export const readStoredDraft = (): WorkbenchDraftSnapshot => {
  try {
    const raw = localStorage.getItem(WORKBENCH_DRAFT_STORAGE_KEY);
    if (!raw) {
      return EMPTY_DRAFT;
    }
    const parsed = JSON.parse(raw) as unknown;
    return isDraftSnapshot(parsed) ? parsed : EMPTY_DRAFT;
  } catch {
    return EMPTY_DRAFT;
  }
};

export const writeStoredDraft = (
  snapshot: WorkbenchDraftInput | WorkbenchDraftSnapshot,
): DraftWriteResult => {
  const nextSnapshot: WorkbenchDraftSnapshot = {
    lexicalJson: snapshot.lexicalJson,
    markdown: snapshot.markdown,
    plainText: snapshot.plainText,
    updatedAt:
      "updatedAt" in snapshot && snapshot.updatedAt
        ? snapshot.updatedAt
        : new Date().toISOString(),
  };
  try {
    localStorage.setItem(WORKBENCH_DRAFT_STORAGE_KEY, JSON.stringify(nextSnapshot));
    return { snapshot: nextSnapshot };
  } catch (error) {
    return {
      snapshot: nextSnapshot,
      error: error instanceof Error ? error.message : String(error),
    };
  }
};

export const useLocalDraft = () => {
  const initialSnapshot = useMemo(() => readStoredDraft(), []);
  const [snapshot, setSnapshot] = useState<WorkbenchDraftSnapshot>(initialSnapshot);
  const [persistError, setPersistError] = useState<string | undefined>(undefined);

  const saveDraft = (draft: WorkbenchDraftInput) => {
    const result = writeStoredDraft(draft);
    setSnapshot(result.snapshot);
    setPersistError(result.error);
  };

  return {
    snapshot,
    persistError,
    saveDraft,
  };
};
