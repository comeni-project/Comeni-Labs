# Plan 4 Phase 5 — the runs screens

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [ ]` as it completes; leave one **unticked** if
> it was not done, and record every deviation in the execution table.

**Goal:** the board and the run page redrawn against the canvas, on top of the projections phase 4
built. **Everything these screens read now exists** — that was phase 4's whole purpose.

**Architecture:** frontend only, unless a pre-execution note below says otherwise. Every number on
these screens comes from an endpoint that already ships.

**Tech Stack:** React 19 · TS · Tailwind 4 · @tanstack/react-query · `frontend/src/runs/`.

**Design source:** the canvas, page 5 — `rn-series`, `rn-timeline`, `rn-absence`, `rn-blocked`,
`rn-settled`, `rn-board`, and the `RunEarly` artboard. `.design/runs_boards.py` renders them from
one task list through the same boundary sweep `wiener_core.series` implements — **read it and
render it before drawing anything**, because it has already found defects by being looked at.

**Depends on:** phases 0–4, all complete and merged into this branch.

---

## The rule this phase exists to enforce

**A derived curve must look derived.** Phase 4 decided *which* curves are honest and labelled
them; this phase is where that labelling either survives contact with a renderer or is quietly
lost. Smoothness is the visual grammar of *I measured this* — so a `derived` curve is drawn
**stepped and hatched**, never smoothed, and an `exact` one is drawn as the step function it
actually is.

The failure mode is specific and it is not hypothetical: **a chart library's default is a smooth
spline**, and one `curveMonotoneX` turns an area-true/shape-false curve into a picture of
measurements nobody took.

---

## Global constraints

- **Absence is absence.** A block with nothing to say does not render. `reported_resources: false`
  is **one sentence**, not four empty charts — an empty curve claims a run that used nothing.
- **`bin_ms` is a suggestion the renderer has not yet taken**, and the sweep it sizes is exact at
  every breakpoint. **Bin for drawing only.** If a chart bins *first*, that exactness is gone and
  no test in phase 4 would notice.
- **The right edge means two different things.** `Series.open` is what separates *ends high
  because work is in flight* from *ends high because the run stopped badly*. The chart must say
  which.
- **A delta needs a finished run.** `-43% vs usual` under a live bar reads as *it was faster*,
  which is the opposite of what it means. A running row says `of ~38m`. `BoardSummary.by_pipeline`
  supplies the number; this rule is the page's to keep.
- **No verdict on a failure.** `137` arrives glossed as `SIGKILL` and the page adds nothing.
  *The OOM killer did it* is W3, and a panel that says it early is wrong often enough to be
  trusted when it is wrong.
- **`submitted_by` is a slot, not a filter** — settled by the operator. The layout keeps the
  space; there is no `who` control.
- **One easing curve and five named movements** (phase 0). A new animation is a sixth, and adding
  one is a decision rather than a detail.
- **The frontend gate** is `npx tsc -b && npx vitest run && npm run lint` from `frontend/`.
  `make check` still has to pass if anything Python moves.

---

## Pre-execution notes — checked against the code on 2026-08-30

**P5-1 — the screens already exist and this is a redraw, not a build.** `frontend/src/runs/`
holds `Board`, `Run`, `Overview`, `Tasks`, `TaskRow`, `Failure`, `Console`, `Graph`, `Menu`,
plus `useRunStream`, `elapsed`, `phases` and `units`, each with tests. **Read what a file does
before replacing it** — W2's `overview()` gives a declared process a row *before the run reaches
it*, which is a property that is easy to lose in a rewrite and expensive to rediscover.

**P5-2 — every endpoint this phase needs already ships**, and the generated client is current:
`readSeries`, `readOverview`, `readTasks` (now carrying `history`), `readResults`,
`readBoardSummary` (carrying `by_pipeline`), `readRunGraph`, `readRunEvents`. **No `make client`
is needed unless a task below changes a route.**

**P5-3 — the escalation panel's data is `TaskOut.history`,** which is new as of phase 4:
`{n, status, exit, signal, memory_bytes, peak_rss_bytes, realtime_ms}` per attempt, ordered.
`TaskOut.attempts` is still the count and did not change meaning, so nothing that reads it moved.

**P5-4 — the palette is already Observatory** (phase 2 migrated the whole product) and
`--running` exists as a token. `tokens.test.ts` greps for undefined custom properties, which is
the guard that caught five dead hover states; a new token means adding it to `tokens.css`, not
only using it.

**P5-5 — nothing in the builder or the runs screens has been driven in a browser.** The operator
has sequenced **one browser pass over all of it after this phase**, not per phase. Component
tests are not that pass and must not be reported as it.

---

## Task 1 — the envelope, drawn honestly

- [x] A chart over `GET /runs/{id}/series`. **Stepped, always** — no spline, no smoothing, and
      `exact` and `derived` curves visibly different rather than differently coloured.
- [x] **Hatch the derived curves** and label them `derived` in the legend, so the distinction
      survives a screenshot with no legend read.
- [x] `Series.open` marks the right edge as *still in flight*, so a high ending is not read as a
      bad ending.
- [x] Bin **for drawing only**, using `bin_ms`, never before the sweep.
- [x] `reported_resources: false` renders **one sentence** and no chart.
- [x] `test_a_derived_curve_is_never_drawn_smooth` — watch it fail with a spline.

## Task 2 — the failure escalation

- [ ] `Failure.tsx` reads `TaskOut.history`: asked beside touched, per attempt, so 36 → 48 → 72 GB
      is one glance.
- [ ] The `signal` gloss is shown **as given**. No cause, no advice, no "try increasing".
- [ ] A single-attempt failure still shows asked-beside-touched — it is the row's only place for
      the reservation.
- [ ] A guard that the panel names no cause. Watch it fail by adding one.

## Task 3 — the board

- [ ] `vs usual` from `by_pipeline`, and **only on a finished run** — a live row says `of ~38m`.
- [ ] A pipeline with no median shows no comparison rather than a zero.
- [ ] The `submitted_by` slot renders and does not filter.
- [ ] Absence rules hold: a lab with no runs is a shorter page, not an empty table.

## Task 4 — the run page's shape

- [ ] The redraw against the canvas, with `Overview`'s declared-row property intact.
- [ ] Dead code from the W2 layout removed rather than left beside the new one.

## Task 5 — write it down, then look at it

- [ ] Journal, `CLAUDE.md` pointer in the same commit, `notes/README.md` row, guard ledger with
      every revert **verified to land** *and* every guard watched failing against the specific
      defect — phase 4's finding, and the reason those are two checks.
- [ ] **Then the browser pass over everything Plan 4 built** — the builder included. It is owed,
      the operator sequenced it here, and every previous session that skipped it found defects
      later that green suites had waved through.

---

## Execution record

| Task | Carried out as written? | Deviation |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
