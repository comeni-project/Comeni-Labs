# Contract schema

A contract declares **one tool**: what it consumes, what it produces, what it can be told, and
how to call it.

It is a hand-written binding to a foreign, dynamically-typed unit — a Nextflow process somebody
else wrote. Nothing in that process is typed, so the contract is the only place the two can be
compared, and `mendel build` refuses to emit if they disagree.

```yaml
# registry/tools/nf-core/samtools/sort/contract.yml
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
| `provenance` | object | *required* | where this came from and who approved it |

## `consumes` — input ports

Model: `comeni_core.declared.contract.InputPort`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | *required* | the port name |
| `type_id` | string | `""` | the type it accepts |
| `state_required` | {string} | `{}` | states the input **must** carry, or it does not match |
| `state_required_conventional` | {string} | `{}` | states convention says it should carry — the resolver will **add a step** to get them |
| `state_conventional_because` | string | `""` | why that convention. Required when the above is set |
| `state_preferred` | {string} | `{}` | states that rank a candidate higher without excluding others |
| `accepts` | [alternative] | `[]` | other types this port will take |
| `prefer` | {string} | `{}` | which alternative to prefer |
| `cardinality` | enum | one | whether the port takes one or many |

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
| `state` | {string} | `{}` | states the output carries |

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
| `join` | object \| null | `null` | how several ports combine into one channel |

**A contract port is not a process argument.** Only one of six spine processes matches its port
count: `featurecounts` takes one channel carrying two ports; `samtools/sort` takes three, of
which two model nothing.

`empty` carries a **width** because Nextflow matches arity — a 2-tuple in a 3-tuple slot dies on
*"Path value cannot be null"*. And `because` is required on it because `-stub-run` cannot see a
hollow input: nf-core stubs never read their inputs, so a process handed nothing where a genome
belongs is exactly as green as one handed a genome. Two shipped that way.

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

`mendel explain MD0105` for the long form; [all codes](diagnostics.md).

## See also

- [Writing a contract](../guides/writing-a-contract.md) — the walkthrough
- [Driving the forge](../guides/writing-a-contract.md) — how a contract gets drafted
- [Vocabulary schema](vocabulary-schema.md) — the types these ports name
- [Routing](../concepts/routing.md) — how one of these gets picked
