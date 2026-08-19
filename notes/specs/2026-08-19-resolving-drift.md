# Resolving drift — Plan 3A phase 5

**Status:** written 2026-08-19, against the code phases 0–4 landed.
**Implements:** [`docs/design/forge-review.md`](../../docs/design/forge-review.md) §7's last three
paragraphs — drift, every field checked, and the verdict block — plus §4's first rung of the
queue's consequence order.
**Extends:** [`2026-08-18-the-interface.md`](2026-08-18-the-interface.md) §4.1c, and
[`2026-08-18-plan-3.md`](2026-08-18-plan-3.md) §4.6 and §4.7, which named this work and left it
to a phase.

---

## 1. What phase 5 is for

Phase 4 landed the contracts list with a `drifted` facet that reads **0**, and a module page that
cannot say what moved. `Band.rank`'s docstring reserves rung 1 for drift with the words *"has no
member yet — it is phase 5"*. This is that phase.

At the end you can see a drifted contract at the top of the queue, open it, read **every field
something checked** with the source line beside it, read whether the change moves what gets built,
and **take the source's value** — producing one commit on a branch in the registry checkout, with
who accepted it and why.

**What phase 5 is not:** it does not learn what upstream says
([#64](https://github.com/comeni-project/Comeni-Labs/issues/64)), it does not edit a contract by
hand, and it does not schedule the check — the nightly cron belongs with Compose in phase 7, which
is where there is a Redis to run it.

---

## 2. What exists, and what does not

Checked by running it, not remembered.

| Exists | Where |
|---|---|
| `ops.check(CheckRequest) -> CheckResult(checked, skipped, drift)` | `mendel_forge/ops.py:537` |
| `Drift(contract_id, field, registry_says, source_says)` — **no evidence, no impact** | `ops.py:485` |
| `assemble.DERIVED_FIELDS` — **three** fields: `nf_process`, `nf_include`, `container` | `assemble.py:47` |
| `conformance.against(contract, spec, path) -> list[Diagnostic]` — MD0101–MD0108 | `mendel_compiler/conformance.py:108` |
| `verify._conforms` already runs that against a **draft** | `mendel_forge/verify.py:199` |
| `land()` — branch, refuse the default branch, refuse a dirty tree, commit | `land.py:58` |
| `Band.rank` reserves **1** for drift | `mendel_api/questions.py` |
| `Status.DRIFTED / UNVERIFIABLE / MATCHING`, cached on the registry digest | `services/contracts.py` |
| `SourceCheck` table, `check_sources` ARQ job | `models.py`, `worker.py` |
| fact evidence carries a real `file:line` locator | measured, below |

| Does **not** exist | Consequence |
|---|---|
| any per-field record of what *agreed* | *"every field checked"* cannot be rendered |
| any classification of what a field affects | the verdict has nothing to derive from |
| any write path from the API into a registry | accepting is the first one |
| a drift row in the queue | rung 1 of the design's sort is empty |
| a cron schedule | *"checked 4 min ago · next nightly"* is half true; `checked_at` is real, "next" is not |

**Measured on this registry, 2026-08-19:**

```
ops.check            0.39s   checked=10  skipped=2  drift=0
conformance sweep    0.09s   12 of 12 contracts clean
layers.load          0.25s
ModuleContract       13 fields
```

The two skipped are the `comeni/` contracts — no source adapter — and **both have readable
modules and conform**, which is phase 4 §3.4's distinction holding up.

**Evidence locators are real**, which the design's *"which source line the contract drifted at"*
depends on:

```
process    modules/nf-core/samtools/index/main.nf:1   process SAMTOOLS_INDEX {
container  modules/nf-core/samtools/index/main.nf:6   container "${workflow.containerEngine …
nf_include modules/nf-core/samtools/index/main.nf     read from …/main.nf
```

`nf_include` is the exception and it is worth naming: that fact is **synthesised from the
convention** rather than read off a line, so its locator has no line number and its text is a
sentence rather than a quotation. The screen must not present it as a quotation.

---

## 3. Decisions

### 3.1 There are two drift checkers, they overlap, and phase 5 declares the coverage rather than merging them

`ops.check` compares three fields by value. `conformance.against` compares the contract's
*structure* to the module and emits MD0101–MD0108. **They already overlap**: MD0101 is
`nf_process` and MD0107 is `container`, which are two of `ops.check`'s three.

Merging them was considered and rejected. They have different callers and different obligations:
conformance runs inside `mendel build` and must **refuse**; `ops.check` reports and writes
nothing. Collapsing them would either make a build depend on the forge or make a report able to
block one.

What phase 5 adds instead is **one declared table** saying, per `ModuleContract` field, what reads
it and what can check it. Two checkers are fine; two undocumented and unequal coverages are not.

### 3.2 *"Every field checked"* means every field something can speak to — and the rest are named

The design asks for four matching rows and then *"11 further fields checked, all matching"*. Taken
literally against this code that sentence would be **false**: nothing checks `roles`, and no source
can state it.

So the screen reports three groups, and every one of the 13 fields is in exactly one. Which code
speaks to which field was read out of `conformance.py`, not assumed:

| Group | Fields | How |
|---|---|---|
| **value** | `nf_process`, `nf_include`, `container` | the source states it; compare |
| **structure** | `nf_inputs`, `produces`, `params`, `ext_args` | MD0102–MD0105, MD0108 |
| **nothing** | `id`, `consumes`, `roles`, `priority`, `priority_because`, `provenance` | no source states it |

Two fields are checked **both** ways — `nf_process` is `ops.check`'s comparison and MD0101, and
`container` is MD0107 — which is §3.1's overlap made concrete rather than described.

**The third group is the uncomfortable one**, and it belongs on the screen rather than in this
file: `consumes`, `roles` and `priority` are all read by the router, so **three of the five fields
that decide routing are verified by nothing at all.** A port's `type_id` is the single most
consequential value in a contract and no source can state it — that is why it is a hole a human
fills, and it is also why a drift report that listed only what it checked would read as a clean
bill of health over an unchecked half.

`value + structure + nothing == 13` is a test, the same shape as phase 4's
`matching + drifted + unverifiable == total`.

**Two conformance codes are not about a field**, and are declared so rather than left to fall out
of the table: MD0100 is the module's *absence*, and MD0106 is registry-wide — it is emitted by
`conformance.check()` over the measurement vocabulary, not by `against()` over one contract, and
its `where` can name a measurement rather than a contract.

### 3.3 The verdict is derived from a total classification, and it is three-way

`2026-08-18-plan-3.md` §4.7 requires the verdict to be **derived from the field, not hardcoded per
case, or it will be wrong the first time a field is added.** So:

```python
class Impact(StrEnum):
    ROUTES  = "routes"   # the resolver reads it: which contract is chosen, and how it connects
    BUILDS  = "builds"   # the compiler reads it: what the emitted Nextflow contains
    RECORDS = "records"  # nothing reads it at build time
```

Read out of the code rather than asserted — `router.py` reads `id`, `roles`, `priority`,
`consumes`, `produces`; `resolve.py` adds `params`; the emitter reads `nf_process`, `nf_include`,
`nf_inputs`, `ext_args`, `container`:

| Impact | Fields |
|---|---|
| `ROUTES` | `id`, `roles`, `priority`, `consumes`, `produces` |
| `BUILDS` | `nf_process`, `nf_include`, `nf_inputs`, `ext_args`, `container`, `params` |
| `RECORDS` | `priority_because`, `provenance` |

Binary was the obvious design and it is wrong: the design's own example sentence — *"Nothing
routes differently, `container` is not read by the router"* — does **not** say nothing changed. A
container bump changes what runs while every pipeline still resolves to the same contract. Two
categories force those into one word.

The verdict is then a fold over what disagreed, worst first:

| Verdict | Fires when | Sentence |
|---|---|---|
| `BREAKS` | any conformance diagnostic that refuses | *a pipeline pinning this cannot be emitted* |
| `REROUTES` | a `ROUTES` field disagrees | *resolution can now pick differently* |
| `REBUILDS` | only `BUILDS` fields disagree | *nothing routes differently; what runs changes* |
| `AGREES` | nothing disagrees | — |

**Two totality tests, because a table like this decays silently:** every field of
`ModuleContract.model_fields` appears exactly once in the table, and every diagnostic in
`REGISTRY` whose `concern` is `conformance` is either claimed by **at least one** field or listed
in a declared `NOT_A_FIELD` set with its reason. At least one rather than exactly one, because
MD0108 genuinely speaks to two — `params` and `ext_args` — and a test demanding one would be
satisfied by dropping the truer half. Adding MD0109 without classifying it fails a test instead of
falling silently out of the verdict.

**Today every checkable field is `BUILDS`**, so `REROUTES` cannot fire against this registry from
a value check. It is reachable through conformance — a renamed `emit:` label is `produces` — and
the unit test constructs it directly. Saying this here is the point: a verdict with one reachable
branch reads like a working verdict.

### 3.4 A drift row is a queue row; the detail lives under the contract

Design §8 makes *one row shape for every kind of work* firm, and the interface spec §4.1 already
decided drift **appears** in the queue and **resolves** under contracts.

`OpenQuestion` gains two fields: `kind: RowKind` (`question` | `drift`) and `about: str | None`
(the contract id, set on a drift row). The frontend switches on `kind` for the link target —
`/forge/contracts/:about/drift` rather than `/forge/queue/question/:subject`.

**The alternative was to overload `asked_by`**, whose docstring says *which drafts ask it*, with a
contract id. That is a lie in a field that already has a meaning, told to save two fields, and it
would be discovered by whoever next reads the queue's aggregation.

A drift row carries `band=Band.DRIFT` (rank 1), `subject=f"{contract_id}#{field}"`,
`what="container moved"`, `why_open` naming both values, and the source excerpt as `evidence`.
`candidates` stays empty: a drift is not answered by choosing, and a row that offered the source
value as a candidate would invite `POST /questions/answer` on a contract that has no draft.

**Aggregation leaves drift rows alone.** `aggregate()` collapses identical questions across
drafts; two contracts drifting on `container` are two pieces of work with two different values,
and collapsing them would offer one accept for two commits.

### 3.5 A contract that fails conformance is `drifted`

Phase 4's `Status` reads only `CheckResult.drift`, so a contract whose module renamed an `emit:`
label — which breaks emission — shows as `matching` today. That is the same class of falsehood as
folding `skipped` into `matching`, one checker over.

`Status.DRIFTED` becomes *value drift **or** a refusing conformance diagnostic*. The health strip's
`matching` count follows, since it is computed from the same numbers.

This makes phase 4's facet stricter rather than adding a fourth status: a reader asking *does this
contract still describe its module* does not care which of two checkers noticed.

### 3.6 Accepting patches one line, and never re-serialises the file

Registry contracts carry **comments that are the reasoning** — `samtools/index.contract.yml` has
six lines explaining why the index port is named `index`, including a note that a previous value
was latent until conformance caught it. `yaml.safe_dump` of a parsed contract deletes every one of
them, and `A128` already records a `priority` justification living only in a discarded comment.

So `ops.accept` **patches the line** that declares the field and writes nothing else:

- the field must appear exactly once, at the top level, on one line, as `field: value`
- anything else — a block scalar, a repeated key, a field inside a flow mapping — is refused with
  `MF0102` rather than guessed at
- the patched text is **parsed and validated before it is written**: it must load as a
  `ModuleContract` and must still pass conformance on the accepted field, or `MF0103` refuses and
  the file on disk is untouched

Only `value`-group fields are acceptable, and only scalars. `container`, `nf_process` and
`nf_include` are all one-line scalars in every shipped contract, which is why this is a
restriction rather than a limitation today — and `MF0102` is what makes the day it stops being
true loud.

### 3.7 Accepting commits into the registry checkout, on a branch, and refuses when it cannot do that safely

**This is the first write from the API into a registry**, and it is where invariant 2 is either
honoured or quietly bent. It is honoured: a human clicked accept, which *is* the approval, and the
commit records who and why. What phase 5 adds is the same guard rail `land()` already carries.

One registry root, not two. A separate writable root was considered and rejected: the drift you
are looking at was computed from the read root, and accepting it into a different checkout would
let the screen and the commit disagree. Point `MENDEL_REGISTRY_ROOT` at a checkout you can write
to — which is what landing already asks for.

Refusals, all coded, all before anything is written:

| | |
|---|---|
| `MF0100` | the checkout is on its default branch and no branch was named |
| `MF0101` | the checkout has uncommitted changes |
| `MF0105` | the checkout is at a **detached HEAD** — which `registry/` in this repository is, being a submodule |

`MF0105` is new and it exists because the default configuration hits it. A submodule at a pinned
commit is exactly the thing you must not commit into by accident, and `land()`'s docstring already
says so about `--registry`; this is that argument reaching the API.

**The branch is reused when HEAD is already on it.** `land()` always creates, because a draft
lands once. Drift is accepted repeatedly, so `forge/drift` is created if absent and committed onto
if present — otherwise the second accept branches off the first and the history reads as two
unrelated lines.

### 3.8 The registry has zero drift, so phase 5 ships a way to see one

`drift=0` and `12 of 12` conform. **Every screen this phase builds renders empty against the real
data**, which is how the confirmable band came to be built and never seen.

So the exit criterion is not *the screen loads*. It is: manufacture a real drift in a throwaway
registry clone — change one container tag — point the API at it, and watch the row appear at the
top of the queue, accept it, and read the commit with `git show`. The recipe is a task, written
into `docs/guides/driving-the-forge.md`, so it can be re-run rather than reconstructed.

---

## 4. The surface

### 4.1 API

| Method | Path | operationId | Over |
|---|---|---|---|
| `GET` | `/api/contracts/{id}/drift` | `readDrift` | `ops.drift` — one contract, every field |
| `POST` | `/api/contracts/{id}/drift/accept` | `acceptDrift` | `ops.accept` — one field, one commit |

`{id}` is a `:path` parameter, as in phase 4. The accept body is `{field, by, why}`; `by` defaults
from `identity.default_author()` and `why` is required — a value changed with no reason recorded is
the thing this project exists not to do.

`GET /api/contracts` and `/api/health/registry` change their **numbers**, not their shapes (§3.5).

### 4.2 The forge

| | |
|---|---|
| `ops.drift(DriftRequest) -> DriftReport` | one contract: value checks, conformance, unchecked fields, verdict |
| `ops.accept(AcceptRequest) -> AcceptResult` | patch one field, validate, commit, return branch and commit |
| `drift.py` | the impact table, the coverage table, the verdict fold, and both totality tests |

`ops.check` keeps its signature — the sweep the worker and the contracts list already call — and
gains conformance into `CheckResult.drift` through a `Drift.code` field that is `None` for a value
drift and the diagnostic code for a structural one.

### 4.3 Routes

```
/forge/contracts/:id/drift          a STATE of a contract, not a destination
/forge/queue                        gains drift rows at rung 1
```

Which is the interface spec §4.1 unchanged.

### 4.4 What the drift screen carries

Top to bottom, and the order is the argument: **what happened**, then **what it means**, then
**what you can do**.

1. the contract id, its status, and when the check ran
2. **the verdict block** — one sentence naming the fields, from §3.3
3. **every field checked**: field, what the registry says, what the source says, the locator, and
   the impact — matching rows collapsed behind *"N further fields checked, all matching"*
4. **conformance**, when it has anything to say, each with its code and `fix:`
5. **what nothing checks**: the six fields, with the sentence that `consumes`, `roles` and
   `priority` route
6. **take the source's value** — per drifted value field, with `by` and a required `why`

A conformance drift has **no accept button**, and the screen says why: which emit label a renamed
channel now means is a judgement, and the path for a judgement is a re-draft through the queue.

---

## 5. What this does not settle

**Whether a re-draft is the right path for structural drift.** `ops.update` re-drafts from source
and produces a scaffold with **every hole open again** — a contract whose ports were answered by a
human last month asks all of it a second time. That is wrong, it is why accepting patches instead,
and the fix for the conformance half is a re-draft **seeded from the landed contract**, which is
its own piece of work.

**Nothing knows what upstream says.** [#64](https://github.com/comeni-project/Comeni-Labs/issues/64).
The screen may say the registry disagrees with the vendored module; it may never imply a newer
version exists.

**The check is not scheduled.** `checked_at` is real; *"next nightly"* is not, and the strip must
not print it until phase 7 adds the cron.

**The sweep is still O(registry).** `ops.drift` for one contract is cheap; `ops.check` grows, and
phase 4's decision to cache on the digest rather than store a table is unchanged and still the
first thing that breaks at 5,800.

**Per-field origin on a landed contract still does not exist** (phase 4 §3.6), so the drift screen
can say what a field is *now* and what the source says, and cannot say who last set it.
