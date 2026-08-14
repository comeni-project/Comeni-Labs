# The design audit

Run 2026-08-14 against `main` at `346eeac`, to the method in
[`2026-08-14-design-audit-brief.md`](2026-08-14-design-audit-brief.md). Four cold reviewers, no
session context, one stream each, pre-assigned number blocks. **44 findings, A76–A131.**

This is the synthesis. The four stream reports are the evidence and carry every demonstration in
full:

| Stream | Angle | Numbers | Report |
|---|---|---|---|
| 1 | the claim, end to end | A76–A86 | [stream 1](2026-08-14-design-audit-stream-1.md) |
| 2 | the compiler, as a compiler | A90–A97 | [stream 2](2026-08-14-design-audit-stream-2.md) |
| 3 | the artifact as the interface | A104–A114 | [stream 3](2026-08-14-design-audit-stream-3.md) |
| 4 | load-bearing assumptions vs. what is left to build | A118–A131 | [stream 4](2026-08-14-design-audit-stream-4.md) |

Stream 2 was run first and died on a 529 with nothing recorded; it was relaunched cold against its
surviving probe artifacts. A76–A89 and A104–A117 have gaps at the top of their blocks because the
blocks were sized generously in advance, not because findings were dropped.

---

## The verdict

**It holds with named repairs.** Every repair below is a field, a check, or a function; none is
architectural, and none requires the registry to be filled first.

The product claim has two halves and they came out differently. Stating them separately is the
single most useful thing this audit produced:

> **"Same goal in → same pipeline out"** — **holds, and is stronger than `ARCHITECTURE.md` §8
> claims.** Four builds across two `PYTHONHASHSEED` values produced byte-identical `main.nf`,
> `nextflow.config` *and* `pipeline.yml`. A goal re-spelled with permuted `have:` and `profile:`
> keys produced a byte-identical `main.nf`. Two streams attacked determinism independently and
> neither moved it.
>
> **"Nothing was guessed silently"** — **does not currently hold.** Of the six values that reach
> the generated Nextflow in a default build, five carry no `why:` at all. A human's edit keeps the
> machine's justification. The shipped registry cites the STAR paper as the reason HISAT2 was
> chosen. This is the half the design is *for*, and it is the half that failed.

One finding is worse than a claim failure and should be read first regardless of the rest: **A92
produces wrong results from a green run**, and the v1 success criterion is structurally incapable
of catching it.

### What the four reviewers agreed on without being able to confer

All four returned *holds with named repairs*. More usefully, all four hit the same root from
different directions — a value can carry a complete, well-formed `why:` and still be inert
(A91), wrong (A118), stale (A104), or cite the wrong paper (A79). The claim that failed is not
"nothing was guessed silently" in the literal sense the guards protect. It is the weaker sentence
nobody wrote down: *a value with a reason attached is a value that reached something and was
right.*

---

## Verification status — read this before acting on any row

The brief's rule: **a finding the synthesiser has not reproduced is PLAUSIBLE, not a result.**
It is applied literally below. `CONFIRMED (mine)` means I reproduced it first-hand in this
session, by running the commands and reading the output. `PLAUSIBLE` means the reviewer marked it
CONFIRMED with a demonstration I did not re-run — it is a hypothesis with evidence behind it, not
a result, and it should be re-verified before anybody spends a day on it.

**25 of 44 are CONFIRMED (mine). 19 are carried as PLAUSIBLE.** Ten findings are rated critical;
**nine of the ten are in the confirmed set, and A119 is the exception** — it is the one critical
carried on the reviewer's word alone, and it should be reproduced before Root 5's repair is
scoped. Every other finding named in the repair order was reproduced first-hand.

---

## The findings

Severity is the reviewer's, adjusted by me where reproduction changed the picture; adjustments are
noted in the row.

### Root 1 — the explanation is optional where the value is not

Every path by which a value reaches a tool *except* `settings[]` carries no `why:`, and nothing
requires one. The mechanism exists — `NfInput.because` → `CallArg.why` is wired and works. Only
the data is missing.

