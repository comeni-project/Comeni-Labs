# Retained regression tests

Files group defects by behavior: boundaries, declared models, decisions, gates and emission, layers, overlays and rules. Test names retain audit IDs for traceability. Shared historical scenarios are in support.audit; fixture and guard records remain in tests/fixtures/.

| Subject | File |
|---|---|
| boundaries | [test_boundaries.py](test_boundaries.py) |
| decisions | [test_decisions.py](test_decisions.py) |
| declared models | [test_declared_models.py](test_declared_models.py) |
| gates and emit | [test_gates_and_emit.py](test_gates_and_emit.py) |
| layers | [test_layers.py](test_layers.py) |
| overlays | [test_overlays.py](test_overlays.py) |
| rules | [test_rules.py](test_rules.py) |

Run `uv run pytest tests/regressions -q` from the repository root.
See the [test index](../README.md) for shared setup and execution requirements.
