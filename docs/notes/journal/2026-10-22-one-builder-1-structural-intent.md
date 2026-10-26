# 2026-10-22 — One builder, plan 1: structural intent in the engine (A1)

[The plan](../../superpowers/plans/2026-10-22-one-builder-1-structural-intent.md), on
`one-builder-1-intent` (stacked on `redesign-walk-fixes`), from
[the design](../../superpowers/specs/2026-10-22-one-builder-design.md) (#395, with #391–#394).
Its *Deviations* section is the long form.

## Where things stand

- **The operator chose A, then A1:** every hand edit is kept through re-plans, read as intent in
  the goal rather than replayed as a patch. Plan 1 is the engine half; plans 2–5 (one builder and
  no fork; the chat as one stream and Describe; the hand-over; the pipeline file) come next, each
  planned when it starts, 3 and 5 with mockups first.
- **Built:** `Constraints.absent_roles`, `exclusions`, `sources`; the resolver honours them, with
  `MD0319`–`MD0321` for conflicts and `inert_intents` for intents that applied nowhere; three
  decision families with `intent_history`; `read_edit` turns a canvas edit into readings with the
  sentence that asks. `pipeline.yml` is version 8; turn blocks shape 3.
- `make check` and `make verify` green. Self-reviewed (no subagent); one fix, four minors in #398.
- **Not merged, not pushed.** The dev database needs `make migrate` before the next `make dev`.

## Traps

- **Stale `__pycache__` from the repository's old location** named files that no longer exist in
  tracebacks (`???`); imports were correct. Deleting the caches fixed the tracebacks.
- **Editing a migration already applied to the test database does nothing**: recreate the
  container (`docker rm -f mendel-test-db && make test-db`).
- **Alembic autogenerate** writes an enum's check constraint twice (the enum's own and an explicit
  one) and silently skips `use_alter` foreign keys in `create_table`; add those with `ALTER TABLE`,
  after `b4e8c2a6d917`.
