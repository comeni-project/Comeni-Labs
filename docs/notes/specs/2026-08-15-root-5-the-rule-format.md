# Root 5 — the rule format, re-derived

**Status: design authority for the root-5 repair. Not yet planned, not yet built.**

Root 5 of the [2026-08-14 design audit](../audits/2026-08-14-design-audit.md) is that the
tier-3 rule format is narrower than the domain it must express: 6 of twenty real rules clean,
4 loading and wrong, 1 contortion, 9 unwritable. The audit said the reform must not be designed
abstractly, because the nine unwritable rules are its specification and they are on disk at
[`../audits/fixtures/rule-attempts/`](../audits/fixtures/rule-attempts/).

This spec was written that way. Every claim in it was run before it was written, against the
twelve contracts actually in `registry/`, and the section that matters most —
[§8](#8-what-broke) — is the four things that broke while running it, two of which were flaws in
earlier drafts of this document.

**Closes:** A119, A120, A121, A122, A123, A124, A127, and A108 and A113 as consequences.
**Does not close:** A118 and A124's exhaustiveness half, both of which wait on declared domains
([§7.1](#71-declared-domains)). A97 ([§7.2](#72-role-instancing)).

---

## 1. The principle: a tier means what it says

`docs/design/mendel.md` §6.1 defines the ladder by a column `CLAUDE.md`'s summary drops, and it
is the load-bearing one:

| Tier | Fires when | **Produces** | Review |
|---|---|---|---|
| 1 structural | no choice exists | value + **the forcing constraint** | none |
| 2 convention | a documented default exists | value + **citation** | none |
| 3 data-profiled | a rule matched measured data | value + **rule + measurement** | advisory |
| 4 ambiguous | no rule matched | proposal + **reasoning + alternatives** | required |

The ladder is not sorted by confidence. It is sorted by **what a reviewer must check**, because
each tier produces a different kind of evidence and each kind fails differently. Tier 3 is the
only tier whose evidence has two independent parts, which is the entire reason it is yellow: the
rule can be right and the measurement wrong, and you get a confidently wrong pipeline.

**Today a tier is assigned by which code path ran. It must be computed from the evidence
produced.** Those come apart, and every place they come apart is already a filed finding. From a
real build of `examples/rnaseq-goal.yml` — 18 `why:` blocks, 12 tier 1, 3 tier 2, 1 tier 3,
2 tier 4:

| In the artifact | Claims | Actually produces | |
|---|---|---|---|
| `the only contract that produces this` ×4 | tier 1 | a fact about registry contents | **A113** |
| a catch-all row match | tier 3 | value + rule, **no measurement** | **the catch-all defect** |
| `selected the first of 1 candidates without judgement` ×2 | tier 4 | no alternatives, no proposal | **A83** |
| goal-pinned strandedness ×2 | tier 1 | the user removed the choice | correct — `tiers.py` says why |
| `the reference is only needed to write CRAM` | tier 1 | a real type-graph constraint | correct |
| the aligner | tier 3 | value + rule + measured read length | correct |

So: **a decision's tier is a function of the evidence it produced, and is therefore checkable.**
The assertion *every tier-3 decision carries a non-empty premise* becomes a guard that can be
watched failing, which is impossible today because tier 3 is a label rather than a claim.

This generalises Plan 1.14 rather than contradicting it. A76 and A128 were the same defect one
rung down — *tier 2 promises a document and had nowhere to put one*. 1.14 fixed those two
instances; this states the rule that produced them.

### 1.1 The four "only contract" cases resolve through the effect split

Today one `why:` answers two questions at once. Separate them ([§4](#4-the-decision-layer)) and
each earns its tier honestly:

- **presence of `bam_sorting` → tier 1.** featureCounts requires `alignment.bam[coordinate_sorted]`;
  the type graph forces a sorter to exist. A real forcing constraint.
- **implementation of `bam_sorting` → tier 2, uncontested.** One candidate *in this stack*. If a
  lab installs a second it becomes a real choice and climbs the ladder on its own.

**This does not grow the review queue.** Tier 1 is silent and tier 2 is green; neither asks for
review. What changes is that the artifact stops claiming the inputs forced something the registry
happened to force.

---

## 2. Two layers

    PREMISE    measurements (measured or asserted) + goal facts + DERIVED facts.
               This is what `when` reads. Every premise carries its provenance.

    DECISION   premises -> a scoped effect on a ROLE. Three effects: presence, param,
               implementation.

The split is not a preference. It is already in the corpus: R15 ("infer strandedness when it was
not measured") and R19 ("max read length across the cohort") do not conclude anything about a
pipeline — **their output is a measurement value.** Today they must be crammed into a decision
format, which is exactly why R15 loads dead (A122) and R19 cannot be written at all.

### 2.1 Both layers live in `rules/`, and there is one of it

A layer's `rules/` directory holds both. A file may carry `derives:`, `decisions:`, or both, and
is parsed by one `Kind[str, Derivation | Decision]` — the same union shape
`Kind[str, Measurement | MeasurementDelta]` already uses, so this is not a new pattern.

**One directory, for three reasons.** A reader asking *"what decides the aligner"* has one place
to look, and a second directory would require knowing which half of the design a thing belongs to
before being able to find it. A derivation and the decision consuming it are usually one thought —
`adapter_free` exists solely to feed `presence: trimming`, and splitting them means a reviewer
reads half an argument. And the stacking machinery is per key rather than per file, so nothing is
gained by separating them physically.

**Keys are namespaced**, because `stack()` has one key space per kind:

| | key |
|---|---|
| a derivation | `derive:adapter_free` |
| presence | `presence:trimming` |
| implementation | `implementation:alignment` |
| a param | `param:quantification:min_mqs` |

`Policy.REPLACE` applies **per key, not per file**. A lab overlaying `derive:adapter_free`
replaces that derivation and leaves `presence:trimming` alone even when the base declared both in
one file. That is the property the A119 repair rests on: two things written together are still two
independently replaceable units, and a rule about one subject can no longer delete a rule about
another.

**The twenty rule attempts under `notes/audits/fixtures/rule-attempts/` are not a layer.**
They are evidence, they are not loaded, and Task 11 of the plan is what turns them into tests.

**A fact-only format was considered and rejected.** Under it, R09 reads well — the rule concludes
*"rRNA carry-over is high"* citing Kopylova 2012, and the contract says SortMeRNA removes rRNA.
But run R01 through it: the fact is *"reads are long"*, and something must still say **long reads
→ STAR**. That is not a fact about data; it is a judgement about tools, and Dobin 2013 is the
citation for *that*. Under a fact-only format it migrates into the STAR contract as a
`when_appropriate:` clause — a rule table again, scattered across contracts and keyed by contract
instead of by decision, losing the property `rules.py` was built for: *a reviewer should read one
block and see the entire effective decision*, which is also what lets them notice a **missing
branch**. Fact-only optimises the nine rules that fail and breaks the six that work.

---

## 3. The premise layer

A premise is a fact `when` may read, carrying `id`, `value`, `origin` and — where derived — what
it was derived from. Origins: `measured`, `asserted`, `goal`, `derived:<fact>`, `unmeasured`.

Premises are built in **one pass, no fixpoint**: measured, then asserted, then goal, then derived.

### 3.1 A derivation naming a declared measurement is a fallback

It may fill a gap and may never overwrite. That is what makes R15 expressible and it is the shape
A122 refused — a row conditioned on an absent measurement loaded clean and could never fire.

```yaml
derives:
  - fact: strandedness
    kind: enum
    rows:
      - when: {strandedness: absent}
        then: reverse
        because: >-
          dUTP protocols dominate current library prep, so reverse is the safer default
          where nothing measured it — and this records that nothing did
        cite: "Wang et al. 2012, doi:10.1093/bib/bbs046"
```

### 3.2 Aggregation over a cohort

R19 and §12's cohort-versus-sample question, which the shipped format cannot express at all:

```yaml
  - fact: cohort_max_read_length
    kind: integer
    aggregate: {measurement: read_length, over: cohort, using: max}
```

### 3.3 A derived fact from a catch-all is a default, not a derivation

The same defect as §1's catch-all, one layer down: a derivation that matched an empty `when`
records no `derived_from`, so the premise chain lies. It must be recorded as a default with a
citation, on the same rule as §4.4.

---

## 4. The decision layer

### 4.1 A decision names a role, never a type and never a bare name

A rule's target naming a **type** is the root of A119 and A123 together. Reproduced first-hand on
2026-08-15 (§8.1): because presence has no target, an author writing R10 reaches for
`producer_of: alignment.bam` — *the same key the shipped aligner rule uses* — and REPLACE
stacking silently deletes the aligner rule. A 50bp goal that routed to HISAT2 routes to STAR, both
builds green at exit 0.

So a contract declares the **roles** it fills, and a decision names a role:

```yaml
decides: {effect: presence,       of: trimming}
decides: {effect: implementation, of: alignment}
decides: {effect: param,          of: quantification, name: min_mqs}
```

The key is `(effect, role[, name])`. Two unrelated decisions can no longer collide, and a rule no
longer names a contract, which dissolves R20 — *a rule naming a contract the local stack does not
hold* — into a role that nothing fills.

**`roles:` does not exist on `ModuleContract` today.** It is an addition this design requires.

### 4.2 A decision may emit several effects

Gap: `star_ignore_sjdbgtf` should depend on whether the index was built with the GTF — *another
decision*, not a premise. Allowing decisions to read decisions buys ordering, cycles, and the loss
of the single pass.

The resolution is that the framing was wrong. **If decision B depends on decision A, then B is not
a separate decision — A and B are one choice landing on two tools.** "Where the annotation is
used" *is* `sjdbGTFfile` on the builder and `star_ignore_sjdbgtf` on the aligner: one premise, one
citation, two flags.

```yaml
  - decides:
      - {effect: param, of: index_building, name: sjdbgtffile,
         when_implementation: [nf-core/star/genomegenerate@1.11.0]}
      - {effect: param, of: alignment, name: star_ignore_sjdbgtf,
         when_implementation: [nf-core/star/align@1.11.0]}
    because: >-
      splice junctions can be supplied when the index is built or at align time, and the two
      must agree; building them in is nf-core/rnaseq's default and costs nothing at align time
    cite: "STAR manual 2.2.3"
```

**Decisions may never read other decisions.** That restriction is what this rule buys.

### 4.3 A param effect must not be dead

`star_ignore_sjdbgtf` is STAR's alone. Validating against the union of params across a role's
fillers accepts a value that is dead whenever HISAT2 wins — the *deadness* of issue #10, arriving
one layer earlier. So a param must be declared by **every** contract that could fill the role, or
the rule must narrow with `when_implementation:`. Refused at load:

> `'star_ignore_sjdbgtf'` is not declared by `nf-core/hisat2/align@2.2.2`, which can fill role
> `'alignment'`. The value would be dead whenever one of those wins. Either narrow with
> `when_implementation:`, or decide a param they all declare.

### 4.4 A row's tier is determined by the rule text

    when: {}                        a catch-all — a documented default. Tier 2.
    when: {strandedness: absent}    nothing measured it, so this is a convention about what
                                    to assume in the gap. Tier 2 — and R15's real tier.
    when: {read_length: ">= 70"}    a premise tested positively. Tier 3.

A row earns tier 3 only by testing a premise **positively**. An absence is still evidence and is
still recorded; it is evidence of a *gap*, which is a convention to fill rather than data to
profile.

Two consequences. **A row that will exit at tier 2 must carry a citation** — tier 2 produces
`value + citation` — enforced at load, because the row's tier is a property of its text. And
because the tier is static, an author sees each branch's tier while writing it, and a reviewer can
predict a build's review load from the rules rather than from a run.

### 4.5 Predicates

Equality; comparison (`">= 70"`); `absent` / `present`; `{not: <value>}`; `{in: [...]}`.

`{not: unstranded}` is A121, whose refusal today misdiagnoses an enum as a malformed number
because `_comparison` runs every literal through `float()`. One evaluator, shared by load-time
validation and runtime matching, because two copies of the predicate is how a rule passes
validation and then fails to fire.

### 4.6 What `when` may read

Measurements, derived facts, **and goal facts** — `purpose` and `required_states`. That is A120,
and `required_states` is the half the router already consults, which closes R11 alone.

**`purpose` is a declared measurement, not a new field on `Goal`.** Checked against the code on
2026-08-15: `Goal` carries `have`, `want`, `constraints` and `profile`, and adding a field to it
would widen a door-1 *and* door-4 payload, pulling in the egress guard and invariant 14's literal
list. None of that is necessary. `Measured` already records a per-entry `source`, and
`ValueSource.GOAL` already means *"asserted by whoever wrote the goal"* — so a goal file writing
`profile: {purpose: variant_calling}` gets validation from `MeasurementRegistry.profile()` and
provenance for free. `n_samples` is the precedent: a measurement that describes the *study*
rather than a read, with no `describes` and no `meta_key`.

That the answer costs nothing is a consequence of the premise layer, not a coincidence. Once
`when` reads *premises* rather than *measurements*, "the goal said so" is just another origin.

### 4.7 A rule is written by a person, and read by one

Every part of this format is authored by hand in YAML and read back in a diff. That is a
constraint on the design, not a presentation concern applied afterwards.

**Authoring.** `decides: {effect: presence, of: trimming}` says what it does in the words a
biologist would use. The format it replaces did not: `decides: {producer_of: fastq.reads}` with
`then: null` was how one had to spell *"do not trim"*, and the refusal it earned —
`'None' is not in the registry` — blamed a misspelled contract. A role and an effect are English;
a type id and a null are not.

**Every refusal names the offending thing and what would have been right.** That rule is already
this repository's practice (`MD0104`, `MD0300`) and §5 holds every new code to it. A message that
says only what is wrong makes the author guess, and guessing is what the whole product opposes.

**No structured value is a reader's only account of itself.** See §6.

---

## 5. Everything is refused at load

Run against the twelve shipped contracts; each message names the offending thing.

| Attempt | Refusal |
|---|---|
| `min_mqs` scoped to `trimming` (A123) | not declared by `nf-core/trimgalore@0.6.10`, which can fill role `trimming` |
| no catch-all (A124) | the last row has a `when`, so some premise leaves this decision unanswered — **but see [§7.1](#71-declared-domains): this check as written would refuse the shipped aligner rule** |
| two blocks, one key (A119) | both decide `presence:trimming` in the same layer |
| a contract the stack lacks (R20) | `nf-core/salmon@1.10.0` does not fill role `alignment` |
| an undeclared premise | `gc_content` is not a declared premise |
| a presence effect whose `then` is a contract | a presence effect is `present` or `absent` |
| a param dead under the other implementation | see §4.3 |
| a row justifying nothing (MD0301) | justifies nothing |
| a tier-2 row with no citation | this row tests no premise positively, so it exits at tier 2 |

**Justification checks run last.** The citation check firing before the structural checks reported
*"salmon does not fill role alignment"* as *"this row needs a cite"* — three of nine messages were
wrong until reordering. The least specific check must run last; this is A74/A75's family.

---

## 6. What reaches `pipeline.yml`, and how it reads

Every decision records the premises it read, with each one's origin. In scenario B of §8, a build
where nothing measured strandedness:

    tier 3  param:alignment:save_unaligned = True
            premise={'strandedness': 'reverse'}  origin={'strandedness': 'derived:strandedness'}

The artifact states that this rested on an **inferred** value. That is A108 — *tier 3 is advisory,
"check the premise", and the artifact carries no premise* — arriving as a consequence rather than
as separate work, and it is the hook `ProfilePolicy` needs for issue #2, where `sealed` must
refuse a tier-3 decision resting on an assertion.

### 6.1 The premise is prose first and a mapping second

A mapping is what a policy reads. It is not what a person reads, and shipping only the mapping
repeats the defect this spec exists to fix one level up. Here is a real tier-3 decision in the
artifact today:

```yaml
reason: 'rule producer_of:alignment.bam matched {''read_length'': ''>= 70''}: STAR''s
  seed-and-extend search is built for long reads …'
```

That is a Python dict repr embedded in YAML with doubled quotes. Worse, it reports the
**predicate** and not the **value**: a reader learns the rule tested `>= 70` and never learns that
`read_length` was 150, or that anything measured it. The premise is the one thing tier 3 asks a
reviewer to check, and it is the one thing the sentence omits.

So `Why.reason` renders the premise as a clause, with the value and its origin:

```yaml
reason: read_length is 150, measured — STAR's seed-and-extend search is built for long reads
  and is nf-core/rnaseq's default aligner; the index cost it pays back over reads this length.
  Dobin et al. 2013, doi:10.1093/bioinformatics/bts635
review: advisory
premise: {read_length: 150}
premise_origin: {read_length: measured}
```

and scenario B's inferred strandedness reads *"strandedness is reverse, inferred — nothing
measured it"*, which is a sentence a biologist can disagree with.

### 6.2 A tier says what it means, where it is used

`tier: 3` is a number whose meaning lives in a table in another document. `review_level_for` is
already a function of the tier, so the artifact can carry `review:` beside it and stop requiring
the reader to hold `CLAUDE.md` open. This costs one field and removes a lookup from every reading
of every decision.

It also makes §1's claim checkable by a person and not only by a test: a decision that says
`tier: 3` and `review: advisory` and then shows an empty premise is visibly wrong on the page.

---

## 7. Unresolved, and honest about it

### 7.1 Declared domains — two halves, and only one is missing

An earlier draft of this section said completeness and arithmetic were the same prerequisite.
**They are not, and the difference is the whole schedule.** Checked against the code on
2026-08-15:

**The premise side already has a domain.** `Measurement` declares `kind`, `values`, `minimum`,
`maximum` and `extensible`, and the shipped registry uses them — `read_length` is
`kind: integer, minimum: 1`; `strandedness` is `kind: enum, values: [forward, reverse, unstranded]`.
So §5's completeness check does **not** need new types. It needs a partition check:

- **ordered kinds** (`integer`, `number`): `>= x` and `< x` are complementary by construction, so
  a pair of comparisons on the same premise at the same boundary is exhaustive without any bound
  being declared at all.
- **enums**: exhaustive when the rows cover `values` and `extensible` is `false`. Where
  `extensible` is `true` an overlay may add a state, so a catch-all is genuinely required and
  demanding one is correct.

This is what lets the shipped aligner rule — `>= 70` and `< 70`, no catch-all — stay legal and
stay at tier 3 with Kim et al. attached, instead of being demoted by §5's own fix.

**The param side has no domain.** `Param.default` is `Any`, with nothing declaring what values are
legal. That is what A118 needs: `MD0300` currently refuses a computed `then` with a *character
class over the measurement names*, which is a heuristic that admits `paired-end` as arithmetic and
misses anything spelled unexpectedly. A declared domain turns it into a type check.

That half is Plan 2's correction 6, reached here from a third direction, and this plan owns it —
it is one task, not a blocker.

### 7.2 Role instancing

A role is assumed to have one slot per pipeline. nf-core/rnaseq runs FASTQC twice, which is A97.
Effects apply to every slot filling a role; a qualifier for naming one is deferred rather than
designed against.

### 7.3 A role is not an interchangeable set

`index_building` is filled by `star/genomegenerate` and `hisat2/build`, which produce **different
types** and are selected structurally by the aligner. An `implementation` decision must validate
against substitutability — same produced type and states — not merely shared role. The prototype
does not, and would emit an unroutable pipeline.

### 7.4 The measurements do not exist

The corpus in §8 needs `adapter_content`, `max_chromosome_length` and `rrna_fraction`. None are
declared. That is [issue #38](https://github.com/comeni-project/Comeni-Labs/issues/38) — *the
measurement vocabulary has no author, and it gates every tier-3 rule* — confirmed as a hard
prerequisite for shipping any of these rules, though not for building the format.

### 7.5 A83 needs a name

"One candidate, no rule" is not ambiguity — tier 4 promises *proposal + reasoning + alternatives*
and there are no alternatives. It is *undeclared*. Whether that is a fifth state or a qualifier on
tier 4 is open; this spec leans qualifier, because the four tiers are a product commitment.

---

## 8. What broke

The useful section. Four things, found by running rather than by review; two were flaws in earlier
drafts of this document.

### 8.1 A119 reproduced, and it is worse than filed

Carried by the audit as PLAUSIBLE on a reviewer's word. Reproduced 2026-08-15. Every route to
expressing presence is refused — `then: null` gives `'None' is not in the registry`, which blames
a misspelled contract when the author asked whether a step could be absent; `{step: …}` and
`{present: …}` are `extra_forbidden`; `{param: skip_trimming}` finds no such param.

Then the part that makes it critical. A lab's two-branch duplicate-handling rule, keyed
`producer_of: alignment.bam` because that is the only legal spelling, **displaces the shipped
aligner rule**:

    read_length: 50, registry/ only        →  HISAT2_ALIGN
    read_length: 50, + lab's dedup policy  →  STAR_ALIGN

Both pass `gate lint` at exit 0, both report *5 modules, 1 requiring review*. The lab's intent —
insert a dedup step — added nothing. The aligner fell tier 3 → tier 2, losing Dobin; `samtools_sort`
rose tier 1 → tier 3 and now carries Smith et al. 2017 as the reason it sorts. And the aligner's
surviving `axis_reason` reads *"the tier-3 rule below decides on read length where one is
measured"* — asserting a rule that has been deleted. The explanation is not missing; it is false,
and false in a way that reassures.

### 8.2 A presence effect can make the pipeline unroutable

The flaw that nearly shipped in this document. `presence: trimming = absent` against the real
registry:

```
mendel: cannot route this goal — a rule pins nf-core/star/align@1.11.0 to produce
alignment.bam, but its inputs are unreachable from this goal (nothing produces
fastq.reads with states ['trimmed']).
```

`star/align` declares `state_required: [trimmed]`, and only TrimGalore produces that state.

**The diagnosis is this spec's own thesis turned on the contracts.** STAR does not require trimmed
reads — it soft-clips, and `--skip_trimming` exists because trimming is optional.
`state_required: [trimmed]` is **a tier-2 convention encoded as a tier-1 structural constraint**,
the same disease as `the only contract that produces this`.

So the design needs one more distinction: **a consumed state is required either structurally or
conventionally, and only a structural requirement may block routing.** A presence decision is
well-formed only if the graph routes without the step, checkable at load. R08 cannot ship until
`fastq.reads[trimmed]` is reclassified on both aligner contracts.

### 8.3 The completeness fix recreated the catch-all pathology

§7.1. A fix for A124 that pushes authors toward catch-alls demotes real tier-3 branches to tier 2.

### 8.4 The load check caught a hole in this document's own corpus

A catch-all row written with a `because` and no `cite` — precisely A76/A128's defect, committed
twenty minutes after writing §1, which names it. The check caught it. That is the argument for
enforcing rather than remembering, and it is why §4.4's citation requirement is at load.

---

## 9. Evidence

A throwaway prototype of both layers, run against the twelve contracts in `registry/`: six
decisions, three scenarios, and eight negative controls — plus a ninth the corpus tripped over on
its own (§8.4). It is **not** in the repository and is not a test — the same standing as the twenty
rule attempts, and for the same reason.

The corpus covered the aligner (R01, the control), trimming presence (R08/A119), MultiQC presence
(R14/A119), `min_mqs` by goal purpose (R07/A120), `index_format` from a derived genome fact,
`save_unaligned` by negation (A121), and the annotation multi-effect (§4.2).

The result worth keeping is that **the tier moves with the evidence, for the same rule text**:

| | A: measured | B: strandedness unmeasured | C: variant calling, axolotl |
|---|---|---|---|
| `implementation:alignment` | **3** star | 2 hisat2 | **3** star |
| `param:bam_sorting:index_format` | 2 bai | 2 bai | **3** csi |
| `param:quantification:min_mqs` | 2 → 0 | 2 → 0 | **3** → 30 |
| `param:alignment:save_unaligned` | **3** true | **3** true, `derived:` | 2 false |

`index_format` is the one to read. Today it is tier 2 — *"BAI, not CSI. Every downstream tool in
this spine reads BAI"* — a convention with a citation, and correct while nothing measures the
genome. Once `max_chromosome_length` exists, the identical setting exits at tier 3 with
`needs_csi_index` as its premise. Same value, different evidence, different tier, and the artifact
says which.

---

## 10. What this does not do

It does not touch the four tiers, the three doors that matter to it, or `--no-ai`. It does not
reopen A14. It adds no fifth tier: a derived fact does not exit the ladder, because it is premise
rather than decision — it needs provenance, not a tier.

It is not a plan, but nothing in it blocks one. §7.1's first draft said otherwise; checking the
code rather than trusting the draft showed the premise domain already exists and only `Param`'s is
missing, which is a task rather than a prerequisite. That correction is itself the rule
`CLAUDE.md` states: write against the code, and expect to correct the document you are executing.
