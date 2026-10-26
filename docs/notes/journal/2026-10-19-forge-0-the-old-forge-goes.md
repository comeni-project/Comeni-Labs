# 2026-10-19 — Forge MVP part 0: the old forge goes

[The plan](../../superpowers/plans/2026-10-19-forge-0-remove-old.md), on `forge-0-remove-old`
(#361). Its *Deviations* section is the long form.

## Where things stand

- `mendel-forge`, the forge routes, worker jobs and eight tables are deleted (migration
  `89d3b4e5ab6f`, no downgrade); the frontend has no `/forge` pages and no *Registry* tab.
- The documentation no longer describes the old forge as current; pages that need the future
  forge point at `docs/superpowers/specs/2026-10-19-forge-mvp-design.md`.
- **Not merged.** Part 1 (#362) lands on this branch first.

## Traps

- The dev stack was stopped with `make dev-down` (volumes kept). Its database still has the old
  tables until `make migrate`; rebuild the baked `ai-worker` before the next `make dev`.
- Diagnostic numbering: `MF0001`–`MF0499` are retired; the new forge allocates from `MF0500`.
