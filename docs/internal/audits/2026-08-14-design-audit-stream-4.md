# Design audit — Stream 4: load-bearing assumptions vs. what is left to build

**Date:** 2026-08-14
**Brief:** `docs/internal/audits/2026-08-14-design-audit-brief.md`, § Stream 4
**Number block:** A118–A131 (all fourteen used)
**Tree:** `main` @ `346eeac`, in a worktree. `make verify` green before any experiment
(608 fast tests + counts matrix + 27 guard tests + drift skipped, no `../comeni-registry`).
**Experiment files:** `audit-tmp/` in this worktree — see *What was left behind*.

**Verdict for this stream: it holds with named repairs, and two of the repairs are load-bearing
before Plan 2 opens door 2.** Nothing found here says the design cannot deliver the claim. Three
findings say it *currently* does not — a cited tier-3 value that means nothing reaches a tool
(A118), a tie answered from the wrong candidate set (A125), and a curator's override orphaned by
installing one contract (A126). All three are reachable by ordinary use rather than by attack.

---

## Findings

| # | What | Shape | Severity | Verdict |
|---|---|---|---|---|
| A118 | A computed `then` is not refused — it loads, resolves at **tier 3 with a citation**, and is emitted verbatim into `ext.args`. `DecisionRow.then` is never checked against the parameter it decides | (i) | **critical** | CONFIRMED |
| A119 | Whether a step **exists** is not a decidable thing. `decides:` has two targets and neither is presence. 4 of 20 rules die here | (ii) | **critical** | CONFIRMED |
| A120 | `when` cannot see the goal — not its purpose and not `required_states`, which the router already consults. 3 of 20 rules die here | (ii) | important | CONFIRMED |
| A121 | Negation over an enum or boolean is inexpressible, and the refusal misdiagnoses it as a malformed number | (ii) | important | CONFIRMED |
| A122 | A row conditioned on a measurement being **absent** loads clean and can never fire — a dead rule, in the format built to make dead rules impossible | (ii) | important | CONFIRMED |
| A123 | `decides: {param: X}` names a parameter **globally**. A rule cited for the aligner sets the same value on TrimGalore, and there is no syntax to scope it | (ii)/(iii) | important | CONFIRMED |
| A124 | Nothing checks a `producer_of` rule for completeness — and a *complete* one makes every later producer permanently unreachable, silently | (ii) | important | CONFIRMED |
| A125 | A producer tie is answered from **every** candidate, not the tied ones. Adding one contract installed the lowest-priority aligner and the artifact says "nothing distinguishes" three contracts that `priority` distinguishes | (i) | **critical** | CONFIRMED |
| A126 | A producer decision's identity is the *winning candidate's* node id. Installing one contract renames it, and a curator's recorded override is reported ORPHANED — "your edit no longer applies to anything" — while the same question is asked one line above | (i)/(ii) | **critical** | CONFIRMED |
| A127 | A tier-3 **parameter** records neither the row nor the measurements it rested on. Issue #2's `ProfilePolicy` has nothing in the artifact to check | (ii)/(iii) | important | CONFIRMED |
| A128 | Tier 2 promises "value + citation". Module selection by `priority` is a bare integer with nowhere to carry one; the shipped justification is a YAML comment the loader discards | (ii) | important | CONFIRMED |
| A129 | Two of the three tier-4 question kinds **cannot cross door 2** — `ParamAsked` and `SourceAsked` candidates fail `AmbiguityRequest` validation. The guard compares field *names* | (iii) | **critical for Plan 2** | CONFIRMED |
| A130 | The artifact cannot state that no model was consulted. `resolved_by` and `confidence` are the resolver's claims about itself; nothing reads either | (ii) | important | CONFIRMED |
| A131 | "The error message is the feature" inverts at registry scale: **40,049 characters on one line** for a one-character typo against 2,000 contracts | (iii) | minor | CONFIRMED |

