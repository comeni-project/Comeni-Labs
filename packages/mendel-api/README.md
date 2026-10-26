# Mendel API

`mendel-api` is the stateful application shell around Mendel. It exposes the FastAPI schema,
stores drafts and authoring sessions in PostgreSQL, runs queued work, and connects the pure
authoring, resolution, compilation, AI, and inspection packages. The browser and external HTTP
clients consume it; other workspace packages do not import it.

## Run it locally

Use the repository's [local stack guide](../../docs/how-to/development/local-stack.md) to start
the full application. The ASGI application is `mendel_api.main:app`; all service routes are under
`/api`, and `/api/health` is the liveness endpoint.

Database schema changes are managed by Alembic. The Docker development stack migrates the
database before starting the API. For a host-run API, set `MENDEL_DATABASE_URL` and run:

```bash
cd packages/mendel-api
uv run alembic upgrade head
uv run uvicorn mendel_api.main:app --reload
```

Do not point development or test commands at a database whose contents must be retained.

## Test a change

From the repository root, prepare the isolated Mendel and Wiener databases and run this package:

```bash
make test-db
MENDEL_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel \
  COMENI_REQUIRE_DB=1 \
  uv run pytest packages/mendel-api/tests -q
```

`COMENI_REQUIRE_DB=1` turns an unavailable database into a failure instead of skipped coverage.
The fixtures truncate test tables and run serially. See the [test index](tests/README.md) for
behavior groups, shared scenarios, and narrow test commands.

## Find the right layer

| Area | Responsibility |
|---|---|
| `main.py`, `routes/` | FastAPI composition, HTTP request/response boundaries, and OpenAPI operations. |
| `services/` | Application use cases, persistence operations, registry access, settings, builds, and read models. |
| `stages/` | Stored authoring protocol handlers and command recorders. |
| `authoring/` | API-owned authoring views, prompts, envelopes, and the optional model resolver adapter. |
| `models.py`, `decision_models.py`, `db.py` | SQLAlchemy schema and transaction boundaries. |
| `worker.py`, `ai_worker.py`, `jobs.py` | Queue submission and worker entry points. |
| `migrations/` | Alembic migration history; add migrations, do not rewrite migrations already in use. |
| `migration_data/` | Versioned migration transforms retained for historical rows. |

The application owns effects and storage. Conversation legality remains in `mendel-authoring`,
resolution in `mendel-resolver`, artifact generation in `mendel-compiler`, provider transport in
`comeni-ai`, and bounded sample reading in `comeni-inspect`. Read the
[package-boundary reference](../../docs/explanation/package-boundaries.md) and the
[authoring protocol explanation](../../docs/explanation/authoring-protocol.md) before moving
responsibilities between packages.

## Contract and operations references

- The generated OpenAPI document is the HTTP contract; operation IDs and response shapes are
  guarded by the infrastructure tests.
- [Architecture](../../docs/explanation/architecture.md) explains the service's place in the
  platform.
- [Settings](tests/settings/README.md), [pipelines](tests/pipelines/README.md), and
  [infrastructure](tests/infrastructure/README.md) index their corresponding behavioral tests.
- [Contributing](../../docs/how-to/development/contribute.md) describes repository-wide checks
  and database safety.
