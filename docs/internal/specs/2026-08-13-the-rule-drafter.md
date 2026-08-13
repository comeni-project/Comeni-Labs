# The rule drafter — where tier-3 rules come from

**Status:** design spec. **Not scheduled**, and deliberately so — see *Prerequisites*. Written
2026-08-13, at the end of Plan 1.12, while the reasoning behind it was fresh.

**Why it exists now, unscheduled:** tier 3 is the differentiator. Tiers 1 and 2 are structural
inevitability and documented convention, both of which a good template with provenance delivers.
Tier 4 is "a human decides". **Tier 3 — a measurement matched a declared rule — is the only tier
that makes Mendel a resolver rather than a very well-documented template engine**, and the domain
is understood to hold thousands of such rules, most of them abstract. This is the component that
makes them exist.

Plan 2 does not build it, and says so in its own text:

> §8 one queue, three proposal kinds | Tasks 9, 10 — contract and state. **Tier-3 rule proposals
> are not implemented**; the queue's `kind` field accepts them and `approve_state` is the template
> to copy, but no drafter emits them yet.

> **Known gap, stated rather than hidden:** […] Rule drafting needs a corpus of tier-4 flags to
> learn from, which does not exist until Mendel has been run on real data — so it belongs after
> Plan 3, not here.

That deferral is correct. This spec records what the thing must be, so the deferral does not also
lose the design.

---

## 1. Prerequisites, and why each one is hard-blocking

**Do not start this before all four are true.** Each has a failure mode that is invisible until
the drafter is already producing output, which is the worst time to discover it.

| # | Prerequisite | Why it blocks | Tracked |
|---|---|---|---|
| 1 | **~20 real abstract rules, hand-authored** | Everything known about the rule format's limits is reasoned from **one** shipped rule. Twenty replaces argument with evidence, and the ones that cannot be written are the specification for #39 | [#39](https://github.com/comeni-project/Comeni-Labs/issues/39) |
| 2 | **The measurement vocabulary has an author** | A rule keys only on declared measurements. A drafter over today's vocabulary will propose rules about read length and strandedness for ever | [#38](https://github.com/comeni-project/Comeni-Labs/issues/38) |
| 3 | **The format reform, designed against (1)** | A drafter emitting into a format that cannot hold the rules it is drafting produces *plausible* proposals that are subtly wrong — this project's worst failure mode | [#39](https://github.com/comeni-project/Comeni-Labs/issues/39) |
| 4 | **A corpus of real tier-4 flags** | Plan 2's stated reason for deferring. Needs Mendel run on real data by real users, which needs Plan 3 | — |

**The ordering matters more than the schedule.** Doing (3) before (1) means designing a format
against imagination; doing the drafter before (3) means a model generating proposals into a
container that cannot hold them. `docs/design/rule-tables-and-port-logic.md` §13.6 has the same
ordering and the reasoning behind it.

---

## 2. Where a rule can come from, and what each source is worth

Three candidate corpora. They are not equivalent and the difference is the whole design.

### 2.1 The tier-4 flag corpus — what Mendel asked, and what people answered

Plan 2's named source. Every tier-4 decision emits a `DecisionRecord`; every human override
records what a person chose when Mendel could not decide. Aggregated across laboratories, that is
a record of **which questions recur and how experts answer them**, which is exactly the shape of a
tier-3 rule waiting to be written.

**Its strength:** the answers are real, made by practitioners on their own data, in context.

**Its weakness, and it is severe:** a recurring answer is evidence of *convention*, not of
*correctness*, and the distinction is the entire product claim. A hundred laboratories choosing
STAR because it is the nf-core default is a tier-2 fact with a hundred citations of itself. **A
rule drafted from frequency alone is a popularity measurement wearing a tier-3 label** — and tier
3 is yellow rather than silent precisely because "the machinery worked, check the premise".

So frequency may *propose* a question worth investigating. It may never *justify* the answer.

