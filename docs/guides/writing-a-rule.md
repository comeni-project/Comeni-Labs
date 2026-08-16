# Writing a rule

A rule is how a choice comes to depend on your data instead of on a convention. It is the
difference between "this registry prefers STAR" and "STAR, because your reads are 150bp,
and here is the paper".

Rules are **data**, not code. A domain expert adds one without touching Python, and the
result is reproducible, free, and reviewable as a diff.

Full field list: [reference/rule-schema.md](../reference/rule-schema.md).

## The shape

One rule table per file, opening with `declares: rule`. **Where you put it is free**; the
convention is `<layer>/rules/<name>.rule.yml`. One block per decision, rows underneath:

```yaml
declares: rule
version: 1
decisions:
  - decides: {param: strandedness}
    because: "featureCounts -s follows library strandedness"
    cite: "Liao et al. 2014, doi:10.1093/bioinformatics/btt656"
    rows:
      - {when: {strandedness: reverse},    then: 2}
      - {when: {strandedness: forward},    then: 1}
      - {when: {strandedness: unstranded}, then: 0}
```

Grouped rather than flat so a reviewer reads the justification once and then reads the
branches — and so that a *missing* branch is visible. Flat rules hide the gap.

Rows are tried in order and the first match wins.

> **Syntax note.** Each row is a YAML *flow mapping* on one line:
> `- {when: {...}, then: N}`. Writing `- when: {...}   then: N` is two block keys on one
> line, which is a parse error. If you prefer block style, put `then:` on its own line.

## Two kinds of decision

**`param:`** sets a parameter on whichever module declares it:

```yaml
  - decides: {param: strandedness}
```

**`producer_of:`** picks which module produces a type:

```yaml
  - decides: {producer_of: alignment.bam}
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@1.11.0}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2}
```

A block decides exactly one of the two.

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
and the build does not stop; the decision simply falls through to the next tier. See
[measuring-your-data.md](measuring-your-data.md).

## Validation is the point

Every table is checked at load against the registry, the vocabulary and the measurement
declarations. A table that cannot fire **refuses to load**, and the error says what you
*can* write:

```
registry/rules/alignment.rule.yml, decision param:aligner
  No contract in the registry declares a parameter named 'aligner'.
  Parameters that do exist: seq_platform, strandedness
```

Refused outright:

- a `param` no contract declares
- a `producer_of` type nothing produces
- a pinned contract that is not in the registry, or that does not produce that type
- a `when` naming a measurement nothing declares
- a comparison against an enum or boolean
- the same target decided twice in one layer

This exists because it was earned. Two of the five rules originally shipped in
`examples/` had *never once executed*: `subject` was an unvalidated free string, no
contract declared `aligner`, and nothing said so. They sat there looking correct for
months. Loading is now the check.

## A pinned module must still be reachable

A `producer_of` rule pins a module; it does not conjure its inputs. If the rule picks
HISAT2 and nothing in the registry can build a HISAT2 index, the build stops:

```
mendel: cannot route this goal — a rule pins nf-core/hisat2/align@2.2.2 to produce
alignment.bam, but its inputs are unreachable from this goal (…). Rule condition:
{'read_length': '< 70'}
```

Loudly, rather than quietly using STAR instead. A rule that says one thing while the
pipeline does another is the failure this whole tool exists to remove.

A pin applies only where the pinned module is genuinely a candidate for the *states* being
asked for. When featureCounts asks for a coordinate-sorted BAM, the only producer is
`samtools/sort` — so the aligner rule does not apply there. It applies one level down, on
the sorter's own BAM input, where the aligners actually compete.

## Layers replace whole blocks

If your layer and the base layer both decide `param:strandedness`, yours replaces the
entire block — not row by row. A reviewer should be able to read one block and see the
complete effective decision. See [registry-layers.md](registry-layers.md).

## What you get

A rule match exits at **tier 3**, review level `advisory`, and carries your citation into
`pipeline.yml`, as the `why.reason` beside the value it explains.

Tier 3 is advisory rather than silent on purpose: a rule match is only as good as the
measurement behind it. Yellow means *the machinery worked, check the premise*.

**A rule miss never calls a model.** It demotes to tier 4 and gets flagged for a human.
That is what keeps the tier labels meaningful and the common case free.