| # | What | Shape | Sev | Status |
|---|---|---|---|---|
| A106 | Five of the six values reaching the generated Nextflow carry **no `why:` at all**, against the file's own header | (i)+(ii) | high | **CONFIRMED (mine)** |
| A80 | `channels[].meta` carries the measured facts — including the one that becomes featureCounts' `-s` — with no `why`, and drops the citation the measurement declares | (ii) | important | **CONFIRMED (mine)** |
| A81 | Positional literals reach the tool with `why: null`. `SAMTOOLS_SORT(…, 'bai')` and `STAR_ALIGN(…, false)` are real choices in no review queue | (i) | important | **CONFIRMED (mine)** |
| A90 | `call[].literal` carries no `why`, cannot be resolved, and a human edit to it is reverted by `upgrade` | (ii)+(i) | high | **CONFIRMED (mine)** — mechanism |
| A82 | `ext_args` reaches the tool with no `why` *and* its justifying premise is graph-contingent | (i)+(ii) | important | **CONFIRMED (mine)** |
| A93 | `via: meta` hardcodes nf-core's `[meta, …]` shape; no route reaches a non-nf-core module at all | (ii)+(i) | high | **CONFIRMED (mine)** — mechanism |
| A84 | `RouteStep.satisfies` is discarded at materialisation, so a structural insertion's reason is a dangling pronoun | (ii) | important | PLAUSIBLE |

**Repair.** Require `why` wherever a value reaches a tool — `MetaEntry`, `CallArg`, `Step.ext_args`
— refused at load. `NfInput.because` already proves the shape works and `NfInput.empty`'s
tier-1 `Why` proves a structural fact can carry one. Cost: three fields and a loader check. No
registry work; the contracts already hold the prose in comments.

### Root 2 — `why:` does not track its value

The record is written once at resolution and never re-derived, re-checked, or invalidated when the
value changes underneath it — whether by a human edit, an overlay, or the graph moving.

| # | What | Shape | Sev | Status |
|---|---|---|---|---|
| A104 | A hand-edited `settings[].value` keeps the `why:` written for the value it replaced; `publish` certifies it | (i) | **critical** | **CONFIRMED (mine)** |
| A77 | A human's tier-4 answer has nowhere to record its reason, and `upgrade` **deletes** a hand-written one | (i)+(ii) | **critical** | **CONFIRMED (mine)** |
| A76 | An overlay changes a value 0→30 with a **byte-identical** `why:`; tier 2's "document" has nowhere to live | (ii) | **critical** | **CONFIRMED (mine)** |
| A105 | `emit` and `upgrade` build **different pipelines from the same file** — `-Q 30` vs `-Q 0` — and neither says a human's edit was dropped | (i)+(ii) | high | PLAUSIBLE |
| A111 | After replay, `source: human` sits on `reason: "…without judgement — please review"`; `replay.py`'s recorded justification is **verified false** | (i) | medium | **CONFIRMED (mine)** |

**Repair.** `Why.for_value:` — the value the reason was written about — refused at load when it
disagrees with `value`. One field. It closes A104 outright, makes A105's divergence visible, and
turns A76 into a diagnostic. `MD0218`/`MD0220` already do this cross-check for tier-4
`ParamDecision`s; they guard the safe direction only.

### Root 3 — the citation mechanism is unaudited

Tier 2 is defined as *"a documented default exists"* and tier 3 as *"a declared rule matched
measured data"*. Both promise a document. Nothing checks that one exists, that it is the right
one, or that it survives to the page.

| # | What | Shape | Sev | Status |
|---|---|---|---|---|
| A79 | `Pin.because()` prefers a block `cite` over a row `because`; the **shipped** registry cites the STAR paper as the reason HISAT2 was chosen | (i) | important | **CONFIRMED (mine)** |
| A107 | Same function, other end: authoring a `cite` **deletes** the plain-English sentence. The registry's only prose explanation of its only tier-3 decision never reaches the artifact | (i) | high | **CONFIRMED (mine)** — mechanism |
| A128 | Tier 2 promises "value + citation"; module selection by `priority` is a bare int with nowhere to carry one | (ii) | important | **CONFIRMED (mine)** — same defect as A76 |
| A78 | A tier-3 rule with no `cite` and no `because` loads, fires, and emits a reason ending in a bare colon | (i) | important | PLAUSIBLE |

