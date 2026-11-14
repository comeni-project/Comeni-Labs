# Contract schema

A contract declares **one tool**: what it consumes, what it produces, what it can be told, and
how to call it.

It is a hand-written binding to a foreign, dynamically-typed unit — a Nextflow process somebody
else wrote. Nothing in that process is typed, so the contract is the only place the two can be
compared, and `mendel build` refuses to emit if they disagree.

```yaml
# registry/tools/nf-core/samtools/sort/contract.yml
declares: contract
id: nf-core/samtools/sort@1.24
roles: [bam_sorting]
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam}]
produces: [{name: bam, type_id: alignment.bam::coordinate_sorted, format: [bam]}]
params:
  - name: index_format
    default: bai
    domain: {kind: enum, values: [bai, csi]}
    because: "BAI, not CSI. Every downstream tool in this spine reads BAI…"
    via: positional
priority: 0
nf_inputs:
  - {ports: [bam]}
  - {empty: 3, because: "the reference is only needed to write CRAM; this emits BAM"}
  - {param: index_format}
container: community.wave.seqera.io/library/htslib_samtools:1.24--d697cfb9dce007cd
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-03"}
```

## Fields

Model: `comeni_core.declared.contract.ModuleContract`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | *required* | `<namespace>/<tool>@<version>`. The part before `@` is the **module key** |
| `nf_process` | string | *required* | the process name, exactly as `main.nf` spells it |
| `nf_include` | string | *required* | the include path, relative to the emitted pipeline |
| `consumes` | [input port] | `[]` | what it needs |
| `produces` | [output port] | `[]` | what it makes |
| `params` | [param] | `[]` | what it can be told |
| `roles` | [string] | `[]` | the jobs it can fill, e.g. `bam_sorting` |
| `priority` | integer | `0` | breaks a routing tie. Higher wins |
| `priority_because` | string | `""` | why. A priority with no reason is a silent preference |
| `container` | string \| null | `null` | the image. Take the **last** quoted string in `main.nf`'s ternary |
| `nf_inputs` | [nf-input] | `[]` | the real call signature — see below |
| `ext_args` | string \| object | `""` | flags the module always needs, via `task.ext.args` |
| `constraints` | [constraint row] | `[]` | what the tool allows between its inputs and params — see below |
| `groups` | [group] | `[]` | inputs or params that go together — see below |
| `provenance` | object | *required* | where this came from and who approved it |

## `consumes` — input ports

Model: `comeni_core.declared.contract.InputPort`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | *required* | the port name |
| `type_id` | string | `""` | the type it accepts |
| `state_required` | {string} | `{}` | states the input **must** carry, or it does not match. Written in the type, `alignment.bam::coordinate_sorted`; a file that writes this key is refused (`MD0110`) |
| `state_required_conventional` | {string} | `{}` | states convention says it should carry — the resolver will **add a step** to get them |
| `state_conventional_because` | string | `""` | why that convention. Required when the above is set |
| `state_preferred` | {string} | `{}` | states that rank a candidate higher without excluding others |
| `accepts` | [alternative] | `[]` | other types this port will take |
| `prefer` | {string} | `{}` | which alternative to prefer |
| `grain` | `study` \| `sample` | the type's | what one invocation reads: one item for the study or one per sample |
| `many` | boolean | `false` | `true` gathers every item of a finer grain into one invocation, with `grain: study`: MultiQC reads every sample's report at once. Without `grain: study` it is refused (`MD0331`) |
| `by` | measurement id | — | with `many: true`, gather per value of this `key` rather than over the study: a co-assembler reads every sample of one group in one call, each group as soon as its own samples are done (`MD0343`) |
| `select` | {measurement: condition} | — | only the samples meeting these conditions, written as a rule's `when`: a tumour port selects `{status: tumor}` (`MD0344`) |
| `parts` | boolean | `false` | the process may run once per part of this port's item: the build splits each sample before the step and merges each output after it, when the registry has a splitter (role `splitting`) for the type and a merger (role `merging`) for each output read, and the step's only per-sample input is this port. A person may keep the step whole (`constraints.whole`). Not with `many`, `by`, `select` or `grain: study` (`MD0346`) |
| `required` | boolean | `true` | `false` for an input the process can run without. Left out, it gets `[]` in its tuple position; an `nf_inputs` entry whose ports are all optional declares `absent` |

