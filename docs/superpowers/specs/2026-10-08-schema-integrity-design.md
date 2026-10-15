# Schema integrity (14.7.8.3d Part E) — design

Issues: #289 (Part E), #279 (drift), #274 (constraints and keys). Parent: #284.

## What this gets us

Both databases say what the code already assumes, and CI notices the day the code and a
database stop agreeing:

- a `state`, `phase`, `kind`, `role` or `by` column holds only the values its enum declares;
- no Wiener event, task or intent points at a run that does not exist, or at another lab's;
- no gate points at a draft that does not exist;
- a table, column, type, nullability, index or constraint that differs between the models and
  the migrated database fails CI, not a deployed instance;
- **the tests that need Postgres run on every pull request.** Today each of them skips itself
  in CI because no database is reachable, so the guards written for #278 and #282 this week
  have never run there.

## Decisions (operator, 2026-10-08)

| Question | Chosen | Why |
|---|---|---|
| How drift is detected | **A Postgres service in CI; `alembic check` per database** | the standard tool, run against the real dialect; reviewed against current practice, an offline parser of our own was not |
| Where a CHECK's values come from | **The enum**, through SQLAlchemy's `Enum(native_enum=False, create_constraint=True)` | one authority, written by the library rather than by us |
| Columns with no enum today | **Each gets one** | every closed column is closed the same way |
| SQLite foreign keys in Wiener's tests | **On** | Wiener's behaviour tests stay on SQLite for now, and meet the refusals Postgres would make |
| Wiener keys | **Lab-scoped composite** (#274, already decided) | a cross-lab child row becomes impossible, not merely filtered |

## The problem, as measured

`alembic check` against freshly migrated throwaway databases (2026-10-08) reports exactly:

- **Mendel:** would remove `ix_forge_event_revision_id` and `ix_forge_message_revision_id`
  (they exist in the migrations, not in the models).
- **Wiener:** would set `run_task.labels` `NOT NULL` (nullable in the database, not in the
  model).

Nothing else differs, types included. `packages/mendel-api/tests/test_migrations.py` compares
only tables and columns, by regex over offline DDL; Wiener has no migration test. No
enum-valued column is constrained, and Wiener has no foreign key.

## 1. Postgres in CI, and in `make check` (#279)

### CI

`ci.yml`'s `check` job gains a `postgres:17-alpine` service (the image compose runs) (pinned by digest, as actions are by SHA)
with two databases, `mendel` and `wiener`. Before the tests, both chains are applied
(`alembic upgrade head` in each package). The test step gets:

- `MENDEL_DATABASE_URL` and `WIENER_TEST_DATABASE_URL` naming the service;
- `COMENI_REQUIRE_DB=1`.

### A test that needs Postgres and cannot reach it fails where Postgres is required

The files that need Postgres each carry their own `_database_is_reachable()`. They are replaced by one
helper in `mendel-api`'s test conftest (and Wiener's opt-in test uses the same rule): it returns
whether the database answers, **and raises when it does not and `COMENI_REQUIRE_DB` is set.**
Without the flag a laptop with no database still skips; with it, CI cannot go green by
skipping, which is the failure this whole section exists for.

### Locally

- `make test-db` starts the throwaway Postgres on `127.0.0.1:5442` (`mendel-test-db`), creates
  both databases and applies both chains. Idempotent.
- `make test` (and so `make check`) passes the throwaway's URLs on pytest's environment
  explicitly, so `make check` can never reach the dev database the `.env` names. That retires
  the gotcha in CLAUDE.md for every `make` path; a bare `uv run pytest` is still dangerous and
  the gotcha says so.
- `make check` without `make test-db` first: the database tests skip, as today, and the
  summary line counts them.

## 2. The drift test (#279)

### `alembic check`, per package

- `packages/mendel-api/tests/test_migrations.py` gains
  `test_the_models_match_the_migrated_database`: runs `alembic check` against the test database
  and asserts it exits 0, printing alembic's list of operations when it does not.
