# Twenty real tier-3 rules, written against the format as it stood on 2026-08-14

**These are evidence, not tests, and they stay frozen.** Do not wire them into `pytest`, and do
not "fix" the eleven that fail. Their entire value is that they record what the rule format could
not express on the day the design audit ran.

**Plan 1.15 is the task that repaired the format, and it did not edit this directory.** A corpus
rewritten in the new format cannot also be the record of what the old one could not express, so
there are now two directories answering two questions:

| | Question |
|---|---|
| `rule-attempts/` (here) | what broke on 2026-08-14 |
| [`tests/fixtures/rule-corpus/`](../../../../../tests/fixtures/rule-corpus) | whether it is fixed |

`tests/test_rule_corpus.py` is the assertion, and it holds the expected outcome per rule with
the reason. It also asserts that **every attempt here has a rewrite and no rewrite is orphaned**,
so the two cannot drift apart.

**Nineteen of the twenty-one now load, and the two refusals are not regressions.** R02b is the
contortion — this directory's own workaround for R02 — and it is *newly* caught: `MD0311` sees
that enumerating one row per read length leaves everything below the lowest one uncovered, which
is the defect the contortion was hiding. It stays refused, because R02 is writable directly now
and a validating contortion would be the format endorsing the workaround it replaced. R20 is
refused by design.

R02 and R03 were refused as arithmetic until **issue #39** gave the format a `transform` chain:
named unary steps over one measurement, left to right, with no parser, no precedence and no way
to name a second fact. `docs/design/rule-tables-and-port-logic.md` §13.2 asked for arithmetic
without reintroducing a solver, and that shape is what satisfies both halves.

## Where they came from

Stream 4 of the [2026-08-14 design audit](../../2026-08-14-design-audit.md), which the brief named
as *the highest-value single thing this audit can do*:

> Take twenty real, abstract tier-3 rules from the literature. Try to write each one in the
> current rule format. Report what breaks.

Each was written as YAML and run through the real `mendel_resolver.layers.load()`, stacked over
`registry/`, with a scratch layer supplying the measurements and contract parameters first — so
every failure is the **format's**, not a missing declaration.

