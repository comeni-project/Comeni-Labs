# `pipeline.yml` — the pipeline file

This is the pipeline. Read it, edit it, and rebuild the Nextflow from it:

```bash
uv run mendel emit build/pipeline.yml --out build/
```

It replaced three files — `pipeline.ir.json`, `mendel.lock.yml` and a publish bundle. Before
that, "what settings does this pipeline use, and why" was four files and four mechanisms, and
one of the four mechanisms carried nothing at all: a resolved value became a `params.<x>` line
in the workflow that no module read.

A `pipeline.yml` is **generated, never hand-authored from nothing**. Resolution needs a
registry and always will. This is the output of resolution that you may then edit; it is not a
second way in. `mendel build --goal` is the only way to make one.

## What a pipeline directory holds

```
build/
  pipeline.yml       the pipeline — read this
  main.nf            generated
  nextflow.config    generated
  modules/           vendored module source
```

**The archive unit is the directory, not the file.** `pipeline.yml` is enough to regenerate
`main.nf` and `nextflow.config` byte for byte with no registry and no network. It is not enough
to *run*: `include` statements point into `modules/`, which `mendel build` copies in and `emit`
has no source to copy from. `mendel emit` refuses when `modules/` is missing rather than
writing a workflow that cannot launch.

What that buys is the part that matters for reproducing a decision: **emission no longer
depends on the registry.** `modules/` is inert vendored source; the registry is the thing that
resolves differently as it changes.

## The file

```yaml
version: 1

goal:                          # what was asked for
  have: [{type_id: fastq.reads}, {type_id: annotation.gtf}, {type_id: genome.fasta}]
  want: [counts.matrix]
  constraints: {required_states: [{type_id: counts.matrix, states: [gene_level]}]}
  profile:
    measurements:
      - {measurement: strandedness, value: reverse, source: goal, by: null}

registry:                      # provenance. NOT a dependency of `emit`.
  layers: [{name: comeni-registry-examples, digest: sha256:1a4f…}]
  displaced: []
  unverified: []

steps:
  - id: star_align
    module:
      contract_id: nf-core/star/align@1.11.0
      digest: sha256:9f2c…
      container: community.wave.seqera.io/library/…
    process: STAR_ALIGN
    include: modules/nf-core/star/align/main
    why:
      tier: 3
      source: resolver
      reason: "rule producer_of:alignment.bam matched read_length >= 70: doi:10.1093/…"
      from_layer: comeni-registry-examples
      displaced_layer: null
    ext_args: "--readFilesCommand zcat"
    inputs:
      - {port: reads, source: trimgalore.reads, states: [trimmed]}
      - {port: gtf, channel: annotation.gtf, states: []}
    call:
      - {ports: [reads]}
      - {literal: false, why: {tier: 1, source: resolver,
                               reason: "no GTF-free splice-junction path in this spine"}}
    settings:
      - name: seq_platform
        value: illumina
        via: ext
        key: args
        template: "--outSAMattrRGline 'ID:${meta.id}' 'SM:${meta.id}' 'PL:{value}'"
        why: {tier: 4, source: human, reason: "our sequencer"}

channels:                      # what the laboratory supplies
  - type_id: fastq.reads
    params: [input]
    expression: "Channel.fromFilePairs(params.input, checkIfExists: true)…"
    meta: [{key: single_end, value: false}, {key: strandedness, value: reverse}]
    test_data: ["https://…/samplesheet.csv"]

decisions:                     # the review queue: tier 4, ties, overrides
  - kind: param
    key: star_align.seq_platform
    subject: seq_platform
    tier: 4
    candidates: [null]
    chosen: null
    resolved_by: flag-only
    reason: "no rule covered 'seq_platform'"
    human_override: illumina

emitted:                       # what was written, and what it was written from
  from_digest: sha256:c41a…
  files:
    - {name: main.nf, digest: sha256:7b31…}
    - {name: nextflow.config, digest: sha256:0ac9…}

gate: test                     # the strongest gate this pipeline actually passed
```

