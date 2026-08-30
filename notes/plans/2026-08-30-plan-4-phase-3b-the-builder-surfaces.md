# Plan 4 Phase 3b — the builder: the surfaces you build with

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [ ]` as it completes, and where a step was
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

- [ ] Search plus filters, over the real canvas — the same surface as the command palette later.
- [ ] **A tool appears under EVERY role it declares**, not `roles[0]` (P3b-3). Watch it fail with
      a two-role fixture.
- [ ] A tool that cannot fit here is **shown and marked**, with the reason, rather than hidden.
- [ ] The type signature is the description; **leave the prose slot empty** (#78, P3b-4).
- [ ] Delete `Modules.tsx` and `LeftPanel.tsx` once this replaces them — and not before, so the
      product can add a step at every commit.
- [ ] The empty canvas's right-click *Add a step here* opens it (3a's unticked box).

---

## Task 4 — swap, and the settings card's missing half

- [ ] *Swap for something else* on the rail, using `compare` scoped to one node. Every consequence
      listed; the canvas previews it struck-through and marked NEW; **nothing applied until the
      person says so**.
- [ ] The settings card offers a no-rule value as **choices** rather than a text field, and shows
      the **premise** beside a measured one (P3b-1 — the rest of the card already exists).

---

## Task 5 — the artifact view, and the run sheet

- [ ] The `Canvas` / `Artifact` toggle from 3a, now with something behind it: `pipeline.yml` **is**
      the pipeline, so the second view of the canvas is the artifact itself. Every value with its
      `why:` — tier, rule, premise. Open values are null and marked.
- [ ] Section jumps are a row of chips, not another left-hand list.
- [ ] The run sheet: typed input **sockets** on the canvas (dashed, no settings, a TYPE and never
      a path), and the binding with the RUN. Reachability stated **before** you commit.
- [ ] **You never type a path.** If one ever reaches `pipeline.yml`, the product's central promise
      is gone — this is not a style choice (`impl-inv`).

---

## Task 6 — the rail stops scrolling itself to the top

- [ ] 3a's unticked box. Find what remounts it — a new key on every verdict, most likely — and key
      the container so it survives a re-render. The walk lost a half-filled parameter form to this.

---

## Task 7 — look at it, then write it down

- [ ] **Render it and use it.** Every phase this session found defects a green suite could not.
- [ ] Journal, `CLAUDE.md` pointer in the same commit, `notes/README.md` row, guard ledger with
      every revert **verified to land**.

---

## Execution record

**Tasks 1 and 2 executed 2026-08-30**, on `worktree-plan-4-phase-0`. `make check` green at
1676; frontend gate green at **287 tests in 53 files**, `tsc` clean, lint unchanged.

**Tasks 3–7 are NOT done and their boxes are unticked**, which is the point: the browse overlay,
swap, the settings card's missing half, the artifact view, the run sheet and the rail's scroll
are what a phase 3c inherits. The picker is the spine and it stands on its own — adding a step
from a port works end to end.

| Task | Carried out as written? | Deviation |
|---|---|---|
| 1 | Yes | The reason is arithmetic against the real registry: asking what feeds featureCounts' coordinate-sorted BAM returns exactly `SAMTOOLS_SORT · the only producer of alignment.bam[coordinate_sorted]`, which is the canvas's own sentence, computed. **I sorted the consuming direction backwards** and my own docstring caught it — found by printing the registry's answer and reading it, not by a test. |
| 2 | Mostly, with one gesture changed and one type extended | **`PortView` had no `states`**, so the picker could only ask *what produces a BAM* — three contracts — when featureCounts asks for one. The states are the difference between a filtered list and an answer, so `PortView` carries them now (the conventional alternative, index 0). **Double-click rather than click**: `onPointerDown` already starts a wire and telling a click from the start of a drag needs movement tracking `Port` does not have; double-click is unambiguous and is the palette's existing *add this* idiom. |
| 2 | And the guard `useCompatibility` had asked for in prose | Its header ends *"A test asserts the absence."* **No test asserted the absence.** `norule.test.ts` does now, over every non-test file in `build/`, and caught a deliberately introduced `split("[")` immediately. A comment claiming a guard exists is worse than one that does not — it stops the next person looking. |
| 3 | **Not done.** | The browse overlay. `Modules.tsx` and `LeftPanel.tsx` stay until it replaces them, so a step can be added at every commit. `roles[0]` is still the grouping bug (P3b-3). |
| 4 | **Not done.** | Swap-with-consequences, and the settings card's two missing halves (choices rather than a text field; the premise beside a measured value). The rest of the card already existed — P3b-1. |
| 5 | **Not done.** | The artifact view and the run sheet. |
| 6 | **Not done.** | The rail still scrolls itself to the top. |
| 7 | Partly | Guards recorded in the ledger, every revert verified to land. **The picker has not been looked at in a browser** — it is covered by six component tests and a real-registry probe of the service behind it, and that is not the same thing. Every phase this session found defects by rendering that a green suite could not. |