**The three requirement levels are the point.** `state_required` excludes; `state_preferred`
ranks; `state_required_conventional` *causes work to happen* — it is why asking for an alignment
gets you a trimmer you never mentioned, and why the reason beside that trimmer names the
convention rather than a judgement.

## `produces` — output ports

Model: `comeni_core.declared.contract.OutputPort`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | *required* | **the emit label** — read as `PROCESS.out.<name>` |
| `type_id` | string | *required* | the semantic type it produces |
| `state` | {string} | `{}` | states the output carries. Written in the type, `alignment.bam::coordinate_sorted`; a file that writes this key is refused (`MD0110`) |
| `format` | {string} | `{}` | the file formats it writes, from `main.nf`, or `folder`. Shown to people and checked (`MD0109`); takes no part in matching |
| `produced_when` | object \| null | `null` | when the process writes it: `null` is always, otherwise a condition, e.g. `{given.fasta: present}` |
| `fans_out` | `part` | — | one item in becomes several out, each a part of it. Only a splitter (role `splitting`) declares it, on an output of the one type it reads (`MD0346`). A splitter and a merger are placed around the steps that need them and never routed as producers |

**`name` is not a name for the thing** — it is the Nextflow channel the compiler reads.
`type_id` carries the meaning. Three contracts got this backwards and `MD0105` found all three;
each was latent only because no goal had yet routed to that port.

## `params` — what a tool can be told

Model: `comeni_core.declared.contract.Param`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | *required* | the parameter |
| `via` | enum | *required* | **how the value reaches the tool** — `ext`, `positional`, `meta` |
| `tier_hint` | integer \| null | `null` | the tier this exits at when nothing else decides |
| `domain` | object \| null | `null` | the permitted values |
| `default` | any | `None` | the value when no rule fires |
| `because` | string | `""` | why that default. This becomes the `why:` in `pipeline.yml` |
| `key` | string \| null | `null` | the `ext.args` key, when `via: ext` |
| `template` | string \| null | `null` | how the value is spelled on the way in |

**`via` is what makes a value real.** A resolved value with nowhere to go is *deadness* — nf-core
modules read `task.ext.args` and `meta`, and a `params.<x>` in the emitted workflow is read by
nothing. A setting whose route reaches no tool is refused rather than emitted.

## `nf_inputs` — the real call signature

