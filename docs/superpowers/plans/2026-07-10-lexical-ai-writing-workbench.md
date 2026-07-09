# Lexical AI Writing Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current home rewrite page with a Lexical-first long-form writing workbench that supports Markdown export, local draft persistence, and AI-assisted review/rewrite through the existing write_agent workflow backend.

**Architecture:** The frontend owns the editor shell and canonical client document transforms: Lexical JSON for editing state, Markdown for AI/export, and plain text for stats. Existing write_agent FastAPI APIs remain the AI runtime; the first production slice uses the existing workflow streaming API instead of inventing new backend endpoints. Old pages remain available as auxiliary routes.

**Tech Stack:** React 19, Vite 7, TypeScript 5.9, Lexical 0.46, Vitest, Testing Library, existing Axios/fetch API client, existing CSS with reference-studio visual language.

---

## Scope And Boundaries

In scope:
- `/` becomes a Lexical editor workbench.
- The workbench supports basic rich text: paragraph, heading, quote, bold, italic, unordered/ordered lists, undo/redo.
- The workbench can export Markdown and plain口播稿 text.
- Drafts autosave locally and restore after reload.
- Right-side AI panel connects to existing `runWorkflowWithStream` for full-document AI review/rewrite.
- The AI panel can replace the current editor content with returned content after user action.
- Tests cover transforms, autosave, export helpers, and AI client event handling.
- Build and lint pass.

Out of scope for this phase:
- Real-time collaboration.
- Server-side document persistence.
- Google Docs-style comments anchored to sentence ranges.
- Block drag/drop and slash command menu.
- Full RAG source citation graph.
- Backend schema changes.

## Acceptance Criteria

- `npm test -- --run` passes in `frontend`.
- `npm run build` passes in `frontend`.
- `npm run lint` passes in `frontend`, or any pre-existing lint failures are documented separately with exact files.
- Opening `/` shows the Lexical workbench as the primary surface, not the legacy three-column rewrite UI.
- User can type a multi-paragraph script, use toolbar actions, reload, and see the draft restored.
- Export Markdown returns Markdown with headings/lists/quotes preserved for the supported nodes.
- Export口播稿 returns readable plain text without Markdown syntax.
- AI full workflow can be triggered from the right panel using current editor content and selected style.
- During AI streaming, content/progress states are visible and errors are surfaced.
- On workflow completion with returned rewrite content, user can insert the AI result into the editor.
- Existing auxiliary routes `/styles`, `/materials`, `/reviews`, `/covers`, `/github-trends`, `/linuxdo-trends`, `/hot-topics`, `/layout` still build and route.

## File Structure

- Create `frontend/src/test/setup.ts`: jsdom test setup and browser API shims.
- Modify `frontend/package.json`: add Vitest scripts and Lexical/testing dependencies.
- Modify `frontend/vite.config.ts`: add Vitest config.
- Create `frontend/src/features/editor/documentTransforms.ts`: pure Markdown/plain-text helpers.
- Create `frontend/src/features/editor/documentTransforms.test.ts`: TDD coverage for transforms.
- Create `frontend/src/features/editor/useLocalDraft.ts`: local draft persistence hook.
- Create `frontend/src/features/editor/useLocalDraft.test.tsx`: TDD coverage for autosave/restore.
- Create `frontend/src/features/editor/LexicalMarkdownPlugin.tsx`: Lexical state to Markdown/plain text bridge.
- Create `frontend/src/features/editor/LexicalToolbar.tsx`: toolbar commands.
- Create `frontend/src/features/editor/LexicalWorkbench.tsx`: main editor shell.
- Create `frontend/src/features/editor/LexicalWorkbench.css`: editor-specific visual system.
- Create `frontend/src/features/ai/aiWritingClient.ts`: thin client around existing workflow API.
- Create `frontend/src/features/ai/aiWritingClient.test.ts`: TDD coverage for event mapping.
- Create `frontend/src/features/ai/AIWritingPanel.tsx`: right-side AI controls and result handling.
- Create `frontend/src/features/workbench/WorkbenchPage.tsx`: page-level composition.
- Create `frontend/src/features/workbench/WorkbenchPage.css`: layout for left/context, center/editor, right/AI.
- Modify `frontend/src/App.tsx`: route `/` to `WorkbenchPage`, leave old `HomePage` available at `/rewrite`.
- Modify `frontend/src/pages/index.ts`: export remains compatible.
- Modify `frontend/src/main.tsx`: keep global style imports.

