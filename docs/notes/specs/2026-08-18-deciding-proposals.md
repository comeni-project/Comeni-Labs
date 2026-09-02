# Deciding proposals — Plan 3A phase 3

**Status:** written 2026-08-18, against the code phases 0–2 landed.
**Implements:** [`2026-08-18-the-interface.md`](2026-08-18-the-interface.md) §3 phase 3 —
*"approve, rename or reject a vocabulary proposal"* — and `docs/design/forge-review.md` §3's rule
that **a proposal is an item in the queue**, not a destination.
**Continues:** [`2026-08-17-vocabulary-proposals.md`](2026-08-17-vocabulary-proposals.md), which
created proposals and deliberately left deciding them open, and
[`2026-08-18-answering.md`](2026-08-18-answering.md), which gave a human the door to make one.

---

## 1. What phase 3 is for

Phase 2 made declining possible. **Right now a declined question is a dead end**: `qc.index_stats`
is sitting in the workspace, proposed and waiting, and nothing in the system can act on it. The
draft cannot land, and no verb changes that.

At the end of phase 3, a reviewer can **approve** a proposal (possibly under a better id),
**reject** it with a reason, and land a draft whose new types travel with it.

**What phase 3 is not:** it does not browse contracts, show drift or draft modules — phases 4–6.
It does not add a proposals *page*: the design's rule is that a proposal is a queue item, and the
first design draft giving proposals their own destination was recorded as wrong.

---

## 2. What exists, and what does not

Checked, not remembered.

| Exists | Where |
|---|---|
| `Proposal(id, description, why, by)` | `mendel_forge/scaffold.py:74` |
| `Scaffold.proposed: dict[str, Proposal]`, `Scaffold.propose()` | `scaffold.py:107,131` |
| `ops.propose`, `ShowResult.proposed`, `POST /api/questions/propose` | phase 2 |
| `OpenQuestion.proposed` — the queue already carries it | phase 2 |
| `land()` — writes the contract on a **new branch**, refuses on default, refuses a dirty tree | `mendel_forge/land.py:58` |
| `Vocabulary.with_measurements()` — a **derived** vocabulary with extra types | `comeni_core/declared/vocabulary.py:213` |
| a vocabulary file is three lines — `declares:`, `id:`, `states:` | `registry/types/alignment.bai.yml` |

| Does **not** exist | Consequence |
|---|---|
| any way to decide a proposal | a declined question is a dead end |
| a rejected state | rejecting could only mean deleting, which loses the decision |
| `land` writing vocabulary | an approved type never reaches the registry |
| a `blocked` band | proposals do not sort where design §4 puts them (rung 2 of 5) |

---

## 3. Decisions

### 3.1 The vocabulary file is written at **land** time, in one commit

**Decided by the operator, 2026-08-18**, and it is
[`2026-08-17-vocabulary-proposals.md`](2026-08-17-vocabulary-proposals.md) §4.2 honoured
literally: *"One review, not two: the proposal and the contract that motivated it are reviewed
together, because a type proposed with no consumer is a type nobody can judge."*

```
land  ->  one branch, one commit:
            types/qc.index_stats.yml          <- the approved proposal
            tools/nf-core/samtools/index.contract.yml
```

`land` already writes the contract and, when present, the module. Approved proposals join that
list. A reviewer opening the branch sees the new type and its first consumer side by side.

**The cost is real and it is §3.3's problem:** between approving and landing, the draft cites a
type the registry does not declare.

### 3.2 Approving is a distinct act from filling, and it bypasses candidate validation **on purpose**

`Scaffold.fill` refuses a value that is not among a hole's candidates — `MF0003`, and that
refusal is a guarantee worth keeping. **An approved proposal is by definition not among them**:
the entire reason it exists is that nothing declared fits.

So approving does not call `fill`. `Scaffold.decide()` moves the value into `filled` itself,
exactly as `propose()` writes into `proposed` itself. That is not a hole in the validation; it is
a second act with a different precondition — *a named human approved this* rather than *the
registry already declares it*.

**What still holds:** the value is recorded with `ValueSource.HUMAN`, a `by` and a `why`, like
every other value. Nothing becomes untraceable.

### 3.3 `verify` checks against the registry **as this draft would leave it**

Between approve and land, `_loads` would raise `UnknownTypeError` — `verify.py:174` calls
`contract.check_against(stack.vocabulary)` and the type is not there yet.

