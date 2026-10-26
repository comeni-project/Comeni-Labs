# Wiener API

`wiener-api` is the stateful execution shell around `wiener-core`. It stores pipeline artifacts
and run events, launches Nextflow through background jobs, maintains query projections, publishes
live tails through Redis, and exports optional telemetry. The browser and external HTTP clients
consume its public API; the ingest process and worker load the package directly.

## Run the service

Use the repository's [local stack guide](../../docs/how-to/development/local-stack.md) for the
normal three-process setup:

- `wiener-api` serves authenticated public routes from `wiener_api.main:create_app`.
- `wiener-ingest` binds the private event receiver from
  `wiener_api.main:create_ingest_app`; it is intentionally not mounted on the public app.
- `wiener-worker` launches runs, records heartbeats, and applies retention policy.

For host-run development, set `WIENER_DATABASE_URL` and `WIENER_REDIS_URL`, migrate the database,
then start only the process you need. For example:

```bash
cd packages/wiener-api
uv run alembic upgrade head
uv run uvicorn wiener_api.main:create_app --factory --port 8001
```

An empty `WIENER_API_TOKEN` leaves the public API open and is suitable only for a local machine.
The ingest app uses a separate per-run secret because the Nextflow head process posts to it.

## Test a change

Most tests use an isolated in-memory SQLite database. PostgreSQL-specific locking and migration
checks use the repository's disposable test server:

```bash
make test-db
WIENER_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/wiener \
  COMENI_REQUIRE_DB=1 \
  uv run pytest packages/wiener-api/tests -q
```

`COMENI_REQUIRE_DB=1` turns an unavailable PostgreSQL dependency into a failure instead of a
skip. Test fixtures can delete or truncate data, so never point them at a database that must be
retained.

## Find the right layer

| Area | Responsibility |
|---|---|
| `main.py`, `routes/` | Public and ingest FastAPI composition, authentication, and HTTP shapes. |
| `repository.py`, `models.py`, `db.py` | Tenant-scoped queries, SQLAlchemy schema, and transactions. |
| `services/artifacts.py`, `launcher.py` | Artifact admission, durable parameters, work directories, and Nextflow launch. |
| `services/projection.py` | Append-only event record and cached run/task projections. |
| `services/stream.py`, `telemetry.py` | Lossy Redis tails and optional observability lenses; PostgreSQL remains authoritative. |
| `services/deletion.py`, `retention.py` | Explicit deletion and scheduled lifecycle policy. |
| `worker.py`, `jobs.py` | Queue entry points, recovery, heartbeats, and scheduled work. |
| `migrations/` | Alembic migration history; add a migration rather than rewriting one already in use. |

`wiener-core` owns pure event admission, folding, policy, graph, timeline, series, and telemetry
descriptions. This package owns effects and storage. See the
[package-boundary reference](../../docs/explanation/package-boundaries.md),
[architecture overview](../../docs/explanation/architecture.md), and
[development-service map](../../docs/reference/development-services.md).

## Public contracts

The generated OpenAPI document is the public HTTP contract. Every operation ID is pinned by
`tests/test_wiener_openapi.py`; changes to routes or shapes may require regenerating the frontend
client. Event JSON and persisted JSON columns are versioned separately, and migration tests compare
the live PostgreSQL schema with the SQLAlchemy models.
