# Driving Mendel

The loop, end to end: a goal in, a pipeline out, and every change made in the pipeline file
rather than in the generated Nextflow.

Written for whoever is *operating* the engine — an agent, or a person doing what an agent does.
Mendel is the engine and the AI is its primary operator ([`design/mendel.md`](../design/mendel.md)
§1), which changes nothing about the commands and one thing about the standard: a person who
meets a value with no reason beside it asks; a model fills it in. So every value carries a
`why:`, and the parts of this loop that keep it honest are the parts worth reading slowly.

Every command below was run against this repository on 2026-08-16, and the output is copied
rather than described.

## 1. Produce a goal

A `Goal` holds type ids, states and declared measurements. **It is a shape, never data**
(invariant 15) — there is no field for a sample name, a filename or a path, so there is nothing
to redact. [`examples/rnaseq-goal.yml`](../../examples/rnaseq-goal.yml):

```yaml
have:
  - type_id: fastq.reads
  - type_id: annotation.gtf
  - type_id: genome.fasta
want:
  - counts.matrix
constraints:
  required_states:
    counts.matrix: [gene_level]
profile:
  read_length: 150
  strandedness: reverse
  n_samples: 12
  paired: true
```

`have` and `want` are what routing solves between. `profile` is what tier-3 rules read — and
every key in it must be a declared measurement, which is why an invented one is refused rather
than ignored. See [`reference/goal-schema.md`](../reference/goal-schema.md).

## 2. Build

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate lint
```

```
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
gate lint: PASS
```

Three kinds of summary line, and their absence is meaningful:

| | |
|---|---|
| `OVERLAY` | a higher registry layer displaced something a lower one supplied. Absent here — one layer is loaded |
| `ANSWERED` | a recorded decision was replayed rather than re-asked |
| `REVIEW` | a setting nothing could settle. **Tier 4 is always listed, at any confidence** (invariant 6) |

Gates run in increasing cost: `lint` parses, `stub` executes the whole DAG with dummy outputs,
`test` runs the nf-core test profile for real. `stub` and `test` need Docker.

## 3. Read the save file

`build/pipeline.yml` **is** the pipeline. `main.nf` is generated from it and is not the thing to
edit. Every value carries a `why:`:

```yaml
- name: star_ignore_sjdbgtf
  value: false
  via: positional
  why:
    tier: 2
    source: resolver
    reason: 'Align *with* the annotation. The GTF is routed into this module, and ignoring
      it would discard the splice-junction information a spliced aligner exists to use.'
    for_value: false
    review_level: none
```

Four fields do the work:

- **`tier`** — how it was settled. 1 structural, 2 convention, 3 a rule matched measured data,
  4 nothing matched. [`concepts/tiers.md`](../concepts/tiers.md).
- **`review_level`** — `none`, `advisory` or `required`. Tier 3 is `advisory` rather than silent
  on purpose: the machinery worked, so what is left to check is the premise.
- **`for_value`** — the value this reason was written *about*. Section 5 is what it is for.
- **`premise`** — the facts a tier-3 rule read, each with where it came from.

**`origin: asserted` is the one to stop on.** It means the premise was declared in the goal, not
measured from data:

```yaml
    premise:
    - id: read_length
      value: 150
      origin: asserted
```

A tier-3 decision is only as good as the premise under it, and an asserted premise is somebody's
belief about their data. Where the belief is wrong the rule fires correctly and chooses wrongly,
and nothing downstream will notice. `mendel profile` emits a pipeline that measures the value for
real — see [`measuring-your-data.md`](measuring-your-data.md).

## 4. Change one thing

Edit the `value:` — and edit the `why.reason` and `why.for_value` beside it. Editing the value
alone is refused:

```
mendel: MD0223: a value was edited and the reason beside it was not.
  star_align.star_ignore_sjdbgtf: value is True, but the reason beside it was written about
  False — Align *with* the annotation. …
  Update `why.reason` to explain the new value and set `why.for_value` to it, or revert the
  value — `mendel explain MD0223`.