**A79 and A107 are one bug read from both ends, and its docstring is wrong about itself:**

```python
def because(self) -> str:
    """The most specific justification available, row before block."""
    return self.row.cite or self.decision.cite or self.row.because or self.decision.because or ""
```

That is cite-before-because, not row-before-block. A row's own `because` is unreachable whenever
its block has a `cite`.

**One correction to A79's framing, from reproducing it.** The rule author's own comment shows the
block `cite` was written to justify the *decision axis* ("read length determines which aligner is
appropriate" — for which Dobin et al. is a fair citation), not either row's choice. So the defect
is not a careless citation; it is that `because()` collapses axis-justification into
row-justification and the artifact presents the result as the reason for the row. That is the
harder problem and the more interesting one.

**Repair.** Fix the precedence to what the docstring says, and separate the two questions the field
is answering: `why.axis_cite` (why this decision is made this way at all) from `why.reason` (why
*this* row won). Require one of them per fired row at load — A78 falls out.

### Root 4 — the emitter knows five things no contract can declare

Stream 2's root, verbatim and confirmed: the join, the meta shape, the entry param name,
process-as-identity, and the untyped positional. Each is a correct guess about nf-core and a
silent wrong answer elsewhere. **Non-nf-core *wiring* holds** — a contract for a module with no
container, no meta, no stub block and no `task.ext.args` routed, emitted, linted and ran green —
so the generalisation claim in `ARCHITECTURE.md` §5a is half true: the plumbing generalises, the
value routing does not.

| # | What | Shape | Sev | Status |
|---|---|---|---|---|
| A92 | Two ports in one channel are joined with `.combine()` — a cross product. **Two samples in, four processes out, half cross-paired.** Green run | (ii)+(i) | **critical** | **CONFIRMED (mine)** |
| A91 | **No `via:` reaches a `val` positional input.** 3 of 10 vendored modules have one, each a real analysis decision | (ii)+(i) | **critical** | **CONFIRMED (mine)** |
| A96 | `Goal` cannot ask for one type in two states; asking for both silently yields one | (ii)+(i) | high | **CONFIRMED (mine)** |
| A94 | `_default_entry` derives `params.<name>` from the type id's last segment, so `tumour.bam`/`normal.bam` collide | (i) | **medium** (was high) | **CONFIRMED (mine)** — mechanism |
| A95 | A contract that drops a consumed port from `nf_inputs` passes all nine diagnostics, lint and preview, then dies at run time | (i) | medium | **CONFIRMED (mine)** — mechanism |
| A97 | A contract can appear at most once per pipeline; nf-core/rnaseq runs FASTQC twice. Fails loudly at lint | (iii) | medium | **CONFIRMED (mine)** — mechanism |

**A94 downgraded.** `_default_entry` fires only when the vocabulary declares no `entry_channel`,
which the finding does not mention. The collision is real; it is conditional.

### Root 5 — the rule format is narrower than the domain it must express

Stream 4's twenty-rule exercise, which the brief named as the highest-value single thing this audit
could do. Twenty real cited rules, each written as YAML and run through the real loader over
`registry/`, with measurements and parameters supplied first so every failure is the *format's*.

**6 clean · 4 load and are wrong · 1 contortion · 9 cannot be written.**

`rule-tables-and-port-logic.md` §13 reasoned three limits from a registry holding one rule. Twenty
rules confirm all three and **understate one badly**: §13.2 says a computed `then` "cannot be
written", when in fact it is not refused.

| # | What | Shape | Sev | Status |
|---|---|---|---|---|
| A118 | A computed `then` loads, resolves at **tier 3 with a citation**, and is emitted verbatim into `ext.args` | (i) | **critical** | **CONFIRMED (mine)** |
| A119 | Whether a step **exists** is not a decidable thing; `decides:` has two targets and neither is presence. 4 of 20 rules die here | (ii) | **critical** | PLAUSIBLE |
| A120 | `when` cannot see the goal — not its purpose, and not `required_states`, which the router already consults. 3 of 20 | (ii) | important | PLAUSIBLE |
| A121 | Negation over an enum is inexpressible and the refusal misdiagnoses it as a malformed number | (ii) | important | PLAUSIBLE |
| A122 | A row conditioned on a measurement being **absent** loads clean and can never fire — a dead rule, in the format built to make dead rules impossible | (ii) | important | PLAUSIBLE |
| A123 | `decides: {param: X}` names a parameter **globally**; a rule cited for the aligner set the same value on TrimGalore | (ii) | important | PLAUSIBLE |
| A124 | Nothing checks a `producer_of` rule for completeness, and a *complete* one makes every later producer permanently unreachable | (ii) | important | PLAUSIBLE |
| A127 | A tier-3 parameter records neither the row nor the measurements it rested on | (ii) | important | PLAUSIBLE |

**A118, reproduced.** The natural spelling is refused — but only by `MD0201`, a *shell-injection
character class*. Remove the spaces and it passes:

```
then: "read_length - 1"   →  MD0201: outside the substitutable class
then: "read_length-1"     →  builds
```

```groovy
withName: STAR_ALIGN { ext.args2 = '--sjdbOverhang read_length-1' }
```

`pipeline.yml` records it as `tier: 3`, `source: resolver`, cited to Dobin et al. 2013, and
`sjdb_overhang` is **absent from the review list**. STAR receives the literal string. The only
thing standing between a computed rule and a tool is a character class that permits `-`, and it
covers one of three routes — `via: directive` is unchecked.

**These nine rules are the specification for the reform**, and they are preserved. Do not design
the repair abstractly; the attempts are on disk (see *Provenance*).

### Root 6 — identity and ranking are derived from the winning candidate

| # | What | Shape | Sev | Status |
|---|---|---|---|---|
| A125 | A producer tie is answered from **every** candidate, not the tied ones. Adding one contract installed the lowest-priority aligner | (i) | **critical** | **CONFIRMED (mine)** |
| A126 | A producer decision's identity is the *winning candidate's* node id, so it is not stable under registry change; a curator's override is reported ORPHANED | (i) | **critical** | **CONFIRMED (mine)** |
| A85 | The review count double-counts a tied module selection — 2 open questions printed as 3 | (i) | minor | **CONFIRMED (mine)** |
| A113 | Tier-1 `reason: "the only contract that produces this"` is a claim about registry contents wearing the tier defined as *"no choice exists"* | (i) | low | PLAUSIBLE |

**A125, reproduced, and sharper than filed.** Baseline builds STAR. Add **one** contract —
`minimap2`, `priority: 10`, tying STAR which is also 10 — and the build selects **HISAT2**,
`priority: 0`, the contract the registry deliberately ranked last and which was *not part of the
tie*:

```python
ambiguity = ProducerAsked(node_id=_node_id(ordered[0]), …,
                          candidates=sorted(c.id for c in ordered))   # every candidate, alphabetical
```

`FlagOnlyResolver` takes `candidates[0]`. `hisat2` < `minimap2` < `star`. The ranking
`(surplus, -priority, id)` is computed, used to detect the tie, and then discarded before the
question is asked.

**A126 confirmed in the same artifact**, which is the tidiest evidence in the audit — that build's
decision record reads:

```yaml
- key: minimap2_align.producer:alignment.bam    # a module that is not in the pipeline
  chosen: nf-core/hisat2/align@2.2.2
```

**Repair.** Hand the resolver the *tied* candidates, and key a producer decision on what is being
decided (`producer:alignment.bam`) rather than on who won it. Both are small and both are
prerequisites for `human_override` surviving a registry that moves — which is the whole of replay.
This is issue #1 reached independently from two directions, and it is now a demonstrated defect
rather than a design question.

### Root 7 — tier 4 cannot be asked, and tier 3 cannot be checked

The two tiers that carry the honesty claim are the two the artifact supports least.

| # | What | Shape | Sev | Status |
|---|---|---|---|---|
| A129 | **Two of the three tier-4 question kinds cannot cross door 2.** `ParamAsked` and `SourceAsked` candidates fail `AmbiguityRequest` validation; the guard is green because it compares field *names* | (iii) | **critical for Plan 2** | **CONFIRMED (mine)** |
| A108 | Tier 3 is `advisory` — "check the premise" — and the artifact carries no premise. Measured and asserted builds have a **byte-identical `steps:` block** | (ii) | high | **CONFIRMED (mine)** |
| A83 | Tier 4 labels "two defensible options" and "nobody ever wrote a default" identically | (ii) | important | PLAUSIBLE |
| A130 | The artifact cannot state that no model was consulted; `resolved_by` and `confidence` are the resolver's claims about itself | (ii) | important | PLAUSIBLE |
| A110 | `decisions[].confidence` is undocumented in the artifact's own spec, has no null, and `0.0` means both "never filled in" and "no confidence" | (ii)+(iii) | medium | PLAUSIBLE |
| A112 | `human_override` reads two ways: the schema doc says it is not writable, `MD0220`'s message says to set it | (ii) | medium | PLAUSIBLE |
| A114 | `publish` — the door with no undo — never mentions an open tier-4 review; a pipeline with `chosen: null` is stamped at exit 0 | (ii) | low | PLAUSIBLE |

**A129, reproduced.** Door 2 is exactly what Plan 2 Task 5 opens:

```
ParamAsked  candidates=[None]        REFUSED: Input should be a valid string
SourceAsked candidates=['star_align.bam']  REFUSED: not a contract id
ProducerAsked                        OK
```

Only producer questions can currently be asked of a model. This is the same family as
[#32 (A68)](https://github.com/comeni-project/Comeni-Labs/issues/32), through a different guard.

**A108, reproduced.** Two builds differing only in whether `read_length: 150` was *measured by a
named profiler* or asserted by a human produce a **byte-identical `steps:` block** (5,030 bytes).
The tier-3 decision that rests on that measurement says which rule matched and cites a paper; it
does not say what the value was, who measured it, or whether anyone did. A reader can join to the
`goal:` section — but the join is theirs to make, and `guarded` will read as though something was
measured either way. This is issue #2's blocker stated precisely: `ProfilePolicy` has nothing in
the artifact to check.

### Carried without a root

| # | What | Sev | Status |
|---|---|---|---|
| A86 | A contract displaced by module key leaves `why.displaced_layer: null` on the step; a *rule* overlay records it correctly | minor | PLAUSIBLE |
| A109 | Root G's second instance: `steps[].inputs[].states` reads three ways | medium | PLAUSIBLE |
| A131 | "The error message is the feature" inverts at scale: **40,049 characters on one line** for a one-character typo against 2,000 contracts | low | PLAUSIBLE |

**Round two's root G has a second instance (A109), so it is not closed.** The brief asked whether
the artifact reads one way; the answer is no, and A112 is a third instance in the documentation
rather than the data.

---

## The philosophy question

The synthesiser holds one lens no stream does. Read the whole thing as the biologist in
`docs/design/mendel.md` §1 — the one who can get a plausible pipeline out of a chat window in
minutes and has no basis for judging it. **Is Mendel visibly better than that chat window for
them, or only for us?**

**First, a correction to the question itself** — recorded by the operator on reading this audit,
and it changes the answer's shape. The comparison assumes the biologist reads `pipeline.yml`
directly. Through Plan 1 there is no AI layer at all, so a naive Mendel-versus-chat-window
comparison is between a substrate and a product. Mendel is the API the model acts through: the
prompt door extracts a goal, tier 4 asks, repair patches, and the deterministic core is what makes
those answers reproducible. The biologist's interface is the layer *above* this one, and it does
not exist yet.

**That reframing makes most of these findings sharper, not softer**, which is why the section
stays. If the artifact is what an AI reads in order to explain a pipeline to a researcher, then a
`pipeline.yml` where five of six tool-reaching values carry no reason gives the model two options:
say nothing, or fill the gap from its own knowledge. The second is confabulation with a
deterministic pipeline standing behind it lending it credibility — the precise failure this whole
design exists to prevent, arriving through the one component that was supposed to prevent it.
Root 1 is a bigger problem for a machine reader than for a human one, because a human notices an
absent reason and a model does not. A129 is purely an API defect and nothing else: two of three
tier-4 question kinds cannot cross door 2, so most of what the design promises to *ask* a model,
it currently cannot.

**It also surfaced a tension the repository had not resolved, and that tension is now settled.**
`CLAUDE.md` says a pipeline is *"a shareable artifact… the file a reader opens"*; the artifact's
own header says *"Read it; edit it"*. Those describe a human-facing document, while "the API the
AI interacts with" describes something else, and the two readings imply different amounts of Root
1–3 repair.

**Decided 2026-08-14: Mendel is the engine and the AI is its primary operator.** A human can drive
it and the CLI is built so they can, but the intended operator is the AI, and `pipeline.yml` is
the save file it sets down, picks up, tunes and re-emits rather than carrying a pipeline in its
context. The statement is `docs/design/mendel.md` §1; the argument against is in
`docs/internal/README.md`.

**That decision promotes three findings in this audit from legibility to correctness**, because
the failure mode becomes a machine's rather than a person's — and it changes no invariant, since
an agent driving the CLI is a user of it rather than a model inside the engine:

- **A104 / A105 / A77** — a human who leaves a stale `why:` beside an edited value does it
  occasionally and may notice; an agent does it systematically and does not.
- **A106** — a person reading a value with no reason sees a blank and asks. A model sees a blank
  and **fills it**, with a deterministic pipeline standing behind the guess lending it
  credibility. Root 1 is a worse problem for a machine reader than for a human one.
- **A130** — nothing distinguishes a model-authored `why.reason` from a human-authored one. Under
  `guarded` and `sealed`, where attribution is required, that is a gap in the protection profiles
  rather than a medium-severity nicety.

What follows is the answer under the documents as they read today.

**For verification, Mendel is not comparable — it is in a different category.** Content digests
over every contract, the layer each decision came from, the gate that passed, byte-identical
rebuilds across hash seeds, a refusal when the artifact and the emitted files disagree. A chat
window offers none of it and cannot. Stream 3 attacked this hardest and it held on every axis.

**For understanding, Mendel is currently about level with the chat window, and that is the
problem.** The biologist's actual question is *why is this pipeline the way it is* — and today:

- five of the six values that reach the tools carry no reason at all, including the strandedness
  flag the project uses as its worked example of the system working;
- the one tier-3 decision in the shipped registry explains itself with a citation to a paper about
  the aligner it did **not** pick, and the plain-English sentence the rule author wrote is dropped
  before the file is written;
- a tier-2 default and a lab's deliberate override of that default are byte-identical in the
  record;
- the tier that exists to say *check the premise* does not carry the premise.

A chat window at least narrates. It narrates unreliably, which is the whole argument for building
this — but a researcher comparing the two experiences gets confident prose from one and a
well-attested file that says `reason: contract default for min_mqs` from the other. The trace is
*auditable* and not yet *legible*, and legibility is what was promised.

**And under the machine-facing reading, the same sentence holds with the consumer swapped.** The
layer above cannot narrate what the artifact does not carry. Whatever explains this pipeline to a
researcher — a model, a dashboard, or a colleague — reads it from here, and five of six values
give it nothing to read.

**This is the audit's central result and it is a good outcome, not a bad one.** The half that is
hard to build — determinism, provenance, refusal, digests, replay — is built and holds under
attack. The half that failed is a set of missing fields on types that already exist. Stream 3 put
it best and reproduction agreed: *the failure runs one direction consistently — wherever the design
has a plain-English explanation, the artifact keeps the machine-readable half and drops the prose.*

Nothing here argues against the design. It argues that the design was finished as an audit
substrate and left unfinished as an explanation.

---

## Clean — attacked and held

Not optional, per the brief, and this section is why the rest can be trusted: it says what was
examined and survived, so a reader can tell coverage from silence.

- **Determinism, attacked twice independently.** Four builds, two `PYTHONHASHSEED` values,
  byte-identical `main.nf`, `nextflow.config` and `pipeline.yml` — stronger than
  `ARCHITECTURE.md` §8 claims. A permuted goal spelling gives a byte-identical `main.nf`.
- **A55's fix holds and generalises.** `MD0221` refused a live Groovy-injection file left from a
  prior probe; `NfTemplate` refuses non-`meta.`/`task.` interpolation at load (`MD0204`) when the
  same shape is tried against `Step.ext_args`.
- **A56's fix survives a resolver that lies about it** — a `HUMAN` claim with no backing `prior`
  record was demoted and kept its flag.
- **The orphan lifecycle is the best-told story in the system**: DRIFT / CHANGED / ORPHANED /
  `MD0203`, nothing written, exit 2.
- **`MD0213` caught staleness on every verb**, every time, including in my own reproductions —
  it interrupted two of them correctly.
- **Non-nf-core wiring works.** A contract for a module with no container, meta, stub block or
  `task.ext.args` routed, emitted, passed `--gate lint` and `--gate stub`, and ran green.
- **Invariant 8 held** — a genuine tie went to tier 4 with both candidates recorded.
- **Invariant 11's `OVERLAY` reporting fired** on every displacement, including the priority
  reroute in A125.
- **Shareability holds** — no path, user or timestamp anywhere in the artifact.
- **All nine unwritable rules failed at *load*, naming the offending thing, nine for nine.** The
  format refuses what it cannot express; the defect is the four that it *accepts*.
- **`MD0108` correctly refused an `ext` route to a hand-written module.**
- **The digest chain is real** — `MD0213`/`MD0214` observed doing their job.
- **92 of 96 artifact keys are documented** in `pipeline-schema.md`.
- **`mendel profile` names what it cannot measure**, and writes `value: null` honestly.
- **`cli.py`'s size was attacked and not substantiated** — no reviewer could name work in it that
  belongs elsewhere *and* show what breaks because it is there. Recorded because "747 lines" would
  otherwise look unexamined.
- **Named as not attacked**, so nobody reads silence as coverage: rule layering, `UnroutablePinError`,
  `accepts`/`prefer`, `MD0100`–`MD0108` as a set, `publish`'s full surface, and the purity and
  egress guards (out of scope by the brief).

---

## Repair order

Ordered by what gets more expensive to fix later, not by severity. The forge is the hinge: once it
drafts contracts at volume, every missing field becomes a migration.

1. **A92 — the join.** `NfInput` needs `join_on:` with `combine` remaining the honest answer for a
   broadcast reference. This is the only finding that produces *wrong results from a green run*,
   and `--gate test` cannot see it because the nf-core test dataset has one sample. Fix before any
   second per-sample port exists — BAM+BAI, tumour/normal, reads+adapters are all ordinary v2
   shapes. **Add a two-sample fixture to the test gate as part of the fix**; the class is invisible
   otherwise.
2. **A91 + A90 — the fourth `Via`.** A `positional` route, or `NfInput.literal` becoming a `Param`
   binding. Costs a `pipeline.yml` `version:` bump, which is exactly what gets expensive once
   archived pipelines exist.
3. **A118 — refuse a computed `then` at load.** A type check on `DecisionRow.then` against the
   parameter it decides, not a character class. Cheap, and it stops a fabricated-looking value
   from wearing a real citation.
4. **A125 + A126 — tie candidates and decision identity.** Two small changes in `_choose`;
   prerequisites for replay surviving a registry that moves.
5. **A129 — door 2's payload.** Blocks Plan 2 Task 5 outright. Two of three question kinds cannot
   be asked.
6. **Roots 1–3 — the explanation fields.** `why` required wherever a value reaches a tool;
   `Why.for_value`; the `because()` precedence and the axis/row split. Together these are the
   "nothing was guessed silently" repair, and they are the reason to do this before Plan 2 rather
   than after: the forge will draft contracts *and their justifications*, and a field that does not
   exist cannot be drafted into.
7. **Root 5 — the rule format.** Do not design it abstractly. The nine unwritable rules are the
   specification and they are on disk. This is issues [#38](https://github.com/comeni-project/Comeni-Labs/issues/38)
   and [#39](https://github.com/comeni-project/Comeni-Labs/issues/39), now with evidence.

---

## What the plans close, and what they do not

Two plans were written against this audit on 2026-08-14. **Between them they close 19 of the 44
findings.** The rest are carried deliberately, and this table is the honest accounting — a repair
order that quietly drops half its input is how a finding gets lost.

| Where | Closes |
|---|---|
| [Plan 1.13](../plans/2026-08-14-closing-the-design-audit.md) — correctness, no schema change | A92, A118, A125, A126, A129 |
| [Plan 1.14](../plans/2026-08-14-the-explanation.md) — the explanation, `version: 2` | A76, A77, A78, A79, A80, A81, A82, A90, A91, A104, A105, A106, A107, A128 |
| **A spec, not a plan** | Root 5's remainder — A119, A120, A121, A122, A123, A124, A127 |
| **Carried as issues** | A83, A84, A85, A86, A93, A94, A95, A96, A97, A108, A109, A110, A111, A112, A113, A114, A130, A131 |

**Root 5's remainder needs a spec before it needs a plan.** A119 (step presence is not decidable),
A120 (`when` cannot see the goal), A121 (negation), A122 (absence), A123 (no scope), A124
(completeness) and A127 (a tier-3 parameter records no premise) are one design question — what the
rule format must express — and the twenty attempted rules are its specification. Writing tasks
against a format that has not been redesigned would be planning against types that do not exist,
which `CLAUDE.md` names as the recurring failure. **Reproduce A119 first**: it is the one critical
finding this synthesis carries on the reviewer's word alone.

**Three carried findings are worth naming rather than leaving in a list.** **A96** (a `Goal` cannot
ask for one type in two states) and **A97** (a contract appears at most once) are both v2 breadth
blockers that fail loudly rather than silently, so they are carried honestly. **A108** (tier 3
carries no premise) is not closed by Plan 1.14 — its Task 2 splits `MEASURED` from `ASSERTED`,
which is A108's foundation and nothing more. And **A130** (nothing distinguishes a model-authored
reason from a human-authored one) was promoted by the 2026-08-14 engine decision from a medium
finding to a gap in the protection profiles; it is carried, and it should not be carried far.

## Confirmations, not discoveries

Reached independently and worth recording as such, per the brief:

- **[#1](https://github.com/comeni-project/Comeni-Labs/issues/1)** (routing ties should ask a
  human) — reached from ordinary use by two streams, and A125/A126 turn it from a design question
  into a demonstrated defect.
- **[#2](https://github.com/comeni-project/Comeni-Labs/issues/2)** (`sealed` and asserted
  measurements) — reached from the legibility side. A108 adds the blocker: the artifact has no
  premise for `ProfilePolicy` to check.
- **[#39](https://github.com/comeni-project/Comeni-Labs/issues/39)** and §13.2/§13.3/§13.4 —
  confirmed, with §13.2 corrected upward from "cannot be written" to "is not refused".
- **[#32 (A68)](https://github.com/comeni-project/Comeni-Labs/issues/32)** — A129 is the same
  family through a different guard.
- **Plan 2 correction 6** (a `Param` has no declared domain) — independently rederived as the
  mechanism behind A118.

## Scope kept

This audit did not reopen the A14 loop, re-audit the guards, re-audit the toolchain, or treat the
registry's emptiness as a finding — all four are brief scope boundaries. Whether the *design*
assumes a small registry was in scope and was tested: load time holds at 2,000 contracts and 2,000
rules (7.18 s), and the failure is diagnostic legibility rather than performance (A131).

---

## Provenance

Every finding's demonstration is in its stream report. The probe artifacts — hand-written registry
layers, the twenty rule attempts, and the build directories — are preserved outside the reviewer
worktrees at `.audit-artifacts/`, untracked:

```
stream-1-probes-2026-08-14/    lab/ (A76) nocite/ (A78) rowbecause/ (A79) tie/ (A83) answer/→reasoned-up/ (A77)
stream-2-probes-2026-08-14/    join/ (A92) metabare/ (A93) collide/ (A94) regmeta/ (A91) regtwice/ (A96)
stream-3-probes-2026-08-14/    17 build directories, 6 probe layers, goal-measured.yml (A108)
stream-4-probes-2026-08-14/    attempts/ — the twenty rules, R01–R20. The specification for the format reform.
stream-2-2026-08-13/           the first stream-2 run's artifacts, before it died on a 529
```

`attempts/` is the one to keep regardless of what happens to the rest: twenty real cited rules
written against the format, with the nine that cannot be expressed. Recreating them is the
expensive part of Root 5.
