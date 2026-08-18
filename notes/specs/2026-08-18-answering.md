# Answering — Plan 3A phase 2

**Status:** written 2026-08-18, against the code phases 0 and 1 landed.
**Implements:** [`docs/design/forge-review.md`](../../docs/design/forge-review.md) §5 and §6.
**Extends:** [`2026-08-18-the-interface.md`](2026-08-18-the-interface.md) §5, which names
`answer-all` as *"the one genuinely new operation"* and leaves its refusal semantics open.
**Depends on:** [`2026-08-17-vocabulary-proposals.md`](2026-08-17-vocabulary-proposals.md) — the
`Proposal` type and `Scaffold.propose()` exist because of it.

---

## 1. What phase 2 is for

Phase 0 proved one answer could reach the artifact. Phase 1 made the queue workable. **Neither
made answering good**, and the design's whole claim about throughput lives in this phase:

> Asked by `samtools/index`, `samtools/sort` and `picard/markduplicates` — answering once settles
> all three.

At the end of phase 2 you can answer one question well, answer it across every draft asking it,
read the evidence behind it without leaving the screen, look a type up mid-decision, and **decline
it** when nothing declared fits.

**What phase 2 is not:** it does not review proposals, browse contracts, show drift or draft
modules. Those are phases 3–6.

---

## 2. What already exists, and what does not

Checked, not remembered.

| Exists | Where |
|---|---|
| `ops.fill(FillRequest)` — one field, one draft, validated against the hole | `mendel_forge/ops.py:232` |
| `Proposal(id, description, why, by)` | `mendel_forge/scaffold.py:74` |
| `Scaffold.propose(field, proposal)` — records it, **hole stays open** | `scaffold.py:131` |
| `Scaffold.proposed: dict[str, Proposal]` | `scaffold.py:107` |
| `Hole.evidence: list[Excerpt]`, `Excerpt(locator, text)` | already on every question |
| `Hole.after` — a hole whose candidates depend on another | `scaffold.py:60` |
| `_with_fresh_candidates` — recomputes dependents after a fill | `ops.py:244` |
| `useKeys` with `INPUT`/`TEXTAREA`/`SELECT` ignored | `frontend/src/app/useKeys.ts` |
| `vocabulary.types[id] -> frozenset[str]` (the states) | `layers.load()` |

| Does **not** exist | Consequence |
|---|---|
| `ops.propose()` | a human has no path to a proposal; only `fill_with_model` can make one |
| any batch verb | `answer-all` is a loop somebody has to write, with semantics |
| `OpenQuestion.proposed` | the queue cannot show that a question was declined |
| a registry lookup route | the Shell's `Registry` button is `aria-disabled` |

**`ops.fill_with_model` can already produce a proposal** — `ModelFillResult.proposed_id` and
`proposed_description`. So the *shape* is settled by a model path that exists; phase 2 gives the
same shape a human author.

---

## 3. Decisions

### 3.1 `answer-all` is best-effort, and reports every refusal

**Decided by the operator, 2026-08-18.**

`POST /api/questions/answer-all` takes one `{subject, value, why, by?}` and settles it on **every
draft that has that subject as an open hole**. A draft that refuses is reported, not rolled back.

```
-> 200 {
     "subject": "consumes[0].type_id",
     "settled": ["samtools-index", "samtools-sort"],
     "refused": [{"draft": "samtools-faidx", "detail": "MF0003: 'alignment.bam' is not legal…"}]
   }
```

**Why not all-or-nothing.** The design's own worked example is a batch where one member is wrong:
four rows reading `alignment.bam` and a fifth from `samtools/faidx`, *"the only faidx input is a
FASTA — check this one"*. Under all-or-nothing that one draft blocks the other four, and the
throughput move the design rests on stops working exactly when it is most needed.

**It is still atomic per draft** — `ops.fill` either writes a draft or raises, and it writes the
whole draft. Never half.

**The partial write is the cost, and it is paid in the response rather than hidden.** `refused` is
never omitted and never empty-by-omission: an empty list means *nothing refused*, and the UI
renders the refusals as `Refusal` components with their codes intact. A 200 carrying refusals is
correct here — the operation did what it was asked and is reporting what it found — and the
alternative, a 207, is a status no generated client models usefully.

