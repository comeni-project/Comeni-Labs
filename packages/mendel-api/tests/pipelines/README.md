# API pipelines tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| build service | [test_build_service.py](test_build_service.py) |
| bundle | [test_bundle.py](test_bundle.py) |
| draft mutations | [test_draft_mutations.py](test_draft_mutations.py) |
| draft provenance | [test_draft_provenance.py](test_draft_provenance.py) |
| drafts | [test_drafts.py](test_drafts.py) |
| drafts service | [test_drafts_service.py](test_drafts_service.py) |
| gate routes | [test_gate_routes.py](test_gate_routes.py) |
| gate runs | [test_gate_runs.py](test_gate_runs.py) |
| gate service | [test_gate_service.py](test_gate_service.py) |

Run `uv run pytest packages/mendel-api/tests/pipelines -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
