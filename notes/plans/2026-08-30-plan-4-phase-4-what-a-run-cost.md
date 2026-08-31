# Plan 4 Phase 4 — what a run cost, and which of those numbers is honest

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [ ]` as it completes; leave one **unticked** if
> it was not done, and record every deviation in the execution table.

**Goal:** the projections the runs screens need — attempt windows, per-attempt resources, and a
`series()` that draws only what the record can honestly support.

**Architecture:** one pure function in `wiener-core` and one endpoint over the **projection**, not
over the event stream. `run_task.attempts` already holds every attempt's window and its fifteen
resource fields; nothing new needs to be recorded, only read.

**Tech Stack:** Python 3.12 · Pydantic · FastAPI · SQLAlchemy.

**Design source:** the canvas, page 5 — `rn-series`, `rn-timeline`, `rn-absence`, `rn-blocked`,
`rn-settled`. The Runs artboards are generated from **one task list** by the same boundary sweep
this phase implements: `.design/runs_boards.py` is a reference implementation that already found
three defects by being rendered. Read it before writing the sweep.

**Depends on:** phases 0–3b. Nothing in the browser depends on this yet; phase 5 draws it.

---

## The rule this phase exists to enforce

**A scalar becomes an honest curve or it does not, and which depends on how it distributes over
its window.** `rn-series`, and it has three branches — not a blanket:

1. **A RESERVATION is constant over the window → the series is EXACT.** `cpus` and `memory_bytes`
   are what Nextflow held for the whole task lifetime, so Σ over live tasks is the true
   reservation curve, not synthetic at all. Same for anything **countable**: tasks in flight,
   queue depth from `submit → start`, completions per minute.
2. **A TOTAL divides over the window → area-true, shape-false.** `pct_cpu` is a mean and
   `read_bytes` a total. Spreading uniformly preserves the integral and **invents the shape**.
   Drawable, **stepped**, labelled derived — smoothness is the visual grammar of *I measured
   this*.
3. **A PEAK does not distribute at all → it is a bound, not a series.** `peak_rss_bytes` is the
   highest value a task ever touched; summing peaks across live tasks describes an instant that
   never happened. **There is no memory-over-time chart at any fidelity.** This is the tempting
   one, and drawing it would be exactly the failure the product claim exists to prevent.

---

## Global constraints

- **`wiener-core` is PURE and has NO CLOCK.** Invariant 1, and a separate scan holds
  `datetime.now` out of it. §6.1's claim — same events in, same decisions out — dies the first
  week a clock is read inside the fold, and a series is the most tempting place to read one:
  *"how long has this been running"* is a question about now.
- **A running task does not release its reservation at `now`.** Closing its interval at the clock
  made the *asked* curve fall to zero at the right edge — the exact artefact the *used* curve is
  hatched to avoid, arriving on the half that is supposed to be exact. Found by rendering it.
- **Build from BOUNDARIES**: `+delta` at start, `−delta` at end, sort, prefix-sum. Exact at every
  breakpoint, no bin artefacts, and 5,000 tasks is 10,000 events. **Bin only to render**, and size
  the bin off run duration or a 40-second stub run collapses to one point.
- **Not a fold in the request** — `rn-blocked`, and A191's rule that a board is a query.
  `projection.state_of` replays every event; `run_task.attempts` is a column. The endpoint reads
  the column.
- **Absent is not zero.** A run launched without `trace.enabled` has no resource fields at all —
  `ProcessRow.reported_resources` exists for exactly this — and gets one sentence, not four empty
  charts.
- **`make check` is the gate.** No task here touches the six files needing `make verify`.

---

## Pre-execution notes — checked against the code on 2026-08-30

**P4-1 — everything the sweep needs is already recorded, and none of it is projected.**
`Attempt` carries `start_ms`, `complete_ms`, `duration_ms`, `realtime_ms`, `cpus`, `pct_cpu`,
`memory_bytes`, `peak_rss_bytes`, `rchar`, `wchar`, `read_bytes`, `write_bytes` — A184 made the
fold keep them. `RunTask.attempts` is a JSON column holding the list. So this phase adds no
recording and no migration.

**P4-2 — `series` must NOT take a `RunState`, and that diverges from `overview()` deliberately.**
`overview(state, declared)` and `spans(state, …)` both take the folded state, and `rn-series` says
`series(state) -> Series` *belongs in `wiener-core`: pure, no clock, the same shape as `overview()`
and `spans()`*. But `rn-blocked` says this one must not be a fold in the request — and taking a
`RunState` forces the caller to have folded one. It takes the **attempts** instead, which is the
minimum it needs, and the endpoint reads them from `run_task`.

**P4-3 — `TaskState` cannot be rebuilt from `run_task`.** It needs `first_seen_ms`, which is not a
column. Another reason the signature takes attempts rather than tasks: the projection can supply
attempts and cannot supply a `TaskState`.

**P4-4 — `durations_by_pipeline` already landed in phase 2**, so the `GROUP BY artifact_id` the
canvas lists as blocking is done. `submitted_by` is also settled: the slot ships, the filter does
not.

---

## Task 1 — `series()` in `wiener-core`

- [x] Add `wiener_core/series.py`: `series(attempts, *, bins) -> Series`. **Pure, no clock**, and
      the module joins the `datetime.now` scan's coverage.
- [x] **The boundary sweep**: `+delta` at `start_ms`, `−delta` at `complete_ms`, sort, prefix-sum.
      Exact at every breakpoint. Bin only to render.
- [x] **Three kinds, and the type says which.** `Curve.kind` is `exact` or `derived`, and there is
      **no third value for a peak** — a peak is not a curve and the type must not offer somewhere
      to put one.
- [x] `cpus` and `memory_bytes` reserved → **exact**. Tasks in flight → **exact**.
- [x] `read_bytes` / `write_bytes` → **derived**, spread uniformly, area-true and shape-false.
- [x] **A running attempt keeps its reservation to the end of the window**, never to a clock this
      function cannot read. `complete_ms is None` means still held.
- [x] **No `peak_rss_bytes` curve, and a test that says so by name.** The absence is the design.
- [x] `test_a_reservation_is_exact_at_every_breakpoint` — watch it fail by binning first.
- [x] `test_a_running_task_does_not_release_at_the_edge` — watch it fail by closing at `max`.
- [x] `test_there_is_no_memory_over_time_curve` — watch it fail by adding one.

---

## Task 2 — the attempt windows, projected

- [x] `GET /api/runs/{id}/series` over `run_task.attempts`, **never** `state_of`.
- [x] Bin size from run duration, so a 40-second stub run does not collapse to one point.
- [x] **A run with no resource fields answers with a sentence, not empty curves.** Follow
      `ProcessRow.reported_resources`.
- [x] `test_the_series_never_folds_the_event_stream` — patch `state_of` to raise. Watch it fail.
- [x] `make client`.

---

## Task 3 — per-attempt resources, for the failure panel

- [x] `TaskOut.attempts` is a **count**, and the escalation panel needs the history:
      `memory_bytes` and `peak_rss_bytes` per attempt, which are in the JSON and not exposed.
- [x] Expose them on the task row so a reader can see 36 → 48 → 72 GB. **A deterministic panel
      when it comes, not an AI one.**
- [x] Do not compute a verdict. `137` is glossed as SIGKILL and nothing more — *the OOM killer did
      it* is an inference, and §18.1 says nothing explains a failure until W3.

---

## Task 4 — write it down

- [x] Journal, `CLAUDE.md` pointer in the same commit, `notes/README.md` row, and the guard ledger
      with every revert **verified to land**.

---

## Execution record

| Task | Carried out as written? | Deviation |
|---|---|---|
| 1 | Yes, with one signature change | The plan's `series(attempts, *, bins)` ships as `series(attempts)`. **The sweep does not bin** — binning is the renderer's job and the plan says so two bullets later ("Bin only to render"), so a `bins` argument would have been a parameter the function was forbidden to use. The suggestion travels as `Series.bin_ms`, derived from the run's own recorded span. |
| 2 | Yes | `bin_ms` lands on the pure model rather than being computed in the route, because it is derived from recorded boundaries and nothing else — putting it in the route would have made a pure derivation impure for no gain. **A run with no resource fields answers with `reported_resources: false` and no empty curves**, following `ProcessRow`'s precedent as instructed; the *sentence* is the page's and belongs to phase 5. |
| 3 | Yes, plus one module the plan implied | The gloss needed somewhere to live, so `wiener_core/signals.py` exists: `signal_of(137) == "SIGKILL"`, the 128+n convention and nothing more, held by a scan that names failure-cause words. `TaskOut.attempts` keeps its meaning as a count and the history arrives as a new `history` field, so no existing consumer moved. |
| 4 | Yes | The journal is a **section appended to `2026-08-30-the-overview.md`** rather than a new file: same day, same branch, same session, and a second entry for one day is what `notes/journal/README.md` has to disambiguate by hand. Its title and "where things stand" were updated in the same edit. |
