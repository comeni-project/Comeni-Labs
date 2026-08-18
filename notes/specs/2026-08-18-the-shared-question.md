# Plan 2.5 — one question, two behaviours

**Status:** design spec, written 2026-08-18 with the operator. Precedes the Plan 3 spec
deliberately: Plan 3 consumes the types this changes, so specifying Plan 3 in detail first would
be writing against types that are about to move — which is what got Plan 2 deleted.

**Precedence:** where this spec and the code disagree, the code is right and this file has
drifted.

**A name collision, recorded so a reader is not misled.** `CLAUDE.md` notes that *Plan 1.7 was
called "Plan 2.5" until 2026-08-05*, and journal entries up to that date still use the old name.
This document is a **different** Plan 2.5, named by the operator on 2026-08-18, and it runs
between forge Phase 2 and Plan 3. Grepping the repository for "Plan 2.5" returns both; the date
distinguishes them.

---

## 1. What this is, in one paragraph

The forge and the build path each ask a reviewer questions, and each grew its own vocabulary for
doing so. `Hole` and `Ambiguity` describe the same thing in different words; `FilledValue` and
`Resolution` record the same answer in different words; `Filler` and `ValueSource` are
overlapping enumerations of who settled a value. This spec unifies the **question**, the
**answer** and the **provenance vocabulary** into shared base classes in `comeni-core`, and
deliberately does **not** unify the one thing that genuinely differs: whether an unanswered
question blocks.

## 2. The duplication, in the real field names

Not asserted — read off the types on 2026-08-18.

| what it means | forge (`mendel_forge/scaffold.py`) | build (`comeni_core/plan/decision.py`) |
|---|---|---|
| what is being decided | `Hole.field` | `Ambiguity.subject` |
| what it is about | `Hole.what` | — |
| why you are being asked | `Hole.why_open` | — (tier 4 implies "no rule matched") |
| what you may answer | `Hole.candidates: list[Candidate]` | `*Asked.candidates` |
| whether that list binds | `Hole.closed: bool` | — (always binds) |
| what the answer rests on | `Hole.evidence: list[Excerpt]` | — |
| the answer | `FilledValue.value` | `Resolution.chosen` |
| who settled it | `FilledValue.filler` + `.by` | `Resolution.source` + `.resolved_by` |
| why | `FilledValue.why` | `Resolution.reason` |

And the two enumerations:

- `Filler` — `DERIVED`, `HAND`, `MODEL`
- `ValueSource` — `RESOLVER`, `GOAL`, `HUMAN`, `MODEL`, `MEASURED`

`HAND` and `HUMAN` are the same fact under two names. `MODEL` appears in both. `DERIVED`
straddles `RESOLVER` and `MEASURED`. **This is the layer where drift will actually bite**: the
day somebody adds a provenance field to one and not the other, two artifacts that should record
the same thing stop agreeing, and nothing fails.

**Three of the build path's cells are empty**, and that is the second finding. A tier-4 question
today hands a reviewer a list of candidates and nothing to judge them on — no statement of what
is being decided, no reason it is open, no quoted evidence. The forge has all three. Unifying is
therefore not only deduplication; it **upgrades the weaker implementation to the better one**,
which is the strongest argument for doing it at all.

## 3. What is not unified, and why

**A hole blocks; an ambiguity ships flagged.** `Scaffold.is_complete()` gates `contract_from`,
so the forge structurally cannot emit a contract with an open hole — `scaffold.py`'s module
docstring says that property is what the whole design rests on. A tier-4 ambiguity does the
opposite: the pipeline is built, runnable and emitted, with the question flagged red for review.

The cleanest statement of that difference is at the two ports, and it is already in the code:

```python
class HoleFiller(Protocol):
    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None: ...

class AmbiguityResolver(Protocol):
    def resolve(self, ambiguity: Ambiguity) -> Resolution: ...
```

**One may return `None`. The other may not.** `ports.py` says why: *"a filler that always
answers is a filler that invents, and a hole a model declines is a hole a human still sees."*
And `FlagOnlyResolver` must always answer, because that is what keeps a pipeline runnable with
no model available and makes the flagged count an honest measure of rule coverage.

