# Repository configuration tests

Checks read packaging, Compose, Dockerfiles, workflows, generators and documentation. They also verify test database configuration. Most inspect declarations without starting services; test-specific prerequisites remain explicit.

| Subject | File |
|---|---|
| architecture | [test_architecture.py](test_architecture.py) |
| changelog section | [test_changelog_section.py](test_changelog_section.py) |
| deployment boundaries | [test_deployment_boundaries.py](test_deployment_boundaries.py) |
| development startup | [test_dev_services.py](test_dev_services.py) |
| compose | [test_compose.py](test_compose.py) |
| doc checks | [test_doc_checks.py](test_doc_checks.py) |
| dockerfile | [test_dockerfile.py](test_dockerfile.py) |
| docs status | [test_docs_status.py](test_docs_status.py) |
| generated types | [test_generated_types.py](test_generated_types.py) |
| packaging | [test_packaging.py](test_packaging.py) |
| protocol doc | [test_protocol_doc.py](test_protocol_doc.py) |
| PostgreSQL configuration | [test_postgres.py](test_postgres.py) |
| PostgreSQL initialization and migration (Docker) | [test_postgres_migration.py](test_postgres_migration.py) |
| pydantic floor | [test_pydantic_floor.py](test_pydantic_floor.py) |
| release workflow | [test_release_workflow.py](test_release_workflow.py) |
| seed demo | [test_seed_demo.py](test_seed_demo.py) |
| test databases | [test_test_databases.py](test_test_databases.py) |
| test helper ownership | [test_test_layout.py](test_test_layout.py) |
| where it runs | [test_where_it_runs.py](test_where_it_runs.py) |
| wiki | [test_wiki.py](test_wiki.py) |
| workflow pins | [test_workflow_pins.py](test_workflow_pins.py) |

Docker build-context and package-copy probes require Docker and run with `-m slow`.

Run `uv run pytest tests/repo -q` from the repository root.
See the [test index](../README.md) for shared setup and execution requirements.
