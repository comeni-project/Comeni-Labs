# Contract schema

`<layer>/contracts/**/*.yml`, one contract per file. Globbed recursively, so subdirectories
are free organisation.

Model: `comeni_core.contract.ModuleContract`.

## ModuleContract

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | *required* | `namespace/tool@version`. The part before `@` is the **module key**, on which shadowing is decided. |
| `nf_process` | string | *required* | the process name **as written in `main.nf`** |
| `nf_include` | string | *required* | include path in the generated pipeline, without `.nf` |
| `consumes` | [InputPort] | `[]` | what it takes, semantically |
| `produces` | [OutputPort] | `[]` | what it emits, semantically |
| `params` | [Param] | `[]` | parameters the resolver must settle |
| `priority` | int | `0` | tiebreak among equally good candidates; higher wins |
| `container` | string \| null | `null` | container URI as the module declares it, tag and all |
| `nf_inputs` | [NfInput] | `[]` | the real call signature; empty means one channel per port |
| `provenance` | Provenance | *required* | who drafted and approved this, and when |

## InputPort

Declare `type_id` **or** `accepts`. Both is an error; neither is an error.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | *required* | port name, referenced by `nf_inputs.ports` |
| `type_id` | string | `""` | the type consumed — single-alternative form |
| `state_required` | [string] | `[]` | states that must all hold |
| `accepts` | [Alternative] | `[]` | ordered alternatives — multi-alternative form |
| `prefer` | [string] | `[]` | tiebreak among sources satisfying the matched alternative |
| `state_preferred` | [string] | `[]` | deprecated spelling of `prefer` |
| `cardinality` | string | `"1"` | reserved; not yet interpreted |

`prefer` never causes a module to be inserted, never causes a failure, and never promotes
a later alternative over an earlier one.

## Alternative

| Field | Type | Default | Meaning |
|---|---|---|---|
| `type_id` | string | *required* | the type |
| `states` | [string] | `[]` | states that must all hold |

Alternatives are ORed in declaration order, first match wins. States within one are ANDed.
One level of disjunctive normal form, deliberately.

## OutputPort

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | *required* | port name, and the Nextflow output channel name |
| `type_id` | string | *required* | the type emitted |
| `state` | [string] | `[]` | states this output carries |

`state` is the semantic overlay that `meta.yml` does not give you, and it is what routing
depends on. Getting it right is the actual work of writing a contract.

## Param

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | *required* | parameter name; a `param:` rule targets this |
| `tier_hint` | int \| null | `null` | which tier the author expects; advisory, recorded in the ambiguity |
| `default` | scalar | `null` | a documented default. Non-null makes an unsettled parameter exit at **tier 2** rather than tier 4. |

## NfInput

One entry per channel the process declares, in order. Exactly one field is meaningful per
entry.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `ports` | [string] | `[]` | port names filling this channel, in tuple order |
| `literal` | scalar | `null` | a plain value for a `val` input with no data dependency |
| `empty` | int | `0` | **tuple width** of a placeholder for an input the type system does not model |

`empty` is a width, not a count. Nextflow matches arity: a 2-tuple handed to
`tuple val(meta), path(fasta), path(fai)` fails with `Path value cannot be null`.
`samtools/sort` needs `3`; most need `2`.

Several ports in one entry are combined into a tuple — `featurecounts` takes one channel
carrying both the BAM and the annotation.

## Provenance

| Field | Type | Meaning |
|---|---|---|
| `source` | string | where the contract came from, e.g. `nf-core-meta-yml`, `hand` |
| `drafted_by` | string | who or what drafted it |
| `approved_by` | string | the person who approved it |
| `approved_at` | string | ISO date, quoted |

All four required. Nothing writes into a registry automatically: AI may draft, a human
approves.

## Validation at load

| Check | Failure |
|---|---|
| every state declared in that type's vocabulary | `UnknownStateError` |
| every `type_id` has a vocabulary file | `UnknownTypeError` |
| a port declares exactly one of `type_id` / `accepts` | `ValueError` |
| no duplicate `id` within one layer | `ValueError` |

And in `tests/test_spine_contracts.py`, against the modules on disk:

- `nf_include` points at a real vendored `main.nf`
- `nf_inputs` length equals the process's declared input count
- `container` matches the module's `container` directive exactly
- no floating tags (`latest`, `dev`, `master`)

## Complete example

```yaml
id: nf-core/subread/featurecounts@2.0.6
nf_process: SUBREAD_FEATURECOUNTS
nf_include: modules/nf-core/subread/featurecounts/main
consumes:
  - {name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}
  - {name: annotation, type_id: annotation.gtf, state_required: []}
produces:
  - {name: counts, type_id: counts.matrix, state: [gene_level]}
params:
  - {name: strandedness, tier_hint: 3}
priority: 0
nf_inputs: [{ports: [bam, annotation]}]
container: quay.io/biocontainers/subread:2.1.1--h577a1d6_0
provenance:
  source: nf-core-meta-yml
  drafted_by: hand
  approved_by: rafael
  approved_at: "2026-08-03"
```
