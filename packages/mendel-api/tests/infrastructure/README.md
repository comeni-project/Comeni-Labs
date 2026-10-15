# API infrastructure tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| ai health | [test_ai_health.py](test_ai_health.py) |
| db transaction | [test_db_transaction.py](test_db_transaction.py) |
| health | [test_health.py](test_health.py) |
| identity | [test_identity.py](test_identity.py) |
| migrations | [test_migrations.py](test_migrations.py) |
| models | [test_models.py](test_models.py) |
| mount | [test_mount.py](test_mount.py) |
| openapi | [test_openapi.py](test_openapi.py) |
| postgres required | [test_postgres_required.py](test_postgres_required.py) |
| registry cache | [test_registry_cache.py](test_registry_cache.py) |
| retention sweep | [test_retention_sweep.py](test_retention_sweep.py) |
| shapes | [test_shapes.py](test_shapes.py) |
| test configuration | [test_test_configuration.py](test_test_configuration.py) |
| worker schedule | [test_worker_schedule.py](test_worker_schedule.py) |

Run `uv run pytest packages/mendel-api/tests/infrastructure -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