---

## Task 1: Test Harness And Dependencies

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/src/test/setup.ts`

- [ ] **Step 1: Add failing smoke test command target**

Create `frontend/src/features/editor/documentTransforms.test.ts` with:

```ts
import { describe, expect, it } from "vitest";
import { normalizeScriptPlainText } from "./documentTransforms";

describe("normalizeScriptPlainText", () => {
  it("collapses markdown syntax into readable script text", () => {
    expect(normalizeScriptPlainText("# 标题\n\n- 第一条\n- 第二条")).toBe(
      "标题\n\n第一条\n第二条",
    );
  });
});
```

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run frontend/src/features/editor/documentTransforms.test.ts`

Expected: fails because `npm test` and `documentTransforms` do not exist.

- [ ] **Step 3: Install dependencies**

Run:

```bash
cd frontend
npm install lexical@0.46.0 @lexical/react@0.46.0 @lexical/rich-text@0.46.0 @lexical/history@0.46.0 @lexical/markdown@0.46.0 @lexical/list@0.46.0 @lexical/utils@0.46.0
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] **Step 4: Add test config**

`frontend/package.json` scripts:

```json
"test": "vitest"
```

`frontend/vite.config.ts` should expose:

```ts
test: {
  environment: "jsdom",
  setupFiles: "./src/test/setup.ts",
  globals: true,
}
```

`frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 5: Keep RED for missing implementation**

Run: `cd frontend && npm test -- --run src/features/editor/documentTransforms.test.ts`

Expected: fails because `documentTransforms.ts` is missing.

## Task 2: Document Transform Helpers

**Files:**
- Create: `frontend/src/features/editor/documentTransforms.ts`
- Modify: `frontend/src/features/editor/documentTransforms.test.ts`

- [ ] **Step 1: Expand failing transform tests**

Add tests for:
- Markdown headings become plain text.
- List markers are removed in口播稿 text.
- Multiple blank lines collapse to one paragraph break.
- `countCjkAwareWords` counts CJK characters and English words.
- `downloadTextFileName` creates safe timestamped names.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/features/editor/documentTransforms.test.ts`

Expected: missing exports fail.

- [ ] **Step 3: Implement helpers**

Implement:
- `normalizeScriptPlainText(markdown: string): string`
- `countCjkAwareWords(text: string): number`
- `buildExportFileName(kind: "markdown" | "script", now?: Date): string`

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run src/features/editor/documentTransforms.test.ts`

Expected: pass.

## Task 3: Local Draft Persistence

**Files:**
- Create: `frontend/src/features/editor/useLocalDraft.ts`
- Create: `frontend/src/features/editor/useLocalDraft.test.tsx`

- [ ] **Step 1: Write failing hook tests**

Test:
- initial value loads from `localStorage`
- save writes latest Lexical JSON, Markdown, and plain text
- corrupt stored JSON falls back to empty draft

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/features/editor/useLocalDraft.test.tsx`

Expected: missing hook fail.

- [ ] **Step 3: Implement hook**

Implement:
- `WORKBENCH_DRAFT_STORAGE_KEY`
- `WorkbenchDraftSnapshot`
- `readStoredDraft()`
- `writeStoredDraft(snapshot)`
- `useLocalDraft()`

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run src/features/editor/useLocalDraft.test.tsx`

Expected: pass.

## Task 4: AI Writing Client

**Files:**
- Create: `frontend/src/features/ai/aiWritingClient.ts`
- Create: `frontend/src/features/ai/aiWritingClient.test.ts`

- [ ] **Step 1: Write failing client tests**

Test:
- workflow content events accumulate into `generatedMarkdown`
- review_done event updates review summary
- done event extracts `rewrite_id` and `review_id`
- error event throws a readable error

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/features/ai/aiWritingClient.test.ts`

Expected: missing module fail.

- [ ] **Step 3: Implement client**

Implement:
- `AIWritingRunRequest`
- `AIWritingRunResult`
- `runAIWritingWorkflow(request, callbacks, signal?)`

This wraps existing `runWorkflowWithStream` and does not create new backend APIs.

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run src/features/ai/aiWritingClient.test.ts`

