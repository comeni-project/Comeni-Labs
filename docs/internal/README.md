# Internal working notes

**These are not documentation.** They are kept for provenance — so that a decision can be
traced to the moment it was made — and they are not maintained against the code.

If you want to know how Mendel works, read [`ARCHITECTURE.md`](../../ARCHITECTURE.md) and
[`docs/`](../README.md). If you want to know *why*, read [`docs/design/`](../design/).

## plans/

Step-by-step implementation plans, written before the work and executed task by task.
They contain code that was proposed, not necessarily code that shipped — several steps in
every plan were corrected during execution, and the corrections are recorded in the commit
messages rather than back-ported here.

| Plan | Status |
|---|---|
| `2026-08-02-mendel-deterministic-spine.md` | complete |
| `2026-08-03-measurements-rules-and-profiling.md` | complete |
| `2026-08-02-mendel-ai-and-forge.md` | not started — predates the types it references |
| `2026-08-02-mendel-api-and-dashboard.md` | not started — predates the types it references |

The last two were written ahead of the code they build on, and say things that are no
longer true. That is the reason this directory is labelled the way it is.

## audits/

`2026-08-03-plan-1-audit.md` — an independent review that defeated all three
test-enforced invariants, using four lines of Python for one of them. All four defects are
closed, and the guards in `tests/` are the shape they are because of it. Worth reading
before trusting any guard in this repository.
