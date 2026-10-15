# 2026-10-08 — 14.7.8.3d Part E, schema integrity

## Where things stand

- **Part E (#289) is done**: #279 and #274 closed. Both databases say what the code assumed:
  every closed column holds only its enum's values, Wiener's children belong to their run in
  their lab, a gate belongs to its draft, and the models and migrations are compared by
  `alembic check` against a real Postgres.
- **The database tests run in CI now.** CI has a Postgres service and `COMENI_REQUIRE_DB=1`, so
  an unreachable database fails the run instead of skipping it. Locally, `make test-db` starts
  the throwaway on :5442 and `make test`/`make check` use it, never `.env`'s database.
- **CI is red on four older tests** (#296), not on anything in Part E; they had failed since at
  least 2026-10-03 unseen, because nothing runs CI on this branch without a pull request (the
  first run was dispatched by hand). The deferred review minors are #297; `proposal.by` holding
  a name rather than person or model is #295, under Part F.
- **Next: Part F** (#290), decisions as rows: brainstorm, spec, plan. Then G, H, I.

## What changed

- `d780fd3c` the test database in CI and `make`; one reachability helper per API package.
- `fc0aaa5b` #279: two forge indexes declared, `run_task.labels` NOT NULL, `alembic check` per database.
- `090af22e` enums for the columns that had none (`GateState`, `TurnRole`, `ProposalKind`, `Agent`, `Outcome`).
- `bed6c7a6`, `91294f0b` CHECK constraints, Mendel then Wiener.
- `91acaa1f` Wiener's lab-scoped foreign keys; `1d2fd5b8` `gate_run.draft_id`.
- `6a3453b9` from the final review: an unknown `phase`/`status` filter is a 422, not a 500, and
  the CHECK test compares ordered values (a set merged the two agents' purposes).
- Migrations: Mendel `e2a6c8f4b157`, `f8b4d2c6a913`; Wiener `f4c8a2e6b913`, `a7d3f9b2c418`,
  `b9e5d1a7c320`. Applied to the dev databases after deleting their orphans (operator): two demo
  runs of 30 August and nine gates whose drafts were gone.

## Decisions made, and why

- **Postgres in CI rather than our own DDL parser** (operator, after a review of current
  practice): `alembic check` is the standard tool, and it also ends the skipping.
- **CHECKs come from SQLAlchemy's `Enum(native_enum=False, create_constraint=True)`**, built from
  the enum; migrations spell the values out. `length=` keeps each column's width.
- **Lab-scoped composite keys** in Wiener: a cross-lab child row cannot exist.

## Traps

- **`alembic check` does not see a CHECK an `Enum` type creates**, and compares CHECKs by name
  only. Each `env.py` hides the Enum-made ones; `test_each_check_names_exactly_its_enum` compares
  name and ordered values against `pg_constraint`.
- **Migration constraint names go through `op.f()`**, or the `ck` naming convention prefixes
  them twice.
- **An `Enum` column refuses an unknown value even in a WHERE.** A filter on one takes the enum.
- **A guard that fails by inserting junk leaves it behind** in the throwaway; the next migration
  then refuses. `docker rm -f mendel-test-db && make test-db` starts clean.
- **This shell does not split `$VAR` into words** (`env $T cmd` passed one argument): write the
  assignments out.
- Eight journal entries now wait for compaction (`compaction.md`).
