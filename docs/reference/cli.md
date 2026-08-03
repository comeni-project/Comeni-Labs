# CLI reference

```
mendel <command> [options]
```

Two commands: `build` and `profile`. Exit codes: `0` success, `1` a gate failed, `2` your
input was rejected.

## Shared options

| Option | Default | Meaning |
|---|---|---|
| `--out PATH` | *required* | output directory, created if absent |
| `--root PATH` | current directory | repository root — used to find `examples/` and `vendor/` |
| `--registry PATH` | `<root>/examples` | a registry layer; **repeatable**, later layers win |
| `--gate {lint,stub,test}` | none | run a validation gate after emitting |

A registry layer is a directory holding `contracts/`, `rules/`, `vocabularies/` and
`measurements/`. See [guides/registry-layers.md](../guides/registry-layers.md).

## `mendel build`

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/
```

| Option | Meaning |
|---|---|
| `--goal PATH` | goal file — see [goal-schema.md](goal-schema.md) |

Writes:

| File | Contents |
|---|---|
| `main.nf` | the Nextflow DSL2 workflow |
| `nextflow.config` | every input parameter declared `null`, plus `docker`, `singularity` and `stub_data` profiles |
| `pipeline.ir.json` | the full intermediate representation — nodes, edges, tiers, decision records |
| `modules/` | the vendored module tree, copied from `<root>/vendor/modules` if present |

Prints to stderr:

```
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
```

Plus a `SHADOW` line per contract displaced by a higher layer.

## `mendel profile`

```bash
uv run mendel profile --have fastq.reads --out profile-build/
```

| Option | Meaning |
|---|---|
| `--have TYPE_ID` | a type you hold; **repeatable** |

Sugar for `build --want measurement.*`. Emits everything `build` does, plus `profile.yml`:

```yaml
measurements:
- by: comeni/profile/fastqc@0.12.1
  measurement: read_length
  source: measured
  value: null
```

`value: null` because the pipeline has been emitted, not run. Wants only the measurements
this registry can actually reach, and names the rest:

```
profiling for: read_length
  NOT MEASURED  n_samples, paired, strandedness — declared, but no contract in
                this registry produces them
```

A registry that can measure nothing at all exits `2`. See
[guides/measuring-your-data.md](../guides/measuring-your-data.md).

## Gates

| Gate | Needs | Time | Proves |
|---|---|---|---|
| `lint` | Nextflow | seconds | the emitted Groovy parses |
| `stub` | Nextflow + Docker | ~1 min warm, ~15 min cold | the whole DAG executes end to end |
| `test` | Nextflow + Docker + data | minutes | the nf-core test profile runs |

`stub` is the one to use. nf-core modules all define stub blocks, so the entire graph runs
with dummy outputs in seconds — it proves the wiring, never that the analysis is right.

It runs under `-profile stub_data,docker`. Docker is genuinely required even for stubs,
because nf-core 4.x captures tool versions with `eval()`, which executes regardless.

## Errors

Every failure is a message rather than a traceback.

| Message | Meaning |
|---|---|
| `cannot route this goal — nothing produces X` | no contract produces that type; you need a contract |
| `cannot route this goal — a rule pins X … inputs are unreachable` | a rule chose a module whose own dependencies cannot be met |
| `this goal is not valid` | the goal file does not match the schema |
| `this goal's profile is not valid` | an undeclared measurement, or a value outside its declaration |
| `a rule table will not load` | a rule cannot fire against this registry; the message says what you can write |

## Other commands

```bash
uv run python tools/generate_types.py           # regenerate the measurement type stub
uv run python tools/generate_types.py --check   # fail if stale — what CI runs
```

```bash
make test    # uv run pytest -v
make lint    # uv run ruff check .
make fmt     # uv run ruff format .
make check   # everything CI runs on a pull request
make stub    # the full stub gate
make types   # regenerate the stub
```
