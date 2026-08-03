# Vocabulary schema

`<layer>/vocabularies/<type_id>.yml`, globbed non-recursively. **The filename is the type
id** — `alignment.bam.yml` declares `alignment.bam`.

Model: `comeni_core.vocabulary.Vocabulary`.

## Fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `states` | [string] | `[]` | every state this type may carry. Closed. |
| `entry_channel` | string \| null | `null` | Groovy expression producing this type when nothing upstream does |

```yaml
# alignment.bam.yml
states: [coordinate_sorted, name_sorted, deduplicated, filtered, indexed]
```

```yaml
# fastq.reads.yml
states: [trimmed, deduplicated, subsampled]
entry_channel: "Channel.fromFilePairs(params.input, checkIfExists: true).map { id, reads -> [ [id: id], reads ] }"
```

## Vocabularies are closed

A contract naming a state this file does not declare **fails to load**:

```
UnknownStateError: 'sorted_by_coord' is not a declared state for 'alignment.bam';
allowed: ['coordinate_sorted', 'deduplicated', 'filtered', 'indexed', 'name_sorted']
```

This is what makes routing provable rather than plausible. `coordinate_sorted` means one
thing across the entire registry, and a typo is an error at load rather than a module that
mysteriously never gets selected.

New states arrive as reviewed data changes, never code changes.

## Naming

Dotted, hierarchical, and **injective after the compiler mangles it**:
`fastq.reads` → `ch_fastq_reads`.

Use the full path. Naming a channel after the last segment alone is not injective —
`qc.report` and `multiqc.report` both became `ch_report`, one assignment shadowed the
other, and two ports were silently fed the same channel.

## Entry channels

A type that nothing in the pipeline produces has to come from somewhere. `entry_channel`
is that Groovy expression, and it belongs here rather than in the compiler because
`mendel-compiler` has no built-in idea what a FASTQ is. The same compiler has to emit calls
for a containerised tool it has never seen.

The expression must produce Nextflow's `[meta, files]` shape. Any `params.<name>` it
mentions is discovered by the emitter and declared in the generated `nextflow.config` —
so a type that declares its own entry channel automatically declares its own parameter.

Omit it and you get:

```groovy
Channel.fromPath(params.<last_segment>, checkIfExists: true).map { f -> [ [:], f ] }
```

For a port with several alternatives, the **first** alternative's type supplies the entry
channel: nothing upstream has narrowed the choice, so the pipeline asks for the one the
contract names first.

## Derived measurement types

`Vocabulary.with_measurements()` adds a stateless `measurement.<id>` type per declared
measurement. **Do not write these by hand** — the measurement file already says what the
measurement is, and a second file repeating it is a thing to drift.

They carry no states, so `vocab.validate("measurement.strandedness", ["forward"])` raises.
An enum's *values* are not states.

## Layer stacking

Keyed on type id; a higher layer replaces the whole entry, states and entry channel
together.

Load order matters: measurements must load before the vocabulary, because the derived
`measurement.*` types have to exist before contracts are validated against them. Use
`mendel_resolver.layers.load()` rather than assembling this by hand.

## The eight shipped types

| Type | States | Entry channel |
|---|---|---|
| `fastq.reads` | `trimmed`, `deduplicated`, `subsampled` | `fromFilePairs(params.input)` |
| `annotation.gtf` | — | `fromPath(params.gtf)` |
| `alignment.bam` | `coordinate_sorted`, `name_sorted`, `deduplicated`, `filtered`, `indexed` | — |
| `alignment.bai` | — | — |
| `counts.matrix` | `gene_level`, `transcript_level`, `normalised` | — |
| `qc.report` | `aggregated` | — |
| `genome.index.star` | — | — |
| `genome.index.hisat2` | — | — |
| `profile.yml` | — | — |

`alignment.bai` exists because an index is **not** a BAM. Declaring it
`alignment.bam[indexed]` is what once let the router hand featureCounts a `.bai` file —
valid Nextflow, no flag raised, and invisible to `-stub-run` because nf-core stubs never
read their inputs.
