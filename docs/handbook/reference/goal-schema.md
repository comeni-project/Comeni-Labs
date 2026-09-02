# Goal schema

A goal says **what you have, what you want, and what your data looks like**. It never says which
tools to use — that is what Mendel works out.

```yaml
# examples/rnaseq-goal.yml
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

Pass it with `mendel build --goal <file>`.

**There is nowhere to put a filename, a path or a sample name**, and that is enforced rather
than encouraged. A goal is a *shape*. What leaves the platform on the build path, and when, is
its own page — not yet written.

## Fields

Model: `mendel_resolver.goal.Goal`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `have` | [input] | `[]` | the types you already hold |
| `want` | [type id] | `[]` | the types you want produced |
| `constraints` | object | empty | states you require, and parameters you are fixing |
| `profile` | object | empty | measured or asserted facts about your data |

### `have` — one entry per type you hold

Model: `comeni_core.goal.asked.GoalInput`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `type_id` | string | *required* | the type, e.g. `fastq.reads` |
| `name` | string \| null | `null` | the channel name, when you hold two of one type |
| `states` | {string} | `{}` | states this input already carries, e.g. `[trimmed]` |

`name` matters when a pipeline takes two channels of the same type. Naming them is what makes
them two parameters rather than one.

### `want` — the types you want at the end

A list of type ids. Everything between `have` and `want` is what routing works out.

### `constraints`

Model: `comeni_core.goal.asked.Constraints`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `required_states` | [required-states] | `[]` | states an output must carry |
| `params` | [param-override] | `[]` | a parameter you are fixing yourself |

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

**A mapping is the natural way to write this, and it works:**

```yaml
constraints:
  required_states:
    counts.matrix: [gene_level]
```

Internally that becomes a list. The ergonomic form to *write* and the safe representation to
*store* are different decisions, and this keeps them from being the same one.

### `profile` — what your data looks like

Model: `comeni_core.goal.profile.DataProfile`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `measurements` | [measured] | `[]` | one entry per declared measurement |

Model: `comeni_core.goal.profile.Measured`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `measurement` | string | *required* | a declared measurement id, e.g. `read_length` |
| `value` | int \| float \| bool \| string | *required* | the value |
| `source` | enum | asserted | how it was obtained |
| `by` | string \| null | `null` | the contract that measured it, when something did |

Written as a mapping, as in the example at the top. **Only declared measurements are accepted** —
an unknown key is refused, which is what stops `profile: {sample_name: ...}` from ever building.

`source` is why this matters. A value you typed is **asserted**; a value a tool produced is
**measured**. Both build, and the difference travels all the way into the reason beside every
choice that read it:

```
rule implementation:alignment where read_length is 150, asserted, not measured: ...
```

Measuring your data is how you turn the first into the second.

## See also

- [Driving Mendel](../your-first-pipeline.md) — the loop this file starts
- [Measurement schema](../../registry/reference/measurement-schema.md) — what may appear under
  `profile`
- [`pipeline.yml`](pipeline-schema.md) — what a goal turns into