```

Exit 2, nothing emitted. This is the check that keeps the file's central claim true: before it
existed, `min_mqs` 0 → 30 emitted `-Q 30` under `reason: contract default for min_mqs`, and
`publish` certified it at exit 0 (audit A104).

**It cannot catch a reason that is merely wrong**, only one written about a different value. A
reason is free text, and the guarantee is that somebody wrote one *for this value*, not that it
is true.

## 5. Rebuild from the file

```bash
uv run mendel emit build/pipeline.yml --out build/
```

**No registry and no network.** The file carries every contract by content digest, so `emit` is a
pure function of the bytes in front of it — which is what makes the pipeline a shareable artifact
rather than a recipe for rebuilding one.

The edit reaches the tool. `main.nf`:

```groovy
STAR_ALIGN(TRIMGALORE.out.reads, STAR_GENOMEGENERATE.out.index, ch_annotation_gtf, true)
```

That `true` is the value edited above, carried by `via: positional`. Every setting declares the
route that carries it to the tool — `ext`, `meta`, `positional` — and a resolved value that
reaches nothing is refused at build rather than emitted (`MD0200`).

If you edit `pipeline.yml` and forget to re-emit, `emit` says so and regenerates:

```
MD0213: build/pipeline.yml has changed since the Nextflow was generated from it. Regenerating.
```

## 6. Answer a tier-4 question

`seq_platform` came out at tier 4 — nothing in the registry knows which sequencer this facility
runs. Answer it in the file, in `decisions:`:

```yaml
decisions:
- key: star_align.seq_platform
  tier: 4
  human_override: ILLUMINA
  override_reason: every run in this facility is on a NovaSeq X; there is no other sequencer here
```

and set the setting's `value:` to match. Re-emit, and it reaches the tool:

```groovy
withName: STAR_ALIGN { ext.args = { "--readFilesCommand zcat --outSAMattrRGline 'ID:${meta.id}' 'SM:${meta.id}' 'PL:ILLUMINA'" } }
```

**The tier stays 4 for ever.** A human answering an ambiguous question does not make the question
unambiguous; it records who answered it and why. What clears is the review, not the tier — that
is issue #10, and answering a question by silently relabelling it tier 2 is exactly what the four
tiers exist to prevent.

`override_reason` is the only field in the whole system written by the person answering, in the
artifact, after resolution — the tenth and newest free-text field on the egress boundary
(invariant 14). Before it existed, `upgrade` replaced what a reviewer wrote with *"selected the
first of 1 candidates without judgement"* (audit A77).

**The setting's own `why.reason` must be updated too, and `MD0223` insists on it.** Setting
`value:` and leaving the resolver's *"no rule covered … please review"* beside it is refused:

```
mendel: MD0223: a value was edited and the reason beside it was not.
  star_align.seq_platform: a human answered this tier-4 question with 'ILLUMINA', and the
  reason beside it is still the resolver's — "no rule covered 'seq_platform'; selected the
  first of 1 candidates without judgement — please review". Put your reasoning in the
  decision's `override_reason`, and make `why.reason` say the override answered it.
```

So the answer is written in **two places, deliberately**: `override_reason` in `decisions:` is
your reasoning, preserved across `upgrade`; `why.reason` beside the value is what a reader meets
first, and it must not still be the resolver's. Set `why.for_value` to the value you chose, and
`emit` accepts it.

Until 2026-08-16 it did not insist. `MD0223` skipped any setting whose `for_value` was `null` —
which a pre-1.14 file has, and so does a tier-4 value nothing resolved — so the one case where a
human is most likely to be editing was the one case the check could not see. That was
[issue #48](https://github.com/comeni-project/Comeni-Labs/issues/48).

## 7. Re-resolve against a moved registry

```bash
uv run mendel upgrade build/pipeline.yml --dry-run
```

```
the generated pipeline differs: main.nf
  CHANGED   star_align.seq_platform (reason): no rule covered 'seq_platform'; selected the first
            of 1 candidates without judgement — please review -> every run in this facility is on
            a NovaSeq X; there is no other sequencer here  (tier 4) the value is unchanged; what
            it is justified by is not
  CHANGED   star_align.star_ignore_sjdbgtf: True -> False  (tier 2) Align *with* the annotation. …
1 decisions replayed, 0 newly asked
```

Two different things happened there, and the difference is the whole point of the verb:

- **The tier-4 answer was replayed.** `1 decisions replayed, 0 newly asked` — the recorded
  `human_override` was applied again rather than the question being put a second time. That is how
  determinism survives having a judgement in the loop (invariant 9).
- **The tier-2 hand edit was re-derived away.** `upgrade` resolves from the registry, so a value a
  rule or a convention owns goes back to what the registry says. `emit` keeps your edit; `upgrade`
  re-decides it. If an edit must survive re-resolution, it belongs in a rule or an override, not
  in the value.

`--dry-run` writes nothing. Without it, `--out` gets the upgraded pipeline.

## Where to go next

| | |
|---|---|
| [`reference/pipeline-schema.md`](../reference/pipeline-schema.md) | every field of the file above |
| [`reference/diagnostics.md`](../reference/diagnostics.md) | every code, and whether it refuses |
| [`concepts/tiers.md`](../concepts/tiers.md) | what the four tiers commit you to |
| [`concepts/privacy-and-egress.md`](../concepts/privacy-and-egress.md) | the four doors, and what may cross them |
| [`writing-a-rule.md`](writing-a-rule.md) | how to make a choice depend on measured data |
