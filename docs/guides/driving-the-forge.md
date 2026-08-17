# Driving the forge

The other loop. [`driving-mendel.md`](driving-mendel.md) is how a pipeline gets built from a
registry; this is how the registry gets written.

Written for whoever is *authoring* declared data — a curator, or an agent doing what a curator
does. The one thing to understand before any command:

> **A scaffold is not a half-built contract.** The forge either produces a valid declared file
> or produces something that is honestly not one yet and says which fields it is missing and
> why. There is no third state, and no defaults.

Every command below was run against this repository on 2026-08-17, and the output is copied
rather than described.

## 1. What can be read

```console
$ uv run forge sources
nf-core
```

One source ships. [pegi3s is issue #65](https://github.com/comeni-project/Comeni-Labs/issues/65)
— designed for rather than built, with a fixture source of its shape in the test suite so the
`Source` protocol has had two implementations since its first commit.

```console
$ uv run forge discover
nf-core:fastqc
nf-core:hisat2/align
nf-core:hisat2/build
nf-core:multiqc
...
```

A reference is `<source>:<tool>`. The bare form is refused (`MF0001`): it is ambiguous the moment
a second source exists, and a second source is why the ingestion layer is a protocol at all.

## 2. Draft

```console
$ uv run forge draft nf-core:fastqc --name fastqc --version 0.12.1
fastqc -> tools/nf-core/fastqc/fastqc.contract.yml
  9 field(s) derived, 7 open
```

Nine fields the module proves, seven it cannot. That split is not a guess —
[`notes/audits/2026-08-16-forge-derivability.md`](../../notes/audits/2026-08-16-forge-derivability.md)
measured it against all twelve shipped contracts, and `assemble.py` implements that table
literally.

The draft lands in `.forge/` by default, **outside every registry layer**. A `proposals/`
directory inside a layer would put non-declared files where the loader globs and the digest
allowlist walks, and would make every draft a commit in the registry's history.

## 3. Read what is open, and why

```console
$ uv run forge show fastqc
fastqc -> tools/nf-core/fastqc/fastqc.contract.yml

filled:
  container = 'quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0'  (derived, nf-core)
  id = 'nf-core/fastqc@0.12.1'  (derived, nf-core)
  nf_include = 'modules/nf-core/fastqc/main'  (derived, nf-core)
  nf_inputs.arity = 1  (derived, nf-core)
  nf_process = 'FASTQC'  (derived, nf-core)
  produces[0].name = 'html'  (derived, nf-core)
  produces[1].name = 'zip'  (derived, nf-core)
  produces[2].name = 'versions_fastqc'  (derived, nf-core)
  provenance.source = 'nf-core'  (derived, nf-core)

open (7):
  consumes[0].name
      what: what this contract calls the thing arriving on channel 0 — the module calls it meta, reads
      why open: a port name says what the channel carries; the module's says what the process
                calls it, and the two are not the same choice
      one of: reads
  produces[0].type_id
      what: a value for produces[0].type_id
      why open: nf-core declares an output as `type: file` with a filename pattern; the semantic
                type exists only in the English description
      one of: alignment.bai, alignment.bam, annotation.gtf, counts.matrix, ...
  ...
```

**A hole says why it is open**, not only that it is. The name alone tells you what to type and
nothing about what to think, and the reasoning is the part worth preserving.

**`one of:` is invariant 7 moved earlier.** Vocabularies are closed, so a contract naming an
undeclared state fails to load. A hole carrying its legal values turns that load-time refusal
into a fill-time one — and, from Phase 2, turns an open prompt into a closed choice: a model
asked *which of these twenty-two types* cannot invent a twenty-third.

A hole with **no** candidates is free text. `priority_because` has no enumerable domain, and
demanding one would make every prose field unfillable.

## 4. Fill

```console
$ uv run forge fill fastqc 'produces[0].type_id' qc.report \
    --by rafael --why "FastQC writes a report"
produces[0].type_id filled; 4 left: priority_because, produces[1].type_id, produces[2].type_id, roles
```

`--by` and `--why` are required. A value with no author and no reason is the thing this whole
project exists not to produce.

For a field holding several values from one closed set, `--list`:

```console
$ uv run forge fill fastqc roles qc_per_sample --list --by rafael --why "it QCs one sample"
roles filled; 3 left: priority_because, produces[1].type_id, produces[2].type_id
```

A value outside the candidates is refused with `MF0003`, and a field that is not open with
`MF0002`.

### Filling with a model

`--model` asks a model to answer the open holes instead. It is **opt-in**: with no `--model`,
nothing in the forge reaches a provider, and that is the mode CI runs.

```console
$ export MENDEL_MODEL=anthropic/claude-sonnet-4-5
$ export MENDEL_API_KEY=sk-...
$ uv run forge fill fastqc --model "$MENDEL_MODEL"
fastqc:
  filled   produces[0].type_id = 'qc.report'
           FastQC emits an HTML report per sample rather than any sequence data
  open     priority_because
           no candidates — free text, and a person answers it
  1 hole(s) still open
```

Name one field to attempt only that one:

```console
$ uv run forge fill fastqc roles --model "$MENDEL_MODEL"
```

**A model answers only the holes with candidates.** Those are the ones whose legal answers come
off the layer stack, so the answer can be checked — and it is, twice: once against the options
the model was handed, and again by the same rule that checks a person's fill. A hole with no
candidates is free text, and the model is never asked about it at all. `priority_because` is the
one such field, and letting a model write it is
[#70](https://github.com/comeni-project/Comeni-Labs/issues/70).

**A model fill lands as an answer, not a suggestion**, and `forge show` says who settled each
value:

```console
$ uv run forge show fastqc
filled:
  nf_process = 'FASTQC'  (derived, nf-core)
  produces[0].type_id = 'qc.report'  (model, anthropic/claude-sonnet-4-5)
  roles = ['qc_per_sample']  (hand, rafael)
```

That marker is the whole reason landing a model fill directly is honest: the model id follows
the value into `provenance.drafted_by` when you `land`, so the contract in the registry names
what drafted it. **Read the diff before you land it** — a model answering a closed choice is
checkable, and checked, but "checkable" is not "correct".

Three things that can go wrong, each with a code:

```console
$ uv run forge fill fastqc --model claude-sonnet-4-5
forge: MA0007: claude-sonnet-4-5: LLM Provider NOT provided...
  run: forge explain MA0007
```

LiteLLM wants `<provider>/<model>`. With no `MENDEL_MODEL` at all you get `MA0001`; if the model
answers with something that is not the shape it was asked for, the hole simply stays open and
the reason is `MA0004`. None of these lose work already done — the draft is saved after **each**
fill, so a provider dying halfway costs you the holes it had not reached yet and nothing else.

## 5. Verify

Five rungs, cheapest first, stopping at the first refusal so you see the cause rather than a
wall of consequences. With holes left:

```console
$ uv run forge verify fastqc
complete     REFUSED
    MF0004  tools/nf-core/fastqc/fastqc.contract.yml
  3 field(s) still open
    priority_because
    produces[1].type_id
    produces[2].type_id
  → run `forge show` for what each hole wants, then `forge fill` for each

refused
```

**That refusal is the design working, not failing.** Filled:

```console
$ uv run forge verify fastqc
complete     ok
constructs   ok
loads        ok
conforms     ok
routes       ok

no refusal
```

| rung | asks |
|---|---|
| `complete` | are all the holes filled? |
| `constructs` | does `ModuleContract` accept it? |
| `loads` | does the layer stack declare every type, state and role it names? |
| `conforms` | does it agree with the module on disk? |
| `routes` | can anything in the layer consume what it produces? |

Rung 4 reuses the **same** conformance codes a build raises — `MD0101` for a wrong process
name, `MD0102` for the wrong channel count. A draft fails for exactly the reason a pipeline
would, so a runbook citing `MD0102` covers both. Rung 5 **warns and never blocks**: a laboratory
adding a tool before the goal that needs it is being reasonable.

## 6. Land

```console
$ uv run forge land fastqc --registry ../comeni-registry --by rafael
landed on forge/fastqc (a1b2c3d4e5f6)
  tools/nf-core/fastqc/fastqc.contract.yml
```

**`--registry` is required here and defaults everywhere else.** Landing is the one verb with a
git commit behind it, and `registry/` in this repository is a submodule at a detached HEAD — a
defaulted target means somebody eventually commits into it by accident.

`land` refuses the default branch (`MF0100`), a dirty tree (`MF0101`) and an incomplete draft
(`MF0004`). It creates a branch, writes the files and commits, and **it does not open a pull
request**: invariant 13 says self-hosted is not a degraded tier, so a lab landing into a private
overlay gets the identical path. The branch *is* the approval queue, which is invariant 2 across
a repository boundary.

`land.py` is the only thing in the package that writes under a registry root, and
`tests/test_forge_write_boundary.py` is a static scan holding that over every other module.

## 7. Maintain

```console
$ uv run forge check
checked 10 contract(s)
  skipped, no source can re-read them: comeni/profile/collect@0.1.0, comeni/profile/fastqc@0.12.1
no drift
```

Does the registry still say what its sources say? **Offline** — whether *upstream* has moved is
[issue #64](https://github.com/comeni-project/Comeni-Labs/issues/64). The skipped contracts are
reported by name rather than folded into the pass, because a contract nothing checks looks
exactly like a contract that agrees.

When something has drifted, `forge update <contract-id> --name <draft>` re-drafts it from its
source into the workspace. It writes a draft and never the registry.

## The same verbs over HTTP

Every verb above is one function in `mendel_forge/ops.py` taking a pydantic request and
returning a pydantic result. The CLI renders those results; `mendel_forge.http` serialises them.
Neither holds logic — `test_no_route_contains_a_branch` refuses an `if` in a route, and
`test_http.py` compares `forge --json <verb>` against the HTTP body directly, so a transport
that grows logic fails rather than drifts.

```python
from fastapi import FastAPI
from mendel_forge.http import app

parent = FastAPI()
parent.mount("/forge", app)
```

The app binds nothing and has no auth. Plan 3's `mendel-api` mounts it and owns those questions.

## What the forge does not do

**It calls no model.** `ports.py` declares `HoleFiller` and ships `NoFiller`, which declines
every hole — so `--no-ai` is not a flag here, it is the only mode, and there is nothing to leave
accidentally on. Wiring a model is Phase 2, and its first question is not an implementation
question: a forge model call sends tool documentation to a provider, and invariant 14 says data
leaves through *four* declared doors. Read §10.3 of
[`the forge spec`](../../notes/specs/2026-08-16-the-forge.md) before writing an adapter.

**It does not approve anything.** Invariant 2: the forge drafts, a person approves. `--by` names
that person and it never defaults to `$USER`.
