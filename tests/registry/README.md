# Registry integration tests

These tests load declared data, validate rule and vocabulary relationships, bind contracts to vendored modules and exercise registry CLI operations. They need an initialized registry submodule. Gate-specific cases may additionally require Nextflow and Docker.

| Subject | File |
|---|---|
| conformance | [test_conformance.py](test_conformance.py) |
| conformance cli | [test_conformance_cli.py](test_conformance_cli.py) |
| conformance verb | [test_conformance_verb.py](test_conformance_verb.py) |
| declared identity | [test_declared_identity.py](test_declared_identity.py) |
| declared loading | [test_declared_loading.py](test_declared_loading.py) |
| docs verb | [test_docs_verb.py](test_docs_verb.py) |
| explanations | [test_explanations.py](test_explanations.py) |
| inspection conformance | [test_inspection_conformance.py](test_inspection_conformance.py) |
| loading diagnostics | [test_loading_diagnostics.py](test_loading_diagnostics.py) |
| measured entries | [test_measured_entries.py](test_measured_entries.py) |
| measurement vocabulary | [test_measurement_vocabulary.py](test_measurement_vocabulary.py) |
| modulespec | [test_modulespec.py](test_modulespec.py) |
| registry layer | [test_registry_layer.py](test_registry_layer.py) |
| registry lint | [test_registry_lint.py](test_registry_lint.py) |
| registry submodule | [test_registry_submodule.py](test_registry_submodule.py) |
| rule corpus | [test_rule_corpus.py](test_rule_corpus.py) |
| spine contracts | [test_spine_contracts.py](test_spine_contracts.py) |

Run `uv run pytest tests/registry -q` from the repository root.
See the [test index](../README.md) for shared setup and execution requirements.
