# Working notes

**These are not documentation.** They are kept for provenance — so that a decision can be
traced to the moment it was made — and they are not maintained against the code.

They lived in `docs/internal/` until 2026-08-16 ([issue #41](https://github.com/comeni-project/Comeni-Labs/issues/41)):
69 of the 94 markdown files under `docs/` were these, so `ls docs/` showed the working record
before it showed anything a reader wanted. Moving them out is the whole change — nothing was
archived, deleted or rewritten.

`make links` deliberately does **not** check this directory. A plan naming a file its own tasks
create is correct at the moment it executes and broken until then, so checking the record would
make `make check` red for the duration of every plan.

If you want to know how Mendel works, read [`ARCHITECTURE.md`](../ARCHITECTURE.md) and
[`docs/`](../docs/README.md). If you want to know *why*, read [`docs/design/`](../docs/design/).

## journal/

**Start here if you are picking the project up.** One append-only entry per working
session: where things stand, what changed, what was decided and rejected, what is next, and
what a fresh reader gets wrong. Newest first — see [journal/README.md](journal/README.md).

## plans/

Step-by-step implementation plans, written before the work and executed task by task.
They contain code that was proposed, not necessarily code that shipped — several steps in
every plan were corrected during execution, and the corrections are recorded in the commit
messages rather than back-ported here.

**Filenames are a log, not an order** — two plans share the date `2026-08-04`. This table is
the order.

| Order | Plan | Status |
|---|---|---|
| 1 | `2026-08-02-mendel-deterministic-spine.md` | Plan 1 — complete |
| 2 | `2026-08-03-measurements-rules-and-profiling.md` | complete |
| 3 | `2026-08-04-the-runnable-spine.md` | Plan 1.5 — **complete** |
| 4 | `2026-08-05-conformance-checking.md` | Plan 1.6 — **complete** |
| 5 | `2026-08-04-publication-and-the-registry-split.md` | Plan 1.7 — **complete** |
| 6 | `2026-08-06-closing-the-audit.md` | Plan 1.8 — **complete.** Closed A1–A13 and A15; A14 and A16 stay open |
| 7 | `2026-08-07-closing-round-two.md` | Plan 1.9 — **complete.** Closed A17–A35; A14, A36 open, A37 fixed |
| 8 | `2026-08-07-the-pipeline-file.md` | Plan 1.10 — `pipeline.yml`. **Complete**, with each task's corrections inline |
| 9 | `../audits/2026-08-10-round-three-audit.md` | Round three audit — **complete.** A38–A54, four critical (A38, A44, A46, A50) |
| 10 | `2026-08-10-closing-round-three.md` | Plan 1.11 — **complete.** Closed A38–A54 (17 tasks), with each task's corrections inline; A14 stays open |
| 11 | `../audits/2026-08-11-round-four-audit.md` | Round four audit — **complete.** A55–A75, four critical (A55, A57, A58, A59). All four review streams landed. **A14 did not close** |
| 12 | `2026-08-13-closing-round-four.md` | Plan 1.12 — **complete, and the last audit-driven plan** (decided 2026-08-13). Closed A55, A56, A57, A58, A59 and A70; the other fifteen findings are carried as issues |
| 13 | `../audits/2026-08-14-design-audit.md` | The design audit — **complete.** Not like rounds one to four: it asked whether the *design* delivers the claim, rather than whether the code matches the design. Four streams, and the split it produced — *"same goal in → same pipeline out"* holds, *"nothing was guessed silently"* did not, and Plan 1.14 closed it — is the most useful thing it returned. This row said **next, not yet run** for two days after it ran, which is the drift A71 and A72 are about |
| 14 | `2026-08-16-the-forge-phase-1.md` + `../specs/2026-08-16-the-forge.md` | **The forge, Phase 1 — DONE, 2026-08-17.** Twenty-three tasks, seven checkpoints, all executed. `mendel-forge` is the first impure package and calls no model: a source is read, facts are derived, and everything else is a typed hole a person fills. Five corrections to the plan are recorded in [`journal/2026-08-17-the-forge.md`](journal/2026-08-17-the-forge.md); the two that mattered are that the diagnostics ownership guard was blind to every non-`MD` prefix, and that a draft could report no holes while producing a contract with no input ports. **The fifth-door question is settled: there is no door 5** (2026-08-17) — invariant 14 tracks prompt-derived data on the build path, `docs/design/clinical-data-protection.md` §4.2's taint rule is the scope it always had, and the forge is offline authoring outside it. That journal entry's Phase 2 section is still the handoff for everything else. Deterministic scaffolding only; a model fills holes in Phase 2. Plan 2 was deleted rather than corrected (operator's decision, 2026-08-16) — both documents were verified against the Plan 1.12 tree, fourteen merged pull requests ago, and neither knew about `AiProvenance`, `MD0225`, `coded()`, `declares:` or the registry being a separate repository. `43b1ce0` is the last commit holding them, and [`journal/2026-08-17.md`](journal/2026-08-17.md) is the argument. The runtime-AI and prompt→goal halves of the old Plan 2 are separate subsystems needing their own specs |
| 15 | [`2026-08-17-forge-phase-2.md`](plans/2026-08-17-forge-phase-2.md) + [`../specs/2026-08-17-forge-phase-2.md`](specs/2026-08-17-forge-phase-2.md) | **DONE, 2026-08-17.** Fourteen tasks, all executed; `make verify` green. Six corrections are recorded in [`journal/2026-08-17-forge-phase-2.md`](journal/2026-08-17-forge-phase-2.md), and the two that mattered were found by running the loop by hand with every test green: every model-access failure reached the user as a traceback, and a model id with no provider prefix escaped as a third-party exception. **The fifth-door question is answered — there is no door 5**, and `DOORS` and `tests/test_egress.py` did not change, which is the evidence rather than the claim. One decision moved during execution: the surface is `generate(shape)` with closed choice as a helper, not closed choice as the primitive, because the rule drafter runs next and does not fit a list of options. A model fills holes the deterministic scaffold left open. Four decisions taken 2026-08-17, before any plan: candidate-bearing holes only by default with prose holes behind an explicit flag; a model fill lands as an **answer** marked model-filled, since `Filler.MODEL` and the model id in `FilledValue.by` already reach `Provenance.drafted_by` and no schema changes; `ModuleSpec` gains **line numbers first**, so `Excerpt.text` quotes the line rather than naming the file — which buys conformance diagnostics the same thing; and a new **`mendel-ai` holds transport only** — LiteLLM client, config, retries — with no `AmbiguityResolver`, because that seam has no spec and invariant 9's replay requirement makes it unguessable. `sealed` makes no forge model call. The golden scaffold test stays pinned to `NoFiller` |
| 16 | [`2026-08-18-the-shared-question.md`](plans/2026-08-18-the-shared-question.md) + [`../specs/2026-08-18-the-shared-question.md`](specs/2026-08-18-the-shared-question.md) | **Plan 2.5 — DONE, 2026-08-18.** Eight tasks. The forge and the build path each had their own vocabulary for *a question a reviewer must answer*: `Hole`/`Ambiguity`, `FilledValue`/`Resolution`, `Filler`/`ValueSource`. One `Question`, one `Answer` and one provenance enum now, in a new `comeni_core/review/`. **What is deliberately NOT unified is the blocking** — a hole blocks and an ambiguity ships flagged, and that difference stays in the containers and the ports because `HoleFiller.fill()` may return `None` and `AmbiguityResolver.resolve()` may not. Putting it on the types would trade a structural guarantee for a runtime check, which is the mistake invariant 1 records. **The egress guard went red on its own** at the re-base commit and green once door 2's widening was decided — that sequence is the evidence the decision was made rather than skipped, and door 2 now carries `what`, `why_open`, `closed` and `evidence` because the forge measured 69% → 88% on exactly those. **`pipeline.yml` is byte-identical and the emitted digests did not move**, proven by building the same goal on both branches rather than asserted. Not a name collision with the *old* Plan 2.5: `CLAUDE.md` records that Plan 1.7 carried that name until 2026-08-05, and the date distinguishes them |
| 17 | [`2026-08-18-plan-3a-phase-0.md`](plans/2026-08-18-plan-3a-phase-0.md) + [`../specs/2026-08-18-the-interface.md`](specs/2026-08-18-the-interface.md) | **Plan 3 is A (forge) · B (landing) · C (Mendel)**, named 2026-08-18. 3A's phase 0 is planned: the foundation, ending on **one real action working end to end** rather than on a shell that compiles. It supersedes `2026-08-18-plan-3-slice-1.md`, which built a working backend and a frontend with **zero event handlers** — the slicing was wrong, and the checkpoint that reported it as "the queue on screen" without saying nothing worked was worse. Every phase now states what you cannot do at the end of it |
| 17b | [`2026-08-18-plan-3-slice-1.md`](plans/2026-08-18-plan-3-slice-1.md) + [`../specs/2026-08-18-plan-3.md`](specs/2026-08-18-plan-3.md) | **Plan 3 — spec written 2026-08-18; SLICE 1 of six is planned, the rest are not.** Each slice produces working software on its own and gets its own plan written against the code the previous one lands — writing all six now would be writing five against code that does not exist, which is what killed Plan 2 and the original Plan 3. Slice 1 is the forge queue end to end, and it comes before the Mendel canvas deliberately: the forge has a backend and the builder does not. The interface is designed ([`docs/design/forge-review.md`](../docs/design/forge-review.md), ten screens) and the spec is written against the code that exists: the forge's HTTP transport is already a mountable app with eleven routes, and the build path has no equivalent because its orchestration lives inside an argparse verb. §4 lists what must exist underneath — DAG layout, a consumers index, which pipelines pin a contract, #69 — each naming the screen that needs it. Supersedes `2026-08-02-mendel-api-and-dashboard.md`, which — predates the types it references. **Gains the tier-4 ambiguity resolver and [#69](https://github.com/comeni-project/Comeni-Labs/issues/69)**, decided 2026-08-17: invariant 6 flags tier 4 even at high model confidence, so a model answer still needs a human, and the thing that makes tier 4 tractable is the review screen rather than the model. Resolver and screen are one feature. #69 — `AiProvenance.available` hardcoded to `[]`, which `MD0225` refuses the moment a resolver writes `source: model` — is its **first design task**, not an assumption |
| 18 | `../specs/2026-08-13-the-rule-drafter.md` | **The rule drafter — spec only, no plan yet. Moved BEHIND Plan 3 on 2026-08-18** (it had been moved *ahead* of it on 2026-08-17). The earlier argument optimised for queue size — nothing authors tier-3 rules, so every ambiguity falls to tier 4 by default. What the project is short of is **feedback**: nothing renders a tier-4 queue, so there is no way to see what the drafter should be aiming at. Its spec also names four hard prerequisites and issue #38's closing note says the drafting question and the measuring question are the same one, which makes it the highest-design-risk item on the board and the worst thing to schedule under time pressure. Originally moved ahead of Plan 3 on the argument that each step shrinks the next one's job: nothing currently authors tier-3 rules, so every ambiguity falls to tier 4 by default, and tier 3 is the differentiator. Its spec names four hard prerequisites and a central risk, and `CLAUDE.md` says read it before building any part of the forge. Issue #38's closing note is the hardest part — the drafting question and the measuring question are the same one, and a measurement has no `meta.yml` to be ground truth |

### Why that order

**Plans 1.5 and 1.6 come before Plan 1.7** because publishing a bundle built on an unverified
spine would push a wrong pipeline through the door with no undo. That earned itself twice: 1.5
found a spine that counted with the wrong strandedness, and 1.6 found three contracts naming
output channels that do not exist.

**Plan 1.7 comes before Plan 2** for two reasons, neither of which was written down until
2026-08-05 — the ordering was asserted by an index and believed for a day.

- *Plan 2 is stale and Plan 1.7 is not.* Plan 2 was written 2026-08-02, before most of the
  types it references existed; the table above says so. Plan 1.7 was written 2026-08-04
  against real code. Every plan in this repository has needed correction during execution —
  six steps in the measurements plan, five in 1.5, six in 1.6 — and the fresher plan is the
  cheaper one to run.
- *Plan 1.7 is pure and Plan 2 is not.* Lockfiles, replay and publish are `comeni-core` and
  `mendel-resolver` work with no new dependency. Plan 2 stands up `mendel-ai`, LiteLLM and
  model access, and opens three of the four egress doors at once. Growing the deterministic
  core while everything is still testable offline is the cheaper sequence.

**The argument against, recorded because it is real:** nothing in Plan 1.7 moves the v1
success criterion, whose one unmet clause is the plain-language prompt — that is Plan 2 Task
3. And `mendel publish` is the door with no undo, built for pipelines drawn from a registry
the forge has not filled yet. If v1 becomes the priority, this order is the thing to revisit.

**Plan 1.8 comes before Plan 2** for one reason, and it is a deadline rather than a preference.
Audit finding A8 is that a resolved routing decision never reaches the pipeline: `_choose`
picks by id order and the resolver is consulted afterwards, only to fill in a record. Plan 2
plugs a model into that exact port. Fixing it first means fixing a signature; fixing it second
means fixing it with a model in the loop and an adapter already written against the broken
shape. The other twelve findings are ordinary technical debt and would not, on their own,
justify inserting a plan here.

**The argument against Plan 1.8, recorded because it is real:** it moves the v1 criterion no
further than Plan 1.7 did, and thirteen fixes is a lot of new code to write immediately before
an audit said fresh code is where the sharpest defects live. The counter is that this is
exactly why round two exists, and why Plan 1.8 Task 12 sets it up rather than declaring victory.
**The exit criterion for that loop was decided on 2026-08-06: no critical findings survive.**
Not "an empty audit" — no audit in this repository has ever come back empty, and important and
minor findings are filed and carried rather than blocking Plan 2 indefinitely.

**Known overlap — resolved 2026-08-13 in favour of absorption**, see
`plans/2026-08-13-plan-2-corrections.md` §2 — deleted with row 14, and in `43b1ce0`: Plan 1.7
ran first, so Task 4 kept only the *persistence* half and feeds the shipped `ReplayResolver`. Original statement of the collision:
Plan 1.7 Task 5 builds `replay.py` in `mendel-resolver`
and Plan 2 Task 4 builds `ReplayingResolver` in `mendel-ai`. They are not the same — one
replays recorded decisions when a curated bundle is edited, the other caches model answers
across runs — but they are close enough that building both without noticing gives two ways to
do one thing. Whichever runs second should absorb the first rather than duplicate it.

### Superseded on 2026-08-18: the rule drafter now runs *after* Plan 3

**What changed and why.** The ordering below argues that each step shrinks the next one's job,
and on that argument the drafter runs before Plan 3. The operator reversed it on 2026-08-18, and
the reason is that the argument optimises for the wrong quantity: **queue size rather than
feedback.** Nothing in the repository renders a tier-4 queue, so nobody has ever looked at one —
and the drafter is the item with the least design clarity on the board (four hard prerequisites,
plus issue #38's note that the drafting question and the measuring question are the same one).
Building it blind, first, under a one-month MVP deadline, is the worst available sequencing.
Plan 2.5 was inserted ahead of Plan 3 in the same decision.

The argument below is kept rather than deleted, because it is still the right argument for the
half that did not change — the forge before either of them.

### Forge Phase 2, then the rule drafter, then Plan 3 — decided 2026-08-17, reversed 2026-08-18

**Each step shrinks the next one's job.** That is the whole argument, and it is why the tier-4
ambiguity resolver — the piece that looks most like "the AI work" — comes last rather than first.

- **The forge fills the registry.** A tier-3 rule cannot match against contracts that do not
  exist, and hand-authoring a registry was never the plan.
- **The rule drafter fills tier 3**, which is what tier 4 is the fallback *from*. Nothing
  currently authors a tier-3 rule, so today every ambiguity the ladder cannot settle lands at
  tier 4 by default. Building a model into tier 4 first would be optimising the fallback path
  while the primary one sits empty.
- **Plan 3 then builds the review queue against a queue as small as it is going to get**, and
  builds the resolver beside the screen that consumes its answer.

**Why the resolver belongs with the GUI and not in its own phase.** Invariant 6 says tier 4 is
always flagged, *even at high model confidence*. So a model answer does not remove the human — it
saves them composing a reply to a question they must still decide. The thing that makes tier 4
tractable is therefore the review screen, and a suggestion with nowhere to be reviewed is half a
feature that invariant 6 guarantees stays half. Today a person answers a tier-4 question by
editing `pipeline.yml` with an `override_reason`, which Plan 1.14 built because that person had
nowhere to say why (A77).

**The argument against, recorded because it is real:** #69 is a `comeni-core` artifact design
question, and putting it inside a frontend plan is how design questions get answered badly. It is
row 17's *first* task rather than an assumption for exactly that reason, and it is filed as an
issue rather than left in this table so it cannot be quietly skipped.

**The other argument against:** this order moves the v1 success criterion no further than the two
plans before it did. Its one unmet clause is the plain-language prompt — goal extraction, door 1
— which is a *third* AI subsystem, distinct from both the forge filler and the ambiguity
resolver, and it is scheduled nowhere. If v1 becomes the priority, that is the row to insert, and
this order is the thing to revisit.

### The loop's exit criterion was overridden on 2026-08-13

**The rule until now:** the fix-then-re-audit loop exits when *no critical finding survives a
fresh audit*. Decided 2026-08-06, and it is why A14 stayed open through four rounds and why
Plans 1.7, 1.8, 1.10 and 1.11 each recorded an argument for deferring Plan 2.

**The decision:** Plan 1.12 is the last audit-driven plan. Plan 2 follows it regardless of what
a round five would find. The operator's reason is that the MVP needs to exist.

**What that means concretely, so nothing here reads as an exit that did not happen:**

- **A14 does not close.** It is carried, not resolved, and round four's own measurement of it
  stands: roughly a fifth of individual guards have a recorded revert. The loop did not exit; it
  was stopped.
- **Fifteen round-four findings are carried** — A60–A69 and A73–A75 as GitHub issues, A71 and A72
  fixed in `CLAUDE.md` directly. None is critical. Two are worth knowing about before Plan 2
  touches the same code: **A62** (`model_construct` and assignment aliases walk past the
  construction guard) and **A68** (the totality guard compares 60% of its field names against
  themselves).
- **Round five's remaining scope was always thin.** Of the three things round four could not
  reach, two — the protection profiles and any impure sender — have no implementation to audit
  yet. The third, the `slow` Docker lane beyond one counts-matrix probe, is real and unaudited.

**The argument against, recorded because it is real and this is the fifth time an ordering
decision has needed one.** Round four found four critical findings, three of them in the guards
themselves, and it found them because cold reviewers attacked a surface they had not written.
Plan 1.12's own surface — two new diagnostics, a changed `resolve()` signature, a rewritten
egress guard, a widened purity scan — gets no such pass, and the audit history says new code is
where the sharpest defects live. Every round so far has found something in the previous round's
fixes.

**The counter, which is why the decision stands:** the v1 criterion's one unmet clause is the
plain-language prompt, which is Plan 2 Task 3, and four plans in a row have now deferred it. An
audit loop whose exit criterion is "the next audit finds nothing critical" has no guaranteed
exit at all — no audit in this repository has ever come back empty. At some point shipping is
the decision, and this is that point. What protects the work is that the fixes are guarded and
the residue is written down, not that another round happened.

### Plan 1.10 — the pipeline file

`specs/` holds nine specs written one per audit root, and one that is not:
**`2026-08-07-the-pipeline-file.md`**. The nine describe fixes to code that exists; that one
describes a design change — `pipeline.yml` as a single readable artifact replacing
`pipeline.ir.json`, `mendel.lock.yml` and `PublishBundle`'s on-disk form, with every setting
carrying its tier, its route to the tool, and its reason.

**It takes precedence over the code it cites**, by the operator's decision on 2026-08-07: the
roots are being implemented concurrently, so its citations will drift, and where they disagree
the spec wins. It may relocate a guard the roots install; it may never weaken one.

**It ran as Plan 1.10 — after Plan 1.9 and *before round three*,** decided 2026-08-07, and it
is complete as of 2026-08-09. **Round three is next**, and the argument below is why it audits
this shape rather than the one before it.

The reason is A14's own logic. Round three is another revert-and-watch sweep over the guards, and A14 is
that a guard never watched failing may be **inert rather than merely weak**. Plan 1.10 moves the surfaces
those guards watch: three artifacts become one, `emit()` loses three arguments, door 4's payload type
changes, sixteen diagnostics arrive. Auditing guards immediately before that is auditing guards that are
about to move — and the guard ledger's rows would attest to code that no longer exists, which is the
exact failure A14 names. Doing 1.10 first means round three audits the shape that will ship.

**The argument against, recorded because it is real and this is the third time:** A14 is critical and
open, the loop's exit criterion is that no critical finding survives, and this defers it again. Plans
1.7, 1.8 and 1.9 each had a version of this argument made against them. The counter is that round three's
value depends on auditing the final surface, not that 1.10 matters more than A14. It changes door 4's
payload type and the shape `replay.py` reads, both of which Plan 2 builds on; doing it second would
mean fixing them with a model already wired to the old shape, which is the same argument that put
Plan 1.8 before Plan 2. **The argument against, recorded because it is real:** it moves the v1
criterion no further than 1.7 or 1.8 did, and the criterion's one unmet clause is still the
plain-language prompt — Plan 2 Task 3. Three plans in a row have now deferred it.

It must not start before 1.9 finishes. Root D is rewriting `diff_ir` and this spec re-targets it;
1.10 landing first would mean rewriting a critical-finding fix underneath its own author.

### What round three inherits from 1.10

Written for whoever audits next, because this is a large new surface and the point of doing
1.10 first was that round three audits the shape that ships.

**New and never audited.** `pipeline.yml` and its round trip; `mendel emit`, `upgrade
--dry-run` and `publish` on a pipeline file; `Pipeline` as door 4's payload; sixteen new
diagnostics (`MD0108`, `MD0202`–`MD0203`, `MD0206`–`MD0216`); `Lockfile.from_pipeline` and
`diff_pipeline`; `ValueSource.HUMAN` and the `needs_review`/`overrides` split.

**Four guards moved or were rebuilt**, and each is worth re-reverting rather than trusting
this plan's own probes:

- `tests/test_egress.py` — its roots come from `DOORS` now, not from `vars(egress)`. The old
  form walked three doors out of four the moment the publication payload moved modules.
- `tests/test_construction.py` — the `Pipeline` allowlist exempts a **spelling**
  (`model_validate` in `pipeline_file.load`), never a file.
- `tests/test_audit_regressions.py` — both A27 tests were rewritten, because both had been
  passing for the wrong reason: they hung a smuggled value on a contract declaring
  `params: []`, so it was dropped before anything validated it.
- `tests/test_counts.py` — has ledger rows now, for the first time.

**Two things this plan found and did not fix**, deliberately, and both are honest candidates
for a finding rather than a fix:

- `MD0216` shipped **inert**: the refusal was written, `make verify` was green, and reverting
  it broke nothing because no test covered it. A guard was written afterwards. That is A14's
  finding happening on the same day as A14's ledger row, and it is recorded rather than
  quietly repaired because the lesson is that green is not evidence.
- `Resolution.source` can be set untruthfully by any resolver, including a future model
  adapter. It is declared vocabulary rather than a proof, on the same standing as `confidence`
  and `reason`. Whether that is acceptable once Plan 2 wires a model to that port is a
  question for round three, not an oversight.

**The guard ledger has five new sections** (Tasks 6–11) and `notes/audits/guard-ledger.md`
is where every probe is recorded, including the ones that found nothing.

### Mendel is the engine and the AI is its primary operator — decided 2026-08-14

**The decision:** everything built through Plan 1 is the engine. A human can drive it and the CLI
is built so they can, but the intended operator is the AI — it turns plain language into a goal,
drives the engine, and `pipeline.yml` is the **save file** it sets down and picks back up, tunes
and re-emits, rather than carrying a pipeline in its context. The full statement is
`docs/design/mendel.md` §1; this records that it was decided and why it needed deciding.

**Why it needed deciding.** The 2026-08-14 design audit's synthesis compared the artifact to a
chat window and asked whether a bench scientist could follow it. The operator's correction was
that this compares a substrate to a product: through Plan 1 there is no AI layer at all, so the
comparison was category-confused. The repository had been documenting both readings at once —
`CLAUDE.md` calls a pipeline "a shareable artifact… the file a reader opens", the artifact's own
header says "Read it; edit it" — without ever saying which one is primary. Two readings implying
different amounts of work is exactly the shape of thing this file exists to settle.

**It costs no invariant, and the check matters more than the conclusion.** An agent running
`mendel build`, editing `pipeline.yml` and running `mendel emit` is a *user of the CLI*, outside
the engine, exactly as a human at a terminal is. Invariant 3 constrains what **Mendel** calls, not
who calls Mendel; the three runtime AI points stay three and the four doors stay four. If a later
design does put a model inside the engine to tune an artifact, that is a fourth point and a new
door, and it must be argued on its own rather than inherited from this decision.

**What it changes: three audit findings get promoted.** Under a human-primary reading these are
legibility defects; under this one they are correctness defects, because the failure mode is a
machine's rather than a person's.

- **A104/A105/A77 — `why:` does not track its value.** A human who edits a value and leaves a
  stale reason beside it does it occasionally and may notice. An agent does it systematically and
  does not.
- **A106 — five of six values reaching the tools carry no `why:`.** A person reading a blank asks;
  **a model reading a blank fills it** from its own knowledge, with a deterministic pipeline
  standing behind the guess lending it credibility. That is the exact failure this design exists
  to prevent, arriving through the component meant to prevent it.
- **A130 — nothing distinguishes a model-authored `why.reason` from a human-authored one.** Under
  `guarded` and `sealed`, where attribution is required, that distinction is load-bearing. It was
  a medium finding; under this decision it is a gap in the protection profiles.

**The argument against, recorded because it is real.** "The AI is the primary operator" is a
claim about a component that does not exist yet — Plan 2 Task 3 is the only thing that will make
it true, and it has been deferred four times. Deciding the shape of an interface around a consumer
nobody has built is how the four-file bundle got designed, and `notes/plans/` is full of
plans written against types that turned out not to exist. There is a real risk that "what the
agent needs" is guessed here and guessed wrong.

**The counter, which is why the decision stands.** It does not add machinery for a hypothetical
consumer; it *raises the standard* on fields the artifact already has and the design audit already
found wanting, and every one of the promoted findings is a defect under the human reading too —
they only change severity. Nothing is built speculatively. And leaving it undecided was itself a
choice with a cost: the audit spent a stream's worth of judgement on a question the documents
could have answered.

### On the numbering

`1.5`, `1.6` and `1.7` are the deterministic core: no AI, no network, no new dependency.
Plan 2 is AI and the forge; Plan 3 is the API and dashboard. **Plan 1.7 was called "Plan 2.5"
until 2026-08-05** — that number recorded when it was written rather than when it runs, and
was read as the latter by everyone including its author. Journal entries dated on or before
2026-08-05 still say "Plan 2.5"; they are append-only and were correct on their date.

Plans 2 and 3 were written ahead of the code they build on, and say things that are no longer
true. That is the reason this directory is labelled the way it is.

### specs/ — the two that are not audit roots

`2026-08-07-the-pipeline-file.md` designed `pipeline.yml` and **shipped** as Plan 1.10.

`2026-08-13-the-rule-drafter.md` is the other, and it is **unscheduled on purpose**. Tier 3 is the
differentiator — the only tier that makes Mendel a resolver rather than a well-documented template
engine — and nothing currently produces tier-3 rules. Plan 2's forge drafts contracts, vocabulary
states and parameters; rule drafting is deferred past Plan 3 by that plan's own reasoning, because
it needs a corpus of real tier-4 flags. The spec records the design so the deferral does not also
lose it, and names four hard prerequisites and the central risk: a model drafting from literature
will produce citations that look right and sometimes are not, and **a rule with a fabricated
citation is strictly worse than no rule**.

## audits/

`2026-08-03-plan-1-audit.md` — an independent review that defeated all three
test-enforced invariants, using four lines of Python for one of them. All four defects are
closed, and the guards in `tests/` are the shape they are because of it. Worth reading
before trusting any guard in this repository.

`2026-08-06-plan-1-to-1.7-audit.md` — the same exercise over everything through Plan 1.7.
Thirteen findings, all reproduced by execution, **none fixed yet**. All three guards fell again,
by shapes they were never written against rather than by shapes they missed. Two findings are
in mechanisms Plan 1.7 shipped and are the reason to read it before starting Plan 2: a resolved
routing decision never reaches the pipeline (A8), and a layer digest does not cover the bytes
the registry loads (A9).
