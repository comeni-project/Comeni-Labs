# Goal schema

The file `mendel build --goal` reads. A goal is a **shape**, not data: there is nowhere to
put a filename, a path or a sample identifier, and a test asserts that.

Model: `mendel_resolver.goal.Goal`.

## Fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `have` | [GoalInput] | `[]` | types you already hold |
| `want` | [string] | `[]` | type ids to produce |
| `constraints` | Constraints | `{}` | states required on outputs, and pinned parameters |
| `profile` | DataProfile | `{}` | measured or asserted properties of your data |

`extra="forbid"` on every model here. An unrecognised key is a loud error rather than a
quietly carried payload — which is the mechanism, not a convention.

## GoalInput

| Field | Type | Default | Meaning |
|---|---|---|---|
| `type_id` | string | *required* | a declared type |
| `states` | [string] | `[]` | states it already carries |

Declaring `states: [trimmed]` on your FASTQs stops the router inserting a trimmer.

## Constraints

| Field | Type | Default | Meaning |
|---|---|---|---|
| `required_states` | map of type id → [string] | `{}` | states a wanted output must carry |
| `params` | [ParamOverride] | `[]` | parameters you are settling yourself |

```yaml
constraints:
  required_states:
    counts.matrix: [gene_level]
  params:
    - {name: seq_platform, value: illumina}
```

A `ParamOverride` is `{name, value}` where `value` is a scalar. It exits at **tier 1**,
source `goal` — no choice existed, because you removed it. The source field is why a
reviewer can still see that Mendel did not derive it.

`params` is a **list of declared records**, not a mapping. A mapping was tried: it was
`dict[str, Any]`, so `{seq_platform: /data/patients/PT-4471023/S1_R1.fastq.gz}` validated,
reached `main.nf` labelled tier 1 review `none`, and *suppressed* the tier-4 flag it
replaced. The build reported "0 requiring review" while carrying a patient path.

## DataProfile

Two forms. The shorthand is what you will normally write:

```yaml
profile:
  read_length: 150
  strandedness: reverse
  paired: true
```

The long form carries provenance, and is what `mendel profile` emits:

```yaml
profile:
  measurements:
    - {measurement: read_length, value: 150, source: measured, by: comeni/profile/fastqc@0.12.1}
    - {measurement: strandedness, value: reverse, source: goal}
```

### Measured

| Field | Type | Default | Meaning |
|---|---|---|---|
| `measurement` | string | *required* | a declared measurement id |
| `value` | scalar \| null | *required* | the value; `null` means not yet measured |
| `source` | `goal` \| `measured` \| `resolver` | `goal` | who established it |
| `by` | string \| null | `null` | the contract that measured it |

The shorthand produces `source: goal` — a scalar in a file a person wrote **is** an
assertion by that person. That is not an abbreviation of provenance; it is the provenance.

### Validation

Every measurement is checked against its declaration when `mendel build` loads the goal:

```
mendel: this goal's profile is not valid — 'sample_name' is not a declared measurement.
  Declared: adapter_content, duplicate_rate, genome_length, library_prep, n_samples,
    node_memory_gb, organism, paired, purpose, read_length, rrna_fraction, strandedness
  To add one, add a file to a layer carrying `declares: measurement`
  and `id: sample_name`. Since comeni-registry#1 the path is free;
  the convention is <layer>/measurements/sample_name.yml.
```

The model itself cannot do this — measurements are declared data, so it has no idea what is
declared. `MeasurementRegistry.profile()` is the only validating constructor,
`tests/test_construction.py` enforces that nothing else builds a profile, and `mendel build`
routes every goal through it. See
[concepts/privacy-and-egress.md](../concepts/privacy-and-egress.md).

## Complete example

```yaml
have:
  - type_id: fastq.reads
  - type_id: annotation.gtf
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

## The goal reaches the pipeline file, and is inert there

`mendel build` copies the goal into `build/pipeline.yml` under `goal:`, so a pipeline records
what was asked for and not only what it resolved to. A recipient can read the question as well
as the answer.

**Editing it there changes nothing until `mendel upgrade`.** `mendel emit` reads none of it —
the facts emission needs are already materialised into `channels[].meta` — and it could not
honour a changed profile even in principle, because validating one needs the measurement
registry and `emit` has no registry by design. See
[pipeline-schema.md](pipeline-schema.md#goal--inert-to-emit).

## What is deliberately absent

No input path. No sample sheet. No output directory. No filename of any kind.

The emitted pipeline references `params.input` as a placeholder your laboratory fills at
run time, in your own environment. Profiling happens where the data is. Mendel builds the
pipeline and never meets what runs through it.
