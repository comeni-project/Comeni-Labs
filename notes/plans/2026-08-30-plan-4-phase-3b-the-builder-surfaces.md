# Plan 4 Phase 3b — the builder: the surfaces you build with

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [x]` as it completes, and where a step was
> carried out differently, tick it anyway and record the deviation in the execution table. Leave
> a box **unticked** if it was not done: that is how the next phase's inheritance stays visible.

**Goal:** adding a step stops being a hunt through a list and becomes a question about types.
Click a port, get only what fits, ranked by a reason the engine computed.

**Architecture:** **nothing new is invented.** The compatibility index already says what satisfies
what, held to `validate` by a test over every port pair in the registry; `producers_of` already
ranks by `(surplus, -priority, id)`; `compare` already puts your graph beside the resolver's with
the resolver's own reason. This phase is one small endpoint and the surfaces that read them.

**Tech Stack:** Python 3.12 · Pydantic · FastAPI · React 19 · TypeScript · Tailwind 4 · vitest.

**Design source:** the canvas, page 1 — `BuilderPort.dc.html`, `BuilderBrowse.dc.html`,
`BuilderSwap.dc.html`, `BuilderArtifact.dc.html`, `BuilderRun.dc.html`. Notes `n-bport`,
`n-bbrowse`, `n-bswap`, `n-bartifact`, `n-brun`, `impl-reuse`, `impl-inv`, `impl-settled`.
**Render them with `.design/_prev.py` first.**

**Depends on:** phase 3a (the shell, the draft lifecycle, the status line).

---

## Pre-execution notes — checked against the code on 2026-08-30

**P3b-1 — the settings card is already built.** `Settings.tsx` groups by tier, opens tier 4 and
tier 3 by default, collapses the rest, takes its group *names* from the API, and is opened from
the node's own `…` menu (`onOpenSettings` → `carded`). `Restored.test.tsx` holds it. **What the
canvas asks for that is genuinely absent** is narrower than it looks: values with no rule offered
as *choices* rather than a text field, and the premise shown beside a measured one.

**P3b-2 — the filtering needs no backend at all; the RANKING does.**
`GET /api/pipeline/compatibility` already returns `emits` (one signature per output port),
`requires` (the accepted signatures per input port) and `satisfies` (output signature → what it
can feed), keyed `contract_id#port`. That is everything a picker needs to decide *what fits*, and
`useCompatibility.accepts()` already reads it.

What is **not** exposed is the order. `producers_of` lives in `comeni_core.declared.registry` and
the `(surplus, -priority, id)` key lives in `mendel_resolver.router`, and no route surfaces
either. The canvas is explicit that the picker's ordering *and its stated reason* come from
there — *SAMTOOLS_SORT is first because it is the only producer of the state FEATURECOUNTS asks
for* is meant to be **computed, not written**. So one endpoint.

**P3b-3 — `roles[0]` is the grouping bug, and it is in `Modules.tsx`.** A tool that both trims
and QCs appears under one of its jobs and is invisible under the other. `ModuleView.roles` is a
list; the grouping takes the first.

**P3b-4 — there is no description to show, and `impl-reuse` says not to invent one.** Issue #78:
`ModuleContract` has no prose field. The type signature is the description that ships today.
Leave the slot empty rather than filling it.

