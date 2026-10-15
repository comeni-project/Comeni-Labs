# Forge registry tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| accept | [test_accept.py](test_accept.py) |
| drift tables | [test_drift_tables.py](test_drift_tables.py) |
| land | [test_land.py](test_land.py) |
| land boundary | [test_land_boundary.py](test_land_boundary.py) |
| land vocabulary | [test_land_vocabulary.py](test_land_vocabulary.py) |
| ops drift | [test_ops_drift.py](test_ops_drift.py) |
| ops maintain | [test_ops_maintain.py](test_ops_maintain.py) |
| rederive registry | [test_rederive_registry.py](test_rederive_registry.py) |
| workspace | [test_workspace.py](test_workspace.py) |
| workspace changed at | [test_workspace_changed_at.py](test_workspace_changed_at.py) |

Run `uv run pytest packages/mendel-forge/tests/registry -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
