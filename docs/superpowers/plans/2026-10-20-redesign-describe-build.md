# Redesign 3 — describe and build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the living builder's conversation rail with a describe page and a build panel
(Step | Assistant), so the chat holds only speech and the engine's cards sit where they belong.

**Architecture:** `stageOf(session)` picks the describe page or the canvas-and-panel. The rail's
`DecisionLog` is split by responsibility: the card waiting for an answer (`Waiting`), the record
of decisions (`StepLine`), and the speech (`Chat`). `LivingSurface` still wires state and draws
nothing itself. No server change.

**Tech Stack:** React 19, TypeScript, Tailwind with the part 1 tokens, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-20-redesign-describe-build-design.md`

## Global Constraints

- Read everything from `AuthoringSessionView` as it is; no server or generated-client change.
- Model output is never applied without the person; the step line only selects.
- Tokens only (no raw colours); type roles from part 1; tabs are a `tablist`.
- Layout at 1440, 1000 and 390 px; below 1000 px the panel stacks above the canvas.
- Run frontend tests with `cd frontend && npx vitest run && npx tsc -b`.

## Review Focus

- A session restored mid-build with no pending proposal: the Step tab shows the step line and an
  empty-state line, never a blank panel — test in Task 4.
- A gap raised during the build (phase `building`, pending kind `gap`) is drawn in the Step tab,
  not lost because the stage is build — test in Task 4.
- A reply arriving while the Step tab shows must mark Assistant, and opening Assistant clears the
  mark — test in Task 4.
- A stop before any step was accepted stays on the describe page with *Correct current answers*;
  a stop after one was accepted is the build stage — test in Task 1.
- The canvas must not pan when the offered step is already in view, or the person's own panning
  is fought — test in Task 5.

---

### Task 1: `stageOf`

**Files:** Create `frontend/src/build/living/stage.ts`, `stage.test.ts`.

**Interfaces:** Produces `stageOf(session: AuthoringSession): "describe" | "build"`.

- [ ] **Step 1:** Tests: `understanding`, `gathering`, `goal_review`, `resolving` → describe;
  `building` with pending kind `pacing` → describe; `building` with pending `step` → build;
  `complete` → build; `stopped`/`failed`/`correcting` with no accepted `step_proposal` decision
  and an empty `graph` → describe; the same with one accepted step → build.
- [ ] **Step 2:** Run, see them fail. **Step 3:** Implement. **Step 4:** Pass. **Step 5:** Commit.

### Task 2: `Chat` — speech only

**Files:** Create `frontend/src/build/living/Chat.tsx`, `Chat.test.tsx`.

**Interfaces:** Produces
`Chat({ session, saying, failedPhase, onRetry, onPoint }: { session: AuthoringSession; saying: string | null; failedPhase: boolean; onRetry: () => void; onPoint: (node: string | null) => void })`.
`onPoint` is called with a block's `node` (or `null`) when a pointer line is pressed.

- [ ] **Step 1:** Tests against `FAKE_SESSION`: person turns are drawn as text; narrative, receipt
  and notice blocks are drawn with `Block`; a refusal with an unreachable code shows *Try again*
  only when `failedPhase`; a `change_set`, `setting_request`, `step_proposal`, `question` or
  `goal_summary` block is one line (`data-testid="pointer"`) that calls `onPoint`; no
  `aria-pressed` decision rows; `saying` is drawn marked *sending…*; a pending assistant turn
  says *The canvas is still yours…*.
- [ ] **Step 2:** Fail. **Step 3:** Implement, moving `TurnEntry`'s speech parts and `UNREACHABLE`
  from `DecisionLog.tsx`; pointer words: *Suggested a change to {node}*, *Asked for a setting on
  {node}*, *Proposed {node}*, *Asked a question*, *Read the goal* — each followed by *— see Step*.
  **Step 4:** Pass. **Step 5:** Commit.

### Task 3: `StepLine` and `Waiting`

**Files:** Create `frontend/src/build/living/StepLine.tsx`, `Waiting.tsx`, `StepLine.test.tsx`.

**Interfaces:**
- `StepLine({ session, selected, onSelect })` — an `<ol aria-label="the plan">`: Goal row; each
  history decision of kind step in order with `processName(node)` and the verb (reuse the
  `DecisionEntry` verb rules); the pending step highlighted (`aria-current="step"`); then
  `N more steps` when `progress.active` gives `total − position > 0`.
- `Waiting(props)` — the pending card switch moved verbatim from `DecisionLog` (step, gap,
  pacing, goal, disagreement, the sampled result, stopped, resolving, *your turn*), with the
  same callbacks `DecisionLog` takes minus the transcript-only ones. Pacing gets the frame title
  *How do you want to build it?*.

- [ ] **Step 1:** Tests: order and verbs against `FAKE_SESSION`; *2 more steps* style count from
  `progress`; no count when `active` is null; a click on a decided step calls `onSelect(node)`.
- [ ] **Step 2–4:** Fail, implement, pass. **Step 5:** Commit.

### Task 4: `DescribePage`, `BuildPanel`, and `LivingSurface` wiring

**Files:** Create `DescribePage.tsx`, `BuildPanel.tsx`; modify `LivingSurface.tsx`,
`CurrentFacts.tsx` (board table: label, value, source chip; `open` prop), `main.css` (`.living`
column widths stay); delete `DecisionLog.tsx`; update `LivingSurface.test.tsx`,
`Conversation.test.tsx` and any other test that read the rail.

**Interfaces:**
- `DescribePage` — region `aria-label="describe"`: heading *What do you want to analyse?*, the
  first person turn quoted, `<Waiting>`, `<CurrentFacts open>` under *What was understood*, then
  `<Chat>` and the `Composer` labelled *Or say it in your own words*.
- `BuildPanel` — region `aria-label="build panel"`: `tablist` with *Step* and *Assistant*; Step
  holds `StepLine`, `Waiting` (or the selected step's `StepTools` and its setting requests, or
  *Nothing is waiting for you.*), and *From the conversation* (suggestions; change sets and
  setting requests of the latest assistant turn); Assistant holds `Chat`. The `Composer` is below
  both. Sending, *Why this one?* and a pointer line switch tabs; a new assistant turn while Step
  shows sets a dot with `aria-label="Assistant, new reply"`.
- `LivingSurface` draws `DescribePage` instead of canvas + panel when `stageOf` says describe.

- [ ] **Step 1:** New tests: describe stage renders no canvas and holds the goal card (guided
  session) and the pacing card; build stage has two tabs, the proposal card is under Step and not
  under Assistant; Assistant has no card; sending from Step switches to Assistant; unread mark
  appears and clears; a gap pending in `building` is under Step; a restored session with nothing
  pending says *Nothing is waiting for you.*; a change set from the latest turn is under *From
  the conversation*.
- [ ] **Step 2:** Fail. **Step 3:** Implement. **Step 4:** Move the existing rail tests to the
  tab or page that now holds what they check; delete only assertions about the rail's existence
  (e.g. "no tabs"). Run the whole suite and `npx tsc -b`. **Step 5:** Commit.

### Task 5: the canvas follows the engine

**Files:** Modify `LivingCanvas.tsx` (new `focus?: string | null` prop), `useView.ts` (new
`reveal(box, viewport)`), `LivingSurface.tsx` (pass `ghost ?? selected`); test in
`LivingCanvas.test.tsx` (create if absent).

**Interfaces:** `reveal(box: {x: number; y: number; w: number; h: number}, viewport: {w: number; h: number})`
pans (k unchanged) so the box is centred, only if any part of it lies outside the viewport.

- [ ] **Step 1:** Tests: a `focus` node outside the measured viewport changes the transform; one
  inside does not; `k` never changes.
- [ ] **Step 2–4:** Fail, implement, pass. **Step 5:** Commit.

### Task 6: browser check and records

- [ ] **Step 1:** Vite on the fakes: `/build/living?fake=1`, `?fake=guided`, `?fake=collect` at
  1440×900 and 390×844, light and dark; compare with `Describe`, `Build`, `Question` boards.
  Fix what differs in layout; record what remains a later part's.
- [ ] **Step 2:** `npx vitest run && npx tsc -b`; `make check` docs/lint parts that touch
  frontend; `CHANGELOG.md` line under the frontend; tick this plan and record deviations.
- [ ] **Step 3:** Commit.
