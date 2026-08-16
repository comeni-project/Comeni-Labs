# Measurement schema

One measurement per file, carrying `declares: measurement` and an `id:`. **Where the file
sits is free** (comeni-registry#1); the public registry keeps them in `measurements/`.

**`id:` is required**, and `MD0012` refuses a file without one — same reasoning as a
vocabulary's, since both took their identity from a filename that a free layout makes a poor
name.

Note that `declares:` is not `kind:`. A measurement's `kind:` is the kind of its *value*
(`integer`, `enum`), which is why the file-level key had to be a different word.

Model: `comeni_core.declared.measurement.Measurement`.

## Fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `kind` | `integer` \| `number` \| `boolean` \| `enum` | *required* | the value type |
| `values` | [string] | `[]` | allowed values; `enum` only |
| `extensible` | bool | `false` | whether a higher layer may `add_values` |
| `minimum` | number \| null | `null` | inclusive lower bound; numeric kinds |
| `maximum` | number \| null | `null` | inclusive upper bound; numeric kinds |
| `unit` | string \| null | `null` | e.g. `bp`. Documentation only. |
| `description` | string | `""` | one line, for humans |
| `cite` | string \| null | `null` | where the definition comes from |
| `edam` | string \| null | `null` | EDAM ontology term, if one applies |
| `deprecated` | bool | `false` | still loads, should not be used in new rules |
| `replaced_by` | string \| null | `null` | the successor measurement id |

## There is no `string` kind

Deliberately. A free-text measurement is exactly the hole the egress guard exists to close
— `organism: "patient 4471023's tumour"` is a perfectly valid string, and no type checker
would object.

A categorical declares its values as an `enum` instead, which has the second benefit of
letting a rule over it be checked for completeness. Declaring `kind: string` is a load
error that says so.

## Extending an enum

```yaml
# base layer: measurements/organism.yml
declares: measurement
id: organism
kind: enum
extensible: true
values: [homo_sapiens, mus_musculus]
```

```yaml
# your layer: measurements/organism.yml
declares: measurement
id: organism
add_values: [ambystoma_mexicanum]
```

A file with `add_values` extends rather than replaces. Without `extensible: true` it is
refused:

```
lab/measurements/strandedness.yml: 'strandedness' is not extensible. Shadow the whole
declaration to change it, or set `extensible: true` where it is declared.
```

Per-measurement because the semantics genuinely differ: `strandedness` has exactly three
values and a fourth is a bug, while `organism` can never be enumerated and a registry that
tries is wrong.

## Deprecation, never reuse

A meaning change gets a **new id**. The old one stays forever, pointing at its successor:

```yaml
declares: measurement
id: read_length
kind: integer
deprecated: true
replaced_by: read_length_median
description: "ambiguous — see read_length_median"
```

Standard OBO practice, which the ontologies this registry cites have used for two decades.

Per-measurement `@version` was considered and rejected: every rule condition would grow a
version, and omitting one would silently mean *latest* — which is the ambiguity versioning
was meant to remove.

## Validation

`MeasurementRegistry.check(id, value)` raises:

| Error | When |
|---|---|
| `UnknownMeasurementError` | nothing declares that id. Message lists what is declared. |
| `BadMeasurementValueError` | wrong type, outside bounds, or not in an enum's values |

A `bool` is never accepted as an `integer`, despite Python's opinion on the matter.

## Every measurement is also a type

`Vocabulary.with_measurements()` derives a stateless `measurement.<id>` type from each
declaration, so a contract can produce one:

```yaml
produces:
  - {name: read_length, type_id: measurement.read_length, state: []}
```

That is what makes `mendel profile` an ordinary build rather than a second subsystem.

Derived rather than declared twice — a vocabulary file repeating the measurement would be
a thing to drift. Stateless because a measurement has a *value*, not a condition; letting
enum values also be states would give routing two places to disagree.

## Generated types

```bash
uv run python tools/generate_types.py
```

Regenerates `packages/comeni-core/src/comeni_core/goal/profile.pyi`, giving `DataProfile.get`
a per-measurement return type in any PEP 561 type checker. `--check` fails if stale, and
CI runs it.

## Some shipped declarations

`ls registry/measurements/` is the count; this is a sample of the shapes.

```yaml
# measurements/read_length.yml
declares: measurement
id: read_length
kind: integer
minimum: 1
unit: bp
description: "Sequenced read length"
```

```yaml
# measurements/strandedness.yml
declares: measurement
id: strandedness
kind: enum
values: [forward, reverse, unstranded]
description: "Library strandedness determined by the prep protocol"
cite: "Signal et al. 2022, doi:10.1186/s12859-022-04572-7"
```

```yaml
# measurements/n_samples.yml
declares: measurement
id: n_samples
kind: integer
minimum: 1
description: "Number of samples in the study"
```

```yaml
# measurements/paired.yml
declares: measurement
id: paired
kind: boolean
description: "Whether the library is paired-end"
```