**Confirmations of things already known, filed as confirmations and not as discoveries:**
issue [#1](https://github.com/comeni-project/Comeni-Labs/issues/1) (A125, A126 reach it from the
replay side rather than the routing side), issue [#39](https://github.com/comeni-project/Comeni-Labs/issues/39)
/ §13.2 (A118), §13.3 (A120), §13.4 (A124, A125), §12 *Cohort versus sample* (R19 in the table
below), Plan-2 correction 6 / `[None]` (A129, and see *Held* on emission).

---

# The twenty-rule exercise

**The brief's highest-value item, and it is reported in full whether or not it produced findings.**

## Method

Twenty real, abstract tier-3 rules from bioinformatics practice, each written as a concrete YAML
attempt against the actual format and run through the actual loader —
`mendel_resolver.layers.load()`, stacked over `registry/`, no mocks. The harness is
`audit-tmp/try_rule.py`; the driver is `audit-tmp/run_all.py`; the attempts are
`audit-tmp/attempts/*.yml`, one file per rule, preserved verbatim.

A scratch layer (`audit-tmp/rulelab-base/`) declares the measurements and the contract parameters
the rules need, **so that every rule fails on the rule format rather than on a missing
declaration.** Seven measurements (`adapter_content`, `available_ram_gb`, `genome_length`,
`library_prep`, `organism`, `rrna_fraction`, `umi_present`) and eight parameters across three
contracts. Where a rule still failed on a missing *contract*, that is recorded as its own outcome
and is a real result, not a harness defect: a rule table is only valid against a registry that can
satisfy it, by design.

Attempts marked **loads but is wrong** are the important column. A rule that will not load is a
message to its author. A rule that loads, fires, is cited, and produces a wrong value is the
failure this project exists to remove.

## The table

| # | Rule | Source | Outcome |
|---|---|---|---|
| R1 | aligner by read length: ≥ 70 → STAR, < 70 → HISAT2 | Dobin 2013 / Kim 2019 | **clean** — the control. Fires, tier 3, cited |
| R2 | STAR `--sjdbOverhang` = `read_length − 1` | STAR manual 2.2.2 | **loads and is wrong.** `then: "read_length - 1"` loads; resolves tier 3 cited to Dobin; refused at emit only by MD0201's *space*. Respelled `"read_length-1"` it emits `--sjdbOverhang read_length-1`. **A118** |
| R2b | the same rule, enumerated one row per read length | — | **contortion.** Eight rows for eight lengths; silently no-ops on the ninth. Turns a rule into a lookup table, exactly as §13.2 predicted |
| R3 | STAR `--genomeSAindexNbases` = `min(14, log2(genome_length)/2 − 1)` | STAR manual 2.2.5 | **loads and is wrong**, same mechanism as R2 |
| R4 | TrimGalore `--length`: 18 below 50 bp, else 20 | TrimGalore user guide | **clean.** Comparison + empty-`when` catch-all row |
| R5 | TrimGalore `--clip_R1 3` for template-switching preps | Takara SMARTer v3 manual | **clean.** Enum equality |
| R6 | STAR `--twopassMode Basic` when junction discovery is the purpose | STAR manual 8; Engström 2013 | **cannot be written.** `'purpose' is not a declared measurement`. **A120** |
| R7 | MAPQ floor: 30 for variant work, 10 for expression | Liao 2014; GATK BP | **cannot be written.** `'want' is not a declared measurement`. **A120** |
| R8 | skip trimming below ~1% adapter content | nf-core/rnaseq `--skip_trimming` | **cannot be written.** `then: null` → `'None' is not in the registry`. **A119** |
| R9 | insert rRNA depletion above ~40% rRNA | Kopylova 2012 | **cannot be written** as *insertion*; only as a producer swap, and the contract must exist. **A119** |
| R10 | UMI dedup / MarkDuplicates / neither for amplicon | Smith 2017 | **cannot be written.** The third branch is "no step". **A119** |
| R11 | Salmon for transcript-level, featureCounts for gene-level | Patro 2017 | **cannot be written.** The discriminator is `constraints.required_states`, which `when` cannot read. **A120** |
| R12 | HISAT2 when the genome exceeds node RAM | STAR manual 3.2.2 | **clean**, and notable: a "measurement" of the *execution node* loads without complaint (see *Held*) |
| R13 | `cpus` by genome size | nf-core resource labels | **loads and is wrong.** One rule, cited for the aligner, sets `cpus = 12` on TRIMGALORE too. **A123** |
| R14 | MultiQC only when `n_samples > 1` | Ewels 2016 | **cannot be written.** Step presence again. **A119** |
| R15 | infer strandedness when it was not measured | Wang 2012 (RSeQC) | **loads and is dead.** `{when: {strandedness: null}}` validates and can never match. **A122** |
| R16 | any stranded library — `strandedness != unstranded` | Liao 2014 | **cannot be written**, and misdiagnosed: *"'!= unstranded' looks like a comparison but 'unstranded' is not a number. Write it as `\"!= 70\"`"*. **A121** |
| R17 | genome build from organism | Ensembl 112 | **clean.** The archetype this format is good at |
| R18 | `paired AND read_length ≥ 100` | STAR manual 2.2.2 | **clean.** AND-within-a-row control |
| R19 | `--sjdbOverhang` from **max** read length across the cohort | STAR manual 2.2.2 | **cannot be written** without declaring a second measurement. This is §12's *Cohort versus sample*, reached independently — a **confirmation** |
| R20 | a rule naming a contract the local stack does not hold | — | **cannot be written**, by design and correctly. Noted because it is the shape a laboratory writing overlay rules meets first |

## Score

- **6 clean** (R1, R4, R5, R12, R17, R18) — every one is *measurement → comparison or equality →
  literal*. That is exactly §13.1's stated expressive class, and §13.1 is accurate.
- **4 load and are wrong** (R2, R3, R13, R15) — the dangerous column, and the one §13 does not
  describe. Three produce a cited tier-3 value that is not the value the rule means; one is a rule
  that can never fire.
- **1 contortion** (R2b).
- **9 cannot be written** (R6–R11, R14, R16, R19).

## What the twenty rules say about §13

**§13 is confirmed, and understated in one specific way.** §13.2 says the computed rule "cannot be
written. It can only be *enumerated*." The stronger and more useful statement is: **the natural
attempt to write it is not refused.** It loads, it fires, it is cited to a paper, it exits at tier
3 with review level `advisory`, and it reaches the tool. §13 reads as a catalogue of expressive
limits; four of twenty rules make it a catalogue of *silent* limits, which is a different and worse
thing. That is A118 and A122.

**§13 is also incomplete in three places the twenty rules found:**

1. **Step presence is not in §13 at all** (A119). Four of twenty rules — a fifth of a real
   corpus — are about whether a step belongs in the pipeline, not about which producer or which
   value. `nf-core/rnaseq` exposes five of these as top-level flags (`--skip_trimming`,
   `--remove_ribo_rna`, `--skip_markduplicates`, `--with_umi`, `--skip_multiqc`), so this is not an
   exotic class. §13.2–13.4 are about the *contents* of a decision; this is about there being no
   decision to attach it to.
2. **Negation over a non-ordered kind** (A121). §4 of the design lists `==` and `!=` among the
   supported operators and `_validate`'s own message says an enum "can only be compared with
   equality" — but `_comparison()` parses every operator's literal with `float()`, so `==` and `!=`
   are usable on integers and numbers only. The one measurement kind for which equality is the
   *only* sensible operator is the one on which the equality operators do not work.
3. **Scoping** (A123). §13 treats a rule's *inputs* (`when`) and *output* (`then`) but never its
   *subject*. `decides: {param: X}` binds a bare name across the whole registry stack, and
   `_resolve_param` calls `rules.value_for(param_name, profile)` with no contract in hand. This is
   invisible at one-contract-per-parameter scale and certain at forge scale — `threads`, `prefix`,
   `min_length`, `min_quality`, `memory` are common parameter names.

**§13.6's recommended order survives the exercise and should be followed.** The nine rules that
could not be written are the specification for the reform, and they group cleanly:
presence (4), goal-visibility (3), negation (1), cohort statistics (1). None of them needs full
boolean logic, and §8's rejection of it is untouched by anything here.

---

# The findings

## A118 — a computed `then` is emitted, not refused. **Critical. Shape (i). CONFIRMED.**

`DecisionRow.then` is a `ParamValue` and reaches the resolver as `value=row.then`, verbatim.
Nothing validates it against the parameter it decides — `_validate` checks `then` only for
`producer_of` blocks (contract in registry, produces the type). For `{param: X}` blocks there is no
check at all, because a `Param` has no declared domain (Plan-2 correction 6).

**Demonstration.**

```
$ cat audit-tmp/rulelab-base/rules/R02.yml
decisions:
  - decides: {param: sjdb_overhang}
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635 (STAR manual 2.2.2)"
    rows: [{when: {}, then: "read_length-1"}]

$ uv run mendel build --goal examples/rnaseq-goal.yml \
    --registry registry/ --registry audit-tmp/rulelab-base --out audit-tmp/build-r02/
5 modules, 7 requiring review          # sjdb_overhang is NOT among them
```

`audit-tmp/build-r02/pipeline.yml`:

```yaml
  - name: sjdb_overhang
    value: read_length-1
    via: ext
    key: args2
    template: --sjdbOverhang {value}
    why:
      tier: 3
      source: resolver
      reason: 'rule param:sjdb_overhang: Dobin et al. 2013, doi:10.1093/bioinformatics/bts635 …'
```

`audit-tmp/build-r02/nextflow.config`:

```groovy
    withName: STAR_ALIGN { ext.args2 = '--sjdbOverhang read_length-1' }
```

**The only thing that ever refuses this is incidental, and covers one of three routes.** The
spaced spelling `"read_length - 1"` is refused by `MD0201` — a *shell-injection* character class
(`letters, digits and _ . : + -`), not a type check. `read_length-1` is inside that class. And
`substitutable()` is called only on the `via: ext` branches of `emit._ext_scope`; `via: directive`
has no such check:

```
$ cat audit-tmp/rulelab-base/rules/R13.yml     # then: "genome_length / 1000000000 * 4"
$ uv run mendel build … --out audit-tmp/build-r13/
$ grep cpus audit-tmp/build-r13/nextflow.config
    withName: STAR_ALIGN { cpus = 'genome_length / 1000000000 * 4' }
```

**Why this is shape (i) and not a bug report.** The product claim is *nothing was guessed
silently*. This value was not guessed — it was *cited*, to Dobin et al. 2013, at tier 3, review
level `advisory`, in the file a curator signs off. A reader following the citation finds a real
paper that says a real thing, and the pipeline does not implement it. `--gate test` would catch it
because STAR errors; `-stub-run` would not, and `mendel emit` on a shared `pipeline.yml` never runs
either.

**Repair.** Two, and they are separable. (a) Validate `then` against the parameter it decides —
which requires `Param` to have a domain, which is Plan 2 Task 11, which Plan-2 correction 6 already
says to schedule before Task 5. (b) If §13.2's restricted arithmetic form is built, it must be a
*declared* shape (`then: {expr: …}`) so that a bare string can keep being refused rather than
guessed at.

---

## A119 — whether a step exists is not a decidable thing. **Critical. Shape (ii). CONFIRMED.**

`DecisionTarget` admits exactly two targets:

```python
class DecisionTarget(BaseModel):
    param: str | None = None
    producer_of: str | None = None
```

Neither says *whether the pipeline should contain a step*. Presence is decided entirely by
backward chaining from `goal.want` plus `constraints.required_states`, and no tier-3 rule can
reach either.

**Demonstration.** Four of the twenty rules are of this shape. The nearest legal attempt is a
`producer_of` block with a `null` branch:

```
$ uv run python audit-tmp/try_rule.py audit-tmp/attempts/R08-skip-trimming.yml
LOAD-FAILED  R08-skip-trimming.yml
  RuleValidationError: 'None' is not in the registry, so this row can never be applied.
```

Same for R14 (single-sample MultiQC). R9 and R10 fail one step earlier — they can only be phrased
as a producer *swap*, which forces "do not deduplicate" to be modelled as a contract that produces
`alignment.bam[deduplicated]` without deduplicating, i.e. a lie in the type system.

**The field that does not exist, and the reasoning it would hold.** A third target —
`decides: {required_state: {type_id: fastq.reads, state: trimmed}}` or a `skip:` target — with rows
whose `then` is a state set rather than a value or a contract. The reasoning it must carry is
already written in the citations: *"trimming costs a pass over the data and gains nothing below ~1%
adapter (Krueger)"*, *"every read in an amplicon library is a duplicate by construction (Smith
2017)"*. Today that reasoning has nowhere to live, so the decision is made by whoever writes the
goal file, silently, at no tier.

**Why this matters more than it looks.** These are the decisions a biologist is *least* equipped
to make and most likely to get from a chat window — "do I need to trim?", "should I mark
duplicates?" A pipeline that cites Dobin for its aligner and says nothing about why it has no
deduplication step has answered the easy question and not the hard one.

---

## A120 — `when` cannot see the goal. **Important. Shape (ii). CONFIRMED. Confirms §13.3.**

```
$ uv run python audit-tmp/try_rule.py audit-tmp/attempts/R06-twopass-by-purpose.yml
LOAD-FAILED — 'purpose' is not a declared measurement.
$ uv run python audit-tmp/try_rule.py audit-tmp/attempts/R07-mapq-by-purpose.yml
LOAD-FAILED — 'want' is not a declared measurement.
$ uv run python audit-tmp/try_rule.py audit-tmp/attempts/R11-quantifier-by-purpose.yml
LOAD-FAILED — 'nf-core/salmon/quant@1.10.1' is not in the registry
```

§13.3 is confirmed. **One extension.** §13.3 frames this as "the goal's *purpose*", which sounds
like something the goal does not currently carry in a structured way. R11 shows a sharper case:
the discriminator between Salmon and featureCounts is `constraints.required_states:
{counts.matrix: [transcript_level]}` — **structured data the router already reads**, on a closed
vocabulary, in the same `Goal` object `rules.value_for` is called from. A rule cannot see it. That
is a narrower and cheaper repair than "let `when` see purpose", and it does not create the
ordering dependency §13.3 warns about: `required_states` is an input to resolution, not an output
of it, so no stratification argument is needed for that half.

---

## A121 — negation over an enum or boolean is inexpressible, and misdiagnosed. **Important. Shape (ii). CONFIRMED. Not in §13.**

```
$ uv run python audit-tmp/try_rule.py audit-tmp/attempts/R16-any-stranded.yml
LOAD-FAILED  RuleValidationError: '!= unstranded' looks like a comparison but
  'unstranded' is not a number. Write it as `"!= 70"`, with a space.
```

`rules._comparison()` recognises the operator, then does `float(literal)` and raises on failure.
So `==` and `!=` — the two operators `_validate` explicitly permits on a non-ordered kind — work
only on `integer` and `number`. `strandedness != unstranded`, `library_prep != amplicon`,
`organism != homo_sapiens` are all unwritable.

Two costs. The obvious one is that negation must be enumerated, which is tolerable for a
three-value enum and not for an `extensible: true` one — `organism` is declared extensible
precisely because it "can never be enumerated" (§6.3), and a rule that means "any organism except
human" must therefore be rewritten every time an overlay adds a value, or it silently stops
covering the new one.

The second is the message. §5 says *"the error message is the feature… it must say what the author
can write."* This one tells an author writing about strandedness to write `"!= 70"`.

**Repair.** One line in `_comparison`: for `==`/`!=`, return the literal unparsed rather than
through `float()`, and compare with `!=`/`==` directly. `_validate`'s existing enum guard already
permits exactly these two operators, so the validator does not change.

---

## A122 — a row conditioned on absence loads clean and can never fire. **Important. Shape (ii). CONFIRMED.**

`DecisionRow.matches` returns `False` the moment a `when` key is unmeasured:

```python
actual = profile.get(measurement_id)
if actual is None:
    return False
```

So `{when: {strandedness: null}}` — the natural spelling of "when strandedness has not been
measured" — validates, loads, and can never match under any profile. If the measurement is present
the equality fails; if it is absent the `None` guard fires first.

```
$ uv run python audit-tmp/try_rule.py audit-tmp/attempts/R15-strandedness-unknown.yml --build
LOADED       R15-strandedness-unknown.yml
  decision: param:min_length  rows=2
      min_length = 20  tier 3  (rule param:min_length: Wang et al. 2012 …)   # row 2, not row 1
```

§1 of the rule-tables design records the decision *"Dead rules: Impossible — every rule is
validated against the registry at load"*, and §2 says the whole format is downstream of making
that true. That guarantee is about a rule's *target*; it does not extend to a row's *conditions*,
and a row that cannot fire is exactly as dead as a rule that cannot.

The class is real: "infer strandedness rather than assume it" is what `nf-core/rnaseq`'s
`--strandedness auto` does, and it is a decision resting on the absence of a measurement.
`ValueSource.GOAL` vs `MEASURED` is a *second* absence-shaped condition already carried in the data
and equally unreachable from `when` — which is issue #2's requirement (see A127).

**Repair.** Either reject `then`-less absence conditions at load with a message naming what to
write, or give the format an explicit spelling (`when: {strandedness: {measured: false}}`). The
cheap half is the refusal.

---

## A123 — a rule cannot be scoped to a module. **Important. Shape (ii)/(iii). CONFIRMED.**

`decides: {param: X}` binds a bare parameter name across the whole registry stack:

```python
# resolve.py, _resolve_param
pin = rules.value_for(param_name, goal.profile)   # no contract, no node
```

**Demonstration.** `audit-tmp/rulelab-base` declares `cpus` on both `star/align` and `trimgalore`.
One rule, cited for the aligner:

```yaml
  - decides: {param: cpus}
    because: "alignment against a large genome parallelises and is the pipeline's long pole"
    cite: "nf-core process resource labels (process_high)"
    rows: [{when: {n_samples: ">= 1"}, then: 12}]
```

```
$ grep cpus audit-tmp/build-scope/nextflow.config
    withName: STAR_ALIGN { cpus = 12 }
    withName: TRIMGALORE { cpus = 12 }
```

Both settings carry `tier: 3` and the identical aligner citation. There is no syntax to scope the
rule, and no diagnostic reports the second binding.

**Does the design assume a small registry?** Here, yes, and this is the clearest instance found.
`decides` is keyed on a name, `RuleTable`'s stacking key is `param:<name>`, and a higher layer
replaces the whole block for that key. So two laboratories writing rules about *different modules'*
`threads` are writing rules with the same key, and the higher layer wins for both. At today's
registry — two parameters, `seq_platform` and `min_mqs`, one of them on two contracts — the
collision cannot occur. At forge scale it is certain.

**Repair.** `decides: {param: {contract: nf-core/star/align, name: cpus}}`, with the bare form
retained as sugar meaning *any contract*. The decision key becomes `param:<contract>:<name>`, and
the existing whole-block replacement semantics carry over unchanged.

---

## A124 — nothing checks a `producer_of` rule for completeness, and a complete one hides every later producer. **Important. Shape (ii). CONFIRMED. Extends §13.4.**

§13.4's third row — write a `producer_of` rule complete over the alternatives — is called "the only
honest one". Two things are true of it that §13.4 does not say.

**Nothing checks that it is complete.** There is no diagnostic for rule coverage; the 32 codes in
`comeni_core/diagnostics.yml` contain no `exhaust`, `complete`, `coverage` or `unreachable`. §6.2
of the rule-tables design asserts the capability — *"a rule over an enum can be checked for
exhaustiveness in a way free strings would prevent"* — and no such check was ever built. So the
honest option cannot be verified to have been taken.

**A complete rule makes every later producer permanently unreachable, silently.** The shipped
`producer_of: alignment.bam` rule covers `>= 70` and `< 70` — the whole integer line. Adding an
aligner:

```
$ uv run mendel build --goal examples/rnaseq-goal.yml \
    --registry registry/ --registry audit-tmp/newaligner --out audit-tmp/build-new1/
MD0100  nf-core/minimap2/align@2.28   unverified: no module source …
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
```

Identical to the baseline. `minimap2_align` appears in no step, and the only mention of it in
`pipeline.yml` is `registry.unverified`. Nothing says the contract can never be selected under any
profile.

This is the exact mirror of the defect §2 of the rule-tables design was written to kill. Validation
made a **dead rule** impossible; it did not make a **dead contract** impossible, and the mechanism
that closes the first opens the second. `KNOWN_DEAD_RULES` was deleted; nothing replaced it for
contracts.

**Repair.** A load-time report — not a refusal — naming every contract that produces a type covered
by a complete `producer_of` block and appears in none of its rows. That is computable at load with
what `RuleTable.load` already holds (`registry`, `vocabulary`, the block's rows), and it is the
warning §13.4 says "nothing currently" gives the author.

---

## A125 — a tie is answered from the whole candidate list, not the tied one. **Critical. Shape (i). CONFIRMED. §13.4 row 2, and worse.**

**Demonstration.** Goal with no `read_length` measured, so the shipped rule does not fire
(`audit-tmp/goal-no-readlength.yml`).

```
$ uv run mendel build --goal audit-tmp/goal-no-readlength.yml --registry registry/ …
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform                       # STAR, tier 2, priority 10

$ … --registry registry/ --registry audit-tmp/newaligner …   # one contract added, priority 10
5 modules, 3 requiring review
  REVIEW  hisat2_align.seq_platform
  REVIEW  hisat2_align (module)
  REVIEW  minimap2_align.producer:alignment.bam
```

Adding a contract that ties with STAR causes the pipeline to be built with **HISAT2** — the
candidate the registry ranked *last*, `priority: 0`, against STAR's deliberate `priority: 10`.

The mechanism is in `router._choose`:

```python
ordered = sorted(candidates, key=rank)          # rank = (surplus, -priority, id)
ambiguity = ProducerAsked(..., candidates=sorted(c.id for c in ordered), ...)
```

`sorted(c.id for c in ordered)` **discards the ranking** and hands the resolver every producer in
alphabetical order. `FlagOnlyResolver` returns `candidates[0]`, and `hisat2` sorts first.

**And the artifact states something false.** `audit-tmp/build-norl-new/pipeline.yml`:

```yaml
    reason: 'nothing distinguishes nf-core/minimap2/align@2.28, nf-core/star/align@1.11.0,
      nf-core/hisat2/align@2.2.2; chosen by flag-only: …'
```

`priority` distinguishes HISAT2 from the other two, deliberately, and `star-align.yml` carries a
comment saying why. Two contracts tied; three are reported as indistinguishable, and the pipeline
was built from the one that did not tie.

**Shape (ii) underneath it.** `ProducerAsked` has one `candidates` list and no way to say *which of
these actually tied*. A model behind door 2 (Plan 2 Task 5) will be asked to choose among options
the deterministic ladder already ranked and rejected, with no field carrying the ranking.

**Repair.** Two lines and a field. Hand the resolver only the tied subset — the candidates equal to
`ordered[0]` on `rank(...)[:2]` — and, if the full list is genuinely useful to a model, add a
declared `rejected: list[ContractId]` to `ProducerAsked` so the two are not confused. Both fit
inside invariant 8 rather than changing it.

**Also demonstrated: §13.4 row 1, the guess wearing a tier-2 label.** With the newcomer at
`priority: 11`:

```
$ … --registry audit-tmp/newaligner --out audit-tmp/build-norl-prio/
1 overlay reroute(s) …
  OVERLAY  minimap2_align (module) = audit/bwa… from 'audit-newaligner', displacing …
4 modules, 0 requiring review
```

A long-read DNA aligner replaces STAR, the STAR index step disappears, and the pipeline reports
**zero** things requiring review, at `tier: 2`, `reason: registry priority 11, over …`. Invariant
11's OVERLAY line does fire and is the one thing standing between this and total silence — see
*Held*.

---

## A126 — a producer decision has no stable identity, so installing one contract orphans a curator's override. **Critical. Shape (i) and (ii). CONFIRMED.**

`Ambiguity.key()` is `f"{node_id}.{subject}"`, and for a producer decision `router._choose` sets
`node_id=_node_id(ordered[0])` — **the top-ranked candidate's process name**. Which contract ranks
first is a function of the registry's contents. So the identity of the question *"which contract
produces `alignment.bam` here?"* changes when the registry changes, which is the one event
`mendel upgrade` exists to survive.

It is already visibly wrong in the baseline artifact: `audit-tmp/build-orphan/pipeline.yml` records
`key: minimap2_align.producer:alignment.bam` while the pipeline's steps are `trimgalore`,
`hisat2_build`, `hisat2_align`, `samtools_sort`, `subread_featurecounts`. **`minimap2_align` is not
a node in the pipeline.**

**Demonstration.** A curator answers the tie by hand — `human_override:
nf-core/star/align@1.11.0` — exactly as federation §4.3 intends. Control, same stack:

```
$ uv run mendel upgrade audit-tmp/build-orphan/pipeline.yml \
    --registry registry/ --registry audit-tmp/newaligner --dry-run
  CHANGED   star_align: (absent) -> nf-core/star/align@1.11.0  (tier 4) … chosen by replay …
1 decisions replayed, 1 newly asked
```

The override replays; STAR comes back. Now install **one more contract** (`audit/bwa/mem@0.7.18`,
same priority, id sorts first) and change nothing else:

```
$ uv run mendel upgrade audit-tmp/build-orphan/pipeline.yml \
    --registry registry/ --registry audit-tmp/newaligner --registry audit-tmp/bwa --dry-run
  CHANGED   bwa_mem: (absent) -> audit/bwa/mem@0.7.18  (tier 4) nothing distinguishes … chosen by flag-only …
0 decisions replayed, 1 newly asked
  ORPHANED minimap2_align.producer:alignment.bam — your edit no longer applies to anything

mendel: MD0203: 1 recorded override(s) answer questions this re-resolution does not ask.
```

**The diagnosis is false.** The question *is* being asked — it is the `1 newly asked`, one line
above, under the name `bwa_mem.producer:alignment.bam`. The curator is told their answer applies to
nothing, when in fact it applies to a question that has been renamed by a contract they did not
choose to install.

CLAUDE.md, on curated pipelines: *"Editing a curated pipeline replays every untouched decision from
its record, so only what you touched can move."* Nothing was touched and the decision did not
replay.

**Shape (ii): the field that does not exist.** A producer decision's honest identity is *the
consumer port that needed the type, plus the states it required* — "the `bam` port of
`samtools_sort`, requiring nothing". `ProducerAsked` carries `states` but has no field for the
requesting node or port; `router.satisfy` knows both at the call site and passes neither.

**Repair.** Give `ProducerAsked` the requesting site (`for_node`, `for_port`) and key on it. That
also makes the key readable — `samtools_sort.bam.producer:alignment.bam` names a place in the
pipeline rather than a candidate that may not be in it.

**Credit where due:** `MD0203` refuses to write. The operator is blocked, not silently harmed —
which is why this is a critical *correctness of the trace* finding rather than a data-loss one.

---

## A127 — a tier-3 parameter records neither the row nor the measurements it rested on. **Important. Shape (ii)/(iii). CONFIRMED.**

`ResolvedValue` carries `value`, `tier`, `source`, `reason`, `from_layer`, `displaced_layer`. There
is no field for the rule id, the matching row, or the measurements the row read.

**The two tier-3 sites disagree about what they record.** `router._choose`, for a module:

```python
f"rule {pinned.decision.decides.key()} matched {pinned.row.when}: {pinned.because()}"
```

`resolve._resolve_param`, for a parameter:

```python
reason=f"rule {pin.decision.decides.key()}: {pin.because()}"
```

The `when` is dropped. In a built artifact:

```yaml
    why: {tier: 3, source: resolver,
          reason: 'rule param:cpus: nf-core process resource labels (process_high)'}
```

A reader is told a rule matched and is not told **what fact it matched on**. Tier 3 means "a
declared rule matched measured data"; the measured data is absent from the record. Where the module
case does carry it, it carries it as prose inside a free-text field.

**The shape-(iii) half: issue #2 cannot be built as an artifact check.** The `sealed` profile must
refuse a tier-3 decision resting on an *asserted* rather than *measured* value. The evidence for
"asserted" exists — `Measured.source` is `goal` vs `measured`, and it survives into
`pipeline.yml`. The *linkage* does not: nothing joins a tier-3 decision to the measurements it
consumed. So `ProfilePolicy` can only be implemented inside `resolve()` at the instant the pin
fires, and a clinical laboratory reviewing or re-verifying a published `pipeline.yml` cannot
perform the check at all.

**Repair.** `ResolvedValue` gains `from_rule: DecisionKey | None` and `on: list[MeasurementId]`
(the row's `when` keys). Both are available at both call sites today — `Pin` carries
`decision.decides.key()` and `row.when`. `pipeline.yml` gains two fields per tier-3 setting, and
the check becomes a function of the artifact.

---

## A128 — tier 2 promises a citation; `priority` has nowhere to put one. **Important. Shape (ii). CONFIRMED.**

`docs/design/mendel.md` §6.1: tier 2 *"a documented default exists for this context"*, producing
*"value + citation"*. Two mechanisms produce tier-2 values and neither has a citation field.

For a **module selection**, the mechanism is `ModuleContract.priority: int`. The contract model has
no field for why the integer is what it is; `Provenance` carries `source`, `drafted_by`,
`approved_by`, `approved_at` and no `cite`. The emitted reason is
`registry priority 11, over nf-core/star/align@1.11.0, nf-core/hisat2/align@2.2.2` — who won and
by how much, never why.

The shipped registry *has* the justification, in a place nothing can reach:

```
$ grep -rn 'nf-core/rnaseq default aligner' registry/
registry/contracts/nf-core/star-align.yml:19:# STAR is the nf-core/rnaseq default aligner, so this registry prefers it by
$ grep -rl 'default aligner' audit-tmp/build-baseline audit-tmp/build-norl-prio
(no matches)
```

A YAML comment. `yaml_strict.load` discards it, so it reaches no digest, no `pipeline.yml` and no
reader. `priority` does not appear in `docs/reference/pipeline-schema.md` at all.

For a **parameter**, `Param` has `default` and no `cite`, and the reason is the tautology
`contract default for min_mqs`.

**Overlap note.** Stream 1's brief carries *"a tier-2 'documented default' is only honest if a
document exists — check that the citation behind a convention is real."* This is that question
reached from the v2 side, and the stream-4 point is the second half: **§13.4's first row is
confirmed** — at v2 breadth `priority` is the only thing ranking alternatives, and it is a
purpose-independent scalar with no document behind it and no field to hold one. If stream 1 files
the same observation, this is a corroboration and the two should be merged.

**Repair.** `ModuleContract.priority_because: str | None` and `Param.cite: str | None`, both
surfaced in the `why:` block. Cheap, and it turns "tier 2" from a label into a claim somebody signed.

---

## A129 — two of three tier-4 question kinds cannot cross door 2. **Critical for Plan 2. Shape (iii). CONFIRMED.**

`AmbiguityRequest.candidates` is `list[ContractId]`. The three ambiguity kinds carry:

| kind | `candidates` type |
|---|---|
| `ProducerAsked` | `list[ContractId]` |
| `ParamAsked` | `list[ParamValue]` — `int \| float \| bool \| str \| None` |
| `SourceAsked` | `list[EdgeRef]` — `<identifier>.<identifier>` |

`tests/test_egress.py::test_every_ambiguity_field_can_cross_the_door` passes, and says why in its
own comment: it asks whether each ambiguity field "has somewhere *to go*", by name.

**Demonstration** — `audit-tmp/door2_projection.py` writes the total projection Plan 2 Task 5 must
write, and runs it against all three kinds:

```
crosses       ProducerAsked (router tie)
   candidates=['nf-core/star/align@1.11.0', 'nf-core/hisat2/align@2.2.2']

CANNOT CROSS  ParamAsked (tier-4 parameter)
   candidates.0  Input should be a valid string [input_value=None]

CANNOT CROSS  SourceAsked (two upstreams tie)
   candidates.0  Value error, 'star_align.bam' is not a contract id.
   candidates.1  Value error, 'samtools_sort.bam' is not a contract id.
```

**Consequence for Plan 2.** Task 5's `LLMResolver` must build an `AmbiguityRequest`. For the
*parameter* case it will find `[None]` unrepresentable, and the obvious workaround — send `[]` — is
Plan-2 correction 6's failure mode made literal: *"asking a model an open question with no
legal-value set is the chat-window failure mode wearing a tier label."* For the **source** case it
is worse, because the candidates genuinely exist and are genuinely closed: a model asked "which
upstream output feeds this port?" would be handed an empty list while two perfectly good answers sit
in the `SourceAsked` it was projected from.

**Relationship to #32 (A68).** Same family — a totality guard comparing names — on a *different*
guard (`test_pipeline_totality` vs `test_egress`), with a different consequence. Not a duplicate,
but they should be fixed together, because the fix is the same one: check the field has a home *of
the right type*, not merely a name-match.

**Repair.** Either widen the door (`candidates: list[ContractId] | list[EdgeRef] | list[ParamValue]`
— note the egress guard's allowlist must be taught each), or give `AmbiguityRequest` one candidate
field per kind. Whichever, `test_every_ambiguity_field_can_cross_the_door` must construct a real
projection of a real instance of each kind, which is what would have caught it.

---

## A130 — the artifact cannot state that no model was consulted. **Important. Shape (ii). CONFIRMED.**

A56 established that `Resolution.source` is a claim a resolver cannot be trusted to make, and moved
its honouring to caller-supplied evidence. The brief asks what else in that protocol is
trust-shaped. Three fields are, and one of them matters.

**Demonstration** — `audit-tmp/lying_resolver.py`, a resolver reporting itself as the deterministic
fallback:

```python
return Resolution(chosen="illumina",
                  reason="documented convention for this sequencing centre",
                  confidence=0.99,
                  resolved_by="flag-only",          # it is not
                  source=ValueSource.HUMAN)         # it is not
```

```
key         : star_align.seq_platform
chosen      : 'illumina'
resolved_by : 'flag-only'   <- written by the resolver, unchecked
confidence  : 0.99          <- written by the resolver, read by nothing
reason      : 'documented convention for this sequencing centre'
tier        : 4
human_override: [None]
  star_align.seq_platform: value='illumina' tier=4 source=resolver review=required
needs_review: ['star_align.seq_platform']
```

**A56's fix holds** — the `HUMAN` claim was demoted to `resolver`, `human_override` stayed `None`,
and the review flag survived. That is the *Held* half and it was verified first-hand.

What does not hold is provenance. `resolved_by` is written verbatim into every `DecisionRecord` and
reaches the published artifact; `grep` finds no reader of it or of `confidence` anywhere outside
tests. So:

- `confidence` is stored, published, and read by nothing. mendel.md §5.4 lists it as part of the
  decision record; invariant 6 makes it non-actionable by design. It is a field that looks like
  evidence and is not.
- `resolved_by` is the **only** trace in the whole artifact of whether a model was in the loop, and
  it is written by the component whose involvement it reports.

**The claim that cannot be stated.** CLAUDE.md sells three model-access lanes and says *"`--no-ai`
must keep working forever… it is how the deterministic guarantee stays testable"*. A recipient of a
`pipeline.yml` — the shareable, publishable, curatable artifact — has no field that says *no model
was consulted in producing this*. Tiers 1–3 emit no `DecisionRecord` at all, so absence of a record
is not evidence either. The question "was AI involved in this pipeline?" is answerable only by
trusting a string the AI adapter wrote about itself, which is exactly the standing A56 rejected one
field over.

**Repair.** A build-level fact, recorded by the caller rather than by the resolver: the
`Pipeline` gains a declared field naming the resolver implementations installed for the build (and
`--no-ai` writes the value that means none). `cli.py` knows this and nothing else does. That is the
same shape as `prior` in `resolve()` — evidence from the party that cannot benefit from lying.

---

## A131 — "the error message is the feature" inverts at registry scale. **Minor. Shape (iii). CONFIRMED.**

`rules._validate`, for a `{param: X}` target, ends its refusal with every parameter name in the
registry. §5 of the rule-tables design says of that line: *"The last line carries most of the
value."*

**Demonstration** — `audit-tmp/make_big_layer.py` generates a synthetic layer; `measure_error.py`
introduces a one-character typo in a rule against 2,000 contracts:

```
error type : RuleValidationError
characters : 40185
lines      : 3
longest ln : 40049
```

A 40,049-character single line. The same shape recurs in `resolve._declared_types` ("Declared: " +
every type), `Vocabulary` state errors, and `measurements.get`'s KeyError.

Filed as minor because it is a message, not a mechanism. Filed at all because it is the cleanest
answer to *"does the design assume a small registry?"*: the feature §5 identifies as carrying most
of the value is one that stops working somewhere between ten contracts and a hundred, and the
forge's whole purpose is to cross that line. The repair is a fuzzy-match shortlist
(`difflib.get_close_matches`) plus a count — better at both scales.

---

# Clean — attacked and held

**Everything below was attacked deliberately and survived. Where a number is quoted it was measured
in this worktree.**

**The rule format's stated expressive class is exactly what §13.1 says it is.** Six of twenty rules
wrote cleanly with no contortion, and every one is *measurement → comparison or equality → literal*:
comparison with a catch-all row (R4), enum equality (R5), enum-to-literal one row per value (R17),
AND-within-a-row (R18), multi-condition producer selection (R12), and the shipped control (R1). The
grouped-block shape does what §3 claims — a missing branch is visible because the branches are
adjacent. **§8's rejection of full boolean logic is untouched by anything in this stream**; none of
the nine unwritable rules needs nesting, and the repairs they imply are new targets and new
condition *sources*, not a constraint language.

**An empty `when: {}` is a working catch-all**, so "otherwise" is expressible and row order does
what §4 says. Attacked by relying on it in R4, R5, R6, R13 and R15; it behaves.

**Load time does not break at the scale the forge is committed to.** Measured, stacked over
`registry/`:

| contracts | rules | `layers.load()` |
|---|---|---|
| 500 | 100 | 0.95 s |
| 2 000 | 400 | 4.15 s |
| 2 000 | 2 000 | 7.18 s |

There *is* an O(rules × contracts × params) term — `_validate` rebuilds the whole parameter-name
set once per decision — and it contributes about 3 s of the last row. It is a one-line hoist and it
is not a design finding; recorded so the next person measures rather than guesses.

**A tier-4 value of `None` is handled correctly everywhere it lands.** `emit._ext_scope` skips the
fragment (with the reasoning written out), the `meta` map omits the key, and no `cpus = null`
appears in the config. The module's own default takes over, which is the honest answer, and
`needs_review()` still names it. Attacked with seven simultaneously-unanswered tier-4 parameters
across three contracts.

**A56's fix holds under a resolver that lies about it.** A `Resolution` claiming
`source=HUMAN` with no backing record in `prior` was demoted to `resolver`, `human_override` stayed
`None`, and the value stayed in `needs_review()` at tier 4. Invariant 6 survived a hostile
implementation of the port. Verified first-hand (`audit-tmp/lying_resolver.py`).

**Invariant 11's displacement reporting fires on the case that matters.** When the added contract
won on priority and rerouted the pipeline, `mendel build` printed
`OVERLAY minimap2_align (module) = … from 'audit-newaligner', displacing 'comeni-registry-examples'`.
That line is the one thing standing between A125's priority branch and total silence, and it works.

**`MD0213` and `MD0203` both refuse rather than proceed.** Editing `pipeline.yml` and running
`upgrade` without re-emitting is refused naming the fix; an orphaned override stops the write
entirely. A126 is a wrong *diagnosis*, not a silent loss.

**`MD0201` catches the half of A118 it is aimed at**, and its message asks for the counterexample it
did not anticipate — which is how the spaced form of the computed rule was caught. The finding is
that it is a shell-injection class doing a type check's job on one of three routes, not that it is
weak at its own job.

**Validation against the registry does what §2 and §5 promise, and the messages name the offending
thing.** Every one of the nine unwritable rules failed at *load*, in `mendel_resolver.layers.load`,
naming the file, the decision, the offending key and (for measurements) what is declared instead.
Nine for nine. `R20` — a rule naming a contract the local stack does not hold — is refused exactly
as designed, and that refusal is correct even though it is the first thing a laboratory writing
overlay rules will meet.

**A measurement of the execution environment loads without complaint.** `available_ram_gb`
(`kind: integer`, no `describes:`) declares, validates and matches in R12. Recorded as *held* rather
than as a finding: `describes:` is optional today and there is a coherent reading in which node RAM
is a measurable fact like any other. It is flagged here only because `mendel profile` would then be
asked to emit a pipeline that measures it, and because `ValueSource.MEASURED` vs `GOAL` — the
distinction issue #2 rests on — means something different for a fact about a machine than for a
fact about the data. Worth a decision before the forge starts drafting measurements (#38); not a
defect now.

**Not attacked, and named so nobody assumes coverage:** whole-block rule layering and its
displacement records (§9); `UnroutablePinError` and pin-binding semantics; `InputPort.accepts` /
`prefer` alternative ordering (§8); the conformance diagnostics MD0100–MD0108; `mendel publish`;
the emitted Groovy beyond the two lines A118 turns on; the four guards, per the brief's scope
boundary.

---

# What was left behind

Everything is under `audit-tmp/` in this worktree, 6.1 MB, nothing outside it was modified.

| Path | What |
|---|---|
| `attempts/*.yml` | the twenty rule attempts, verbatim. **The primary artifact of this stream** |
| `try_rule.py` | loads one attempt as an overlay over `registry/`; `--build` also resolves and prints every value with its tier |
| `run_all.py` | runs all twenty and prints the table |
| `rulelab-base/` | the scratch layer: 7 measurement declarations, 3 contracts carrying 8 parameters, plus the two rules used in A118 and A123 |
| `newaligner/`, `bwa/` | one added `alignment.bam` producer each — A124, A125, A126 |
| `goal-no-readlength.yml` | the goal that makes the shipped rule not fire, so the tie is reachable |
| `build-baseline/`, `build-r02/`, `build-r13/`, `build-scope/`, `build-new1/`, `build-norl-{base,new,prio}/`, `build-orphan/` | the builds each finding cites. `build-orphan/pipeline.yml` carries the hand-added `human_override` A126 turns on |
| `door2_projection.py` | A129 — the door-2 projection Plan 2 must write |
| `lying_resolver.py` | A130 — and the A56 *Held* result |
| `make_big_layer.py`, `measure_error.py` | A131 and the load-time table. The generated 2,000-contract layer was deleted; regenerate with `uv run python audit-tmp/make_big_layer.py 2000 2000` |

`registry/`, `packages/`, `tests/` and `docs/` are untouched apart from this file.