- `packages/wiener-api/tests/test_wiener_migrations.py` (new: a second `test_migrations.py`
  would collide under pytest's import mode) holds the same test, plus
  `test_the_chain_has_one_head` (Wiener gains it).

`alembic check` compares tables, columns, types, nullability, indexes, unique constraints,
foreign keys and, by name, check constraints. It does **not** compare server defaults (off by
default; not turned on here) or what is inside a check constraint.

Mendel's regex tests for tables and columns are superseded and removed; its specific
assertions stay (the partial indexes, no cascades, the data migrations, one head).

### What is inside a CHECK: `test_each_check_names_exactly_its_enum`

Per package, against the migrated database: for every `CheckConstraint` in the metadata, the
same-named constraint in `pg_constraint` lists exactly the values the model's does. This is the
half `alembic check` cannot see: an enum gaining a member keeps the constraint's name and
changes its values.

### The fix for today's drift

- Mendel: `index=True` on `ForgeEvent.revision_id` and `ForgeMessage.revision_id`. No
  migration: the indexes exist.
- Wiener: a migration making `run_task.labels` `NOT NULL`, after setting any null to `[]`.

**Watched failing:** the new tests, run before the fix, report exactly these three.

## 3. Enums for the columns that have none

| Column | Enum | Where |
|---|---|---|
| `gate_run.state` | new `GateState`: queued, running, passed, failed | `mendel_api/services/gates.py` |
| `pipeline_authoring_turn.role` | new `TurnRole`: person, assistant (`AuthoringRole` is person and *model*, door 5's payload, and stays apart) | `mendel_api/authoring/types.py` |
| `pipeline_authoring_proposal.kind` | new `ProposalKind`: step, goal, gap, pacing (today four module constants in `stages/`) | `mendel_api/authoring/types.py` |
| `run_intent.outcome` | `verbs.Outcome`, made a `StrEnum` (a plain class today) | `wiener_api/services/verbs.py` |
| `run_intent.prior_phase` | `RunPhase` | existing |
| `ai_invocation.agent` | new `Agent`: forge, builder | `mendel_forge/workflow.py`, beside `InvocationPurpose` and `InvocationState` |

Writers use the members, not string literals. No schema change: its own commit.

## 4. CHECK constraints (#274)

### How a column is written

```python
state: Mapped[str] = mapped_column(
    Enum(GateState, native_enum=False, create_constraint=True, length=16,
         values_callable=values, name="state"),
    index=True,
)
```

- `native_enum=False`: a `VARCHAR` with a `CHECK`, not a Postgres enum type (`GateRun.state`'s
  docstring argues why).
- `length=` keeps today's width; without it SQLAlchemy sizes the column to the longest member
  and `alembic check` reports a type change.
- `values_callable`: the stored value is the member's value, not its name.
- **SQLAlchemy also refuses an unknown value in Python, at flush**, before the database does.

**A naming convention on both `MetaData`s**: `ck_%(table_name)s_%(constraint_name)s`, and
`ix_%(column_0_label)s` (SQLAlchemy's default, so no index is renamed). Primary keys, unique
constraints and foreign keys keep the names Postgres gave them; a new one is named explicitly
in the model. `alembic check` stays clean after adding it.

### Mendel

| Column | Values |
|---|---|
| `gate_run.gate` | `comeni_core.artifact.gates.Gate` |
| `gate_run.state` | `GateState` |
| `forge_adaptation.state` | `AdaptationState` |
| `forge_revision.state` | `RevisionState` |
| `forge_event.kind` / `.from_state` | `mendel_forge.workflow.EventKind` / `AdaptationState`, nullable |
| `forge_message.role` / `.state` | `MessageRole` / `MessageState` |
| `ai_invocation.state` | `InvocationState` |
| `ai_invocation.agent` | `Agent` |
| `ai_invocation.(agent, purpose)` | one table-level `CheckConstraint`: forge with an `InvocationPurpose`, or builder with an `authoring_ai.Purpose`. Purpose is scoped by agent (`Purpose`'s docstring), so it stays a `String` |
| `pipeline_authoring_session.phase` / `.failed_from` | `mendel_authoring.types.Phase`, the second nullable |
| `pipeline_authoring_turn.role` / `.state` | §3 / `TurnState` |
| `pipeline_authoring_proposal.kind` / `.state` | §3 / `ProposalState` |

### Wiener

| Column | Values |
|---|---|
| `run.phase` | `wiener_core.state.RunPhase` |
| `run_event.kind` | `wiener_core.events.EventKind` |
| `run_task.status` | `wiener_core.events.TaskStatus` |
| `run_intent.kind` / `.because` | `IntentKind` / `wiener_core.policy.Reason` |
| `run_intent.prior_phase` / `.outcome` | `RunPhase` / `Outcome` |

**Left open on purpose:** `forge_source_snapshot.source` and `forge_catalogue_item.source` (a
source is an adapter somebody registers, not a state), and `run.executor` (opened by
configuration as `k8s` and `awsbatch` arrive).

**`pipeline_authoring_proposal.by` is not a vocabulary.** Its docstring says `person`, `model`
or `resolver`; the writers store an author's name or a model's id (the dev database holds
`unknown`, the author fallback). Constraining it would be wrong, and the person-or-model
distinction the docstring promises (A130) is not recorded. Filed as its own issue under Part F,
which makes decisions rows; this part corrects the docstring only.

### Before each migration

The plan queries every constrained column's distinct values on the dev database. A value
outside its enum is a defect found, not something to coerce: stop, file it, ask.

Measured 2026-10-08: every value in both dev databases is inside its enum. **Orphans exist:**
9 `gate_run` rows whose draft is gone and 2 `run` rows whose artifact is gone (test fixtures
that once truncated the dev database). The keys cannot be added over them; the plan stops and
asks before deleting them.

## 5. Wiener foreign keys, lab-scoped (#274)

- `run`: `UNIQUE (lab_id, id)`; `run_artifact`: `UNIQUE (lab_id, id)`.
- `run_event`, `run_task`, `run_intent`: `(lab_id, run_id)` → `run (lab_id, id)`.
- `run_intent`: `(lab_id, resulting_run_id)` → `run (lab_id, id)`; a null `resulting_run_id`
  skips the key (`MATCH SIMPLE`).
- `run`: `(lab_id, artifact_id)` → `run_artifact (lab_id, id)`.
- All `ON DELETE RESTRICT`. Nothing in Wiener deletes a row today.

The model docstrings that name the cross-lab leak cite the key.

Tests: Wiener's SQLite engine turns on `PRAGMA foreign_keys=ON`; `a_run` and the four other
places that build rows by hand create the artifact first; `test_seq_race.py` too.

## 6. `gate_run.draft_id` → `pipeline_draft` (#274)

`ON DELETE RESTRICT`; nothing deletes a draft. Fixtures that `TRUNCATE pipeline_draft` name
`gate_run` in the same statement (Postgres refuses to truncate a referenced table alone);
`test_gate_runs.py` creates real drafts.

## Guards, each watched failing

| Guard | Fails on |
|---|---|
| `test_the_models_match_the_migrated_database`, per package | today's three drifts; later, each model change before its migration |
| `test_each_check_names_exactly_its_enum`, per package | a member added to an enum with no migration |
| the require-DB helper raises under `COMENI_REQUIRE_DB` | the database unreachable in CI |
| Wiener: a run with a phase outside `RunPhase` is refused (SQLite) | the CHECK removed |
| Wiener: an event for a run that does not exist is refused (SQLite) | the FK removed |
| Wiener: an event whose `lab_id` differs from its run's is refused (SQLite) | the key made `run_id`-only |
| Mendel: a gate with an unknown state is refused at the database (raw SQL) | the CHECK removed |
| Mendel: a gate for a draft that does not exist is refused | the FK removed |

Each goes in `tests/fixtures/guard-ledger.md` with its revert.

## Commits

1. #279: Postgres in CI and `make test-db`, the one require-DB helper.
2. #279: the drift tests (watched failing), the two indexes, the `labels` migration.
3. #274: enums for the columns that had none.
4. #274: the naming convention and Mendel's CHECK constraints.
5. #274: Wiener's CHECK constraints.
6. #274: Wiener's lab-scoped foreign keys; SQLite enforcing them in tests.
7. #274: `gate_run.draft_id`.
8. Docs.

Each is applied to the dev databases (`make migrate`, `make wiener-migrate`) and the baked
containers rebuilt before the next. #279 closes on commit 2, #274 on commit 7, #289 then.

**The first CI run is the risk:** tests that have only ever run on a laptop run on a pull
request. Commit 1 is pushed, with the operator's go (nothing is pushed today), and its CI run
watched before anything is built on it; what fails there is filed, not patched in passing.

## Docs

CLAUDE.md: "CI has no Nextflow or Docker" becomes "CI has Postgres, no Nextflow or Docker";
the database gotcha points at `make test-db`. `tests/README.md`: where the require-DB helper is
and what the flag does.

## Out of scope

- Moving Wiener's behaviour tests from SQLite to Postgres.
- Comparing server defaults.
- Part F's new tables; they are written with this pattern from the start.
- Native Postgres enums.
