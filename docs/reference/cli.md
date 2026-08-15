# CLI reference

```
mendel <command> [options]
```

Six commands: `build`, `profile`, `emit`, `publish`, `upgrade` and `explain`. Exit codes: `0` success, `1` a gate
failed, `2` your input was rejected — which includes a contract that disagrees with its
module.

## Shared options

| Option | Default | Meaning |
|---|---|---|
| `--out PATH` | *required for `build` and `profile`* | output directory, created if absent |
| `--root PATH` | current directory | repository root — used to find `examples/` and `vendor/` |
| `--registry PATH` | `<root>/examples` | a registry layer; **repeatable**, later layers win |
| `--gate {lint,preview,stub,test}` | none | run a validation gate after emitting |

`--root` and `--registry` are different things and are frequently confused. `--registry` is
where *contracts* live; `--root` is where *module source* lives, at `<root>/vendor`. A
laboratory wrapping bare containers has the first without the second.

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
| `pipeline.yml` | **the pipeline** — every step, setting, decision and provenance. See [pipeline-schema.md](pipeline-schema.md) |
| `modules/` | the vendored module tree, copied from `<root>/vendor/modules` if present |

`pipeline.yml` replaced `pipeline.ir.json`, `mendel.lock.yml` and a publish bundle. Read that
one file to answer "what settings does this pipeline use, and why".

`build` writes it, reads it back, and emits the Nextflow **from the copy it read** — so the
round trip is exercised on every build rather than asserted once, and a field that does not
survive YAML is a refused build (`MD0206`) instead of a file that quietly means less than it
says.

Prints to stderr:

```
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
```

Plus an `OVERLAY` line per declaration displaced by a higher layer, and an `ANSWERED` line
per tier-4 question a human has already settled.

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

## Conformance

Before anything is resolved, `build` and `profile` check every contract in the loaded
registry against the module it claims to describe — the vendored `main.nf` and `meta.yml`
under `<root>/vendor`. A contract is a hand-written binding to a foreign, dynamically-typed
unit, and nothing else compares the two.

Any disagreement exits `2` and emits nothing at all:

```
MD0101  nf-core/star/align@1.11.0
  process 'STAR_ALIGNN' is not what this module declares
    vendor/modules/nf-core/star/align/main.nf   process STAR_ALIGN {
  → nf_process: STAR_ALIGN

mendel: 1 contract(s) disagree with their modules. Nothing was emitted.
`mendel explain MD0101` for the long form.
```

<!-- BEGIN GENERATED DIAGNOSTICS -->

#### A contract disagrees with its module

| Code | Says |
|---|---|
| `MD0100` | no module source to check against — **warns, never blocks**; recorded in `pipeline.yml` under `registry.unverified` |
| `MD0101` | `nf_process` is not the process the module declares |
| `MD0102` | `nf_inputs` declares a different number of channels than the process takes |
| `MD0103` | an `{empty: N}` placeholder is the wrong tuple width |
| `MD0104` | a placeholder sits where the module declares `path(...)`, with no `because` |
| `MD0105` | a `produces[].name` is not one of the module's `emit:` labels |
| `MD0106` | a `meta` key the module reads that nothing declares, or a declared `meta_key` no module reads |
| `MD0107` | `container` has drifted from the module's directive |
| `MD0108` | a setting routes to an `ext` key this module never reads |

#### The pipeline file — a setting, an override, or the format

| Code | Says |
|---|---|
| `MD0200` | a setting declares no `via:`, so nothing would carry its value |
| `MD0201` | a resolved value is outside the substitutable character class |
| `MD0202` | a replayed value is frozen against a contract that has since been edited |
| `MD0203` | an override answers a question this re-resolution never asks |
| `MD0204` | a `template:` never mentions `{value}`, or sits on a route that takes none |
| `MD0205` | `via:`/`key:` are not a legal pair — including `key: when` |
| `MD0206` | the `pipeline.yml` just written does not parse back to the object it was written from |
| `MD0207` | `version:` is newer than this Mendel understands |
| `MD0208` | two writers for one destination — a non-composing `ext` key, or a meta key a measurement already writes |
| `MD0209` | `via: directive` names something Nextflow silently ignores |
| `MD0210` | `modules/` is absent, so the emitted `include` paths would point at nothing |
| `MD0211` | `channels[].params` disagrees with what its `expression` references |
| `MD0212` | two steps share an `id`, or two settings on one step share a `name` |
| `MD0213` | `pipeline.yml` has changed since the Nextflow was generated from it |
| `MD0214` | `main.nf` or `nextflow.config` was edited by hand since it was generated |
| `MD0215` | an input names neither `source` nor `channel`, or names both |
| `MD0216` | a resolved binding names a parameter its contract does not declare |
| `MD0217` | a test_data reference contains a character that would inject into the generated config |
| `MD0218` | a tier-4 answer is written in two places that disagree |
| `MD0219` | two decision records share one key |
| `MD0220` | a setting claims source: human with no override recording the answer |
| `MD0221` | an untemplated `via: ext` value is outside the substitutable class |
| `MD0222` | this pipeline records no `emitted:` block, so its directory cannot be certified |
| `MD0223` | a value was edited and the reason beside it still describes the value it replaced |
| `MD0224` | a setting fills a positional argument and is unanswered, so the call would read `null` |

