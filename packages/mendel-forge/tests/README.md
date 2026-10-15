# Registry authoring test index

These tests exercise tool discovery, declared-data proposals, model-assisted drafting,
validation and reviewed landing. Model and HTTP calls use fake or recorded responses.
Use the [repository test index](../../../tests/README.md) for setup and shared commands.

| Group | Responsibility | Dependencies |
|---|---|---|
| [sources/](sources/README.md) | Source adapters, authentication, catalogues, evidence and recorded upstream responses. | HTTP doubles and fixtures in `fixtures/sources/`; no live upstream calls. |
| [authoring/](authoring/README.md) | Observations, scaffolds, bundles, contracts, module generation and prompt/scaffold goldens. | Registry submodule and committed fixtures. |
| [ai/](ai/README.md) | Provider schemas, context, prompt rendering, selection, generation and optional model paths. | Fake model transport; no live model. |
| [validation/](validation/README.md) | Candidate ranking and verification, including proposed vocabulary. | Temporary bundles and controlled module/gate evidence. |
| [registry/](registry/README.md) | Workspace drift, rederivation, reviewed landing and approval boundaries. | Temporary writable registry/workspace copies. |
| [cli/](cli/README.md) | Command workflows and operations. | Temporary workspace, fake adapters and controlled execution. |

Run `uv run pytest packages/mendel-forge/tests/<group> -q` from the repository root.
The Forge library tests do not require the API database. Worker and persistence integration
belongs in `packages/mendel-api/tests/forge/`.

## Support and goldens

Package `conftest.py` supplies complete and module-less scaffolds, mutation fixtures and the
explicit golden-regeneration option. `mendel_forge_tests` holds reusable examples:

| Helper | Responsibility |
|---|---|
| `paths.py` | Stable package fixture paths, independent of test depth. |
| `scaffolds.py` | nf-core/PEGiS bundles, scaffold setup and golden comparison. |
| `opaque.py` | A source with no Nextflow module or structured ports. |
| `nfcore_http.py` | Recorded nf-core catalogue responses and HTTP handlers. |
| `pegi3s_http.py` | Recorded PEGiS Docker/GitHub responses and HTTP handlers. |

Tests import these helpers directly rather than importing test modules. Keep fixture files and
expected outputs in their existing `fixtures/` and `golden/` directories. Regenerate goldens
only after independently reviewing the changed behavior and resulting diff:

```bash
uv run pytest packages/mendel-forge/tests/authoring/test_scaffold_goldens.py --regenerate
uv run pytest packages/mendel-forge/tests/authoring/test_prompt_goldens.py --regenerate
```
