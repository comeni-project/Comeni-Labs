# 2026-08-18 — one question, two behaviours, and a pivot

Two things happened today: **the roadmap changed**, and **Plan 2.5 was specified and executed**.
The roadmap change is the more consequential of the two and it is what the rest follows from.

## The pivot, in one paragraph

The operator needs an MVP in about a month. The forge is frozen where it is — 88% overall and
**97% on the fields that change which pipeline gets built**, with the remaining gap documented as
the registry disagreeing with itself rather than a prompt problem. **The rule drafter moves
behind Plan 3**, reversing yesterday's decision to put it ahead. **Plan 3 is the GUI and the API,
and the week's work.** The plain-language prompt follows it, and an agent will drive Mendel over
the same API the GUI uses.

**Why the drafter moved.** Yesterday's argument was that each step shrinks the next one's job:
the forge fills the registry, the drafter fills tier 3, tier 4 is the fallback from tier 3. That
argument optimises for **queue size**. What the project is short of is **feedback** — nothing in
the repository renders a tier-4 queue, so nobody has ever looked at one. The drafter is also the
item with the least design clarity on the board: its spec names four hard prerequisites, and
issue #38's closing note says the drafting question and the measuring question are the same one.
Highest design risk, least clarity, no feedback loop — the worst thing to schedule first under a
deadline.

## Where things stand

**Plan 2.5 is done**, eight tasks, in `.worktrees/plan-2-5-shared-question`. `make verify` exits
0: 1183 fast tests, 5 slow, 75 guards, `make residue` unchanged at 245.

**`pipeline.yml` is byte-identical to `main`'s, and `main.nf` and `nextflow.config` are too.**
That is proven rather than asserted — the same goal was built on both branches and diffed, which
is the method that caught the machine-dependent layer digest on 2026-08-16 while `make verify`
was green throughout. `76355bbf9f10d6e6` is unmoved.

## What Plan 2.5 did

The forge and the build path each had their own vocabulary for *a question a reviewer must
answer*. Nine cells said the same thing twice — and three of them were **empty on the build
path**, which is the part that made this an upgrade rather than only a deduplication.

```
Question                    subject, what, why_open, candidates, closed, evidence
  ├── Hole                  forge   (+ after, channels)
  └── Ambiguity             build   (+ node_id, and the three *Asked kinds)

Answer                      value, by, how, why
  ├── FilledValue           forge   (adds nothing — the signal the base is drawn about right)
  └── Resolution            build   (+ confidence)
```

`Filler` is gone; `HAND` was `HUMAN` under a second name. `DERIVED`, `RESOLVER` and `MEASURED`
stay distinct, because reading a declaration, choosing between options and measuring data are
three different answers to *why does this value say what it says*.

**What is deliberately not unified is the blocking**, and that is the load-bearing decision. A
hole blocks; an ambiguity ships flagged. That difference is not a field and not an overridden
method — it lives in the container and in the port, and the cleanest statement of it is that
`HoleFiller.fill()` may return `None` and `AmbiguityResolver.resolve()` may not.

## What a fresh reader gets wrong

**"It is a refactor, so nothing changed."** Two things changed. A tier-4 producer question now
says what it is about and cites every candidate with the registry's own ranking reason — the
build path had no evidence at all. And door 2's payload is wider.

**"The base class is where the shared logic goes."** The base is inert. `legal()` is the only
method on it and a test asserts nothing else appears. A `blocks()` method would be tidier than a
boolean and exactly as wrong.

**"The egress guard broke."** It worked. See below.

## The guard went red on purpose, and that is the report

`AmbiguityRequest` is asserted to be *the union of what the `*Asked` types carry*. Making
`Ambiguity` a `Question` gave it four fields with no slot at the door, so the guard failed **on
its own** — no revert needed — at the re-base commit, with the message the plan had predicted
before the code was written:

```
ParamAsked.what has nowhere to go in AmbiguityRequest, so a model behind
door 2 would never be told it
```

That commit was landed red, deliberately, because the question it forces is real: *does a tier-4
model call get the quoted source lines?* It was answered **yes**, on a measurement rather than a
preference — the forge's prompt search took a local model from 69% to 88%, and two of the three
fixes behind that were *the question never said what it was about* and *the evidence was not
readable*. A door handing a model bare candidates rebuilds the 69% configuration on the build
path, having already paid to learn it.

Free-text fields: **ten to fourteen**. `Excerpt` is the first entry on that list that is not an
*author* — its text is quoted from a source file rather than composed — and that weaker claim is
written down rather than assumed, because *"it is only quoted"* is how a boundary widens
unnoticed.

## What the allowlist extracted, unprompted

