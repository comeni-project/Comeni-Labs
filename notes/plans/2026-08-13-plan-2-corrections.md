# Plan 2 — corrections against the code that exists

**Read this before executing `2026-08-02-mendel-ai-and-forge.md`.** Where they disagree, this
file wins.

`notes/README.md` has said since 2026-08-05 that Plan 2 "predates the types it references;
rewrite before executing". This is that rewrite, and it is an addendum rather than a new plan on
purpose: **most of Plan 2 is still correct.** Its TDD steps, its test code and its task
decomposition survive. What has moved is a countable set of types and two semantics, and
enumerating those is more honest than reissuing 2,800 lines that would claim a verification they
did not get.

**Verified against the tree at Plan 1.12 (2026-08-13).** Every claim below was checked by grep or
by reading the type, not inferred from the journal.

---

## What did *not* move, checked and worth knowing

Two things were expected to be stale and are not. They are recorded because a rewrite that only
lists breakage teaches the reader to distrust everything.

- **`AmbiguityResolver` is unchanged.** The port is still
  `def resolve(self, ambiguity: Ambiguity) -> Resolution: ...` (`mendel_resolver/ports.py:19`),
  and Plan 2 Tasks 5 and 6 declare exactly that signature. **A56 changed the module-level
  `resolve()` in `resolve.py`, not the port** — an earlier reading of this said otherwise and was
  wrong. Task 5's `LLMResolver` needs no signature change.
- **The artifact rename barely touched this plan.** `PublishBundle` appears zero times and
  `mendel.lock.yml` zero times; `pipeline.ir.json` appears once. Plan 1.10 renamed less of Plan 2's
  surface than its blast radius suggested.

---

## Correction 1 — `DecisionRecord` is a union, not a class

**Affects:** Task 4 (the decision store), Task 5, anywhere a record is constructed or keyed.

`DecisionRecord` was one class when Plan 2 was written. Audit A16 split it into three, and it is
now a discriminated union alias (`comeni_core/decision.py:181`):

```python
DecisionRecord = Annotated[ParamDecision | ProducerDecision | SourceDecision, ...]
```

with `AmbiguityKinds = (ParamAsked, ProducerAsked, SourceAsked)` as the matching request types.

**What to do:** a store that persists or looks up records must round-trip the discriminator, not
just the fields. `Ambiguity.key()` is `f"{node_id}.{subject}"` and is the identity to key on — do
not invent a second key format. Construct the specific kind (`ParamDecision`, …), never
`DecisionRecord(...)`, which is not callable.

## Correction 2 — Task 4 must absorb `replay.py`, not duplicate it

**Affects:** Task 4.

Task 4 produces `ReplayingResolver(inner, store)`. `mendel_resolver/replay.py` already ships
`ReplayResolver(records, fallback)`, built in Plan 1.7, and it already handles the hard parts:
first-record-wins on duplicate keys, `_still_applies` staleness, and the `replayed` / `fresh` /
`stale` / `stale_overrides` / `orphaned` split that `mendel upgrade` reports from.

`notes/README.md` flagged this collision when Plan 1.7 was written:

> They are not the same — one replays recorded decisions when a curated bundle is edited, the
> other caches model answers across runs — but they are close enough that building both without
> noticing gives two ways to do one thing. **Whichever runs second should absorb the first rather
> than duplicate it.**

Plan 1.7 ran first. **So Task 4 absorbs.** The genuinely new part is *persistence* — a store on
disk that survives between runs — not the replay logic. Build `DecisionStore` as the store and
feed its records to the existing `ReplayResolver`; do not write a second resolver that does the
same job one layer over.

## Correction 3 — a resolver can no longer certify an answer as human

**Affects:** Task 4's `.override(key, value, by)`, and any future model resolver. **This is a
semantic change, not a signature change, which is why it is easy to miss.**

Audit A56: `source: HUMAN` on a `Resolution` clears the tier-4 review, so it is not a claim a
resolver may make about its own output — invariant 6 is what that would defeat. Since Plan 1.12,
`resolve()` honours `HUMAN` **only when a record the caller supplied backs it**:

