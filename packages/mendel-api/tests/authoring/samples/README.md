# API authoring / samples tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| gaps | [test_gaps.py](test_gaps.py) |
| inspect | [test_inspect.py](test_inspect.py) |
| measurers | [test_measurers.py](test_measurers.py) |
| protection | [test_protection.py](test_protection.py) |

Run `uv run pytest packages/mendel-api/tests/authoring/samples -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../../README.md).
