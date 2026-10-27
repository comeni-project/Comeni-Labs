# Writing a rule

A rule is how a choice comes to depend on your data instead of on a convention. It is the
difference between "this registry prefers STAR" and "STAR, because your reads are 150bp,
and here is the paper".

Rules are **data**, not code. A domain expert adds one without touching Python, and the
result is reproducible, free, and reviewable as a diff.

Full field list: [reference/rule-schema.md](../../reference/registry/rule-schema.md).

## Write the declaration

One rule table per file, opening with `declares: rule`. **Where you put it is free**; the
convention is `<layer>/rules/<name>.rule.yml`. One block per decision, rows underneath:

```yaml
declares: rule
version: 1
decisions:
  - decides: {effect: implementation, of: alignment}
    because: "read length determines which aligner is appropriate"
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@2.7.11b}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2}
```

Grouped rather than flat so a reviewer reads the justification once and then reads the
branches — and so that a *missing* branch is visible. Flat rules hide the gap.

Rows are tried in order and the first match wins.

> **Syntax note.** Each row is a YAML *flow mapping* on one line:
> `- {when: {...}, then: N}`. Writing `- when: {...}   then: N` is two block keys on one
> line, which is a parse error. If you prefer block style, put `then:` on its own line.

## Choose the decision target

A `decides:` names an **effect** and the **role** it applies to. A role is a job — `alignment`,
`trimming`, `quantification` — not a tool and not a type.

**`implementation`** — which tool fills the role:

```yaml
  - decides: {effect: implementation, of: alignment}
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@2.7.11b}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2}
```

**`presence`** — whether the role happens at all:

```yaml
  - decides: {effect: presence, of: trimming}
    rows:
      - {when: {read_length: ">= 70"}, then: true}
```

**`param`** — what a parameter is set to. Needs `name:` as well:

```yaml
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "featureCounts -s follows library strandedness"
    cite: "Liao et al. 2014, doi:10.1093/bioinformatics/btt656"
    rows:
      - {when: {strandedness: reverse},    then: 2}
      - {when: {strandedness: forward},    then: 1}
      - {when: {strandedness: unstranded}, then: 0}
```

Add `when_implementation: [<contract id>]` to restrict a decision to particular tools.

Targets must name an effect and a role. Direct targets such as `{param: strandedness}`
and `{producer_of: alignment.bam}` are invalid. A role target lets the rule choose
between compatible tools without using either tool as its key.

## Conditions

`when` maps measurement ids to expectations. All must hold.

| Form | Means |
|---|---|
| `{strandedness: reverse}` | equal to |
| `{read_length: ">= 70"}` | comparison — `>=`, `>`, `<=`, `<`, `==`, `!=` |
| `{paired: true}` | equal to |

A comparison is a **string with a space**: `">= 70"`, not `">=70"`. Comparisons work only
on `integer` and `number` measurements — comparing an enum refuses to load, because
`strandedness >= 70` has no meaning and a rule that cannot fire is worse than no rule.

**A measurement that was never measured makes the row fail to match.** Rows are not skipped
and the build does not stop; the decision simply falls through to the next tier. In the current
alpha, profiling and input collection are still moving surfaces, so write rules against facts
the lab can either measure or assert clearly.

## Validate against the registry

Every table is checked at load against the registry, the vocabulary and the measurement
declarations. A table that cannot fire **refuses to load**, and the error says what you
*can* write:

```
registry/rules/alignment.rule.yml, decision param:aligner
  No contract in the registry declares a parameter named 'aligner'.
  Parameters that do exist: seq_platform, strandedness
```

Refused outright:

- an `of:` role no layer declares
- a `name:` parameter no contract in that role declares
- a pinned contract that is not in the registry, or that does not produce that type
- a `when` naming a measurement nothing declares
- a comparison against an enum or boolean
- the same target decided twice in one layer

Validate the table against the loaded registry before relying on it. A syntactically
valid file can still name a role, parameter or measurement that does not exist.

## Layers replace whole blocks

If your layer and the base layer both decide the same target, yours replaces the
entire block — not row by row. A reviewer should be able to read one block and see the
complete effective decision. See [your-labs-own-layer.md](add-layer.md).

## What you get

A rule match exits at **tier 3**, review level `advisory`, and carries your citation into
`pipeline.yml`, as the `why.reason` beside the value it explains.

Tier 3 is advisory rather than silent on purpose: a rule match is only as good as the
measurement behind it. Yellow means the rule matched, and the person responsible for the
analysis should check the fact it read.

**A rule miss never calls a model.** It demotes to tier 4 and gets flagged for a human.
That is what keeps the tier labels meaningful and the common case free.

For the design and constraints, see [Data-backed rules and reachable tools](../../explanation/data-backed-rules.md).