## Section by section

### `version`

What schema this file uses. A file declaring a version newer than your Mendel understands is
**refused** (`MD0207`) rather than read for the parts it recognises — an older build silently
ignoring a section a newer one added is how a pipeline gets emitted without whatever that
section carried.

### `goal` — inert to `emit`

What was asked for. **Editing this changes nothing until `mendel upgrade`.**

That is worth stating rather than leaving implicit, for two reasons. A reader who finds
`profile: {strandedness: reverse}` in a file they were told to edit will reasonably expect
changing it to matter. And `emit` could not honour it even in principle: validating a profile
needs the measurement registry, and `emit` has no registry by design. The facts emission needs
are already materialised into `channels[].meta`.

To change the goal, edit it and run `mendel upgrade`, which re-resolves against a registry.

### `registry` — provenance, not a dependency

Which layers built this, by name and content digest; what an overlay displaced; and which
contracts had no module source to check against. `emit` reads none of it.

Layer **names** rather than paths, deliberately. A path is meaningless on the machine that
reads the file, and invariant 15 keeps filesystem paths out of anything shareable.

### `steps` — what runs, pinned, with its reasons

One entry per process. `module` pins the contract by content digest and records the container
as the contract declared it — a version string cannot pin a contract, because a contract can be
edited without its `@version` moving, and in a private overlay it routinely is.

`why` is on the step and on every setting: the tier it exited at, who settled it, which layer it
came from, and the citation. This is the legibility the four-file split could not provide — the
answer sits beside the value instead of in a decision record you had to join by hand.

`inputs` says where each consumed port comes from: `source: <step>.<port>` for something an
earlier step produced, or `channel: <type_id>` for something the laboratory supplies. Exactly
one of the two (`MD0215`) — the written file carries both keys with one of them `null`, and the
example above elides the nulls for readability.

`call` is the process's positional arguments, including tier-1 literals that appeared in no
artifact at all before this — `STAR_ALIGN(reads, index, gtf, false)` recorded neither that
`false` nor why. Each `CallArg` is exactly one of three shapes, written out with no positional
shorthand (a second reading of one field is how root G miswires a pipeline silently):

| field | is | example |
|---|---|---|
| `ports` | one or more channels carrying named ports | `{ports: [reads]}` |
| `literal` | a positional constant the process takes | `{literal: false, why: {…}}` |
| `empty_width` | an empty placeholder channel, and its **tuple width** | `{empty_width: 2, why: {…}}` |

`empty_width` is the arity of an empty tuple `[[:], []]` handed to an input the goal does not
fill — Nextflow matches arity, so a 2-tuple in a 3-tuple slot dies at launch. A literal and an
empty placeholder each carry a `why`: a positional choice is a decision, and `NfInput.empty`
already required a `because`, so the artifact records the whole provenance rather than an
exception for the one route that had no artifact.

### `settings` — and where each value goes

Every setting declares the **route** that carries it to the tool. There are three destinations,
and a setting without one is refused (`MD0200`):

| `via:` | lands in | `key:` |
|---|---|---|
| `ext` | `process { withName: X { ext.<key> = … } }` | `args`, `args2`, `args3`, `prefix` |
| `meta` | the channel's `meta` map | — |
| `directive` | a process directive such as `cpus` | — |

`via: ext` with an `args` key also needs a `template` mentioning `{value}` — a template that
forgets it renders real flags and silently discards your value, which is harder to spot than an
honest no-op (`MD0204`).

**Values are validated, not escaped.** A substituted value may contain letters, digits and
`_ . : + -` only, or be a number or a boolean (`MD0201`). Escaping-for-context is where
injection bugs live, and a value that cannot contain a quote cannot close one. If a real tool
setting needs a space or a slash, that is a case we assumed did not exist rather than one we
decided to forbid — please report it.

