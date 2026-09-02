# Rule schema

One rule table per file, carrying `declares: rule`. **Where the file sits is free**
(comeni-registry#1); the public registry uses `rules/<name>.rule.yml`.

No `id:`: a rule is keyed on the target its decision names, not on the file.

A rule targets a **role** — *what job is being filled* — not a type id and not a tool. That
changed in Plan 1.15; anything you read describing `producer_of:` is the superseded format.

## File

```yaml
declares: rule
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "featureCounts -s follows library strandedness"
    cite: "Liao et al. 2014, doi:10.1093/bioinformatics/btt656"
    rows:
      - {when: {strandedness: reverse},    then: 2}
      - {when: {strandedness: forward},    then: 1}
      - {when: {strandedness: unstranded}, then: 0}
```

`version` is recorded and currently unused.

## Decision

Model: `mendel_resolver.rules.format.Decision`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `decides` | DecisionTarget | *required* | what this block settles |
| `rows` | [DecisionRow] | `[]` | branches, tried in order, first match wins |
| `because` | string \| null | `null` | why this decision exists, in prose |
| `cite` | string \| null | `null` | the citation — reaches `selection.reason` and the generated `main.nf` |

One block per target. Deciding the same target twice **in one layer** is an error; a higher
layer replaces the whole block.

## DecisionTarget

What a decision is *about*. Three effects, and the effect decides what `then:` may hold.

Model: `mendel_resolver.rules.format.DecisionTarget`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `effect` | enum | *required* | `presence`, `implementation` or `param` |
| `of` | string | *required* | the **role** — the job being filled, e.g. `alignment` |
| `name` | string \| null | `null` | for `effect: param`, which parameter |
| `when_implementation` | [contract id] | `[]` | restrict this decision to particular tools |

| effect | settles | `then:` holds |
|---|---|---|
| `presence` | whether the role appears at all | a boolean |
| `implementation` | which tool fills it | a contract id |
| `param` | what a parameter is set to | the value |

```yaml
decides: {effect: implementation, of: alignment}
```

**`of` is a role, not a type.** *Something must align these reads* is the decision; which type
comes out is a consequence. Targeting a type made a rule unable to say anything about a step
that produces the same type as the one it replaces.

## DecisionRow

Model: `mendel_resolver.rules.format.DecisionRow`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `when` | map | `{}` | measurement id → expectation. All must hold. |
| `then` | scalar | `null` | the value, or a contract id for `effect: implementation` |
| `because` | string \| null | `null` | overrides the block's `because` for this row |
| `cite` | string \| null | `null` | overrides the block's `cite` for this row |

### Expectations

| Form | Means |
|---|---|
| `reverse`, `150`, `true` | equal to |
| `">= 70"` | comparison |

Operators: `>=`, `>`, `<=`, `<`, `==`, `!=`.

A comparison is **a string with a space after the operator** — `">= 70"`. Without the
space, `">=70"` fails to load with a message telling you so.

Comparisons work only on `integer` and `number` measurements. Against an `enum` or
`boolean` the table refuses to load.

**A measurement absent from the profile makes the row not match.** No error, no skip — the
decision falls through and the value settles at a lower tier.

## Validation at load

Every table is checked against the registry, the vocabulary and the measurement
declarations. `RuleValidationError` if:

| Problem | Because |
|---|---|
| an `of:` role no layer declares | the rule could never fire |
| a `name:` parameter no contract in that role declares | same |
| `then` naming a contract not in the registry | the row can never be applied |
| `then` naming a contract that does not fill that role | same |
| `when` naming an undeclared measurement | the condition can never be evaluated |
| a comparison against an enum or boolean | `strandedness >= 70` has no meaning |
| the same target decided twice in one layer | a copy-paste; resolving by file order would be a silent arbitrary pick |
| `effect: param` with no `name:` | which parameter is unstated |

Errors name what you *can* write:

```
rules/rnaseq.yml, decision param:aligner
  No contract in the registry declares a parameter named 'aligner'.
  Parameters that do exist: seq_platform, strandedness
```

This is the load-bearing part of the format. `subject` used to be an unvalidated free
string, and two of the five rules originally shipped had never once executed.

## Layer composition

Keyed on the target — `implementation:alignment`, `param:quantification.strandedness`. A higher layer
replaces the **whole block**, so a reviewer reads one block and sees the entire effective
decision.

## What a match produces

Tier 3, review level `advisory`, and a reason of the form:

```
rule implementation:alignment where read_length is 150, asserted, not measured: STAR's
seed-and-extend search is built for long reads and is nf-core/rnaseq's default aligner; the
index cost it pays back over reads this length; Dobin et al. 2013,
doi:10.1093/bioinformatics/bts635
```

Note *asserted, not measured*. The reason carries how the fact behind it was obtained, because
a rule match is only as good as its premise.

A miss demotes to tier 4. It never calls a model.

## Pinned producers must be reachable

An `implementation` rule chooses a module; it does not supply that module's inputs. If the
pinned module is selected and its dependencies cannot be met, the build stops with
`UnroutablePinError` naming the rule condition — rather than quietly using something else.

A pin applies only where the pinned contract is a candidate for the states being requested.
See [concepts/routing.md](../concepts/routing.md).

## Complete example

```yaml
declares: rule
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "featureCounts -s follows library strandedness"
    cite: "Liao et al. 2014, doi:10.1093/bioinformatics/btt656"
    rows:
      - {when: {strandedness: reverse},    then: 2}
      - {when: {strandedness: forward},    then: 1}
      - {when: {strandedness: unstranded}, then: 0}

  - decides: {effect: implementation, of: alignment}
    because: "read length determines which aligner is appropriate"
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@1.11.0}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2}
```
