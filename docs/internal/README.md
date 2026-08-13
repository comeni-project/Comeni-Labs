# Internal working notes

**These are not documentation.** They are kept for provenance — so that a decision can be
traced to the moment it was made — and they are not maintained against the code.

If you want to know how Mendel works, read [`ARCHITECTURE.md`](../../ARCHITECTURE.md) and
[`docs/`](../README.md). If you want to know *why*, read [`docs/design/`](../design/).

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
| 13 | `../audits/2026-08-14-design-audit-brief.md` | **The design audit — next.** Not like rounds one to four: does the *design* deliver the claim, rather than does the code match the design. Brief written; not yet run |
| 14 | `2026-08-02-mendel-ai-and-forge.md` | Plan 2 — after it. Predates the types it references; rewrite before executing |
| 15 | `2026-08-02-mendel-api-and-dashboard.md` | Plan 3 — predates the types it references |

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

**Known overlap, not yet resolved:** Plan 1.7 Task 5 builds `replay.py` in `mendel-resolver`
and Plan 2 Task 4 builds `ReplayingResolver` in `mendel-ai`. They are not the same — one
replays recorded decisions when a curated bundle is edited, the other caches model answers
across runs — but they are close enough that building both without noticing gives two ways to
do one thing. Whichever runs second should absorb the first rather than duplicate it.

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

**The guard ledger has five new sections** (Tasks 6–11) and `docs/internal/audits/guard-ledger.md`
is where every probe is recorded, including the ones that found nothing.

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
