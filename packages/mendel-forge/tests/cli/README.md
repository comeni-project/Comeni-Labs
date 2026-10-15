# Forge cli tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| cli | [test_cli.py](test_cli.py) |
| cli model fill | [test_cli_model_fill.py](test_cli_model_fill.py) |
| decide op | [test_decide_op.py](test_decide_op.py) |
| ops | [test_ops.py](test_ops.py) |
| workflow | [test_workflow.py](test_workflow.py) |

Run `uv run pytest packages/mendel-forge/tests/cli -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