Model: `comeni_core.declared.contract.NfInput`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `ports` | [string] | `[]` | which ports fill this argument |
| `literal` | any | `None` | a constant |
| `param` | string | `""` | a parameter's value |
| `because` | string | `""` | why. **Required for `empty`** |
| `empty` | integer | `0` | an empty slot, and **the tuple width** it must have |
| `join` | string \| object \| null | `null` | how several ports combine into one channel: `broadcast` or `by_sample` for every port after the first, or a map giving each its own. Two ports may also meet `by_key` (one sample of each per value of `key`: a patient's tumour and normal) or `by_ref` (each sample of the first port with the item of the sample its `key`, a `sample_ref`, names: a ChIP sample and its control) |
| `key` | measurement id | — | for `by_key`, a `key`; for `by_ref`, a `sample_ref` (`MD0344`). A patient with two normals, or none, stops the run naming the patient |
| `absent` | integer | `0` | the tuple width passed when every port of this entry is left out. Required when all its ports are optional, refused when any is required (`MD0601`) |

**A contract port is not a process argument.** Only one of six spine processes matches its port
count: `featurecounts` takes one channel carrying two ports; `samtools/sort` takes three, of
which two model nothing.

**A shared slot** keeps the tuple `main.nf` declares, even when some of its files are optional
(#464). A file left out passes `[]` in its own position, so no `absent` is needed unless every
file in the slot can be left out. Each later port joins by the entry's `join`, or by its own:

```yaml
# gatk4/haplotypecaller: tuple val(meta), path(input), path(input_index), path(intervals),
# path(dragstr_model). The index and DRAGstr model are per sample; the intervals are one file
# for the run; intervals and dragstr_model are optional.
nf_inputs:
  - ports: [input, input_index, intervals, dragstr_model]
    join: {input_index: by_sample, intervals: broadcast, dragstr_model: by_sample}
```

When the slot's first port is optional, the first port that is on stands in for it, so its later
ports must all join the same way (`MD0601`).

`empty` carries a **width** because Nextflow matches arity — a 2-tuple in a 3-tuple slot dies on
*"Path value cannot be null"*. And `because` is required on it because `-stub-run` cannot see a
hollow input: nf-core stubs never read their inputs, so a process handed nothing where a genome
belongs is exactly as green as one handed a genome. Two shipped that way.

## `constraints` and `groups` — what a tool allows

Models: `comeni_core.declared.contract.ConstraintRow`, `Group`.

A constraint is a fact about the tool: when its condition holds, these inputs or params must or
must not be given. It never chooses; choosing is a rule's.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `when` | object | `{}` | the condition, in rules' syntax, over `given.<input>`, `param.<name>`, `type.<input>`: the type connected to an input with `accepts`, as one type id, `{in: [...]}` or `{not: ...}`, and `fact.<measurement>`: a fact each sample has |
| `requires` | [string] | `[]` | inputs or params that must be given when `when` holds |
| `forbids` | [string] | `[]` | inputs or params that must not be given |
| `because` | string | *required* | why, in a sentence a person reads |
| `cite` | string | `""` | where the tool says so |

A group is shorthand for rows: `kind` is `one_of` (exactly one member), `any_of` (at least one)
or `all_or_none`, over at least two `members`, with an optional `when` and a required `because`.

```yaml
# quast: the GFF is read only against a reference
constraints:
  - {when: {given.gff: present}, requires: [fasta],
     because: "QUAST reads --features only against a reference (-r)"}
# salmon/quant: which inputs it needs depends on the type its reads were connected with
constraints:
  - {when: {type.reads: alignment.bam}, requires: [transcript_fasta], forbids: [index],
     because: "alignment mode quantifies BAM reads against the transcripts, not an index"}
  - {when: {type.reads: fastq.reads}, requires: [index],
     because: "mapping mode maps FASTQ reads against a salmon index"}
# gatk4/haplotypecaller: the VCF and its index go together
groups:
  - {kind: all_or_none, members: [dbsnp, dbsnp_tbi],
     because: "the tabix index is read with the VCF it indexes"}
```

Every name must be one this contract declares, and a `type.` condition names only types its
input accepts (`MD0602`). The load-time check tries each type an input accepts as its own
case, and refuses a type no combination allows (`MD0612`).

A row may test a sample's fact, `fact.<measurement>`, for a measurement describing a per-sample
input (`MD0336` otherwise; only constraint rows may, not groups or `produced_when`). It is then
settled per sample:

- a row some samples break: a value a default or a rule gave is left unset for those samples; a
  person's or a model's value stops such a sample before the step runs, naming it and the rule;
- a row every sample is known to break: a default is not passed at all, and a person's or a
  model's value is refused (`MD0337`).

```yaml
# fastp merges only paired reads
constraints:
  - {when: {fact.paired: false}, forbids: [save_merged], because: "merging needs both reads"}
```

The step card lists these as "checked for each sample before this step runs".

## `provenance`

Model: `comeni_core.declared.contract.Provenance`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `source` | string | *required* | where the draft came from, e.g. `nf-core-meta-yml` |
| `drafted_by` | string | *required* | what produced it — `hand`, or a model |
| `approved_by` | string | *required* | **a person.** Nothing lands unreviewed |
| `approved_at` | string | *required* | the date |

## `ext_args`

Model: `comeni_core.declared.contract.ContractExtArgs`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `template` | string | `""` | flags composed into `task.ext.args` |
| `because` | string | `""` | why the tool always needs them |

May also be written as a bare string when there is nothing to explain.

## What is checked

`mendel build` and `mendel conformance` compare every contract against its module — the `main.nf`
and `meta.yml` under `tools/<org>/<tool>/module/` in the same layer. A disagreement exits `2` and
emits nothing.

| | |
|---|---|
| `MD0101` | `nf_process` is not what the module declares |
| `MD0104` | the contract and the module disagree |
| `MD0105` | a `produces[].name` is not an emit the module has |

`mendel explain MD0105` for the long form; [all codes](../pipelines/diagnostics.md).

## See also

- [Writing a contract](../../how-to/registry/add-tool.md) — the walkthrough
- [Vocabulary schema](vocabulary-schema.md) — the types these ports name
- [Routing](../../explanation/tool-selection.md) — how one of these gets picked
