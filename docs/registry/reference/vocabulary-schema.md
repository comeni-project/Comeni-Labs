# Vocabulary schema

A vocabulary file declares **one type**: what it is called, which states it may carry, and how
it enters a pipeline when nothing upstream produces it.

Types are what routing matches on. `fastq.reads` and `alignment.bam` are types; `trimmed` and
`coordinate_sorted` are states of them.

```yaml
# registry/types/fastq.reads.yml
declares: vocabulary
id: fastq.reads
states: [trimmed, deduplicated, subsampled]
sample_columns: 2
param: input
entry_channel: "Channel.fromFilePairs(params.{param}, checkIfExists: true).map { id, reads -> [ [id: id], reads ] }"
test_data:
  - "https://.../SRR6357070_1.fastq.gz"
  - "https://.../SRR6357070_2.fastq.gz"
```

**Where the file sits is free.** The public registry keeps general types in `types/` and puts a
type beside the only tool that produces it — `genome.index.star.type.yml` lives in
`tools/nf-core/star/`. The loader reads `declares:`, not the path.

**`id:` is required**, and `MD0012` refuses a file without one. The filename used to be the id;
once a file could live anywhere, `align.type.yml` in a tool folder would have silently declared
a type called `align.type`.

## Fields

Model: `comeni_core.declared.vocabulary.TypeDeclaration`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | *required* | the type id. Validated, because it is emitted as a channel name |
| `states` | [string] | `[]` | every state this type may carry. **Closed** — an undeclared state fails to load |
| `sample_columns` | integer | `1` | how many samplesheet columns one sample occupies. **1 or 2** |
| `scope` | string | `sample` | `sample` or `run` — how many arrive, relative to the run |
| `entry_channel` | string \| null | `null` | Groovy producing this type when nothing upstream does |
| `param` | string \| null | `null` | the parameter `entry_channel` reads. Defaults to the id's last segment |
| `test_data` | string \| [string] \| null | `null` | a pinned example, for the generated `test` profile |

### `states` is closed, and that is the point

A contract using a state no vocabulary declares **fails to load**. New states arrive by review,
through the forge, as a data change — never as a code change. That is what makes a state mean
the same thing in two contracts written a year apart.

### `scope` — `run` or `sample`

A reference genome is `run`: one file for the whole analysis, so it must emit as a **value**
channel. A Nextflow process with several *queue* inputs runs as many times as the shortest, so
a queue of one genome silently capped a twenty-four-sample run at one invocation.

A pipeline may override this, and the override carries a reason into `pipeline.yml` — per-sample
annotation instead of a shared one is a judgement about an experiment, and no judgement here is
silent.

### `sample_columns` is not derivable

`fastq.reads` is 2 — `fastq_1` and `fastq_2`, nf-core's convention, an empty second column
meaning single-end. `annotation.gtf` is 1.

Nothing about the id or the states says a FASTQ arrives in pairs. The entry channel says it only
by using `fromFilePairs`, which is a fact about the glob, not about the type. So it is declared.

Column **names** come from the channel rather than from here: `reads` becomes `reads_1` and
`reads_2`; a pipeline taking two GTFs gets `gtf` and `gtf_2`.

### `entry_channel` is the one place unbounded Groovy is allowed

It is emitted verbatim, and that is the designed exception rather than an oversight.

It carries **one placeholder**, `{param}`, substituted at materialisation with the channel's own
parameter. Not a template language — one substitution, matched as seven literal characters,
because `{` is legal Groovy and appears throughout these expressions already.

It used to hold a literal `params.<name>`, which fused a *pipeline* decision into a *type*: two
channels of the same type shared one parameter and were therefore one hole, whatever the pipeline
said.

## The stacked result

When layers load, all the type files merge into one object. You do not write this — it is what
the resolver reads.

Model: `comeni_core.declared.vocabulary.Vocabulary`

| Field | Type | Meaning |
|---|---|---|
| `types` | dict | every type id to its declared states |
| `displaced` | list | which layer replaced which, recorded rather than silent |
| `test_data` | dict | per type, from `test_data` above |
| `params` | dict | per type, from `param` above |
| `columns` | dict | per type, from `sample_columns` above |
| `scopes` | dict | per type, from `scope` above |
| `entry_channels` | dict | per type, from `entry_channel` above |

**Overlays extend or replace.** `states:` replaces a type's states; `add_states:` extends them.
A replacement is recorded as a `Displacement` and printed in the build's `OVERLAY` block, so an
installed overlay can never reroute a pipeline silently.

## See also

- [Registry layers](../your-labs-own-layer.md) — how a stack is assembled
- [Routing](../../handbook/how-tools-get-chosen.md) — what types and states are matched on
- [Contract schema](contract-schema.md) — what consumes and produces these types