So the null implementations are **opposites, and both are correct**: `NoFiller` declines
everything; `FlagOnlyResolver` picks the first candidate and flags it.

### 3.1 Why the difference must not become a field or a method

The obvious shortcut is one type with `blocks: bool`, or a base class with a `blocks()` method
the subclasses override. **Both are refused**, and for the same reason.

The guarantee today is not that a hole *knows* it blocks. It is that `contract_from` refuses
while any hole is open — the guarantee lives in the **container**, and the question object is
inert data. Moving it onto the object converts a structural property into a runtime check on a
value, and this repository has one very expensive lesson about exactly that distinction:
invariant 1 was sold as structural — *"the pure packages cannot import an HTTP client"* — until
audit A1 opened a TCP socket out of allowlisted imports. `CLAUDE.md` now says **cost-raising,
not a proof**, and the correction was to weaken the claim rather than the guard.

A `blocks()` method is tidier than a boolean and is the same category of mistake.

**So the containers keep the behaviour, unchanged:**

- `Scaffold` holds `Hole`s and cannot assemble a contract while one is open.
- The resolver holds `Ambiguity`s, flags them tier 4, and emits anyway.

The two subclasses then differ by **nothing but which container holds them and which port
answers them**. The base is shared vocabulary with no behaviour.

## 4. The shape

```
Question                    base — closed vocabulary, no behaviour
  ├── Hole                  forge. Held by Scaffold, answered by HoleFiller
  └── Ambiguity             build. Held by the resolver, answered by AmbiguityResolver
        ├── ParamAsked
        ├── ProducerAsked
        └── SourceAsked

Answer                      base — the answer, and the provenance of it
  ├── FilledValue           forge
  └── Resolution            build
```

`Ambiguity` is already a base class with three subclasses, so the build side becomes three
levels. That is not new depth being invented; it is one level added above a hierarchy that
exists.

### 4.1 What goes on `Question`

The five cells the two sides share or should share: what is being decided, what it is about, why
it is open, what may be answered, and what the answer rests on. `Candidate` and `Excerpt` move
to `comeni-core` with it — `Excerpt` is currently `mendel_forge.observe.Excerpt`, and a
build-path question that quotes its evidence needs the same type.

**`Hole.after` and `Hole.channels` stay on `Hole`.** `after` orders holes whose candidates depend
on another hole's answer; the resolver ladder handles that ordering itself, so the field has no
build-side meaning. `channels` is nf-core module vocabulary and belongs nowhere near the build
path.

**`Hole.closed` is a base field**, because the build side has a latent version of the same
question: `ProducerAsked`'s candidates bind, but the vocabulary-proposal problem in §7.2 is
exactly "the right answer is not among them".

### 4.2 What goes on `Answer`

Four fields: `value` (the answer), `by` (who or what settled it, as an id), `how` (the
provenance enum of §4.3), and `why` (their reason).

**`Resolution.chosen` becomes `Answer.value`, narrowed.** Pydantic permits a subclass to
redeclare an inherited field with a narrower type, so `Resolution` keeps its `ParamValue`
typing while `Hole`'s side stays `Any`. That is the one place the base is intentionally looser
than a subclass, and it is worth an explicit test: a `Resolution` carrying a non-`ParamValue`
must still fail validation after the re-base, or the narrowing silently did not happen.

`Resolution.confidence` stays on `Resolution` — a forge fill has no confidence and inventing one
would be a field nothing writes. `FilledValue` keeps nothing extra, which is itself a signal
that the base is drawn at about the right place.

### 4.3 One provenance vocabulary

`Filler` and `ValueSource` collapse into one enumeration:
`RESOLVER / GOAL / HUMAN / MODEL / MEASURED / DERIVED`.

**`HAND` folds into `HUMAN`** — the same fact under two names, and the clearest win in the whole
refactor.

