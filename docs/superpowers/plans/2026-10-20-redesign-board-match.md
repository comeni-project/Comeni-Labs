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
- [x] Tests: caption *N steps · N inputs* and the sample sentence from the sample channel;
  *Fit* calls the view's fit; legend present; a node's footer counts by tier (*1 measured · 13
  settled*); ports rendered with `<`/`>`; the ghost's footer *Proposed · not added yet*; an input
  box carries *Input*, name, type and its scope sentence; no label on the wire.
- [x] Implement; comparison loop (Build canvas); commit.

### Task 3: the step panel, the step card, the composer, `WalkProgress.upcoming`
**Files:** `packages/mendel-authoring/src/mendel_authoring/progress.py` and its test;
`packages/mendel-api` route model if it re-declares progress; `make client`;
`build/living/StepLine.tsx`, `blocks/StepProposalCard.tsx`, `Composer.tsx`, `BuildPanel.tsx`,
`Waiting.tsx` and tests.
- [x] Python test: `progress_of(order, …, pending)` gives `upcoming == order[position:]`, `[]`
  when the offer is last or nothing is offered. Implement; `uv run pytest packages/mendel-authoring -q`.
  *Deviation:* each upcoming step carries its `position` (`Upcoming(node, position)`), and a step
  whose review still holds is left out — after a swap the plan can put a reviewed step after the
  offer, and the walk will not offer it again; names alone could not say *step 5* then.
- [x] `make client`; frontend: the step line names upcoming steps (*SAMTOOLS_SORT · step 5*) in
  grey with hollow dots, green line segments between finished steps, amber ring on a step whose
  settings include a measured one, right-hand *settled* / *you chose* / *N measured*. *Deviation:* who chose stays beside the count
  (*you chose · 1 measured*, spec departure 6); places read *step 4*, not *step 4 of 5*.
- [x] Step card tests: title *Step 4 · SAMTOOLS_SORT*, tier chip (*required* for tier 1, the tier
  word otherwise), radio cards with *suggested*, **Add it** / **Why this one?** / **Skip** (Skip
  calls `onReject`), *Preview* as a link on an alternative; no sentence above the card.
  *Ruling:* no **Skip** — rejecting a step is not in the protocol (spec departure 4); the chip is
  the served tier name, not *required* (departure 5). `Primary`/`Secondary` are rounded for every
  card; `useTiers` treats a non-list answer as no vocabulary yet.
- [x] Composer: rounded, send button labelled *Send*. Panel as a card. Implement; comparison loop; commit.

### Task 4: Question — a selected step's open values
**Files:** `BuildPanel.tsx`, new `blocks/QuestionCard.tsx`, tests.
- [x] Tests: selecting a step with a tier-4 setting shows a card per open value — the setting
  as the question, *needs you*, the path *settings.<name>*, the reason, radio options from the
  setting's domain (or a field when none), a reason field, *Save answer* writes through
  `onSetParam`, *Cancel* closes; no open values → no card; the tools follow under *Change this step*;
  × closes the step.
- [x] Implement; comparison loop (Question); commit.
  *Rulings:* the question reads *What should `name` be?* — a setting carries no question text
  (the board's strandedness is a fact, not a setting: featureCounts' contract says so); no notes
  under the answers (a domain is a list of values); the reason goes to `DraftParam.why`, which the
  server keeps as the value's recorded reason, so the card says only that it is saved beside the
  value. An opened step replaces the step line, as the board draws it (× brings it back). The
  panel's and canvas's steps now carry the person's typed values, so an answered value is not
  asked again (mutation-checked). `?fake=question` added for the comparison.

### Task 5: Describe
**Files:** `DescribePage.tsx`, `CurrentFacts.tsx` (the table), `blocks/GoalCard.tsx` (edit
controls moved onto lines), `LivingBuilder.tsx`/`useAuthoringSession` (pace chain), tests.
- [x] Tests: the table's rows (*You have*, *You want*, each fact) with source chips (*you said*,
  *convention*, *will be measured*, *needs you*) and *From "…"* quotes where the goal heard them;
  clicking a line opens its editor; *Start building* confirms the goal; with pacing *ask*, the
  chosen pace answers the pacing proposal when it arrives (once); with pacing fixed, no cards;
  the hero title and lede; no header strip.
- [x] Implement; comparison loop (Describe); commit.
  *Rulings:* chips are the fact's own source (spec departure 8); the determinism line names the goal
  and answers (7); each input is its own line under *You have*, opened by `correct <type>`; open
  facts and the engine's unanswered `fact_subjects` are *Not known yet · needs you* lines; fact
  lines open the existing `FactEditor` when the page can correct; the separate *Current answers*
  list is not drawn while the goal is checked (unless a tool choice is pinned, which only it can
  release). The pace is read from `building.pacing` in the settings menu (`usePacing`), which is
  what the engine's `pace` route reads at confirmation; a menu that fails to load leaves the
  question to the engine's card. Hero and lede sizes are allowed on Describe (`main.css` note).

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
- **Canvas, loop 1:** full-bleed area, striped nodes, `·` ports, *runs 12×*, white inputs with a
  bar, grey dotted ghost → a card with caption, samples line, Fit, legend; outlined nodes with
  `<`/`>` ports and *1 measured · 2 settled*; *Proposed · not added yet*; inputs on now-soft.
  **Loop 2:** plain ground → `--canvas` with a resting dot grid (living canvas only); ghost wire
  grey → dashed blue, one line; card inset 28 px; no rule under the header. Remaining by choice:
  nodes keep the fixed 172×112 geometry the wires use (the board sizes them to content); the
  collection ribbons stay (which steps run per sample or gather is not said anywhere else); a
  selected step still labels its wires.
- **Step panel, loop 1:** full-height rail, grey line, *1 more step*, a sentence above a square card
  with *tier 2*, checkbox squares, *Continue* / *Show me why*, a square composer → a card beside the
  canvas; the line green to the offer and grey after, STAR_ALIGN ringed amber with *1 measured*, the
  step to come named (*SUBREAD_FEATURECOUNTS step 5*); *Step 4 · SAMTOOLS_SORT* with a *convention*
  chip, radio cards with *suggested*, *Add it* / *Why this one?*, *Preview* as a link; a rounded
  composer with a Send button. **390 and dark:** the canvas's corner marks cut through its caption
  and the legend sat over *+ Add step* → no marks on the dotted ground, one wrapping footer row.
  Remaining by choice: the tabs (departure 1), no *Skip* (4), the served tier word (5), process
  names for steps (3).
- **Question, loop 1:** an opened step showed only its tools in a square box under the line →
  name and tool, a needs-you question card (path, reason on a red rule, two radio cards, reason
  field, *Save answer* / *Cancel*), tools as three buttons under *Change this step*, × in the tab
  row. **Loop 2:** setting name in the data face; status chip before *1 value needs you*, as the
  boards order them; `BlockFrame` rounded for every card. **390 and dark:** read as drawn. Remaining
  by choice: *Not sure? Measure it instead* (only where the engine offers a measuring step, which a
  setting never has today) and *Learn it in Code* are not drawn.
- **Describe, loop 1:** a 22 px title, a square goal card of chips with *+ add a type*, *That's
  right / Not quite*, the pace asked later as a card → the hero question and the board's lede; *What
  was understood* as a table (a line per input, output and fact; source chips; *From "…"* quotes;
  click a line to correct it); the two pace cards when the installation asks; *→ Start building*.
  **390 and dark:** read as drawn once the page gutter was 16 px (the spacing scale made `px-4`
  10 px). Remaining by choice: departures 7 and 8.