```python
resolve(goal, registry, rules, measurements, *, vocabulary, resolver=…, prior=…)
```

`prior` is a `Sequence[DecisionRecord]`; a claimed `HUMAN` whose key has no matching
`human_override` in `prior` is **demoted to `RESOLVER` and keeps its review flag**.

**What to do:** `DecisionStore.override()` writes a human override, and that override will not
clear anything unless the record reaches `resolve(prior=…)`. `mendel_compiler/cli.py` threads
`prior=previous.replayable_decisions()` on the upgrade path; Task 7 must thread the store's
records the same way when it wires AI into the CLI. **A silently-ignored override is the failure
mode here**, and it fails safe (over-flagging) rather than dangerously — but it fails.

## Correction 4 — the egress boundary is wider than Task 1A assumes

**Affects:** Task 1A, and every task that opens a door.

Plan 2 was written when invariant 14 said *two* free-text fields. The literal set in
`tests/test_egress.py` now holds **seven**, and the guard is the honest count — `CLAUDE.md`'s
sentence has drifted three times (A33), which is why no number should be repeated in prose.

Door 4 also changed payload: `DOORS["publication"]` carries a **`Pipeline`**, not a
`PublishBundle`. The artifact on disk *is* the payload.

**What to do:** Task 1A's `EgressRecord.of(door, payload, …)` must be written against `DOORS` as
it is, and its test must read the door table rather than restating it. Plan 1.12 also widened the
guard itself (A57): every rule now asks `_serialised_hints`, which covers `@computed_field`, and
payloads may not define a `@model_serializer`. **A new payload with a computed field will be
rejected by the guard** — that is intended, and Task 1A should not work around it.

## Correction 5 — `ProfilePolicy` still does not exist, and issue #2 is still open

**Affects:** Task 1A.

`ProfilePolicy` is correctly listed as something Plan 2 *creates*; `ARCHITECTURE.md` names it as a
future type and the design audit brief confirms it has no implementation to audit. No correction to
the design — but note that [issue #2](https://github.com/comeni-project/Comeni-Labs/issues/2)
("`sealed` must block tier-3 decisions on asserted measurements") is blocked on exactly this type,
so Task 1A should close it rather than leave it dangling.

## Correction 6 — Task 11 must design `Param`'s domain, and `[None]` is why

**Affects:** Task 11, and Task 5 more than it looks.

A tier-4 parameter's candidate list is literally `[None]` (`resolve.py`, the `ParamAsked`
construction), because a `Param` has no declared legal values. Task 11 is where that is fixed, and
Plan 1.5 deliberately left `Param` untouched so it could be designed against a corpus.

**The ordering consequence Plan 2 does not state:** Task 5 wires a model to a port whose questions
carry no domain. Asking a model an open question with no legal-value set is the chat-window
failure mode wearing a tier label, and `resolve.py`'s own comment says this site "becomes
symmetric with the other two on the day" a domain exists. **Consider Task 11 before Task 5**, or
accept that the first model resolver answers domainless questions.

---

## Two things to carry into whatever plan executes this

- **[#26 (A62)](https://github.com/comeni-project/Comeni-Labs/issues/26)** — `model_construct` and
  assignment aliases walk past `tests/test_construction.py`. Plan 2 constructs payloads in new
  packages, which is exactly where that gap gets exercised.
- **[#32 (A68)](https://github.com/comeni-project/Comeni-Labs/issues/32)** — the totality guard
  compares 60% of its field names against themselves. Any new payload type inherits that blind
  spot.

## What is still true and should not be re-litigated

Task 11's argument that **runtime model resolution buys almost nothing** — invariant 6 flags tier 4
even at high confidence, so a model guessing at build time fills the review queue with plausible
text rather than shortening it, while an approved forge draft becomes tier 2 with a source and
never needs reviewing again. *"Offline authoring reduces the queue; runtime guessing decorates
it."* That is the strongest sentence in Plan 2 and it should shape the execution order: the forge
tasks (8–11) deliver more than the runtime tasks (3, 5, 6, 6B), with the single exception of
**Task 3**, which is the one unmet clause of the v1 success criterion.
