# Forge sources tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| catalogue models | [test_catalogue_models.py](test_catalogue_models.py) |
| nfcore evidence | [test_nfcore_evidence.py](test_nfcore_evidence.py) |
| source auth | [test_source_auth.py](test_source_auth.py) |
| source base | [test_source_base.py](test_source_base.py) |
| source nfcore | [test_source_nfcore.py](test_source_nfcore.py) |
| source nfcore catalogue | [test_source_nfcore_catalogue.py](test_source_nfcore_catalogue.py) |
| source opaque | [test_source_opaque.py](test_source_opaque.py) |
| source pegi3s | [test_source_pegi3s.py](test_source_pegi3s.py) |
| source pegi3s dio | [test_source_pegi3s_dio.py](test_source_pegi3s_dio.py) |
| sources | [test_sources.py](test_sources.py) |

Run `uv run pytest packages/mendel-forge/tests/sources -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
