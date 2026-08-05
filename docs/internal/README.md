# Internal working notes

**These are not documentation.** They are kept for provenance — so that a decision can be
traced to the moment it was made — and they are not maintained against the code.

If you want to know how Mendel works, read [`ARCHITECTURE.md`](../../ARCHITECTURE.md) and
[`docs/`](../README.md). If you want to know *why*, read [`docs/design/`](../design/).

## journal/

**Start here if you are picking the project up.** One append-only entry per working
session: where things stand, what changed, what was decided and rejected, what is next, and
what a fresh reader gets wrong. Newest first — see [journal/README.md](journal/README.md).

## plans/

Step-by-step implementation plans, written before the work and executed task by task.
They contain code that was proposed, not necessarily code that shipped — several steps in
every plan were corrected during execution, and the corrections are recorded in the commit
messages rather than back-ported here.

**Filenames are a log, not an order** — two plans share the date `2026-08-04`. This table is
the order.

| Order | Plan | Status |
|---|---|---|
| 1 | `2026-08-02-mendel-deterministic-spine.md` | Plan 1 — complete |
| 2 | `2026-08-03-measurements-rules-and-profiling.md` | complete |
| 3 | `2026-08-04-the-runnable-spine.md` | Plan 1.5 — **complete** |
| 4 | `2026-08-05-conformance-checking.md` | Plan 1.6 — **complete** |
| 5 | `2026-08-04-publication-and-the-registry-split.md` | Plan 1.7 — **complete** |
| 6 | `2026-08-02-mendel-ai-and-forge.md` | **Plan 2 — next.** Predates the types it references; rewrite before executing |
| 7 | `2026-08-02-mendel-api-and-dashboard.md` | Plan 3 — predates the types it references |

### Why that order

**Plans 1.5 and 1.6 come before Plan 1.7** because publishing a bundle built on an unverified
spine would push a wrong pipeline through the door with no undo. That earned itself twice: 1.5
found a spine that counted with the wrong strandedness, and 1.6 found three contracts naming
output channels that do not exist.

**Plan 1.7 comes before Plan 2** for two reasons, neither of which was written down until
2026-08-05 — the ordering was asserted by an index and believed for a day.

- *Plan 2 is stale and Plan 1.7 is not.* Plan 2 was written 2026-08-02, before most of the
  types it references existed; the table above says so. Plan 1.7 was written 2026-08-04
  against real code. Every plan in this repository has needed correction during execution —
  six steps in the measurements plan, five in 1.5, six in 1.6 — and the fresher plan is the
  cheaper one to run.
- *Plan 1.7 is pure and Plan 2 is not.* Lockfiles, replay and publish are `comeni-core` and
  `mendel-resolver` work with no new dependency. Plan 2 stands up `mendel-ai`, LiteLLM and
  model access, and opens three of the four egress doors at once. Growing the deterministic
  core while everything is still testable offline is the cheaper sequence.

**The argument against, recorded because it is real:** nothing in Plan 1.7 moves the v1
success criterion, whose one unmet clause is the plain-language prompt — that is Plan 2 Task
3. And `mendel publish` is the door with no undo, built for pipelines drawn from a registry
the forge has not filled yet. If v1 becomes the priority, this order is the thing to revisit.

**Known overlap, not yet resolved:** Plan 1.7 Task 5 builds `replay.py` in `mendel-resolver`
and Plan 2 Task 4 builds `ReplayingResolver` in `mendel-ai`. They are not the same — one
replays recorded decisions when a curated bundle is edited, the other caches model answers
across runs — but they are close enough that building both without noticing gives two ways to
do one thing. Whichever runs second should absorb the first rather than duplicate it.

### On the numbering

`1.5`, `1.6` and `1.7` are the deterministic core: no AI, no network, no new dependency.
Plan 2 is AI and the forge; Plan 3 is the API and dashboard. **Plan 1.7 was called "Plan 2.5"
until 2026-08-05** — that number recorded when it was written rather than when it runs, and
was read as the latter by everyone including its author. Journal entries dated on or before
2026-08-05 still say "Plan 2.5"; they are append-only and were correct on their date.

Plans 2 and 3 were written ahead of the code they build on, and say things that are no longer
true. That is the reason this directory is labelled the way it is.

## audits/

`2026-08-03-plan-1-audit.md` — an independent review that defeated all three
test-enforced invariants, using four lines of Python for one of them. All four defects are
closed, and the guards in `tests/` are the shape they are because of it. Worth reading
before trusting any guard in this repository.

`2026-08-06-plan-1-to-1.7-audit.md` — the same exercise over everything through Plan 1.7.
Thirteen findings, all reproduced by execution, **none fixed yet**. All three guards fell again,
by shapes they were never written against rather than by shapes they missed. Two findings are
in mechanisms Plan 1.7 shipped and are the reason to read it before starting Plan 2: a resolved
routing decision never reaches the pipeline (A8), and a layer digest does not cover the bytes
the registry loads (A9).