#### Routing and resolution

| Code | Says |
|---|---|
| `MD0300` | a rule's `then` reads as arithmetic, and `then` is emitted verbatim |
| `MD0301` | a rule row justifies nothing — no `because` and no `cite`, on the row or the block |
| `MD0302` | a contract declares a role no layer in the stack declares |
| `MD0303` | a measurement is declared named `required_states`, which is the goal's own shape |
| `MD0304` | a derivation has no rows, so it can never fire |
| `MD0305` | a `when` clause uses a mapping predicate nothing implements |
| `MD0312` | a scalar comparison is applied to a per-sample measurement |

<!-- END GENERATED DIAGNOSTICS -->

Codes carry a two-letter prefix naming the subsystem that emits them. **`MD` is Mendel's
deterministic core** — the resolver, the compiler, contracts and the pipeline file. Bands of one
hundred group by concern: `MD01xx` is conformance. A code is never renumbered once published, so a
full band overflows into a new one rather than shifting.

**The prefix arrived on 2026-08-09**; these eight were `M0100`–`M0107` before that. Working notes
under `docs/internal/` are append-only and were correct on their date, so entries written earlier
still use the old spelling.

`MD0100` is not a failure. A laboratory wrapping a bare container has no nf-core-style module
directory, which is legitimate — the contract is listed under `registry.unverified` in
`pipeline.yml`, so a shared pipeline carries which claims went unchecked and a curator may
decline to curate one.

## `mendel emit`

```bash
uv run mendel emit build/pipeline.yml --out build/
```

Rebuilds `main.nf` and `nextflow.config` from the pipeline file. **No registry, no network.**

That is what materialising the pipeline was for: a laboratory can archive a validated pipeline
and regenerate its Nextflow years later without the registry it was built against — the part
that resolves differently as it changes.

This is the verb you run after editing `pipeline.yml`. It reports `MD0213` when the file has
moved since the Nextflow was generated, and then cures it by regenerating and restamping.

It refuses in two cases. `MD0210` when `modules/` is absent, because the emitted `include`
paths would point at nothing and the workflow would die at launch rather than here. And
`MD0214` when `main.nf` or `nextflow.config` was edited by hand, because regenerating would
overwrite that in silence — the message names `pipeline.yml`, since somebody editing the
workflow was trying to change the pipeline and that is the file which does it. To discard a
hand edit instead, delete the file and re-emit.

## `mendel publish`

```bash
uv run mendel publish build/pipeline.yml --gate test
```

**The directory is the artifact**, so this writes no file of its own, and it re-resolves
nothing: `pipeline.yml` is self-contained, so certifying it needs no registry and no network.
It refuses if the directory has diverged from its file, runs the gate you ask for, and stamps
the verdict into `pipeline.yml`. What you hand somebody is `pipeline.yml` plus `modules/`, which
is what they had to be handed anyway. Because publish reads no contracts, conformance is checked
at `build`; the legitimate edit-then-publish flow is edit → `mendel emit` → `publish`.

It takes no `--out`: it certifies the pipeline you give it rather than producing a new one.
`mendel upgrade --out` is the verb that produces one.

**It writes files and sends nothing.** Transmitting them is a later, separate act, which is
deliberate: publication is the door with no undo, so a person can read what they are about to
publish before any of it leaves.

The file holds **no filesystem paths and no timestamps**. A path is meaningless on the machine
that reads it; a timestamp would make every artifact differ from every other one and turn the
determinism tests into noise. Publishing the same goal twice produces byte-identical files, and
a test asserts it.

Contracts are pinned by *digest*, not version — a contract can be edited without its
`@version` moving, and in a private overlay it routinely is.

`gate: null` is not a weak gate. It is no evidence at all, and a curator reads the two
differently. Only `--gate test` runs the tools on data; conformance, `lint`, `-preview` and
`-stub-run` all pass a mis-wired pipeline, because nf-core stubs never read their inputs.

## `mendel upgrade`

```bash
uv run mendel upgrade build/pipeline.yml --out upgraded/     # re-resolve and write
uv run mendel upgrade build/pipeline.yml --dry-run           # report only; = verify
```

Re-resolves a pipeline against the current registry and reports what moved. The goal comes from
`pipeline.yml`, never from a `--goal` — re-resolving a *different* goal and calling the result
an upgrade is how "only what you touched moved" quietly becomes false.