**`DERIVED`, `RESOLVER` and `MEASURED` all stay, and are not merged.** They look mergeable and
are not: `DERIVED` is a fact read off a source file, `MEASURED` is a tool that looked at data and
named itself, and `RESOLVER` is the deterministic ladder settling a question. A reviewer asking
*"why does this value say what it says"* gets three different answers, and collapsing them would
lose exactly the distinction `pipeline.yml` exists to carry.

**Corrected 2026-08-18, while writing the plan.** This section first claimed the collapse
changes bytes in a published artifact and therefore forces a `SCHEMA_VERSION` break. **That was
wrong**, and reading the code is what showed it — the same rule `notes/README.md` states about
writing plans against code rather than memory.

`assemble._drafted_by` returns the **string literal** `"hand"`, not `Filler.HAND.value`:

```python
fillers = {v.filler: v.by for v in scaffold.filled.values()}
return fillers.get(Filler.MODEL, "hand")
```

So `Provenance.drafted_by` never carries the enum, and **no published registry artifact changes
at all**. The migration is therefore:

- **Keep `ValueSource` as the surviving name**, and keep every existing spelling. `RESOLVER`,
  `GOAL`, `HUMAN`, `MODEL` and `MEASURED` are untouched, so **`pipeline.yml` does not change and
  there is no `SCHEMA_VERSION` bump**. `DERIVED` is added, and nothing on the build path writes
  it yet.
- **Delete `Filler`**, mapping `DERIVED → DERIVED`, `HAND → HUMAN`, `MODEL → MODEL`.
- The only files whose bytes move are **forge workspace drafts** and the golden scaffold
  (`filler: "hand"` becomes `how: "human"`). Those are working files, not published artifacts.

That is a far smaller blast radius than this section originally assumed, and it removes the
alias-or-bump decision entirely.

## 5. The egress rule, which is not optional

`Ambiguity` projects to `AmbiguityRequest`, a **door-2 payload**. `Hole` crosses no door — the
forge is offline authoring, settled 2026-08-17. A shared base therefore puts fields into a door
payload's ancestry, and two rules follow.

**Rule 1 — the base carries closed vocabulary only.** No `Mark.FREE_TEXT` field on `Question` or
`Answer`. `CLAUDE.md` tracks the free-text field count literally, field by field, because that
number has drifted every time it was summarised; a forge-motivated free-text field on a shared
base would widen door 2 without anybody editing the test that says *these are all the ways data
leaves*. Free text stays on the subclasses.

**Rule 2 — the totality assertion does the work, and we let it.** `tests/test_egress.py` asserts
`AmbiguityRequest` is the **union of what the three `*Asked` types carry** — a field on an
ambiguity with nowhere to land at the door is a field a model would silently not be told, which
is the quiet half of A32.

So adding `evidence` and `why_open` to `Question` **will fail that test until somebody decides
whether they cross to a model.** That is the correct outcome and the plan must not route around
it: the decision is real (does a tier-4 model call get the quoted source lines?), and the guard
forces it into the open rather than letting it be skipped. Answering it is a task.

## 6. Why the seam is here and not higher or lower

**Not higher** — an API-layer projection alone. That was the first proposal and it is not wrong,
but it leaves the two vocabularies in place and only hides them from one consumer. The
duplication in §2 stays, and `Filler`/`ValueSource` stay two enums.

**Not lower** — merging `Hole` and `Ambiguity` into one type. §3 is why.

**The precedent is `stack()`.** Invariant 11: every declared kind stacks through *one*
mechanism, `comeni_core.layered.stack()`, parameterised by a `Kind` that declares only how its
files parse, key and merge — and *"hand-written loaders disagreeing on six axes is what audit
root B was."* `stack()` unified the mechanism and parameterised the differences. It did **not**
merge the kinds into one kind. This spec applies the same shape one subsystem over.

## 7. What this makes visible, and what it does not fix

### 7.1 The build path has no evidence

Closing this is the point of §4.1, and it is the user-visible payoff: a tier-4 card that quotes
the lines the decision rests on instead of listing bare candidates.

### 7.2 The build path has no `Proposal`

