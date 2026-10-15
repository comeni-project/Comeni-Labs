# Diagnostic ownership tests

Checks cover declaration coverage, diagnostic identity and emission through coded(). Diagnostic source data belongs to comeni-core; these tests inspect ownership across the repository.

| Subject | File |
|---|---|
| diagnostics ownership | [test_diagnostics_ownership.py](test_diagnostics_ownership.py) |
| diagnostics registry | [test_diagnostics_registry.py](test_diagnostics_registry.py) |

Run `uv run pytest tests/diagnostics -q` from the repository root.
See the [test index](../README.md) for shared setup and execution requirements.
