# 2026-10-06 — 14.7.8.2, the build plan

## Where things stand

- **`plan_of(blueprint, declared) → BuildPlan` exists, pure, in `mendel-authoring`**, and nothing
  calls it yet: part 3 (14.7.8.3) wires it into stage ④. `uv run pytest packages/mendel-authoring/tests -q`.
- For every step, in the blueprint's order: its card (does, why, makes, check, each marked
  `engine` or `curated`) and what it needs (nothing, a fact, a choice); then the wrap-up (what
  you'll get, what you need to run it, who decided what). `waits(plan, pacing)` picks the steps
  the walk stops at.
- **The resolver records which facts a rule lacked**: `ProducerDecision.unknown`, absent from
  `pipeline.yml` when empty. Over the real registry, the RNA-seq goal with no read length gives an
  aligner that needs `read_length`: `uv run pytest packages/mendel-api/tests/test_build_plan.py -q`.
- `Blueprint` (without `mode`) and `committed` live in `mendel_authoring.blueprint`; the shell
  re-exports them. Migration `e5f1a9c3b7d2` removes `"mode"` from stored blueprints.

## What changed

- `f7a82a08` the router writes `unknown` (#174's facts, typed).
- `ecfa516e` `Blueprint` and `committed` into the pure core; `mode` dropped; the migration.
- `4c61c333` `brief_of`, and the shell's `services/declared.py` adapter.
- `b3844b61` `need_of`. `a9354503` `wrap_up`. `345c6bb8` `plan_of`, `waits`, two goldens.
- `42ea963f` the real registry through the plan, watched failing (guard ledger).
- The spec's §4 was rewritten the day before, in the brainstorm (`50f2b378`), and the plan is
  `docs/superpowers/plans/2026-10-05-14.7.8.2-the-build-plan.md`.

## Decisions made, and why

- **No stages.** The walk follows the blueprint's order, which already puts every step after its
  inputs; the overview is a count. Every grouping tried either reordered the walk past a step's
  inputs or fragmented across parallel branches, and a grouping the canvas does not show is a
  second system for the person to infer.
- **`unknown` is typed in the record**, not parsed from the reason and not recomputed in the plan
  (which would have made `mendel-authoring` depend on the resolver and decided one thing twice).
- **`mode` removed by a migration, not a validator** that drops it on every load forever.
- **Narrow ports**: `Contracts` (which `Registry` already satisfies) and `Declared` (outputs, tool,
  family), so the pure tests use a dictionary.

## What is next

1. **14.7.8.3, stage ④**: the handlers of spec §5 call `plan_of` and `waits`; `Mode`, Build/Spawn,
   `alternatives` and `proposal` go; the Pacing setting is made live.
2. Then parts 4 and 5, 14.7.9 (#210), 14.7.10.

## Open questions

- The `comeni-core` version bump for `ProducerDecision.unknown`, judged at release.
- **A tier-4 setting whose only candidate is `null`** (STAR's `seq_platform` in the shipped
  registry) is a choice by the spec's rule, but a card offering only "nothing" is a poor question.
  For the walk (#210).

## Traps

- **This machine's baseline `make check` is red** for reasons outside this work: no Postgres on
  :5432 (91 errors), the truncated-gzip inspection cases, and `now.md` citing `.run/registry`.
  `make verify`'s slow tests need `nextflow`, which is not installed here; Docker's socket is
  root-only, so the throwaway Postgres ran on rootless `podman`.
- The goldens are written with `COMENI_WRITE_GOLDEN=1` and must be read before committing.
- `make check` stops at lint before the tests: a lint error makes a diff against the baseline
  look clean.