The forge can say *"nothing declared fits, and here is what would"*
(`notes/specs/2026-08-17-vocabulary-proposals.md`). The build path forces a pick from candidates
— `choose_one` cannot decline, so *"no declared type fits this port"* becomes a wrong answer
instead of a signal. The same defect, one layer up: *"no contract produces this type"* has
nowhere to be said.

**This spec does not fix it.** It requires only that `Question` leave the slot open, so closing
it later is not a schema break. Naming it here so it is a known gap rather than a discovery.

### 7.3 What a fresh reader will get wrong

**"This is a refactor, so it changes no behaviour."** It changes two. The build path gains
evidence, which is new data in `pipeline.yml`. And the provenance vocabulary collapses, which
changes a value that artifacts already on disk carry. Neither is cosmetic and both need the
golden files read rather than regenerated.

**"The base class is where the logic goes."** The base is inert. Every behavioural difference
lives in the container or the port. A method added to `Question` is a design smell by
construction here.

## 8. The API projection, in one paragraph

Plan 3 exposes one schema — `OpenQuestion` — that both subclasses project into, published in
`openapi.json`, consumed by the generated TypeScript client and by an agent driving Mendel over
HTTP. **Two consumers, one schema**: the React review queue renders it as a card; the agent GETs
the same route and POSTs answers back. After this spec lands, that projection is nearly free,
because the two sides already share a base. It stays in `mendel-api` rather than `comeni-core`
regardless — the door rules in §5 are about `comeni-core`, and an API DTO is not a door payload.

Detail belongs in the Plan 3 spec, written after this lands.

## 9. Testing and guards

- **Golden files are read, not regenerated.** The forge's scaffold golden and the emitted
  `main.nf`/`nextflow.config` digests (`76355bbf9f10d6e6`, `72ddb081638edf76`) are the check that
  a refactor refactored. A digest that moves must be explained in the commit message or reverted.
- **`make verify`, not `make check`.** This touches `comeni-core/artifact/pipeline.py` and the
  resolver, both on `CLAUDE.md`'s named list.
- **The egress guard is expected to fail once**, at §5 Rule 2, and its passing again is the
  record that the question was answered.
- **A guard-ledger row.** Any new guard here is watched failing and recorded in
  `notes/audits/guard-ledger.md`, per A14.
- **Round-trip a pre-refactor `pipeline.yml`.** §4.3 concludes the artifact does not change;
  this is the test that proves it rather than assuming it.

## 9.1 The import direction, which has one trap

`review/` must not import `plan/`. `Ambiguity` lives in `plan/decision.py` and will import
`Question` from `review/`, so a `review → plan` edge in the other direction is a **circular
import**. `ValueSource` therefore *moves* to `review/answer.py`, with `plan/tiers.py` re-exporting
it so every existing `comeni_core.plan.tiers.ValueSource` import and the package's public surface
keep working.

The resulting order is `spell/ ← review/ ← plan/`, with `mendel-forge` importing `review/`
directly.

## 10. What this deliberately does not do

- **No rule drafter.** Deferred behind Plan 3 by the operator on 2026-08-18. It will be the
  third instance of this pattern, and the shared base is what it inherits rather than reinvents.
- **No tier-4 model resolver.** Still Plan 3, still gated on issue #69.
- **No factories.** The discriminated-union pattern already in use — `AmbiguityKinds` with
  `Literal[DecisionKind.PARAM]` discriminators — is what `tests/test_egress.py` uses to assert
  the door projection is *total*. A factory would lose that check. Superclasses yes; factories
  only where the union pattern does not fit, and it does fit here.
- **No protection profiles.** Issue #71, unrelated and larger.

## 11. Task shape

Rough, for the plan to argue with rather than inherit.

1. `Question` and `Answer` in `comeni-core`, with `Candidate` and `Excerpt` moved in beside them.
2. `Hole` and `FilledValue` re-based; forge tests and golden scaffold read.
3. `Ambiguity` and `Resolution` re-based; `AmbiguityKinds` and the door totality test.
4. The provenance enum collapse, and the §4.3 alias-or-bump decision.
5. `evidence` and `why_open` on the build path — including the door-2 decision §5 forces.
6. `make verify`, golden digests read, guard-ledger row.