**P3b-5 — 3a left four boxes unticked**, and they belong here: the `Canvas`/`Artifact` toggle,
the empty-canvas *Add a step here* menu (it opens the browse overlay, which is this phase's), the
rail scrolling itself back to the top, and the three-layer arc field.

---

## Global constraints

- **Never a second implementation of the rule.** The port picker filters through the
  compatibility index and orders through the new endpoint. If a line in the browser ever splits a
  signature on `[`, compares type ids or subtracts state sets, the rule that decides whether a BAM
  can feed featureCounts lives in two places and the second is invisible to the agreement test.
  `useCompatibility.ts`'s header names this as drift the repository has already paid for twice.
- **Invariant 15 decides the run sheet.** No input accepts a sample identifier, filename or path;
  the `Goal` holds a **shape**. A source node carries a TYPE and never a path, and the binding
  lives with the RUN. Same pipeline, different data, no edit.
- **Invariant 3 decides the assistant.** A model produces a **goal**, never a pipeline. Nothing in
  this phase adds a model call; the assistant tab stays unwired and says so.
- **Invariant 6.** Tier 4 is always flagged. Open values show on the node, in the status line, in
  the settings card and in the run sheet — four places is correct, not redundant.
- **Swap shows, then asks.** Every consequence listed, previewed on the canvas, nothing applied
  until the person says so. *A resolver that silently rewrites four things is indistinguishable
  from one that guessed.*
- **`make check` for the API, and the frontend gate from `frontend/`.** `make client` after any
  route change.

---

## Task 1 — `GET /api/pipeline/candidates` — what could go here, and why that order

**Deliverable:** the ranking `producers_of` already computes, exposed once.

- [x] Add `candidates(port_key, side)` to `mendel_api.services.build` (or a sibling): given a port
      the canvas can name, return the contracts that could sit on the other end of a wire.
- [x] **Order by `(surplus, -priority, id)`** — the same key `router.py` uses. Import it or lift
      it into one shared function; do not retype the tuple.
- [x] **Carry the reason.** The row says *the only producer of `alignment.bam[coordinate_sorted]`*
      or *ranked first: no surplus states* — composed from the numbers that produced the order,
      never from a sentence somebody wrote.
- [x] It resolves nothing and touches no goal. It is a registry query, cached on the registry
      digest like every other one, and the front door's performance rule applies.
- [x] Add `test_the_order_is_the_resolvers_own` — assert the endpoint's order matches
      `producers_of` + the rank key for a case with a real tie-break. **Watch it fail** by sorting
      alphabetically.
- [x] Add `test_a_candidate_names_why_it_is_first`. Watch it fail.
- [x] `make client`.

---

## Task 2 — the port picker

**Deliverable:** click a port, get only what fits.

- [x] Click an **output** → what accepts it. Click an **input** → what produces it. Both filtered
      through the compatibility index, which is the same index that colours a wire mid-drag.
- [x] Show the **filtered count against the total** — *6 of 1,604*. #77 means the total is
      aspirational today (discovery reads vendored modules only), and the filtered number is the
      useful one either way; render the total only when it is real.
- [x] Search sits **inside** the popover, for when six becomes sixty. It is not how the list comes
      to exist.
- [x] Choosing one **adds the step and draws the wire** — the whole point. Adding from a port is
      also what fixes placement by construction: the new node has a place to go.
- [x] Keyboard-first: focus on open, arrows to move, Enter to take, Escape to close.
- [x] Add `it("offers only what the index says fits")` — watch it fail by dropping the filter.
- [x] Add `it("never parses a signature in the browser")` — a scan asserting no `split("[")` or
      state-set arithmetic in `build/`. This is the drift guard `useCompatibility` asks for.

---

## Task 3 — the browse overlay replaces the palette

**Deliverable:** one way to find a tool, and it is keyboard-first.

- [x] Search plus filters, over the real canvas — the same surface as the command palette later.
- [x] **A tool appears under EVERY role it declares**, not `roles[0]` (P3b-3). Watch it fail with
      a two-role fixture.
- [x] A tool that cannot fit here is **shown and marked**, with the reason, rather than hidden.
- [x] The type signature is the description; **leave the prose slot empty** (#78, P3b-4).
- [x] Delete `Modules.tsx` and `LeftPanel.tsx` once this replaces them — and not before, so the
      product can add a step at every commit.
- [x] The empty canvas's right-click *Add a step here* opens it (3a's unticked box).

---

## Task 4 — swap, and the settings card's missing half

- [x] *Swap for something else* on the rail, using `compare` scoped to one node. Every consequence
      listed; the canvas previews it struck-through and marked NEW; **nothing applied until the
      person says so**.
- [x] The settings card offers a no-rule value as **choices** rather than a text field, and shows
      the **premise** beside a measured one (P3b-1 — the rest of the card already exists).

---

## Task 5 — the artifact view, and the run sheet

- [x] The `Canvas` / `Artifact` toggle from 3a, now with something behind it: `pipeline.yml` **is**
      the pipeline, so the second view of the canvas is the artifact itself. Every value with its
      `why:` — tier, rule, premise. Open values are null and marked.
- [x] Section jumps are a row of chips, not another left-hand list.
- [x] The run sheet: typed input **sockets** on the canvas (dashed, no settings, a TYPE and never
      a path), and the binding with the RUN. Reachability stated **before** you commit.
- [x] **You never type a path.** If one ever reaches `pipeline.yml`, the product's central promise
      is gone — this is not a style choice (`impl-inv`).

---

## Task 6 — the rail stops scrolling itself to the top

- [x] 3a's unticked box. Find what remounts it — a new key on every verdict, most likely — and key
      the container so it survives a re-render. The walk lost a half-filled parameter form to this.

---

## Task 7 — look at it, then write it down

- [~] **Render it and use it.** Every phase this session found defects a green suite could not.
- [x] Journal, `CLAUDE.md` pointer in the same commit, `notes/README.md` row, guard ledger with
      every revert **verified to land**.

---

## Execution record

**All seven tasks executed 2026-08-30**, on `worktree-plan-4-phase-0`. `make check` green at
**1676**; frontend gate green at **291 tests in 54 files**, `tsc` clean, lint unchanged at its
five pre-existing warnings, production build compiles to one easing curve.

**Every box is ticked except Task 7's, which is `[~]`** — the shell was rendered and read, the
four new surfaces have component tests and no browser pass.

| Task | Carried out as written? | Deviation |
|---|---|---|
| 1 | Yes | The reason is arithmetic against the real registry: asking what feeds featureCounts' coordinate-sorted BAM returns exactly `SAMTOOLS_SORT · the only producer of alignment.bam[coordinate_sorted]`, which is the canvas's own sentence, computed. **I sorted the consuming direction backwards** and my own docstring caught it — found by printing the registry's answer and reading it, not by a test. |
| 2 | Mostly, with one gesture changed and one type extended | **`PortView` had no `states`**, so the picker could only ask *what produces a BAM* — three contracts — when featureCounts asks for one. The states are the difference between a filtered list and an answer, so `PortView` carries them now (the conventional alternative, index 0). **Double-click rather than click**: `onPointerDown` already starts a wire and telling a click from the start of a drag needs movement tracking `Port` does not have; double-click is unambiguous and is the palette's existing *add this* idiom. |
| 2 | And the guard `useCompatibility` had asked for in prose | Its header ends *"A test asserts the absence."* **No test asserted the absence.** `norule.test.ts` does now, over every non-test file in `build/`, and caught a deliberately introduced `split("[")` immediately. A comment claiming a guard exists is worse than one that does not — it stops the next person looking. |
| 3 | Yes, and it took the drag handlers with it | The overlay replaced the palette, so `Modules.tsx`, `LeftPanel.tsx` and `Steps.tsx` are deleted — and with them the canvas's `onDragOver`/`onDrop`, which were **half a gesture whose other half no longer exists**. A drop target with no drag source is dead code that reads as a feature. Three ways in now: the port picker, the overlay, and the canvas's own context menu (3a's unticked box). `roles[0]` is fixed and guarded. |
| 3 | And `Restored.test.tsx` was restated a third time | That file exists so four operator-restored things cannot vanish quietly, and **three of the four were about the palette**. Reversing them in the test that held them — with what each was protecting and where it lives now — is the only honest way. The *question* each protected is still answered; the answers moved. |
| 4 | Narrower than written, because most of the card already existed | P3b-1 was right that `Settings.tsx` already groups by tier and renders a `<select>` for any declared domain — so *choices rather than a text field* was **already true**. The genuinely absent half was the **premise**, which needed a new `SettingView.premise` carrying `PremiseRecord.prose()`. That is what tier 3 is yellow FOR: *the machinery worked, check the premise* — and the card said a rule matched without ever saying what it matched on. |
| 4 | Swap computes its consequences rather than describing them | Choosing a candidate runs `validate` against the graph **as it would be** and diffs the verdict. *Would break MD0506 align.index* is a finding the resolver produced, not a prediction. Nothing is applied until asked. |
| 5 | Both, and I was wrong about the second being expensive | `GET /drafts/{id}/artifact` serves the `pipeline.yml` **verbatim** — a re-serialised model would show something structurally similar to what `mendel emit` reads, which is the gap the view exists to close. **The input sockets were first called "a layout change of the same class as the arc field" and that was wrong**, which the operator caught. The arc field is decorative ambience with no data behind it; a socket carries information a person needs and the data is already in the browser — an input is entry-fed when it is `met` and no wire targets it, a question about **edges** rather than types. `Sources.tsx` is ~90 lines and touches neither `dag-core` nor the API. |
| 5 | And the defect it replaced was worse than nothing | An entry channel drew a **wire stub running off the left edge with a clipped label and no terminus**: the canvas said *something feeds this* and never what, so the only way to learn what the pipeline required was to press Run. Looking at it then found the sockets landing at **x = −200**, off-canvas, because the layout starts at x≈40 and the view opened at origin — fixed by moving the camera, not the layout, since an entry channel is not a node and giving one a position in `dag-core` would make the canvas and the emitted `.nf` disagree about what a step is. |
| 6 | Yes, and the cause was structural | The rail sat inside **two nested scroll containers** — `Side`'s and its own. The outer scrolls, the inner content changes height, the outer clamps to zero. `Side` is not a scroller any more. |
| 7 | `[~]` — the shell was looked at, the new surfaces were not | Looking found the grid still declaring **five columns for three children**, leaving 335px of dead ground beside the rail. The picker, overlay, swap and artifact view have component tests and no browser pass; headless Chrome cannot cheaply drive the clicks that reach them. Recorded as W1 recorded it. |
