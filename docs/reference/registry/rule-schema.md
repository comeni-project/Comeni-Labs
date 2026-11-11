# Rule schema

One rule table per file, carrying `declares: rule`. **Where the file sits is free**
(comeni-registry#1); the public registry uses `rules/<name>.rule.yml`.

No `id:`: a rule is keyed on the target its decision names, not on the file.

A rule targets a **role** — *what job is being filled* — not a type id and not a tool. Direct `producer_of:` and `param:` targets are invalid; use `effect`, `of` and,
for parameter targets, `name`.

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
| `hit` | `first` \| `unique` | `first` | `first`: the first matching row decides. `unique`: at most one row may match; two matching rows are a tie, asked at tier 4 |
| `rows` | [DecisionRow] | `[]` | branches, tried in order |
| `because` | string \| null | `null` | why this decision exists, in prose |
| `cite` | string \| null | `null` | the citation — reaches `selection.reason` and the generated `main.nf` |
| `coverage` | `all` \| null | `null` | `all`: a fact read from part of the data does not satisfy it; see [Coverage](#coverage) |

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
| `then` | scalar \| `{fact: <id>}` | `null` | the value, or a contract id for `effect: implementation`. For `effect: param`, `{fact: <id>}` takes the value of a measured or derived fact; a fact with no value makes the row not fire |
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
| a fractional boundary on an integer measurement (`MD0310`) | no value can sit on it |
| a comparison against an enum or boolean | `strandedness >= 70` has no meaning |
| the same target decided twice in one layer | a copy-paste; resolving by file order would be a silent arbitrary pick |
| `effect: param` with no `name:` | which parameter is unstated |
| a case no row matches, over every fact the rows test (`MD0311`) | that profile would silently fall to tier 4 |
| under `hit: first`, a row that is first for no case (`MD0323`) | it reads as a rule and never decides |
| more than 4096 cases to try (`MD0324`) | a clean check must mean every case was tried |
| a literal `then` the tool's constraints refuse with every input, its other settings at their defaults (`MD0325`) | the rule would set it and every build would stop |
| `{fact:}` whose kind does not fit the parameter, or on a non-param decision (`MD0300`) | the tool would receive a value its flag does not accept |
| `hit: unique` on an `implementation` or `presence` decision (`MD0300`) | a tie there cannot be asked yet |

**How the table is checked** (#461). Load tries every case the rows can tell apart: each value
of an enum (plus one an overlay may add, when it is `extensible`) or boolean, and for a number
each boundary a comparison, `in` or `not` names, a point between neighbouring boundaries (none
between adjacent integers) and one beyond each end. The check is exact, not sampled. Under
`hit: unique` an overlap is legal: it is the question the build asks. A catch-all `when: {}`
is never judged dead, because it decides when a fact is not known.

Errors name what you *can* write:

```
rules/rnaseq.yml, decision param:aligner
  No contract in the registry declares a parameter named 'aligner'.
  Parameters that do exist: seq_platform, strandedness
```

This is the load-bearing part of the format. `subject` used to be an unvalidated free
string, and two of the five rules originally shipped had never once executed.

## Derived facts

A file may also declare `derives:`, facts computed from others, which `when` keys read and a
`then: {fact: <id>}` takes. One computation each:

| Form | Fields | Means |
|---|---|---|
| rows | `fact`, `kind`, `rows` | rows with literal `then` values, first match |
| aggregate | `fact`, `kind`, `aggregate: {measurement, over: cohort, using: max \| min \| mean}` | one value from every sample's |
| transform | `fact`, `kind`, `source`, `transform` | a chain of steps over `source`, left to right |

Transform steps: `add`, `subtract`, `multiply`, `divide`, `at_most`, `at_least` (each with
`by`), and `log2` and `round` (half to even, as `printf "%.0f"`) with none. An `integer` fact
is truncated to a whole number when the chain does not round it. A row reading a derived fact
records the facts it was computed from, so the setting's reason says where the value came from.

STAR's genome index, which nf-core's module sizes inside `main.nf`:

```yaml
derives:
  - fact: star_sa_index_nbases
    kind: integer
    source: genome_length
    transform: [{op: log2}, {op: divide, by: 2}, {op: subtract, by: 1},
                {op: at_most, by: 14}, {op: round}]
    cite: "STAR manual 2.7.11b, section 2.2.5"
decisions:
  - decides: {effect: param, of: index_building, name: sa_index_nbases,
              when_implementation: [nf-core/star/genomegenerate@2.7.11b]}
    rows:
      - {when: {}, then: {fact: star_sa_index_nbases}, cite: "STAR manual 2.7.11b, section 2.2.5"}
```

A genome length of 29,903 bp gives 6; 3.1 Gb gives 14.

## Coverage

A decision may say `coverage: all`. A fact the server read from part of an upload
(`coverage: head`) then does not satisfy it: the rows are tried as if the fact were unknown. A
person's statement satisfies it, and so does a fact measured on all the data.

```yaml
decisions:
  - decides: {effect: implementation, of: alignment}
    coverage: all
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@2.7.11b}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2}
```

A fact derived from a `head` fact is `head` too. Without `coverage:`, an estimate decides like any
fact, and the pipeline measures it again over all the data to confirm it.

## Decided at run time

When a `param` decision waits on a fact nobody stated, the build can decide it in the run
instead. This happens when all of the following hold:

- once every known fact is substituted, the rows wait on exactly one fact;
- a [measurer](measurer-schema.md) that runs in the pipeline measures that fact;
- the fact `describes` one of the goal's inputs, and the step reads that input or descends from
  a step that does;
- the decision is `hit: first`;
- nobody has answered the setting.

The build then adds the measuring step. The fact joins the input's `meta`, and the setting is
emitted as a lookup over it. Every row the lookup can take is listed in `pipeline.yml` and on the
step card before the run. So is the fallback, used when the measurement comes back undetermined
or no row matches. The fallback is the setting's default, or nothing for a setting the tool can
do without, or else a question. Each value the run used is recorded per sample in
`<outdir>/decided/<step>.<setting>.tsv`. No model runs at run time, and the same goal gives the
same pipeline.

A row's `then: {fact: ...}` over a derived fact becomes its chain, written in Groovy from the
same closed operations: `round` is half to even, as here. STAR's index size is the example. With
29,903 bp stated, the build decides 6. With nothing stated, the pipeline measures the genome with
samtools faidx and decides in the run: 8 for nf-core's 230,218 bp test genome.

| Code | When |
|---|---|
| `MD0328` | a setting's rows wait on two facts the pipeline could measure; state all but one |
| `MD0329` | routing again to add the measuring steps moved the pipeline; a defect, report it |
| `MD0330` | a run-time setting routes outside `ext`, or its template does not hold `{value}` once |

Implementation and presence decisions are never decided at run time: the graph is fixed when the
pipeline is built, so they stay questions.

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
See [How tools get chosen](../../explanation/tool-selection.md).

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
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@2.7.11b}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2}
```
