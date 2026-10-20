# Redesign — matching the boards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every difference in the spec's tables, so each screen reads the same as its
board at 1400 px, then at 390 px and in dark.

**Architecture:** Mostly restyling of existing components, keeping their props and tests'
behaviour. Two behaviour changes: Describe draws the goal as the *What was understood* table and
chains the pace; a selected step shows its open values as question cards. One server change:
`WalkProgress.upcoming`.

**Tech Stack:** React 19, Tailwind (part 1 tokens), Vitest; Python (`mendel-authoring`,
`mendel-api`), pytest; `make client` for the generated types.

**Spec:** `docs/superpowers/specs/2026-10-20-redesign-board-match-design.md`

## Global Constraints

- The spec's *cannot override* list holds: no invented data, no false claims, no labs, no relaunch.
- Named radii only; colour by meaning; mono only for data (types, ids, values, process names).
- Every task ends with the **comparison loop**: screenshot the screen beside its board at
  1400×900 (`pair.py` in the session scratchpad, fixtures through the DevTools script), list what
  still differs in this plan's *Comparison log*, fix, repeat until nothing structural differs;
  then 390 and dark once.
- `cd frontend && npx vitest run && npx tsc -b && npm run lint`; Python: `make test` scope for
  the touched packages (`uv run pytest packages/mendel-authoring -q`), `make client` after the
  schema change, `uv lock --check` untouched.

## Review Focus

- A selected step with no open values: no question cards, tools only — Task 4.
- Pacing setting not *ask*: no pace cards; *Start building* alone — Task 5.
- A plan whose offered step is the last: `upcoming` empty, no *more steps* row — Task 3.
- Long process names in the narrow panel and canvas nodes: truncate with a title, never overflow — Tasks 2, 3.
- The proposal card's *Preview* kept reachable by keyboard after the restyle — Task 3.

---

### Task 1: the builder header
**Files:** `build/living/LivingHeader.tsx`, `LivingHeader.test.tsx`.
- [x] Tests: status chip words per phase (*Building · step 4 of 5*, *Checking the goal*, *Valid*
  on complete, *Stopped*); disabled Run is the quiet button (no `bg-action`); no header while
  describing (`views={false}` → the surface draws none).
- [x] Implement; run tests; comparison loop (Build, Question headers); commit.

### Task 2: the canvas
**Files:** `build/living/LivingCanvas.tsx`, `LivingNode.tsx`, `CollectionChannel.tsx`
(`SourceNode`, `Flowline`), `LivingSurface.tsx` (panel frame), tests beside them.
- [ ] Tests: caption *N steps · N inputs* and the sample sentence from the sample channel;
  *Fit* calls the view's fit; legend present; a node's footer counts by tier (*1 measured · 13
  settled*); ports rendered with `<`/`>`; the ghost's footer *Proposed · not added yet*; an input
  box carries *Input*, name, type and its scope sentence; no label on the wire.
- [ ] Implement; comparison loop (Build canvas); commit.

### Task 3: the step panel, the step card, the composer, `WalkProgress.upcoming`
**Files:** `packages/mendel-authoring/src/mendel_authoring/progress.py` and its test;
`packages/mendel-api` route model if it re-declares progress; `make client`;
`build/living/StepLine.tsx`, `blocks/StepProposalCard.tsx`, `Composer.tsx`, `BuildPanel.tsx`,
`Waiting.tsx` and tests.
- [ ] Python test: `progress_of(order, …, pending)` gives `upcoming == order[position:]`, `[]`
  when the offer is last or nothing is offered. Implement; `uv run pytest packages/mendel-authoring -q`.
- [ ] `make client`; frontend: the step line names upcoming steps (*SAMTOOLS_SORT · step 5*) in
  grey with hollow dots, green line segments between finished steps, amber ring on a step whose
  settings include a measured one, right-hand *settled* / *you chose* / *N measured*.
- [ ] Step card tests: title *Step 4 · SAMTOOLS_SORT*, tier chip (*required* for tier 1, the tier
  word otherwise), radio cards with *suggested*, **Add it** / **Why this one?** / **Skip** (Skip
  calls `onReject`), *Preview* as a link on an alternative; no sentence above the card.
- [ ] Composer: rounded, send button labelled *Send*. Panel as a card. Implement; comparison loop; commit.

### Task 4: Question — a selected step's open values
**Files:** `BuildPanel.tsx`, new `blocks/QuestionCard.tsx`, tests.
- [ ] Tests: selecting a step with a tier-4 setting shows a card per open value — the setting
  as the question, *needs you*, the path *settings.<name>*, the reason, radio options from the
  setting's domain (or a field when none), a reason field, *Save answer* writes through
  `onSetParam`, *Cancel* closes; no open values → no card; the tools follow under *Change this step*;
  × closes the step.
- [ ] Implement; comparison loop (Question); commit.

### Task 5: Describe
**Files:** `DescribePage.tsx`, `CurrentFacts.tsx` (the table), `blocks/GoalCard.tsx` (edit
controls moved onto lines), `LivingBuilder.tsx`/`useAuthoringSession` (pace chain), tests.
- [ ] Tests: the table's rows (*You have*, *You want*, each fact) with source chips (*you said*,
  *convention*, *will be measured*, *needs you*) and *From "…"* quotes where the goal heard them;
  clicking a line opens its editor; *Start building* confirms the goal; with pacing *ask*, the
  chosen pace answers the pacing proposal when it arrives (once); with pacing fixed, no cards;
  the hero title and lede; no header strip.
- [ ] Implement; comparison loop (Describe); commit.

### Task 6: pipeline file, run sheet, Home, runs, run
- [ ] Pipeline file: section chips, file tab wording, the footer line. Run sheet: in the page,
  *Your files* first, *Checked* as the summary line. Home: results file icon, *All results*, the
  table note. Runs: active-row tint. Run: the code line from `signal`, full-width attempt bars,
  *Each attempt used almost all of what it asked for*, failed lane tint, panel figures as drawn.
  Tests for each new sentence and condition; comparison loop for each board; commit.

### Task 7: records
- [ ] CHANGELOG lines; journal entry; tick; hand over for the operator's Chrome check.

## Comparison log

(One line per loop: screen, what still differed, what was fixed.)
- **Header, loop 1:** status was a mono line → chip; Run faded green → quiet. **Loop 2:** name
  22 → 25 px, inset 20 → 28 px, Run borderless grey. Matches but for *Saved 3 s ago* (no save
  time exists). Departures: *Complete* not *Valid* (only the gate can say valid); a reply in
  flight is *now*, not amber (amber means measured). Describe has no header, so its status chip
  moved into the sentence panel's footer line, where the board has a line (issues 110, 112).
