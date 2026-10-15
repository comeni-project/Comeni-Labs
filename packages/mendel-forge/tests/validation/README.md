# Forge validation tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| candidate ranking | [test_candidate_ranking.py](test_candidate_ranking.py) |
| candidates | [test_candidates.py](test_candidates.py) |
| hole ranking | [test_hole_ranking.py](test_hole_ranking.py) |
| verify | [test_verify.py](test_verify.py) |
| verify with proposals | [test_verify_with_proposals.py](test_verify_with_proposals.py) |

Run `uv run pytest packages/mendel-forge/tests/validation -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
