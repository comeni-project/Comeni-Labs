# Adding a tool

The platform can only use tools it has been told about. Telling it about one is a YAML file —
no Python — and from then on the tool can be chosen, wired up and justified automatically
wherever it fits.

The file is called a **contract**: what the tool takes, what it produces, and what it can be
told.

Full field list: [reference/contract-schema.md](../reference/contract-schema.md).

## The shape

One contract per file, opening with `declares: contract`. **Where you put it is free** — the
loader reads that line, not the path — and the convention is
`<layer>/tools/<namespace>/<tool>/<name>.contract.yml`, so a tool's files sit together.
Here is a complete one:

```yaml
declares: contract
id: nf-core/samtools/sort@1.21.0
roles: [bam_sorting]
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]
params:
  - name: index_format
    default: bai
    domain: {kind: enum, values: [bai, csi]}
    because: "BAI, not CSI. Every downstream tool in this spine reads BAI and it is nf-core's own default."
    via: positional
priority: 0
nf_inputs:
  - {ports: [bam]}
  - {empty: 3, because: "the reference is only needed to write CRAM; this emits BAM"}
  - {param: index_format}
container: community.wave.seqera.io/library/htslib_samtools:1.24--d697cfb9dce007cd
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-03"}
```

That is the file in the registry, copied. **`because` on `{empty: 3}` is not optional here** —
an empty slot that the module expects a *file* in is refused without one, because `-stub-run`
cannot see a hollow input and would go green either way.

Read that as a sentence: *SAMTOOLS_SORT takes a BAM in any state and gives you back one
that is coordinate-sorted.* That sentence is the entire reason the router can place it.

## The part that does the work

`state` is the semantic overlay, and it is what `nf-core`'s `meta.yml` does not give you.
Upstream, `samtools/sort`'s output and `star/align`'s `bam_unsorted` are both
`type: file, pattern: "*.bam"` — identical. "Sorted" exists only in an English
description, so a router reading `meta.yml` cannot tell them apart.

Declaring `state: [coordinate_sorted]` is the missing ~40%, and writing it is the actual
work of authoring a contract. Everything else is transcription.

States are **closed**: every one must be declared in that type's vocabulary file, or the
contract fails to load. A typo is an error at load time rather than a module that
mysteriously never gets picked.

```yaml
# <layer>/types/alignment.bam.yml
declares: vocabulary
id: alignment.bam
states: [coordinate_sorted, name_sorted, deduplicated, filtered, indexed]
```

## Ports are not process arguments

This trips up everyone once, so it is worth the paragraph.

A **port** is semantic: a typed thing the module consumes. A **process input** is
plumbing: one channel in the Nextflow call signature. They do not correspond. Of the twelve
contracts in the registry, five differ:

| Process | Ports | Channels |
|---|---|---|
| `SUBREAD_FEATURECOUNTS` | 2 | 1 |
| `SAMTOOLS_SORT` | 1 | 3 |
| `HISAT2_BUILD` | 2 | 3 |
| `STAR_ALIGN` | 3 | 4 |
| `HISAT2_ALIGN` | 2 | 4 |

`nf_inputs` declares the real call signature, one entry per channel, in order:

- `{ports: [bam]}` — this channel carries that port
- `{ports: [bam, annotation]}` — two ports share one channel, combined into a tuple
- `{literal: bai}` — a plain `val` with no data dependency
- `{empty: 3}` — a placeholder for an input the type system does not model

`empty` is a **tuple width**, not a count of channels. Nextflow matches arity, so a
2-tuple handed to a slot declared `tuple val(meta), path(fasta), path(fai)` dies at launch
with `Path value cannot be null`. `samtools/sort` wants 3; most want 2.

Omit `nf_inputs` entirely and you get one channel per port, in order — right for the
simple majority.

## Ports that accept more than one thing

Sometimes a tool genuinely takes either of two inputs:

```yaml
consumes:
  - name: reads
    accepts:
      - {type_id: alignment.bam,  states: [coordinate_sorted]}
      - {type_id: alignment.cram, states: [coordinate_sorted]}
```

Order is your preference, and it is first-match-wins: the router tries the BAM branch and
only falls to CRAM if nothing can produce a BAM. A port declares `type_id` **or**
`accepts`, never both and never neither.

`prefer` breaks ties *among sources satisfying the alternative that matched*. It never
promotes a later alternative over an earlier one and never causes a module to be inserted.

## Read the module, not the plan

Two rules, both learned the expensive way:

**The process name comes from `main.nf`.** It is `SUBREAD_FEATURECOUNTS`, not
`FEATURECOUNTS`.

**The container comes from `main.nf` too** — take the *last* quoted string in the
`container` ternary. nf-core 4.x mostly uses `community.wave.seqera.io`, not `quay.io`.

```bash
grep -A2 "process SUBREAD_FEATURECOUNTS" \
  registry/tools/nf-core/subread/featurecounts/module/main.nf
```

`tests/test_spine_contracts.py` compares every contract against the module on disk, so a
guess fails in milliseconds instead of at pipeline launch.

## Check it

```bash
uv run pytest tests/test_spine_contracts.py -q
uv run mendel build --goal your-goal.yml --out build/ --gate stub
```

Loading is itself a check: an undeclared state, a container that disagrees with the
module, or an `nf_inputs` arity that does not match are all load-time errors.

## Priority, and when to use it

`priority` breaks ties between contracts that are otherwise equally good, and a choice
settled that way is recorded as **tier 2, convention** — a documented default. Use it to
say "this registry prefers STAR", not to express something that depends on the data. That
is what a rule is for, and a rule exits at tier 3 with a citation attached.
