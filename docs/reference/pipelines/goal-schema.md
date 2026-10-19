# Starter file (goal schema)

A starter says **what you want and what you know about your data**. It never says which tools
to use — that is what Mendel works out. It is a [`pipeline.yml`](pipeline-schema.md) with only
its top half, `intent` and `facts`; building it writes the rest.

```yaml
# examples/rnaseq.yml
version: 7
intent:
  want: [counts.matrix]
  constraints:
    required_states:
      - {type_id: counts.matrix, states: [gene_level]}
facts:
  inputs:
    - {type_id: fastq.reads}
    - {type_id: annotation.gtf}
    - {type_id: genome.fasta}
  measurements:
    - {measurement: n_samples, value: 12, source: said}
    - {measurement: paired, value: true, source: said}
    - {measurement: read_length, value: 150, source: said}
    - {measurement: strandedness, value: reverse, source: said}
```

Build it with `mendel build <file>`. A file that also has `steps:` is a whole pipeline, not a
starter: re-resolve that with `mendel upgrade`.

**There is nowhere to put a filename, a path or a sample name**, and that is enforced rather
than encouraged. A goal is a *shape*. What leaves the platform on the build path, and when, is
its own page — not yet written.

## Fields

Model: `comeni_core.artifact.starter.Starter`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `version` | 7 | 7 | the `pipeline.yml` schema version |
| `intent` | object | *required* | what is wanted: `want` and `constraints`, below |
| `facts` | object | *required* | what is known: `inputs` and `measurements`, below |
| `intent.want` | [type id] | `[]` | the types you want produced |
| `intent.constraints` | object | empty | states you require, parameters you fix, tools you choose |
| `facts.inputs` | [input] | `[]` | the types you already hold |
| `facts.measurements` | [measured] | `[]` | what is known about your data, and where it came from |

### `facts.inputs` — one entry per type you hold

Model: `comeni_core.goal.asked.GoalInput`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `type_id` | string | *required* | the type, e.g. `fastq.reads` |
| `name` | string \| null | `null` | the channel name, when you hold two of one type |
| `states` | {string} | `{}` | states this input already carries, e.g. `[trimmed]` |

`name` matters when a pipeline takes two channels of the same type. Naming them is what makes
them two parameters rather than one.

### `intent.want` — the types you want at the end

A list of type ids. Everything between the inputs and what you want is what routing works out.

### `intent.constraints`

Model: `comeni_core.goal.asked.Constraints`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `required_states` | [required-states] | `[]` | states an output must carry |
| `params` | [param-override] | `[]` | a parameter you are fixing yourself |
| `producers` | [producer-pin] | `[]` | a tool you chose for a step; left out of the file when empty |

`required_states` is what turns *get me a count matrix* into *get me a gene-level count matrix*.
Without it, any producer of the type matches.

Model: `comeni_core.goal.asked.RequiredStates`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `type_id` | string | *required* | the type the requirement applies to |
| `states` | [string] | `[]` | states it must carry |

Model: `comeni_core.goal.asked.ParamOverride`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | *required* | the parameter |
| `value` | int \| float \| bool \| string | *required* | what to set it to |

Model: `comeni_core.goal.asked.ProducerPin`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `site` | [site] | *required* | the place in the pipeline: the type a step makes, with its states |
| `contract` | string | *required* | the tool to use there, e.g. `nf-core/hisat2/align@2.2.2` |

Model: `comeni_core.goal.asked.Site`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `type_id` | string | *required* | the type the step makes |
| `states` | [string] | `[]` | the states asked of it there |

A tool you choose is used in place of the engine's pick. When they differ, the step is marked
tier 4 and yours, with the engine's pick and its reason kept beside it. A tool that applies
nowhere (it cannot make that type, or the site is not one this pipeline asks for) is reported by
`mendel build`, and `mendel upgrade` refuses (`MD0230`).

**A mapping is the natural way to write this, and it works:**

```yaml
constraints:
  required_states:
    counts.matrix: [gene_level]
```

Internally that becomes a list. The ergonomic form to *write* and the safe representation to
*store* are different decisions, and this keeps them from being the same one.

### `facts.measurements` — what your data looks like

One entry per declared measurement.

Model: `comeni_core.goal.profile.Measured`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `measurement` | string | *required* | a declared measurement id, e.g. `read_length` |
| `value` | int \| float \| bool \| string | *required* | the value |
| `source` | enum | `said` | how it was obtained: `said` (a person stated it), `measured`, `model` (read by AI) |
| `by` | string \| null | `null` | the contract that measured it, when something did |
| `pieces` | [string] | `[]` | the inspector pieces that measured an uploaded sample, e.g. `[fastq@1.1.0, read_length@1.0.0]`; left out when empty, and never set together with `by` |
| `evidence` | object \| null | `null` | how much the pieces read: `records`, `rows`, `share` (counts only, each written only when known, at least one); left out when there is none |

**Only declared measurements are accepted** — an unknown one is refused, which is what stops a
`sample_name` from ever building.

`source` is why this matters. A value you typed (`said`) is **asserted**; a value a tool produced is
**measured**. Both build, and the difference travels all the way into the reason beside every
choice that read it:

```
rule implementation:alignment where read_length is 150, asserted, not measured: ...
```

Profiling and measurement support is how you turn the first into the second.

## See also

- [Your first pipeline](../../tutorials/first-pipeline.md) — the app loop this file supports
- [Measurement schema](../registry/measurement-schema.md) — what may appear under
  `facts.measurements`
- [`pipeline.yml`](pipeline-schema.md) — what a starter turns into