**This is also an egress question.** Aggregating decision records across laboratories means those
records leave the laboratory, and `DecisionRecord` carries free-text `reason` fields. Nothing in
the four doors currently covers "telemetry of what people decided", and inventing a fifth door
for it would need invariant 14 reopened deliberately. Do not assume this corpus is collectable.

### 2.2 The literature — where the abstract rules actually live

The rules described as "thousands, completely abstract" are in methods sections, benchmarking
papers and tool documentation. This is the corpus that matches the claim, and it is the reason a
model is needed at all: extracting *"for reads under 70bp, HISAT2 outperforms STAR on splice
detection"* from prose is precisely what a language model is good at and a parser is not.

**Its strength:** a real citation exists, because the claim came from a cited work.

**Its weakness:** see §3. Citation fabrication is the central risk of this component.

### 2.3 Pipeline configuration — already spoken for, and it is tier 2

`nf-core`'s `conf/modules.config` is Plan 2 Task 11's corpus and it is explicitly **the tier-2
corpus**: its conditionals key on pipeline *parameters* (`params.gencode ? …`), not on measured
data. It yields defaults with attribution. Do not mine it for tier-3 rules; it does not contain
them, and a drafter that treats it as though it does will relabel convention as measurement.

---

## 3. The central risk: a fabricated citation is worse than no rule

**State this first in any plan that implements this spec.**

A tier-3 rule's whole value is the `cite`. The tier ladder says a rule matched *declared data* and
carries a *citation*; that is what makes it yellow-advisory rather than red-required, and what a
reviewer relies on when they accept it. A model drafting rules from literature will produce
citations that look exactly right and sometimes do not exist, or exist and do not say what the
rule claims. **A rule with a fabricated citation is strictly worse than no rule**, because it
converts a question a human would have been asked into an answer they will not check.

Three mechanisms, and none of them is optional:

1. **A citation must resolve.** DOI or PMID, checked against a resolver at draft time. A drafted
   rule whose citation does not resolve is rejected by the drafter, not by the reviewer — a
   proposal queue is a scarce human resource and must not be spent on obvious rejects.
2. **The claim must be quoted, not summarised.** The proposal carries the *span of source text*
   the rule is drawn from, alongside the rule. A reviewer approving a rule is approving that the
   quoted sentence supports it, which is a judgement a person can make in seconds and a model
   cannot make for them.
3. **The reviewer sees the impact.** See §5.

This is where invariant 2 earns itself more than anywhere else in the system: *AI authors
artifacts offline; humans approve; runtime is pure lookup.* The forge queue is not a formality
here — it is the only thing standing between a plausible sentence and a laboratory's pipeline.

---

## 4. What a rule proposal is

The queue already accepts a `kind`; `approve_state` is the template. A rule proposal is one
`decides` block — target, rows, `because`, `cite` — plus the evidence a reviewer needs.

```
RuleProposal
  decides       DecisionTarget      param: <name> | producer_of: <type id>
  rows          [DecisionRow]       when / then / because / cite
  because       str                 why this decision exists, in prose
  cite          str                 DOI or PMID — resolved at draft time, §3.1
  quoted        str                 the source span the claim is drawn from, §3.2
  source        str                 where `quoted` came from — a resolvable locator
  drafted_by    str                 model id and version, as every forge output records
  impact        Impact              §5 — what changes if this is approved
  needs         [MeasurementId]     measurements this rule requires, §6
```

`quoted` and `source` are the fields that do not exist for any other proposal kind, and they are
the reason this cannot simply reuse `ContractDrafter`'s shape. A contract is checkable against the
module it binds — that is what conformance (`MD0100`–`MD0108`) does. **A rule has no equivalent
ground truth in the repository**, so the evidence has to travel with the proposal.

---

## 5. Mechanical validation, before a human sees anything

Two checks the drafter runs on its own output. Both are cheap and both reject silently.

### 5.1 It must load

`RuleTable.load` already validates rules against the registry, the vocabulary and the declared
measurements: a rule deciding a parameter no contract declares, or keying on an undeclared
measurement, or naming a contract id that is not in the layer, fails to load. **The drafter
attempts the load and discards anything that fails.** No new validation code, and it closes the
largest class of nonsense for free.

