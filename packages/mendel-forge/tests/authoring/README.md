# Forge authoring tests

Use this index to find the relevant test file. Names identify the behavior; shared
setup lives in the package helper namespace documented in the parent index.

| Behavior | File |
|---|---|
| assemble contract | [test_assemble_contract.py](test_assemble_contract.py) |
| assemble scaffold | [test_assemble_scaffold.py](test_assemble_scaffold.py) |
| bundle | [test_bundle.py](test_bundle.py) |
| decide | [test_decide.py](test_decide.py) |
| filler | [test_filler.py](test_filler.py) |
| golden | [test_golden.py](test_golden.py) |
| hole manifest | [test_hole_manifest.py](test_hole_manifest.py) |
| modulegen | [test_modulegen.py](test_modulegen.py) |
| observe | [test_observe.py](test_observe.py) |
| prompt goldens | [test_prompt_goldens.py](test_prompt_goldens.py) |
| propose | [test_propose.py](test_propose.py) |
| scaffold | [test_scaffold.py](test_scaffold.py) |
| scaffold goldens | [test_scaffold_goldens.py](test_scaffold_goldens.py) |
| scaffold rebase | [test_scaffold_rebase.py](test_scaffold_rebase.py) |

Run `uv run pytest packages/mendel-forge/tests/authoring -q` from the repository root.
Database and tool prerequisites are described in the [package test index](../README.md).