**Answering a tier-4 question is editing this file.** Set the `value`, run `mendel emit`, and
the answer reaches the tool. The tier stays 4: resolution met a real ambiguity and could not
settle it, and a reviewer needs to see that the pipeline contains a question somebody had to
answer. What clears is the *review*, not the tier — `mendel build` then prints `ANSWERED`
rather than `REVIEW`.

### `channels` — what the laboratory supplies

One entry per type consumed but not produced inside the pipeline. `expression` is the Groovy
that reads it, declared by the type's vocabulary rather than built into the compiler — the
compiler has no built-in idea what a FASTQ is. `params` lists the `params.<name>` that
expression references, and must agree with it (`MD0211`).

`meta` carries the measured facts a module reads. This is how `strandedness: reverse` becomes
featureCounts' `-s 2`: the module contains that translation, so the fact travels and the module
decides what to do with it.

`test_data` points at a small public example, pinned to a commit. Never a laboratory's own
path — this file is shareable, and a dataset that moves is one you cannot compare a result
against next year.

### `decisions` — the review queue

Every ambiguity, what was on the table, what was taken, and by whom. `human_override` **records**
a person's answer — it is what `mendel upgrade` replays rather than re-asking — but it is not
where you *write* one. The single writable home of a tier-4 answer is `settings[].value` (see
`settings`, above); `human_override` is derived from it, and a stored one that contradicts the
value is refused (`MD0218`) rather than silently preferred by whichever verb reads it. A setting
that claims `why.source: human` must have a matching non-null `human_override` — a review cleared
by assertion, with no recorded answer behind it, is refused (`MD0220`).

Two things can happen to a recorded answer when the registry moves, and they are not the same
event:

- **stale** — the question is still asked but its options moved, so the answer no longer fits.
  Re-asked and flagged, because replaying would assert a choice between options that no longer
  exist.
- **orphaned** — the question is not asked at all: the step is gone, or a rule now decides it.
  **Refused** (`MD0203`), because there is nothing left for the answer to be an answer to.

### `emitted` — and why `from_digest` exists

`files` records the digest of each generated file, so a hand-edited `main.nf` is caught
(`MD0214`).

`from_digest` catches the opposite and likelier mistake: **Nextflow runs `main.nf`, not
`pipeline.yml`.** Edit the file you were told to edit, forget to re-emit, and the pipeline that
runs is not the pipeline that is documented — with every file digest matching, because the
bytes on disk are exactly what was written. `from_digest` is the digest of everything above it,
so that divergence is detectable (`MD0213`).

`mendel emit` reports `MD0213` and cures it. `mendel upgrade` and `mendel publish` refuse,
because both make statements about the generated files and a `main.nf` built from a different
`pipeline.yml` makes those statements about nothing.

### `gate`

The strongest gate this pipeline actually passed, or `null`. **`null` is not a weak gate — it
is no evidence at all**, and it must read differently from `lint`.

Only `--gate test` runs the tools on data. Conformance, `nextflow lint`, `-preview` and
`-stub-run` all pass a mis-wired pipeline, because nf-core stubs never read their inputs.
Requiring `test` to publish was considered and rejected — minutes, Docker and network per
publish is too high a floor — so the file carries the evidence instead and a curator may
decline a pipeline that never ran the gate which checks wiring.

## Editing it safely

1. Edit `pipeline.yml`.
2. `mendel emit build/pipeline.yml --out build/`
3. `nextflow run build/main.nf -profile test,docker`

Skip step 2 and the next Mendel verb that opens the directory will tell you (`MD0213`).

Edit `main.nf` instead and `mendel emit` refuses (`MD0214`) rather than overwriting your change
in silence — and its message names `pipeline.yml`, because somebody editing the workflow was
trying to change the pipeline and that is the file which does it.

## See also

- [cli.md](cli.md) — the verbs, and every diagnostic code
- [goal-schema.md](goal-schema.md) — what goes in `goal:`
- [../concepts/tiers.md](../concepts/tiers.md) — what the four tiers mean