### 5.2 It must change something, and the drafter must say what

**Impact analysis is the mechanism this component needs most and the one with no precedent in the
codebase.** Re-resolve the layer's example goals with the proposed rule in place, and diff.

| Impact | Meaning | What the reviewer should do |
|---|---|---|
| **nothing changes** | the rule is inert — it never fires, or it fires and produces the value that was already chosen | reject, or investigate why. Issue [#10](https://github.com/comeni-project/Comeni-Labs/issues/10)'s shape: a mechanism that runs and changes nothing |
| **a tier-4 flag becomes tier 3** | the intended case — a question nobody could answer now has a cited answer | approve if §3 holds |
| **a tier-2 default is superseded** | the rule overrides a convention. This is legitimate — it is exactly what the shipped `producer_of` rule does to `priority: 10` | scrutinise: the citation must beat the convention it displaces |
| **many pipelines move** | a broad rule, and broad rules are where a wrong one does the most damage | highest scrutiny; consider narrowing the `when` |

A proposal that cannot state its impact is not ready to be reviewed.

---

## 6. The drafter must be able to propose measurements, or it is bounded for ever

§1's prerequisite 2 is not only about having *an* author for the measurement vocabulary — it is
about the drafter being one of them.

A rule can only key on a declared measurement. A drafter restricted to today's vocabulary can only
ever produce rules about the measurements somebody already thought of, which caps the whole
mechanism at the imagination of whoever seeded it. When the literature says *"for genomes above
3Gb, index construction requires a sparse suffix array"*, the rule needs `genome_size` — and if
nobody declared it, the honest drafter output is **two coupled proposals**: the measurement, and
the rule that needs it.

That coupling has consequences a plan must handle rather than discover:

- A measurement is only useful if something can **measure** it. `mendel profile` emits a pipeline
  that does the measuring, so a proposed measurement implies a proposed *measuring step*, and
  there may be no contract that produces it. A measurement nobody can measure is a rule that never
  fires — §5.2's inert case, arriving one level down.
- Approval becomes **transactional**: approving the rule without the measurement gives a rule that
  cannot load; approving the measurement without the rule gives an unused declaration. The queue's
  `approve` is currently per-proposal. This needs a group.
- Invariant 7 — vocabularies are closed — means a new measurement is a *data* change through the
  approval queue, never a code change. That already holds and must keep holding.

---

## 7. What this spec deliberately does not decide

- **Which model, and how prompted.** That is a plan's problem, and it will be wrong if decided
  before the format reform (§1) settles what a rule can even be.
- **Whether the tier-4 corpus is collectable.** §2.1 raises it as an egress question, not a
  solved one. It may turn out that the literature corpus is the only lawful one, and the design
  should survive that.
- **How a rule is retired.** A cited claim can be superseded by a later paper. Contracts have
  versions and digests; rules have neither, and a layer replaces a whole `decides` block. Whether
  that is sufficient for a registry with thousands of rules is unexamined, and it becomes urgent
  at roughly the same moment this component ships.
- **Cohort versus sample.** `docs/design/rule-tables-and-port-logic.md` §12 already carries it: a
  measurement like `read_length` is per-sample and a rule needs one value. Thousands of rules make
  that question thousands of times more consequential.

---

## 8. The one-paragraph version

The rule drafter reads the literature, proposes one `decides` block at a time carrying a resolving
citation and the quoted sentence it came from, discards anything that will not load against the
layer, states what would change if it were approved, and proposes any measurement it needs
alongside the rule that needs it. A human approves. Nothing writes to `rules/` automatically. It
is not scheduled, and it must not start until twenty real rules have been written by hand, the
format has been reformed against the ones that broke it, and the measurement vocabulary has an
owner — because a drafter is a machine for producing plausible output, and plausible output that
nobody can check is the thing this entire project exists to be an alternative to.