**Order is by draft name.** Workspace order is directory order, which moves under a refactor
nobody asked for — the same argument as `aggregate`'s `asked_by.sort()`.

### 3.2 Phase 2 creates proposals; phase 3 decides them

**Decided by the operator, 2026-08-18.**

A closed choice with no way to decline forces a wrong answer, so the escape hatch ships with the
screen that presents the choice. `POST /api/questions/propose` records a `Proposal` on the draft
through a new `ops.propose()`.

**The hole stays open.** That is `Scaffold.propose`'s existing contract and this must not weaken
it: `is_complete()` stays false, `contract_from` still refuses, `land` still refuses. What changes
is that the hole now says *why* it is open.

Phase 3 adds the queue row, the review screen and approve/rename/reject.

**A question that carries a proposal must look different from one nobody has reached.** That is
the point of proposing at all, so `OpenQuestion` gains `proposed: Proposal | None` and the row
says so.

### 3.3 Evidence is collapsed by default, and `E` opens it

Design §5, verbatim: *"This is the change that removes the overwhelm: on the confirmable questions
you never open it, and the screen is a question, three options and a button."*

Collapsed state is **in the URL** (`?evidence=open`), like every other view state — a curator
sending a link to a question they find confusing is sending it *because* of the evidence.

### 3.4 The registry lookup is a panel, not a page

Design §3: *"Registry is a BUTTON rather than a nav item, deliberately: you consult it
mid-decision, and navigating away from a question you are answering is the friction the design
removes."*

`?lookup=<type-id>` on any route, served by `GET /api/registry/types/{id}`, returning the type's
**states** and **which contracts already use it**. That second half is what makes it a decision
aid rather than a dictionary: *"7 contracts consume this"* answers "is this the normal choice"
in a way a description cannot.

**Exact retrieval, not similarity** — `CLAUDE.md`'s note on why there is no vector store applies
directly: the useful lookup names which contracts use each type, and every fact is versioned and
diffable.

### 3.5 `A` accepts and `E` opens evidence

Completing the design's map, now that both act on something. `useKeys` already ignores keystrokes
aimed at a field, which is what makes `A` safe beside a reason box.

---

## 4. The surface

### 4.1 API

| Method | Path | operationId | Over |
|---|---|---|---|
| `POST` | `/api/questions/answer-all` | `answerAll` | a loop over `ops.fill`, best-effort |
| `POST` | `/api/questions/propose` | `proposeType` | `ops.propose` — **new forge verb** |
| `GET` | `/api/registry/types/{id}` | `lookupType` | `layers.load()` — states and users |

Every one carries an `operationId`, a tag and a summary; `test_openapi.py` holds them literally.
Refusals are 422 with the code intact, through the app-level handler.

### 4.2 Forge

`ops.propose(ProposeRequest) -> ProposeResult`:

```
ProposeRequest: name, field, id, description, why, by, workspace_root
ProposeResult:  name, field, remaining   # remaining is UNCHANGED — a proposal is not a fill
```

`ProposeResult.remaining` deliberately mirrors `FillResult.remaining` **and deliberately still
contains `field`**. A caller that reads `remaining` to decide whether a draft can land must get
the truthful answer, and the truthful answer is that it cannot.

### 4.3 Routes

No new routes. `/forge/queue/question/:subject` gains `?evidence=open`; `?lookup=` works
everywhere. That is §4.1 of the interface spec unchanged, which is the test of whether it was
designed right.

---

## 5. What this does not settle

**Answer-all across a *filtered* queue.** The design's §6 grouping — "four rows reading
`alignment.bam`" — is a view over answers, and phase 2 answers by subject rather than by proposed
value. Grouping identical *answers* is phase 3's problem, with proposals.

**Whether a partial `answer-all` should be undoable.** There is no undo anywhere in the forge
today; `forge fill` is equally final. Adding one for the batch path only would be inconsistent,
and adding one everywhere is its own piece of work.

**`queue.read()` still re-reads every draft per request.** Fine at two drafts, first thing to
break at scale. Phase 2 makes it worse — `answer-all` reads them all again to find who asks — and
that is acceptable at this size and worth measuring before designing around.