Expected: pass.

## Task 5: Lexical Editor Core

**Files:**
- Create: `frontend/src/features/editor/LexicalMarkdownPlugin.tsx`
- Create: `frontend/src/features/editor/LexicalToolbar.tsx`
- Create: `frontend/src/features/editor/LexicalWorkbench.tsx`
- Create: `frontend/src/features/editor/LexicalWorkbench.css`

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/features/editor/LexicalWorkbench.test.tsx`.

Test:
- renders editable area with placeholder
- calls `onMarkdownChange` after text input
- toolbar buttons are present with accessible labels

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/features/editor/LexicalWorkbench.test.tsx`

Expected: missing component fail.

- [ ] **Step 3: Implement minimal editor**

Use:
- `LexicalComposer`
- `RichTextPlugin`
- `ContentEditable`
- `HistoryPlugin`
- `ListPlugin`
- `MarkdownShortcutPlugin`
- `OnChangePlugin`

Use `@lexical/markdown` transformers for Markdown serialization.

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run src/features/editor/LexicalWorkbench.test.tsx`

Expected: pass.

## Task 6: AI Panel And Workbench Page

**Files:**
- Create: `frontend/src/features/ai/AIWritingPanel.tsx`
- Create: `frontend/src/features/workbench/WorkbenchPage.tsx`
- Create: `frontend/src/features/workbench/WorkbenchPage.css`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing page tests**

Create `frontend/src/features/workbench/WorkbenchPage.test.tsx`.

Test:
- renders brief, material, outline, editor, and AI panel regions.
- export buttons are present.
- `/` route points to workbench.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/features/workbench/WorkbenchPage.test.tsx`

Expected: missing workbench fail.

- [ ] **Step 3: Implement page**

Implement:
- Left rail: brief, material notes, outline.
- Center: `LexicalWorkbench`.
- Right rail: `AIWritingPanel`.
- Export markdown/script buttons using transform helpers.
- AI result can replace editor content through a controlled `externalMarkdown` prop.

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run src/features/workbench/WorkbenchPage.test.tsx`

Expected: pass.

## Task 7: Integration, Accessibility, And Visual Verification

**Files:**
- Modify: CSS files as needed, primarily `WorkbenchPage.css` and `LexicalWorkbench.css`

- [ ] **Step 1: Run focused tests**

Run: `cd frontend && npm test -- --run`

Expected: all tests pass.

- [ ] **Step 2: Run build**

Run: `cd frontend && npm run build`

Expected: TypeScript and Vite build pass.

- [ ] **Step 3: Run lint**

Run: `cd frontend && npm run lint`

Expected: pass or document exact pre-existing failures.

- [ ] **Step 4: Browser acceptance**

Start dev server:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Verify:
- `/` renders the workbench.
- Text can be entered.
- Export buttons produce downloadable content.
- Reload restores draft.
- AI panel shows disabled state until style/content requirements are met.

## Task 8: GitHub Delivery

**Files:**
- No code changes unless CI requires fixes.

- [ ] **Step 1: Review diff**

Run:

```bash
git status --short
git diff --stat
git diff -- frontend
```

- [ ] **Step 2: Run final verification**

Run:

```bash
cd frontend && npm test -- --run
cd frontend && npm run build
cd frontend && npm run lint
```

- [ ] **Step 3: Commit**

Run:

```bash
git add frontend/package.json frontend/package-lock.json frontend/src docs/superpowers/plans/2026-07-10-lexical-ai-writing-workbench.md
git commit -m "feat: add lexical ai writing workbench"
```

- [ ] **Step 4: Push and PR**

Run:

```bash
git push origin codex/import-write-agent
gh pr create --base main --head codex/import-write-agent --title "feat: add lexical ai writing workbench" --body "Adds a Lexical-first AI writing workbench with Markdown export, local draft persistence, and workflow-backed AI review/rewrite."
```

- [ ] **Step 5: Verify PR**

Run:

```bash
gh pr checks --watch
```

Expected: all required checks pass.

- [ ] **Step 6: Merge**

Run:

```bash
gh pr merge --merge --delete-branch
git checkout main
git pull origin main
```

Expected: PR merged into `main`. If branch protection or auth blocks merge, report the exact blocker and leave PR ready for owner action.
