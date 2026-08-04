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
| 4 | `2026-08-04-publication-and-the-registry-split.md` | Plan 2.5 — **next.** Written, unimplemented |
| 5 | `2026-08-02-mendel-ai-and-forge.md` | Plan 2 — predates the types it references |
| 6 | `2026-08-02-mendel-api-and-dashboard.md` | Plan 3 — predates the types it references |

**Plan 1.5 comes before Plan 2.5** because publishing a bundle built on an unverified spine
would push a wrong pipeline through the door with no undo.

Plans 2 and 3 were written ahead of the code they build on, and say things that are no longer
true. That is the reason this directory is labelled the way it is.

## audits/

`2026-08-03-plan-1-audit.md` — an independent review that defeated all three
test-enforced invariants, using four lines of Python for one of them. All four defects are
closed, and the guards in `tests/` are the shape they are because of it. Worth reading
before trusting any guard in this repository.
