# Build API test index

These tests cover the HTTP shell, jobs, settings and persistence around pipeline construction.
Pure conversation and routing contracts are tested in `mendel-authoring` and `mendel-resolver`.
Use the [repository test index](../../../tests/README.md) for environment setup.

## Find a behavior

| Group | Responsibility | Dependencies |
|---|---|---|
| [authoring/](authoring/README.md) | Session commands, handlers, HTTP conversation, build plans, preview and canvas. | Fake model/queue; persistence cases require Postgres. |
| [authoring/decisions/](authoring/decisions/README.md) | Facts, grounded changes, suggestions, corrections, revisions, forks and deletion. | Most require Postgres and authored session scenarios. |
| [authoring/samples/](authoring/samples/README.md) | Upload admission, inspection, characterisation, gaps and protection rules. | Controlled inspection/model responses; session cases require Postgres. |
| [settings/](settings/README.md) | Settings actions, reports, model purposes, codecs and persistence. | Memory store by default; persistent-store cases use `real_settings`. |
| [pipelines/](pipelines/README.md) | Drafts, saved bundles, build services and gate services. | Temporary artifacts; route/persistence cases require Postgres; subprocesses are stubbed where appropriate. |
| [infrastructure/](infrastructure/README.md) | Transactions, migrations, identity, shapes, health, OpenAPI and worker scheduling. | Mix of pure checks and PostgreSQL-specific behavior. |

Run `uv run pytest packages/mendel-api/tests/<group> -q` from the repository root.
For one behavior, append `::test_name` to its test-file path. Use `make test-db` first and
`COMENI_REQUIRE_DB=1` when database cases must run rather than skip.

## Fixture scope

The pytest startup plugin in `tests/support/pytest_bootstrap.py` chooses an isolated database
before importing application settings. It is loaded through `pyproject.toml` for every test path.
Set `MENDEL_TEST_DATABASE_URL` to use another disposable Mendel database. Normal application
URLs are not inherited. Database fixtures truncate shared tables; the suite runs serially.
Parallel database workers need separately isolated databases or schemas.

Package `conftest.py` owns explicit database cleanup fixtures and the empty memory settings store.
The settings store is isolated for each test; `real_settings` opts into the real settings table.
`authoring_case` is an explicitly requested, database-backed scenario used by canvas, shape and
delete tests. It is not an autouse fixture.

`authoring/conftest.py` owns the authoring-only defaults: one-step goal extraction and together
pacing. Tests of family selection or pacing override those settings explicitly. Settings,
pipeline and infrastructure tests retain the normal application defaults.

## Shared scenarios

Tests import reusable setup from `mendel_api_tests`, never from another collected test module.
The namespace is test support and must not be imported by production code.

| Helper | Responsibility |
|---|---|
| `database.py` | Reachability policy, required-DB failure, test-owned table truncation and disposable migration databases with optional separate test administration. |
| `session_setup.py` | Explicit phase/decision seeding for tests; bypasses normal interaction when preparing a starting state. |
| `canvas_scenarios.py` | Recorded authored sessions, `authoring_case` and query capture. |
| `building.py` | Confirmed goals, resolution, step answers and resulting drafts. |
| `gathering.py` | Waiting questions, replies and gathered facts. |
| `http.py` | HTTP clients, fake queues/model responses and conversation request helpers. |
| `samples.py` | Sample observations, data questions and inspection-result builders. |
| `characterisation.py` | Bounded model-reading scenarios and recorded responses. |
| `changes.py` | Versioned change commands and version reads. |
| `corrections.py` | Explicit correction commands. |
| `disagreements.py` | Conflicting observations and disagreement choices. |
| `manual_forks.py` | Manual draft/fork scenarios. |
| `step_review.py` | Step cards, pacing, compatible tools and wrap-up scenarios. |

Helper fixtures keep scenario-specific cleanup where their starting states differ. Test files
contain their behavior checks and small local setup. Repository paths come from `support.paths`;
shape goldens stay in `golden/shapes/` regardless of where their tests are grouped.
