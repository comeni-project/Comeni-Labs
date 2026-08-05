# Measuring your data

Tier-3 rules reason about measured properties — read length, strandedness, sample count.
This is where those numbers come from.

The short version: **Mendel never looks at your data.** It emits a pipeline that measures
it, your laboratory runs that pipeline, and you hand the answers back.

## Declaring a measurement

A measurement is declared data, so adding one is a file rather than a release. They live
in `<layer>/measurements/<id>.yml`, and the filename is the id:

```yaml
# registry/measurements/read_length.yml
kind: integer
minimum: 1
unit: bp
description: "Sequenced read length"
```

```yaml
# registry/measurements/strandedness.yml
kind: enum
values: [forward, reverse, unstranded]
description: "Library strandedness determined by the prep protocol"
cite: "Signal et al. 2022, doi:10.1186/s12859-022-04572-7"
```

Four kinds: `integer`, `number`, `boolean`, `enum`.

**There is deliberately no `string` kind.** A free-text measurement is exactly the hole the
egress guard exists to close — `organism: "patient 4471023's tumour"` is a perfectly valid
string. A categorical declares its values instead, which also lets a rule over it be checked
for completeness.

Full field list: [reference/measurement-schema.md](../reference/measurement-schema.md).

## Asserting values you already know

If you know your library prep, just say so in the goal:

```yaml
profile:
  read_length: 150
  strandedness: reverse
  paired: true
```

Every value is validated against its declaration — an undeclared measurement, a value
outside its bounds, or one not in an enum's list all stop the build:

```
mendel: this goal's profile is not valid — 'sample_name' is not a declared measurement.
  Declared: n_samples, paired, read_length, strandedness
  To add one, declare <layer>/measurements/sample_name.yml
```

That refusal is invariant 15 doing its job. A hand-written value is recorded as
`source: goal` — an **assertion by you**, which is a different thing from a measurement,
and the record says which it was.

## Measuring values you do not know

```bash
uv run mendel profile --have fastq.reads --out profile-build/
```

```
profiling for: read_length
  NOT MEASURED  n_samples, paired, strandedness — declared, but no contract in
                this registry produces them
1 modules, 0 requiring review
```

Two files come out. `profile-build/main.nf` is an ordinary Nextflow pipeline that measures
what this registry knows how to measure. And `profile-build/profile.yml`:

```yaml
measurements:
- by: comeni/profile/fastqc@0.12.1
  measurement: read_length
  source: measured
  value: null
```

**`value: null` is deliberate.** The pipeline has been emitted, not run. Reporting a number
Mendel has never looked at would be exactly the thing it promises not to do.

## The round trip

1. `mendel profile` emits the measuring pipeline
2. you run it on your data, in your environment
3. you fill the `value:` fields in
4. that block goes straight into a goal's `profile:` — it is the same shape

```yaml
# your-goal.yml
have: [{type_id: fastq.reads}, {type_id: annotation.gtf}]
want: [counts.matrix]
profile:
  measurements:
    - {measurement: read_length, value: 150, source: measured, by: comeni/profile/fastqc@0.12.1}
```

Now the tier-3 rules have something to match, and the record shows the value was measured
rather than assumed — including *by what*.

## Why profiling is not special

A measurement is a **type**, derived automatically from its declaration as
`measurement.<id>`. A contract that produces one is an ordinary contract:

```yaml
id: comeni/profile/fastqc@0.12.1
nf_process: FASTQC
nf_include: modules/nf-core/fastqc/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces:
  - {name: read_length, type_id: measurement.read_length, state: []}
```

So `mendel profile` is sugar for `mendel build --want measurement.*`. One router, one
emitter, one set of decision records — and a test asserts the two produce byte-identical
`main.nf`.

Two rules keep it honest:

**A profiling build resolves against an empty profile.** Otherwise profiling would need a
profile to profile with. Profiling contracts exit at tiers 1, 2 and 4 only — never 3.

**It wants only what this registry can reach.** Declaring a measurement is how you *start*,
before any tool for it exists. What cannot be measured is named on stderr rather than
dropped silently, and a registry that can measure nothing at all is an error rather than an
empty pipeline that looks like success.

## Adding your own measurer

Write a contract that produces `measurement.<id>` and put it in your layer. Nothing else
changes — the router already knows how to reach a type.

```bash
uv run mendel profile --have fastq.reads --registry registry/ --registry ./lab-registry \
  --out profile-build/
```

## Editor support

`DataProfile.get` is typed per measurement through a generated stub, so an editor knows
that `get("strandedness")` returns `Literal["forward", "reverse", "unstranded"] | None`.
After adding a measurement:

```bash
uv run python tools/generate_types.py
```

CI runs `--check` on it. A stale stub costs autocomplete and never correctness — which is
precisely why nobody would notice it rotting.