`docs/design/rule-tables-and-port-logic.md` §13 reasoned three limits from a registry holding
**one** rule. These twenty are what turn that argument into evidence, and they are the
specification for the reform: issues
[#38](https://github.com/comeni-project/Comeni-Labs/issues/38) and
[#39](https://github.com/comeni-project/Comeni-Labs/issues/39).

## The result

**6 clean · 4 load and are wrong · 1 contortion · 9 cannot be written.**

The nine that cannot be written all failed **at load, naming the offending thing, nine for nine**
— the format refusing what it cannot express, which is the format behaving well. **The four that
load and are wrong are the problem**, and A118 is the sharpest: §13.2 called that case unwritable
when it was writable and unrefused.

| File | Rule | Source | Outcome |
|---|---|---|---|
| `R01` | aligner by read length: ≥ 70 → STAR, < 70 → HISAT2 | Dobin 2013 / Kim 2019 | **clean** — the control |
| `R02` | STAR `--sjdbOverhang` = `read_length − 1` | STAR manual 2.2.2 | **loads and is wrong** — **A118**, now refused by `MD0300` |
| `R02b` | the same rule, enumerated one row per read length | — | **contortion.** Eight rows, silently no-ops on the ninth |
| `R03` | `--genomeSAindexNbases` = `min(14, log2(genome_length)/2 − 1)` | STAR manual 2.2.5 | **loads and is wrong**, same mechanism as R02 |
| `R04` | TrimGalore `--length`: 18 below 50 bp, else 20 | TrimGalore guide | **clean.** Comparison + empty-`when` catch-all |
| `R05` | TrimGalore `--clip_R1 3` for template-switching preps | Takara SMARTer v3 | **clean.** Enum equality |
| `R06` | `--twopassMode Basic` when junction discovery is the purpose | STAR manual 8; Engström 2013 | **cannot be written** — `'purpose' is not a declared measurement`. **A120** |
| `R07` | MAPQ floor: 30 for variant work, 10 for expression | Liao 2014; GATK BP | **cannot be written** — `'want' is not a declared measurement`. **A120** |
| `R08` | skip trimming below ~1% adapter content | nf-core/rnaseq | **cannot be written** — `then: null` → `'None' is not in the registry`. **A119** |
| `R09` | insert rRNA depletion above ~40% rRNA | Kopylova 2012 | **cannot be written** as insertion. **A119** |
| `R10` | UMI dedup / MarkDuplicates / neither, for amplicon | Smith 2017 | **cannot be written.** The third branch is "no step". **A119** |
| `R11` | Salmon for transcript-level, featureCounts for gene-level | Patro 2017 | **cannot be written.** The discriminator is `constraints.required_states`, which `when` cannot read. **A120** |
| `R12` | HISAT2 when the genome exceeds node RAM | STAR manual 3.2.2 | **clean**, and notable — a "measurement" of the *execution node* loads without complaint |
| `R13` | `cpus` by genome size | nf-core resource labels | **loads and is wrong.** Cited for the aligner, sets `cpus = 12` on TrimGalore too. **A123** |
| `R14` | MultiQC only when `n_samples > 1` | Ewels 2016 | **cannot be written.** Step presence. **A119** |
| `R15` | infer strandedness when it was not measured | Wang 2012 (RSeQC) | **loads and is dead.** `{when: {strandedness: null}}` validates and can never match. **A122** |
| `R16` | any stranded library — `strandedness != unstranded` | Liao 2014 | **cannot be written**, and misdiagnosed: *"'unstranded' is not a number. Write it as `\"!= 70\"`"*. **A121** |
| `R17` | genome build from organism | Ensembl 112 | **clean.** The archetype this format is good at |
| `R18` | `paired AND read_length ≥ 100` | STAR manual 2.2.2 | **clean.** AND-within-a-row |
| `R19` | `--sjdbOverhang` from **max** read length across the cohort | STAR manual 2.2.2 | **cannot be written** without a second measurement — §12's cohort-versus-sample, reached independently |
| `R20` | a rule naming a contract the local stack does not hold | — | **cannot be written, by design and correctly.** The shape a lab writing overlay rules meets first |

## What the failures group into

- **A119 — step presence has nowhere to be decided.** `decides:` has two targets, `param` and
  `producer_of`, and neither is *whether a step exists*. Four of twenty die here (R08, R09, R10,
  R14) — a fifth of a real corpus. **Still carried as PLAUSIBLE**: it is the one critical the
  audit did not reproduce first-hand, and it should be reproduced before the reform is scoped.
- **A120 — `when` sees only measurements.** Not the goal's purpose, and not
  `constraints.required_states`, which the router already consults. Three of twenty (R06, R07,
  R11). The `required_states` half is the cheaper repair and closes R11 alone.
- **A121 — negation over an enum is inexpressible**, and the refusal misdiagnoses it as a
  malformed number, because `_comparison` runs every literal through `float()`.
- **A122 — a row conditioned on an *absent* measurement loads clean and can never fire.** A dead
  rule, in the format built to make dead rules impossible.
- **A123 — rules have no scope.** `decides: {param: cpus}` binds a bare name registry-wide.
- **A118 — a computed `then` was not refused.** Fixed in Plan 1.13 (`MD0300`); `R02` and `R03`
  now fail at load rather than reaching a tool. **They are kept unchanged**: what they record is
  that the format cannot express the rule, which is still true, and `MD0300` only makes the
  refusal honest.

## Reproducing

Stack one over the shipped registry and load it:

```bash
uv run mendel build --goal examples/rnaseq-goal.yml \
  --registry registry/ --registry <a layer containing this rule> --out /tmp/probe --gate lint
```

The scratch layer supplying the measurements and parameters these rules assume is **not**
committed — recreating it is a few lines of YAML, and committing it would invite someone to make
the eleven failures pass, which is the one thing that must not happen to this directory.
