# mendel-compiler

Pipeline IR to Nextflow DSL2, the validation gates, and the `mendel` CLI for
[Comeni Labs](https://github.com/comeni-project/Comeni-Labs).

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
uv run mendel profile --have fastq.reads --out profile-build/
```

```python
from mendel_compiler import emit, emit_config

source = emit(ir, registry, vocabulary)
```

**Deterministic.** The same IR produces byte-identical output, proven across
`PYTHONHASHSEED` values rather than assumed. `cli.main` is the only thing here that touches
disk; everything else takes objects and returns strings.

Three gates: `lint` parses the emitted Groovy, `stub` executes the whole DAG with dummy
outputs in about a minute, and `test` runs the nf-core test profile. `stub` is the one to
use — it proves the wiring, never that the analysis is right.

Documentation: [CLI reference](../../docs/reference/cli.md) ·
[diagnostic codes](../../docs/reference/diagnostics.md) ·
[the tutorial](../../docs/tutorial.md). Licensed Apache-2.0.