The fix is not to weaken the rung. It is to verify against the vocabulary **the draft is
proposing to create**, which is what a reviewer actually wants to know: *if I land this, does it
load?* `Vocabulary.with_measurements` is the precedent — a method returning a derived vocabulary
with extra types, rather than a mutation.

```python
stack.vocabulary.with_proposals(scaffold.approved())   # a derived Vocabulary
```

**A rejected or undecided proposal contributes nothing**, so a draft that still has open
proposals fails `_complete` first and never reaches `_loads`. The extension only ever contains
types a named human approved.

### 3.4 A rejection is **recorded**, not deleted

**Decided by the operator, 2026-08-18.** Deleting the proposal returns the hole to looking exactly
like one nobody has reached — and distinguishing those two is what §3.2 of the proposals spec says
a decline exists to do. Throwing that away at the moment of decision is the wrong direction.

`Proposal` gains a decision:

```python
decision: Decision = Decision.OPEN     # OPEN | APPROVED | REJECTED
decided_by: str = ""
decided_why: str = ""
```

The hole reopens on rejection; the record stays beside it. A model that proposes the same thing
again meets a reviewer who can read *this was already answered, and here is why*.

### 3.5 Rename is approve-with-a-different-id

Not a third verb. `decide(field, APPROVED, id="qc.report.html")` — omit `id` and the proposed one
stands. The design lists *approve, rename or reject* as three actions in the interface; underneath
there are two decisions and one optional argument, because renaming and approving differ only in
what gets written.

**The reviewer's id wins and the proposer's is kept.** `Proposal.id` stays as proposed;
`decided_id` carries what was approved. A rename is a judgement about somebody's suggestion and
losing the suggestion loses the judgement's subject.

### 3.6 Proposals sort into the queue's **blocked** band

Design §4's ladder is drift, **blocked**, ask, confirm, label. `Band.rank` left 1 and 2 free for
exactly this. An open proposal is rung 2 — a proposal the vocabulary needs before a module can
land — and it outranks every ordinary question.

`Band.BLOCKED = "blocked"` with `rank == 2`, derived in `band_for` from the question carrying an
open proposal rather than stored. **The band is a function of the question's state**, which is
what `band_for`'s docstring already promises.

---

## 4. The surface

### 4.1 API

| Method | Path | operationId | Over |
|---|---|---|---|
| `POST` | `/api/questions/proposals/decide` | `decideProposal` | `ops.decide` |

One route, not two. Approve and reject are one decision with a value, the same way a tier-4
answer is; two endpoints would let them drift apart.

The interface spec §5 predicted `GET /questions/proposals` as well. **It is not needed**: every
open proposal is already on an `OpenQuestion` in `GET /questions`, and a second listing would be
a second projection of the same data — the mistake §3 of the design names.

### 4.2 Forge

```
DecideRequest:  name, field, decision, id?, why, by, workspace_root
DecideResult:   name, field, decision, value?, remaining
```

`value` is what landed in `filled` on an approval and `None` on a rejection; `remaining` shrinks
on approval and does not on rejection.

`land` gains: for every `APPROVED` proposal on the draft, write `types/<decided_id>.yml` with
`declares: vocabulary`, the id, and `states: []`.

**States are empty, deliberately.** A new type's states are a separate judgement, and inventing
them at approval time would be the reviewer guessing at a second thing while judging the first.
`add_states:` exists for a later layer to extend it — invariant 11.

### 4.3 Routes

No new routes. `/forge/queue/proposal/:id` from the interface spec's §4.1 table is **not built**:
a proposal is attached to a question, and the question's own route already shows it (phase 2
renders `q.proposed`). Deciding happens there.

**That is a deviation from the route table and it is deliberate.** The table was written before
proposals were attached to holes; a proposal has no identity apart from the `(draft, field)` it
belongs to, so a route keyed on a proposal id would need an id nothing generates.

---

## 5. What this does not settle

**Whether an approved type should be checked for near-duplicates.** `CLAUDE.md` names this as one
of the two cases that genuinely need semantic retrieval: two drafts proposing `qc.report` and
`quality.summary` for one thing, which no exact lookup catches. Phase 3 shows the reviewer every
declared type through the phase 2 lookup panel and nothing more.

**Whether landing should be possible from the interface at all.** `land` runs git and writes to a
submodule at detached HEAD; phase 3 makes `land` *able* to carry vocabulary but does not put a
button on it. That is phase 6's question, with drafting.

**What happens to a rejected proposal's hole when nothing else fits either.** The reviewer rejects,
the hole reopens, and the same person may immediately propose again. That loop is correct but
unbounded, and nothing counts it.