Making `Excerpt` reachable from a payload tripped **three further guards in one run**, none of
them in the plan, and each wanted a real change rather than an exemption: `locator` and `text`
were bare `str` (now `Text`), and `Excerpt` was unfrozen (now frozen, so what a reviewer read is
what is sent).

That is what an allowlist buys over a blocklist. A19, A20 and A30 were each a shape nobody had
thought to *forbid*; this is the same guard catching a shape nobody had thought to *permit*.

## The defect the plan did not anticipate

`Question.legal()` assumed candidates are `Candidate` models. The build-path subclasses re-narrow
`candidates` to `list[ContractId]` / `list[ParamValue]` / `list[EdgeRef]` — **bare strings** —
because door 2 types them as `CandidateRef`, and A129 records that payload accepting only one of
three `*Asked` types until their *values* were checked rather than their names.

So `Ambiguity` inherited a method that was broken for it, silently, from the moment of the
re-base. It was found by `test_evidence.py` being the first thing ever to call `legal()` on the
build path — before Plan 2.5 `Ambiguity` had no such method, so nothing else would have. Both
shapes are read now and the docstring says why they differ.

**The general lesson**: inheriting a method is not free the way inheriting a field is. A field
that a subclass re-narrows still validates; a method written against one subclass's shape breaks
against the other's and nothing type-checks it.

## Corrections to the plan — six

Recorded because `notes/README.md` says to expect them.

1. **The spec was wrong about the migration cost.** It claimed the `Filler` collapse changes
   bytes in a published artifact and forces a `SCHEMA_VERSION` break. `assemble._drafted_by`
   returns the **string literal** `"hand"`, not `Filler.HAND.value`, so `Provenance.drafted_by`
   never carried the enum and nothing published moves. Found by reading the function while
   writing the plan, which is the *write plans against code* rule earning itself again. The spec
   is corrected in place with the correction marked rather than silently edited.
2. **The golden regenerates with `FORGE_GOLDEN=update`**, not `--snapshot-update`. The plan
   flagged this line as a guess and it was wrong.
3. **`scaffold.py` needs an explicit `__all__`.** `Candidate` and `Excerpt` are re-exports, and
   `ruff --fix` deletes them as unused imports — sixteen test modules stopped collecting.
4. **A purity guard tripped on a docstring.** `test_no_pure_package_imports_an_impure_one` is a
   substring scan over file *text*, so naming the forge's package in prose inside a pure package
   fails it. The guard is blunt rather than wrong; rewording is cheaper than teaching it to read
   Python.
5. **`ProducerAsked` is built in `router.py`, not `resolve.py`.**
6. **`_choose` does not take a `Registry`**, so `_layer_name` — which would make a better
   evidence locator than a contract id — is not reachable. Threading a ninth parameter into a
   function whose own docstring calls its return *"one past what a tuple should carry"* is a
   refactor this plan did not authorise, so the locator names the contract and the gap is
   recorded in the code.

## Two stale lines corrected in `CLAUDE.md`, found while editing near them

The architecture block listed `frontend/` and `mendel-api/` as though they exist. `frontend/` has
**zero files** and `packages/` has five members, neither of them the API. Both are Plan 3's and
both now say so. Same drift A71 and A72 are about, in the block that is supposed to be the map.

## What is next

**Plan 3** — `notes/specs/2026-08-18-plan-3-thin.md`, deliberately thin, and the detailed plan is
written *after* this lands rather than before. Its three load-bearing decisions:

- **Task 1 is an extraction, not a scaffold.** The plan's premise that `mendel-api` is *"a thin
  FastAPI skin over the existing packages"* is false: the whole build orchestration lives inside
  `resolve_verbs.run(args, parser)`, which takes an argparse `Namespace`, prints to stderr and
  returns exit codes. It has to be lifted into a callable first, or the API and the CLI become
  two orchestrations that drift — and `test_counts.py` guards only one of them.
- **One schema, two consumers.** `OpenQuestion` in `mendel-api`, which both `Hole` and
  `Ambiguity` project into. React renders it; an agent GETs the same route. Plan 2.5 is what
  makes that projection nearly free.
- **Vertical slice, not tasks 1→9 in order.** The stack is the full one — Postgres, Alembic, ARQ,
  Redis, Compose — but narrow before wide, because the stated goal is to have the moving parts
  interacting early.

**Still open from Plan 2.5**, neither of them blocking: `ParamAsked` and `SourceAsked` carry no
evidence (honest — the field exists and nothing lies about being filled), and the build path
still has no `Proposal` equivalent, so *"no contract produces this type"* has nowhere to be said.
`Question` leaves the slot open so closing it later is not a schema break.
