# Boundary guards

These checks intentionally inspect dependency or payload structure where that structure is the design boundary. Keep the tested constraint explicit and preserve non-empty scans, admission checks and failure evidence. `make guards` selects the core purity, egress and construction checks; `make test` collects this whole directory.

| Subject | File |
|---|---|
| construction | [test_construction.py](test_construction.py) |
| egress | [test_egress.py](test_egress.py) |
| forge write boundary | [test_forge_write_boundary.py](test_forge_write_boundary.py) |
| inspector pieces | [test_inspector_pieces.py](test_inspector_pieces.py) |
| no clock | [test_no_clock.py](test_no_clock.py) |
| no live model | [test_no_live_model.py](test_no_live_model.py) |
| purity | [test_purity.py](test_purity.py) |
| purity runtime | [test_purity_runtime.py](test_purity_runtime.py) |
| settings secrets | [test_settings_secrets.py](test_settings_secrets.py) |

Run `uv run pytest tests/guards -q` from the repository root.
See the [test index](../README.md) for shared setup and execution requirements.
