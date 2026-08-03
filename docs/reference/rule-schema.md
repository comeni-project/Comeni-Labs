# Rule schema

`<layer>/rules/*.yml`, globbed non-recursively per layer.

Model: `mendel_resolver.rules.RuleTable`.

## File

```yaml
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

`version` is recorded and currently unused.

## Decision

| Field | Type | Default | Meaning |
|---|---|---|---|
| `decides` | DecisionTarget | *required* | what this block settles |
| `rows` | [DecisionRow] | `[]` | branches, tried in order, first match wins |
| `because` | string \| null | `null` | why this decision exists, in prose |
| `cite` | string \| null | `null` | the citation — reaches `selection.reason` and the generated `main.nf` |

One block per target. Deciding the same target twice **in one layer** is an error; a higher
layer replaces the whole block.

## DecisionTarget

Exactly one of the two.

| Field | Type | Meaning |
|---|---|---|
| `param` | string \| null | a parameter name some contract declares |
| `producer_of` | string \| null | a type id; rows name contract ids |

## DecisionRow

| Field | Type | Default | Meaning |
|---|---|---|---|
| `when` | map | `{}` | measurement id → expectation. All must hold. |
| `then` | scalar | `null` | the value, or the contract id for `producer_of` |
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
| `param` no contract declares | the rule could never fire |
| `producer_of` naming an undeclared type | same |
| `then` naming a contract not in the registry | the row can never be applied |
| `then` naming a contract that does not produce that type | same |
| `when` naming an undeclared measurement | the condition can never be evaluated |
| a comparison against an enum or boolean | `strandedness >= 70` has no meaning |
| the same target decided twice in one layer | a copy-paste; resolving by file order would be a silent arbitrary pick |
| a decision naming both or neither of `param` / `producer_of` | ambiguous target |

Errors name what you *can* write:

```
rules/rnaseq.yml, decision param:aligner
  No contract in the registry declares a parameter named 'aligner'.
  Parameters that do exist: seq_platform, strandedness
```

This is the load-bearing part of the format. `subject` used to be an unvalidated free
string, and two of the five rules originally shipped had never once executed.

## Layer composition

Keyed on the target — `param:strandedness`, `producer_of:alignment.bam`. A higher layer
replaces the **whole block**, so a reviewer reads one block and sees the entire effective
decision.

## What a match produces

Tier 3, review level `advisory`, and a reason of the form:

```
rule producer_of:alignment.bam matched {'read_length': '>= 70'}:
  Dobin et al. 2013, doi:10.1093/bioinformatics/bts635
```

A miss demotes to tier 4. It never calls a model.

## Pinned producers must be reachable

A `producer_of` rule chooses a module; it does not supply that module's inputs. If the
pinned module is selected and its dependencies cannot be met, the build stops with
`UnroutablePinError` naming the rule condition — rather than quietly using something else.

A pin applies only where the pinned contract is a candidate for the states being requested.
See [concepts/routing.md](../concepts/routing.md).

## Complete example

```yaml
version: 1
decisions:
  - decides: {param: strandedness}
    because: "featureCounts -s follows library strandedness"
    cite: "Liao et al. 2014, doi:10.1093/bioinformatics/btt656"
    rows:
      - {when: {strandedness: reverse},    then: 2}
      - {when: {strandedness: forward},    then: 1}
      - {when: {strandedness: unstranded}, then: 0}

  - decides: {producer_of: alignment.bam}
    because: "read length determines which aligner is appropriate"
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@1.11.0}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2}
```