**`--dry-run` is `verify`.** A separate verb comparing digests was the alternative and answers a
strictly weaker question: it can say a contract moved, but not whether the pipeline would
resolve differently. One code path, one answer, and the flag decides only whether bytes are
written.

**`--out` never writes in place, and refuses another pipeline's directory.** Writing over the
file it read would destroy the only record of what you had; and a `--out` that already holds a
*different* `pipeline.yml` is refused too, since upgrading into it would erase that pipeline's
evidence. Pass `--force` to replace it deliberately. An empty `--out`, or one holding a
byte-identical copy, is the normal case and is allowed.

Five kinds of report, because they answer different questions:

| Prefix | Means |
|---|---|
| `DRIFT` | the registry moved underneath the pins — a contract was edited, deleted, or a layer changed |
| `CHANGED` | that actually changed *this* pipeline: a module, setting or wiring resolved differently, with its tier and reason |
| `MD0202` | which of your values are frozen against a contract that has since been edited |
| `STALE` | a recorded answer no longer fits the question being asked — re-asked and flagged |
| `ORPHANED` | a recorded answer applies to nothing any more. **Refuses** (`MD0203`) |

`DRIFT` and `CHANGED` are both printed, because a contract can be edited in ways that change
nothing here and the pins no longer describing what is on disk is still worth knowing.

Stale reports and orphaned refuses. The difference is whether there is still a question: a stale
answer is re-asked, and an orphaned one has nothing left to be an answer to. An override that
silently stopped applying is the same failure as a guard that silently stops guarding.

Every recorded decision **replays** rather than being asked again — federation §4.3, and what
makes editing a curated pipeline safe. Against an unchanged registry it reports that the
generated pipeline is byte-identical to the one recorded.

Nothing upgrades implicitly, and **`upgrade` never writes over the pipeline it read**: `--out`
is required and must name a different directory. The one you have is the evidence — the
replayed overrides, the previous digests, the gate that passed.

## `mendel explain`

```bash
uv run mendel explain MD0104
```

The long form of a diagnostic, after `rustc --explain`: what the check means, and which
real defect earned it. Loads nothing, so it answers even when the registry will not load.
An unknown code lists the ones that exist.

## Gates

| Gate | Needs | Time | Proves |
|---|---|---|---|
| `lint` | Nextflow | seconds | the emitted Groovy parses |
| `preview` | Nextflow | seconds | names resolve and the dataflow connects, without executing |
| `stub` | Nextflow + Docker | ~1 min warm, ~15 min cold | the whole DAG executes end to end |
| `test` | Nextflow + Docker + data | minutes | the nf-core test profile runs |

`lint` and `preview` need no Docker and together take about six seconds, so they run on
every pull request — `make static`. They are not redundant: `nextflow lint` accepts
`STAR_ALIGN.out.NOSUCHCHANNEL` and exits `0`, while `-preview` rejects it and exits `1`.

`stub` is the one to use for wiring. nf-core modules all define stub blocks, so the entire
graph runs with dummy outputs in seconds — it proves the wiring, never that the analysis is
right, and it cannot see a hollow input at all, because nf-core stubs never read theirs.

It runs under `-profile stub_data,docker`. Docker is genuinely required even for stubs,
because nf-core 4.x captures tool versions with `eval()`, which executes regardless.

## Errors

Every failure is a message rather than a traceback.

| Message | Meaning |
|---|---|
| `cannot route this goal — nothing produces X` | no contract produces that type; you need a contract |
| `cannot route this goal — a rule pins X … inputs are unreachable` | a rule chose a module whose own dependencies cannot be met |
| `this goal is not valid` | the goal file does not match the schema |
| `contract is not valid` | a contract file does not match the schema — the message names the contract, not the goal you did write |
| `MD0200: contract … declares no via` | a contract parameter names no route, so its value would reach no tool |
| `this goal's profile is not valid` | an undeclared measurement, or a value outside its declaration |
| `a rule table will not load` | a rule cannot fire against this registry; the message says what you can write |
| `N contract(s) disagree with their modules` | conformance refused the build; each diagnostic says what to write instead |

## Other commands

```bash
uv run python tools/generate_types.py           # regenerate the measurement type stub
uv run python tools/generate_types.py --check   # fail if stale — what CI runs
```

```bash
make test    # uv run pytest -v
make lint    # uv run ruff check .
make fmt     # uv run ruff format .
make check   # everything CI runs on a pull request (~1 min, no Docker)
make verify  # check + counts matrix + guards + drift — the gate for a routing or emission change
make static  # conformance + nextflow lint + preview — everything checkable without Docker
make stub    # the full stub gate
make types   # regenerate the stub
```
