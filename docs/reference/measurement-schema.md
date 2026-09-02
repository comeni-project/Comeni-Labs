# Measurement schema

A measurement declares **one fact a rule may reason about**: what it is called, what kind of
value it holds, and whether any tool can actually produce it.

Measurements are what a goal's `profile:` may contain, and what a tier-3 rule's `when:` reads.
Both are closed against this list — an undeclared key is refused, which is what stops
`profile: {sample_name: ...}` from ever building.

```yaml
# registry/measurements/read_length.yml
declares: measurement
id: read_length
kind: integer
per_sample: true
minimum: 1
unit: bp
description: "Sequenced read length"
cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
```

`declares: measurement` **and** an `id:` are both required; `MD0012` refuses a file without one.

## Fields

Model: `comeni_core.declared.measurement.Measurement`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | *required* | what a profile and a rule call it |
| `kind` | enum | *required* | `integer`, `number`, `boolean` or `enum` |
| `values` | [string] | `[]` | for `enum`: the permitted values |
| `extensible` | boolean | `false` | for `enum`: whether values outside the list are allowed |
| `per_sample` | boolean | `false` | whether each sample can have its own value |
| `assertion_only` | boolean | `false` | **no tool can produce this** — see below |
| `assertion_only_because` | string | `""` | why not. Required when `assertion_only` is set |
| `minimum` | number \| null | `null` | lower bound, checked on load |
| `maximum` | number \| null | `null` | upper bound, checked on load |
| `unit` | string \| null | `null` | `bp`, `GB` — for display, never for conversion |
| `description` | string | `""` | one line, for a human |
| `cite` | string \| null | `null` | where the definition comes from |
| `edam` | string \| null | `null` | the EDAM ontology term, when one fits |
| `describes` | string \| null | `null` | the type this is a fact *about*, e.g. `fastq.reads` |
| `meta_key` | string \| null | `null` | the key this becomes in a Nextflow `meta` map |
| `meta_values` | [string] | `[]` | how its values are spelled in `meta`, when they differ |
| `deprecated` | boolean | `false` | still loads, should not be used in new rules |
| `replaced_by` | string \| null | `null` | what to use instead |

## `assertion_only` is the honest field

A measurement is only as good as whatever produced it. **`assertion_only: true` means nothing
in the registry can measure this — you can only assert it**, and `assertion_only_because` has to
say why:

```yaml
id: organism
kind: enum
values: [homo_sapiens, mus_musculus, danio_rerio]
extensible: true
assertion_only: true
assertion_only_because: >-
  measurable by classification against a reference database — Kraken2 and friends — which is
  a whole tool this spine does not carry.
```

`MD0315` refuses `assertion_only: true` with no reason given.

**Five of the original six measurements turned out to be assertion-only**, including
`strandedness`. That was a surprise worth recording rather than smoothing over: a tier-3 rule
firing on an asserted premise is doing arithmetic on a guess, and the reason it writes into
`pipeline.yml` says so in those words — *asserted, not measured*.

`node_memory_gb` is a second kind of honesty. It is a property of the *execution environment*
rather than of the data, and such a "measurement" loads without complaint. It is declared
because people really write rules against it, and marked so a reader can see it is not about
the reads.

## `describes` and `meta_key` — the two directions

`describes` points at the **type** the fact is about. `strandedness` describes `fastq.reads`.

`meta_key` is how the fact reaches a tool. nf-core modules read a `meta` map, and a module does
its own translation from a fact to a flag — which is why the strandedness rule was **deleted**
rather than wired: `-s 2` is featureCounts' encoding of a fact, not a decision anybody makes.

`meta_values` exists for where the spellings differ. `paired` describes `fastq.reads` and its
`meta_key` is `single_end` — the same fact, inverted, because that is what the modules read.

## Kinds and bounds

| kind | value | bounds |
|---|---|---|
| `integer` | whole number | `minimum`, `maximum` |
| `number` | any number | `minimum`, `maximum` |
| `boolean` | `true` / `false` | — |
| `enum` | one of `values` | `extensible` widens it |

`extensible: true` is for lists that genuinely cannot be enumerated — `organism` is the example.
It is a real weakening of the closed-vocabulary guarantee and should be rare.

## See also

- [Measuring your data](../guides/measuring-your-data.md) — turning an assertion into a measurement
- [Rule schema](rule-schema.md) — what reads these
- [Goal schema](goal-schema.md) — what a `profile:` may contain
