# Builder plan 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The step's tools open from the step itself (a menu and cards beside it), the pipeline file page becomes direction A with the AI panel, and many-port steps are drawn whole.

**Architecture:** Frontend-led. The cards replace the step sheet that opened over the chat and write through the verbs the canvas already uses (`edit`, `switchInput`, `keepWhole`, `review`). The pipeline file page keeps the server's text and draws an outline, folds and inline reasons over it; its AI panel is the builder's own thread and composer. The geometry change is shared: `dag_core.layout.node_height` and `geometry.ts nodeHeight`, held together by the existing geometry guard.

**Tech Stack:** React + TanStack Query + Tailwind (frontend), `dag-core` (pure Python layout), vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-builder-plan-2-design.md`

## Global Constraints

- A port's anchor stays `SPINE + index × PORT_GAP` per side; a node's height is `max(112, 89 + 22 × (n − 1))` for `n` = the larger side's port count; siblings in a rank are spaced by `max(SIBLING_PITCH, height + 58)`.
- Every card writes through an existing verb; no new route.
- No `localStorage`; breakpoints are CSS (the source guards in `sources.test.ts`).
- Browser check at 1440 and 390, light and dark, on the fake sessions.

## Review Focus

1. **A step with more ports than fit in 112px** (QUAST: 6 inputs): every port mark is inside the node and every wire ends on its own row.
2. **Two tall steps in one rank:** they do not overlap, and the main chain stays straight.
3. **A card open when its step is removed** (by the agent or the person): the card closes rather than drawing a step that is gone.
4. **Selecting text across a fold** in the pipeline file: the quoted lines are the file's real line numbers.
5. **A keyboard-only person:** the menu opens with Shift+F10 or the menu key on a focused step, arrows move, Enter chooses, Esc closes and returns focus to the step.

---

### Task 1: Many-port steps are drawn whole

**Files:**
- Modify: `packages/dag-core/src/dag_core/layout.py` (`node_height`, sibling pitch, `Placed.height`), `packages/dag-core/tests/test_dag_layout.py`, `packages/dag-core/tests/test_geometry_agrees.py`
- Modify: `frontend/src/build/geometry.ts` (`nodeHeight`), `frontend/src/build/living/LivingNode.tsx`, `LivingCanvas.tsx`, `frontend/src/build/Minimap.tsx`
- Test: `frontend/src/build/living/CanvasBoard.test.tsx`

**Interfaces:** Produces `node_height(ports: int) -> int` and `nodeHeight(ports: number): number`, identical values.

- [ ] **Step 1: Failing tests:** `test_a_tall_step_grows_and_its_siblings_make_room` (a node with 6 inputs is `89 + 22*5 = 199` high; the next sibling's `y` ≥ its `y + 199 + 58`); `test_the_canvas_and_the_layout_agree_on_geometry` extended with `node_height(1..8)`; vitest `draws every port of a many-port step inside it, each on its own row` (6 inputs, 3 outputs: node height 199, each `data-port-mark` top within the node, row *i* holds input *i* left and output *i* right).
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement; rows show the port name with the type and states as the title. **Step 4:** `uv run pytest packages/dag-core` and `npx vitest run src/build` — PASS. **Step 5:** Commit `feat: a step with many ports grows to fit them, each wire on its own row (#494)`.

### Task 2: The canvas never re-zooms by itself; a new message fades in

**Files:** Modify `LivingCanvas.tsx`, `LivingSurface.tsx`, `AgentThread.tsx`, `frontend/src/main.css`. Test: `follow.test.tsx`, `AgentThread.test.tsx`.

- [ ] **Step 1: Failing tests:** `pans to a step that arrives off screen, and never changes the zoom` (the view's `k` is unchanged after a new node arrives); `fades a new thread item in, and nothing under reduced motion` (the newest item carries `agent-arrive`; `sources.test.ts` finds `.agent-arrive` under the reduced-motion block).
- [ ] **Step 2–4:** FAIL, implement, PASS. **Step 5:** Commit `fix: the canvas fits only when asked, and a reply fades in without moving the thread (#494, #496)`.

### Task 3: The step menu and its cards

**Files:**
- Create: `frontend/src/build/living/StepMenu.tsx`, `StepCard.tsx` (the host beside the node), `cards/SettingsCard.tsx`, `cards/InputsCard.tsx`, `cards/SwapCard.tsx`, `StepMenu.test.tsx`
- Modify: `LivingCanvas.tsx` (right-click, long press, `⋯`, Shift+F10 / menu key; empty-canvas and input-node menus), `LivingSurface.tsx` (one open card; closes when its step is gone), `ChatPanel.tsx` (no step sheet over the thread; *Ask about this step* fills the composer), `useAuthoringSession.ts`
- Delete: `StepSheet.tsx` (its sections move into the cards), `StepSheet.test.tsx`, `Question.test.tsx` → `cards/SettingsCard.test.tsx`; `blocks/StepTools.tsx` splits into the Swap card and Remove
- Test: `StepMenu.test.tsx`, the moved card tests, `StepTools.test.tsx` rewritten against the cards

**Interfaces:** `StepMenu({ node, at, items, onChoose, onClose })`; `StepCard({ node, kind: "settings" | "inputs" | "swap", anchor, onClose })`; the surface holds `card: { node, kind } | null`.

- [ ] **Step 1: Failing tests:** `right-click on a step opens its menu with the items it allows` (no *Why is it here?*; *Keep whole* only where `parts` exist; *Looks right* only on an AI-chosen unreviewed step); `the menu works from the keyboard` (Shift+F10, arrows, Enter, Esc returns focus); `a click opens the step's Settings card beside it, and the chat stays` (the thread is still in the document); `Ask about this step names the step in the composer`; `a card closes when its step is removed`; `Swap lists the other tools and choosing one is an edit`; `Remove asks, then edits`; `Looks right reviews the step`.
- [ ] **Step 2–4:** FAIL, implement, PASS (`npx vitest run && npx tsc -b`). **Step 5:** Commit `feat: a step's tools open from the step: a menu and a card beside it (#499)`.

### Task 4: The pipeline file page, direction A with the AI panel

**Files:**
- Create: `frontend/src/build/living/FileOutline.tsx`, `FileView.tsx` (folds, inline reason, selection toolbar), `AiPanel.tsx`, `folds.ts`, `folds.test.ts`, `FileView.test.tsx`
- Modify: `PipelineFile.tsx` (layout: outline · file · AI panel; tabs; Download in the tab row), `LivingSurface.tsx` (passes the thread and composer to the panel), `AgentThread.tsx` (the AI's answers carry *the AI's words* and step chips from the tools of that turn), `main.css` (`.pipeline-file` grid: 264px · 1fr · 420px; the panel folds below 1180px; file only on a phone)
- Delete: the `Reason` column and its "Click a value…" text
- Test: `PipelineFile.test.tsx` rewritten; `folds.test.ts`; `FileView.test.tsx`; `AgentThread.test.tsx`

**Interfaces:** `folds(text) -> Fold[]` with `{ start, end, summary }` (0-based lines; `module`, `why`, `inputs` of each step and each top-level section); `stepsUsed(turn) -> string[]` from the turn's tool lines whose name is `read_step | choose_tool | set_value | keep_whole | switch_input` (their node from the label is not reliable: the tool line gains the node it touched, server side, as `ToolLine.node`).

- [ ] **Step 1: Failing tests:** `folds a step's module, why and inputs to one summary line` (`{ nf-core/star/align@2.7.11b · 4 lines }`); `the outline lists the steps with their state and jumps to each`; `clicking a value opens its reason beneath the line, with Ask the AI and Change`; `selecting lines offers Explain this, which asks in the conversation with the real line numbers`; `the AI panel is the builder's thread and its answers link the steps they read`; `main.nf and nextflow.config compile on first open`; `the empty "click a value" column is gone`; backend `test_a_tool_line_names_the_step_it_touched` (`ToolLine.node`).
- [ ] **Step 2–4:** FAIL, implement, PASS (`make client` after `ToolLine.node`; the v12 turn golden is rewritten, as #504 did). **Step 5:** Commit `feat: the pipeline file page: an outline, folds, reasons in place and the AI beside it (#495, #499)`.

### Task 5: Docs, checks and the browser check

- [ ] **Step 1:** Update `docs/how-to/pipelines/build.md` and `docs/reference/pipelines/builder-interface.md` for the menu, the cards and the file page.
- [ ] **Step 2:** `make check`, `make guards`, `cd frontend && npx vitest run && npx tsc -b`, `npm run lint` — PASS.
- [ ] **Step 3:** Browser check on `?fake=1` and `?fake=collect`, plus a many-port fake (QUAST), at 1440 and 390, light and dark. Record findings.
- [ ] **Step 4:** Tick #499's items; the live walk follows (operator).
