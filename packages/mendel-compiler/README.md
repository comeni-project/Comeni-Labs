# mendel-compiler

`mendel-compiler` turns a resolved pipeline artifact into deterministic Nextflow DSL2. It also
checks declared contracts against vendored modules, stages module sources, runs validation gates,
and provides the `mendel` command-line interface.

## How to use it

Build a starter into a self-contained pipeline directory:

```console
uv run mendel build examples/rnaseq.yml --registry registry --out build --gate stub
```

Re-emit an archived artifact without resolving it against a registry:

```console
uv run mendel emit build/pipeline.yml --out rebuilt
```

For task-oriented guidance, see [Build a pipeline](../../docs/how-to/pipelines/build.md). The
complete command and diagnostic references are [CLI](../../docs/reference/pipelines/cli.md) and
[diagnostic codes](../../docs/reference/pipelines/diagnostics.md).

## Python reference

The supported top-level emission functions take a saved `Pipeline`:

```python
from mendel_compiler import emit, emit_config

main_nf = emit(pipeline)
nextflow_config = emit_config(pipeline)
```

| Module | Responsibility |
| --- | --- |
| `emit` | Render `main.nf`, `nextflow.config`, and test-profile data deterministically. |
| `orchestrate` | Resolve and materialise a pipeline in memory for CLI and API callers. |
| `pipeline_file` | Read, write, stamp, and detect divergence in pipeline directories. |
| `conformance` / `modulespec` | Compare declarations with facts parsed from Nextflow modules. |
| `gates` | Prepare local gate inputs and invoke Nextflow with bounded timeouts. |
| `staging` | Copy only the module sources referenced by an artifact. |
| `registry_lint` / `tool_docs` | Check declared registry layout and render tool reference pages. |
| `layout` | Adapt compiler IR to the shared `dag-core` layout model. |
| `cli` | Parse commands, perform filesystem operations, and render refusals and reports. |

## Design boundaries

Emission is deterministic: the same `Pipeline` produces byte-identical output across hash seeds.
Resolution lives in `mendel-resolver`; artifact schemas and declared vocabularies live in
`comeni-core`; graph arithmetic lives in `dag-core`. Filesystem, Git, and Nextflow subprocess
operations remain in explicit compiler adapters rather than the pure artifact models. See
[Package boundaries](../../docs/explanation/package-boundaries.md) and
[Pipeline lifecycle](../../docs/explanation/pipeline-lifecycle.md).

## Verification

```console
uv run pytest -q packages/mendel-compiler/tests
uv run pytest -q tests/emit tests/artifact tests/registry tests/diagnostics tests/regressions
```

Execution gates require Nextflow, and the stub/test gates also require their configured container
runtime. Tests that need unavailable executors are reported separately from pure compiler checks.

Licensed under Apache-2.0; see `LICENSE`.
