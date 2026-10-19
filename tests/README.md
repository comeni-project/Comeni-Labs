# Test index

Use this page to find the behavior you want to check, identify its dependencies and run the
appropriate suite. Package tests stay beside their implementation; repository tests cover
shared boundaries, declared registry data and interactions across packages.

## Run tests

Run commands from the repository root. `uv sync` installs Python test dependencies.

| Check | Command | Requirements |
|---|---|---|
| Regular Python suite | `make test` | Registry submodule; database tests need the isolated server. |
| Prepare test databases | `make test-db` | Docker; starts Postgres on localhost:5442 and migrates both databases. |
| Require database coverage | `COMENI_REQUIRE_DB=1 make test` | Both test databases reachable and migrated. |
| Repository checks | `make check` | Lint, regular tests, generated types and documentation checks. |
| Invariant guards | `make guards` | Focused Python boundary tests. |
| Real workflow execution | `make slow` | Docker, Nextflow and Java; may download tool images. |
| Full verification | `make verify` | Regular checks, slow execution tests and guards. |
| Frontend components | `cd frontend && npx vitest run` | Frontend npm dependencies; in-process DOM environment. |
| Frontend types | `cd frontend && npx tsc -b` | Frontend npm dependencies. |

Ordinary pytest runs exclude `slow` tests. Python collection includes `tests/`, `packages/`
and `registry/inspectors/`; frontend tests run separately through Vitest. To inspect collection
without executing test bodies, use `uv run pytest --collect-only -q`.

### Database isolation

The startup plugin `tests/support/pytest_bootstrap.py`, loaded through `pyproject.toml`,
selects test database URLs before application settings are imported, including package-only runs.
Inherited `MENDEL_DATABASE_URL` and `WIENER_DATABASE_URL` are replaced with isolated test
configuration. To use another disposable server, set `MENDEL_TEST_DATABASE_URL` and
`WIENER_TEST_DATABASE_URL`. `make test` supplies the URLs prepared by `make test-db`.

The two legacy-schema migration tests create disposable databases. When application test roles
are restricted, supply `MENDEL_TEST_ADMIN_DATABASE_URL` for administration on the same isolated
server. That account creates/drops test databases owned by the application role; migrations
and data checks still use the application connection. The default local test server can use
its existing administrative test account.

Fixtures truncate tables. Explicit test URLs must refer to databases whose contents can be
discarded. Database tests may skip when their server is unavailable; `COMENI_REQUIRE_DB=1`
makes an unavailable required database fail instead. Some execution tests also skip when
Docker or Nextflow is unavailable; read their prerequisite checks when interpreting results.

## Repository behavior and boundaries

| Behavior | Location | Focus |
|---|---|---|
| Saved pipelines | [artifact/](artifact/README.md) | Serialization, provenance, compatibility, validation, emission and publication. |
| Generated workflows | [emit/](emit/README.md) | Channels, joins, fan-out, samplesheets and real execution. |
| Registry data | [registry/](registry/README.md) | Loading, declared identity, rule corpus, module binding and conformance. |
| Design boundaries | [guards/](guards/README.md) | Purity, egress, measurement construction, secrets and model isolation. |
| Diagnostic ownership | [diagnostics/](diagnostics/README.md) | Declared codes and their emitting packages. |
| Repository configuration | [repo/](repo/README.md) | Packaging, Compose, images, workflows, documentation and test configuration. |
| Historical defect coverage | [regressions/](regressions/README.md) | Retained regressions grouped by behavior, with audit IDs preserved. |

Run a group with `uv run pytest tests/<group> -q`, or a case with
`uv run pytest path/to/test_file.py::test_name -q`. Start test databases first if the group
needs them. `make guards` and `make slow` have deliberate execution scopes; update their
callers before moving a test they select explicitly.

## Package and frontend suites

| Owner | Location | Coverage and dependencies |
|---|---|---|
| Shared declarations and artifacts | [comeni-core tests](../packages/comeni-core/tests/) | Pure schemas, layers, goals, settings and artifact models. |
| Routing and rules | [resolver tests](../packages/mendel-resolver/tests/) | Pure routing, rules, premises and resolution. |
| Nextflow construction | [compiler tests](../packages/mendel-compiler/tests/) | Emission, gates, derivability and generated tool documentation. |
| Conversation protocol | [authoring tests](../packages/mendel-authoring/tests/) | Pure protocol, commands, decisions, projections and review planning. |
| Build API and persistence | [API test index](../packages/mendel-api/tests/README.md) | Authoring, samples, decisions, Forge integration, settings and pipelines; some require Postgres. |
| Model transport | [comeni-ai tests](../packages/comeni-ai/tests/) and [Mendel shim tests](../packages/mendel-ai/tests/) | Provider formats and recorded or fake responses. |
| Inspection subprocesses | [inspection tests](../packages/comeni-inspect/tests/) | Wire protocol and subprocess isolation. |
| Module fetching | [vendor tests](../packages/comeni-vendor/tests/) | Fetching and pin checks against controlled fixtures. |
| Run-state calculation | [wiener-core tests](../packages/wiener-core/tests/) | Pure event admission, folding, decisions and projections. |
| Execution API | [wiener-api tests](../packages/wiener-api/tests/) | SQLite-backed routes and streams; PostgreSQL-specific cases use the isolated server. |
| Graph layout | [dag-core tests](../packages/dag-core/tests/) | Deterministic layout geometry. |
| Inspector pieces | [registry/inspectors/](../registry/inspectors/) | Codec, format and measurement pieces owned by the registry submodule. |
| Browser components | [frontend/src/](../frontend/src/) | Colocated `.test.ts` and `.test.tsx` files; shared setup in `setupTests.ts`. |

## Organize a test or helper

Choose the owner and behavior first. Group a larger suite by responsibilities readers already
recognize. Keep smaller cohesive suites flat. Split a file when its subjects need different
setup or are difficult to find together, rather than applying a line-count threshold.

Within a file, lead with its contract and dependencies, keep local fixtures small, and group
cases by behavior. Shared scenarios and fixtures belong in explicit helper modules, not in
another collected test module. Helpers should expose relevant inputs and outcomes rather than
hide the operation being tested. Directory-local `conftest.py` files own fixtures with that
scope; package-wide autouse fixtures must be justified by every test they affect.

Import shared pytest fixtures explicitly as re-exports, for example
`from mendel_api_tests.http import clean as clean`. Pytest injects them by parameter name;
ordinary unused-import cleanup can otherwise remove their registration.

`support.paths` provides repository, registry, package and fixture paths independent of file
depth. `support.pipeline` owns shared saved-pipeline setup; `support.audit` supports retained
regressions. `support.egress` owns payload-boundary declarations and traversal helpers;
`support.purity` owns import-policy declarations and scanning helpers. Package helper
namespaces are documented in their local indexes. Keep committed
fixtures and golden outputs distinct from generated temporary data.

Assertions should describe observable behavior or a deliberate architectural boundary. A loop
over a derived collection needs a non-empty assertion when emptiness would make it pass
without exercising the contract. Independently review expected outputs, and verify a new
regression test fails for the intended defect before relying on it. Preserve diagnostic IDs,
regression IDs, parameterized cases and guard evidence when reorganizing tests.
