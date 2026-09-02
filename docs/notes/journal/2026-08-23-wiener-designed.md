# Wiener, designed — and nothing built

**2026-08-23**, branch `mendel-wiener-boundary`, in the worktree
`.worktrees/plan-3e-builder`. **Seven commits, unpushed.** `make check` green (1510),
`make verify` green earlier in the day.

> ## READ THIS FIRST IF YOU ARE A FRESH SESSION
>
> **The work is not on `main`.** It is on `mendel-wiener-boundary`, checked out at
> `.worktrees/plan-3e-builder`. The main checkout is on `main` and has none of it.
>
> ```bash
> cd .worktrees/plan-3e-builder && git log --oneline -7
> ```
>
> **Your shell's working directory resets between tool calls.** Two files landed in the wrong
> checkout today because of it. Use absolute paths, or `cd` inside every compound command.
>
> **Nothing here is code.** Wiener has zero lines. Everything below is a design document, a
> plan, four artboards and a test fixture. `packages/wiener-core` does not exist yet — Task 1
> creates it.

---

## What happened

The operator asked to move toward running pipelines, and the day went: **audit → spec → plan**,
with no implementation on purpose.

1. **An audit of yesterday's boundary work** (`093d32f`) found the `execution-boundary.md`
   document had gone stale **inside a day** — §6 still said "no executor block at all, that is
   the gap" on the same branch that closed it. Two guards were hardened, and reverting one found
   it **half-inert**: `test_the_registry_is_not_in_the_database` fires when a `run` table is
   added to `mendel-api` — making it the only structural guard on `execution-boundary.md` §8 —
   but it printed `unexpected: {…}`, whose obvious repair is to add `"run"` to the set.
2. **[`docs/design/wiener.md`](../../design/wiener.md)** — 1049 lines, fourteen decisions.
   Wiener was treated as unspecced; every prior sentence about it predates Mendel.
3. **[`notes/plans/2026-08-23-wiener-w1-phases-0-2.md`](../plans/2026-08-23-wiener-w1-phases-0-2.md)**
   — 85 steps, three operator checkpoints, phases 0–2 only.
4. **A design canvas**, four artboards plus four rejected direction sketches:
   <https://claude.ai/code/artifact/6518257f-b5e3-4f13-808d-abab64a60f6b>
   (private to the operator's account; the working files are in
   [`docs/design/wiener-mockups/`](../../design/wiener-mockups/) and rebuild with
   `python3 build.py`).

---

## The decisions that carry

Read §1 of the spec for all fourteen. The four that shape everything else:

- **Run state arrives as typed `nf-weblog` events.** The "logging rework" the brief anticipated
  **does not exist** — the CLI flag is deprecated, the feature moved to config, and it is already
  an official plugin.
- **`wiener-core` is PURE and joins invariant 1.** Supervision splits into *deciding* and
  *doing*; only the doing touches the world. This pays off in a place nobody planned: the OTel
  SDK is a network client, so the guard makes it structurally impossible to put the exporter on
  the wrong side.
- **OpenTelemetry is the lens, never the record.** Sampling and expiry are what make a tracing
  store affordable and are exactly what run state cannot tolerate.
- **The AI is beside the loop, not in it** — so *same events in → same run state, same decisions*
  stays literally true, and a three-day run replays in milliseconds in a test.

---

## What was found by running things rather than reading about them

**A real capture corrected the design five times.**
[`tests/fixtures/weblog/failing-run.jsonl`](../../../tests/fixtures/weblog/failing-run.jsonl) is
thirteen events from an actual Nextflow 25.10.4 run, committed as the replay corpus.

- **`error` carries nothing** — no trace, no message. The diagnosis lives in the *failed*
  `process_completed`. A design that waits for `error` learns nothing.
- **`completed` fired twice**, byte-identical → the fold must be idempotent.
- **`error` arrived *after* `completed`** → terminality is a set, not a flag.
- **"Structured fields only" is not a privacy guarantee.** `trace.script` holds filenames,
  `trace.workdir` a path, and `started.metadata.parameters` carries the samplesheet path in the
  **first event of every run**. This was stated as a guarantee in the first draft and is false.
- **The resource metrics are opt-in.** With `trace.enabled = true` the payload gains **fifteen**
  more fields (`%cpu`, `peak_rss`, `read_bytes`…). Without it the dashboard is empty for a reason
  nothing on screen would explain.

---

## What is next, in order

1. **Execute the plan** with `superpowers:executing-plans`, task by task, **not**
   `subagent-driven-development` — `CLAUDE.md` forbids farming out implementation.
   Start at Task 1. Tick each `- [ ]` as it completes and record deviations in the plan's
   execution table.
2. **Checkpoint 1** after Task 4: a library and a fixture, nothing runs.
3. **Checkpoint 2** after Task 8 — **the one that matters**, because everything before it is
   testable without Nextflow and it is not.
4. **Checkpoint 3** after Task 12: twenty minutes of actual use, and a tab closed for two minutes
   then reopened.

**Before phase 3:** research whether OTel's batch/job semantic conventions genuinely fit, rather
than inventing `wiener.*` attributes. The operator's answer, and the last question still open.

---

## What a fresh reader gets wrong

- **"There is code to look at."** There is not. `packages/wiener-core` does not exist; Task 1
  creates it. Every code block in the plan is a proposal.
- **"The spec was reviewed."** It was not. The operator answered seven design questions and read
  summaries; nobody has read the 1049 lines end to end. §12.1 and the new tenancy guard are the
  two places most likely to be wrong.
- **"Authentication is handled."** It is not, and that is a *named gap* rather than an oversight:
  §12.1 makes it a W1 requirement, `submitted_by` is attribution only, and phases 0–2 assume one
  operator on a laptop. The first deployment anyone else can reach needs the check first.
- **"The tenancy guard works."** It passes **vacuously** at Task 5 — there are no queries yet to
  scan. It earns its ledger row at Task 6. A query-scanning AST guard is easy to write so that it
  passes for the wrong reason; this is the thing most worth a second pair of eyes.
- **"Depth is adopted."** The visual direction was chosen and built **in the mockups only**. The
  four tokens (`--e1 --e2 --e3 --well`) are **not** in `frontend/src/tokens.css`; adopting them is
  four lines plus a `docs/design/dashboard.md` §2 edit, because that file is authoritative over it.
- **"A gate is a run."** It is not — `execution-boundary.md` §3, and the test between them is one
  question: *does it take a samplesheet?* `gate_run` lives in `mendel-api` and has a column guard
  saying so.
