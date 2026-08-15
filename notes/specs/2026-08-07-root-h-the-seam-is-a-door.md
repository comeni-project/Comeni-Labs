# Root H — the seam a model sits behind is held to the door's standard

**Spec, 2026-08-07.** Closes A32, A33. Root H in
[`../audits/2026-08-07-root-causes.md`](../audits/2026-08-07-root-causes.md).

Verified against the code at `7f918b1`. **This is the cheapest of the nine roots and the only one
that gets more expensive on a schedule** — the moment Plan 2 writes an adapter, this is a
retype with a consumer.

---

## The problem

`AmbiguityResolver.resolve(ambiguity) -> Resolution` is the call a model adapter implements. It
is where Plan 2 puts a model. And:

```python
class Ambiguity(BaseModel):          # ← no model_config at all: no extra="forbid"
    node_id: NodeId
    subject: Subject
    candidates: list[Any]            # ← Any
    context: dict[str, Any]          # ← a mapping of Any


class Resolution(BaseModel):         # ← no model_config either
    chosen: ParamValue
    reason: Text
    confidence: float = 0.0
    resolved_by: str = "flag-only"   # ← bare str
```

`list[Any]`, `dict[str, Any]` and a bare `str` are three of the shapes root A's guard exists to
forbid. The guard never sees them, because `Ambiguity` is not reachable from an `EgressPayload`.

**So the typed door and the object actually handed across it are different objects.** Invariant
14 declares `AmbiguityRequest` as door 2's payload — closed vocabulary, `extra="forbid"`,
`frozen=True`. Nothing constructs an `AmbiguityRequest` from an `Ambiguity` today, and
`AmbiguityRequest` **has no field for what `context` carries**: `_source_for` puts `type_id` and
`required` in it, `_choose` puts `states`, `_resolve_param` puts `tier_hint`. Only the last has
a home.

A mapping that is lossy in the direction of *"the adapter improvises"* is the one thing a
declared boundary exists to prevent.

---

## The design

### 1. `Ambiguity` is discriminated the same way a decision is

Root E introduces `DecisionKind` (`PARAM`, `PRODUCER`, `SOURCE`). The seam uses **the same
vocabulary** — inventing a second one beside it is how this codebase got four loaders.

```python
class _Asked(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: NodeId
    subject: Subject

class ParamAsked(_Asked):
    kind: Literal[DecisionKind.PARAM]
    candidates: list[ParamValue] = []
    tier_hint: int | None = None

class ProducerAsked(_Asked):
    kind: Literal[DecisionKind.PRODUCER]
    candidates: list[ContractId] = []
    type_id: TypeId
    states: list[StateName] = []

class SourceAsked(_Asked):
    kind: Literal[DecisionKind.SOURCE]
    candidates: list[EdgeRef] = []
    type_id: TypeId
    required: list[StateName] = []
```

`context: dict[str, Any]` disappears — **its three uses become three declared fields on the three
kinds**, which is what it was standing in for.

`Resolution` gains `extra="forbid"` and `resolved_by: ResolverId`.

### 2. The seam types join the guard's roots

`tests/test_egress.py` adds `Ambiguity` and `Resolution` to `_payload_types()`'s roots. They are
not doors — nothing sends them — but **they are handed to an adapter that will send something
derived from them**, and holding them to the same standard is the only way the derivation cannot
lose or invent a field.

This is the smallest change with the largest effect on Plan 2: the adapter's job becomes a
total mapping between two closed types, rather than a judgement call.

### 3. `AmbiguityRequest` gains the fields it was missing

Door 2's payload is currently `node_id`, `subject`, `candidates`, `states`, `tier_hint`. With
the above it becomes a projection of the three `*Asked` types with nothing dropped. If a field
cannot cross the door, that is a decision to argue in review — but it must be a decision, not an
omission nobody noticed.

### 4. A33's four smaller items

- **`router._choose`'s tier-4 reason can be false.** It emits `"nothing distinguishes …; chosen
  by id order"` even when A8's fix means the resolver's answer selected. Not emitted into
  `main.nf` today, but it is in the IR and the bundle — and A8 was precisely about records that
  contradict the pipeline. Fix: the reason states what happened.
- **`_resolve_param` trusts a non-candidate answer.** `router._choose` and `_source_for` both
  fall back when `resolution.chosen` is not among the candidates, with comments explaining why.
  `_resolve_param` accepts whatever comes back. Defensible today — `candidates=[None]` means a
  tier-4 parameter has no domain, which is A16 — but it is **the one site where a model's answer
  is taken on trust, and Plan 2 is what puts a model there.** At minimum the asymmetry is
  documented at the site; better, `ParamAsked` gaining a real domain from Plan 2 Task 11 removes
  the exception.
- **A symlink in a layer produces a raw traceback.** `layers.load` raises a bare `ValueError`
  that `cli.main`'s except-list does not catch. Add it, so the refusal reads as a `mendel:` line.
  A35's `UnknownStateError` has the same problem and is fixed by the same list.
- **CLAUDE.md invariant 14 is stale** — it says "exactly two fields may hold free text" while
  `FREE_TEXT_FIELDS` holds four. The guard is the honest one; the prose is corrected.

---

## Verification

Root I applies.

| probe | expected |
|---|---|
| `Ambiguity(..., extra_field=1)` | refused |
| `ParamAsked(candidates=[{'patient_id': …}])` | refused — no `Any` left to accept it |
| a `context=` keyword anywhere | fails; the field is gone |
| `Resolution(resolved_by=…)` unmarked string | refused |
| `Ambiguity`/`Resolution` under root A's leaf allowlist | pass |
| every `*Asked` field maps to an `AmbiguityRequest` field | asserted by a test, so a future field cannot silently fail to cross |
| `FlagOnlyResolver` and `ReplayResolver` | still satisfy the protocol; `make verify` green |

---

## Blast radius

- `comeni_core/decision.py` — the three `*Asked` types, `Resolution`.
- `comeni_core/egress.py` — `AmbiguityRequest` becomes a faithful projection.
- `mendel_resolver/ports.py` — the protocol signature.
- `mendel_resolver/router.py`, `resolve.py` — construct the right kind.
- `tests/test_egress.py` — two new roots.

**Depends on root E**, which defines `DecisionKind` and `EdgeRef`. Doing H first means inventing
that vocabulary twice.

---

## What this spec does not cover

- **The model adapter itself**, LiteLLM, or any transport. That is Plan 2, and this spec exists
  so Plan 2 lands on a typed seam instead of retyping one that has consumers.
- **A parameter's value domain** — Plan 2 Task 11, and the reason `_resolve_param`'s exception
  survives here rather than being closed.
