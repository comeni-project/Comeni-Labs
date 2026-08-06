# Root E — a declared identifier names something that exists

**Spec, 2026-08-07.** Closes A29, A18, and A16 (open from round one). Root E in
[`../audits/2026-08-07-root-causes.md`](../audits/2026-08-07-root-causes.md).

Verified against the code at `7f918b1`.

---

## The problem

`Annotated[str, "type-id"]` says *somebody named this*. It does not say *this is a declared
type*. Three consequences, all verified:

**A29 — nothing validates a goal's type ids.** `resolve.py` mentions `vocab` **zero** times.
`router._have_satisfies` only *compares*, so a `have` entry that satisfies nothing is never
looked up and never rejected. A patient name and a file path reached a `PublishBundle` as a
`type_id`, and a sentence of clinical notes reached it as a `required_states` key.

**A16 — `DecisionRecord.chosen` carries three kinds of value under one type**, and the
discriminator is a string prefix that is *inconsistent*:

```python
subject=f"producer:{type_id}"    # chosen is a ContractId
subject=f"source:{port.name}"    # chosen is "{node}.{port}"
subject=param_name               # chosen is a ParamValue — and no prefix at all
```

Two of three kinds are prefixed and one is not, so "what kind of decision is this?" is answered
by pattern-matching a string that was never designed to be parsed. This is why A3's blocklist
could not be applied to `chosen`: `dual.bam` (an edge reference) is character-for-character a
filename.

**A18 — the construction guard matches a spelling, not a type.** `test_construction.py` is
`if name == "DataProfile"`, with no alias resolution and one known construction form. It is the
guard for invariant 15, and `from … import DataProfile as _DP; _DP.model_construct(...)` walks
past it.

**The common root:** a marker asserts a domain it never defines, so every check downstream has to
re-derive the domain — by grepping a spelling, by parsing a prefix, or by not checking at all.

---

## The design

### 1. A decision declares its kind

```python
class DecisionKind(StrEnum):
    PARAM = "param"
    PRODUCER = "producer"
    SOURCE = "source"
```

`DecisionRecord` becomes a discriminated union over that kind, sharing a base:

```python
class _Decided(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: DecisionKey
    subject: Subject
    reason: Line          # root C
    confidence: float = 0.0
    resolved_by: ResolverId
    tier: Tier = Tier.AMBIGUOUS

class ParamDecision(_Decided):
    kind: Literal[DecisionKind.PARAM]
    candidates: list[ParamValue] = []
    chosen: ParamValue
    human_override: ParamValue = None

class ProducerDecision(_Decided):
    kind: Literal[DecisionKind.PRODUCER]
    candidates: list[ContractId] = []
    chosen: ContractId
    human_override: ContractId | None = None

class SourceDecision(_Decided):
    kind: Literal[DecisionKind.SOURCE]
    candidates: list[EdgeRef] = []
    chosen: EdgeRef
    human_override: EdgeRef | None = None

DecisionRecord = Annotated[
    ParamDecision | ProducerDecision | SourceDecision, Field(discriminator="kind")
]
```

`EdgeRef` is `<node>.<port>` where both halves are `NfIdentifier` (root C) — so it is a declared
shape rather than an unlucky filename, and the ambiguity that forced A3's scoping disappears.

**`HumanParamValue`'s blocklist can then be deleted for two of the three kinds**, because a
producer override must be a contract id and a source override must be an edge reference. It
survives only on `ParamDecision.human_override`, which is the one case with no domain yet — and
that is Plan 2 Task 11's job, exactly as `_reject_path_shaped`'s docstring says.

### 2. `resolve()` validates every type id against the vocabulary

`resolve()` gains a required `vocabulary` parameter — the same shape A2's fix used for
`measurements`, and required for the same reason: *an optional guard is the guard the next verb
forgets.* It validates every `type_id` in `goal.have`, `goal.want` and
`goal.constraints.required_states`.

An undeclared type in a goal is already a user error worth a clear message. **Closing A29 is a
side effect of doing the obvious thing**, which is the right shape — a closed vocabulary rather
than another blocklist.

In `mendel upgrade` this is the check that matters, because the goal comes from a stranger's
bundle rather than from a file the operator wrote.

### 3. The construction guard stops matching spellings

Two changes, and the second matters more than the first:

- **Fix the hole**: reuse `test_purity.py`'s `_imported_names` to resolve aliases, and flag
  `model_construct` / `model_validate` / `model_validate_json` on a binding that resolves to
  `DataProfile`.
- **Record that it is secondary.** A2's fix already re-checks every measurement inside
  `resolve()`, so any `DataProfile` that reaches resolution is validated *regardless of how it
  was constructed*. The AST scan is belt and braces over a runtime check that already holds, and
  its docstring should say so — otherwise the next reader treats a spelling-matcher as the
  enforcement, which is how A18 was written.

---

## How this composes

- **Root A** governs what shape may cross a door. The three decision types are all shaped from
  marked strings, scalars and enums, so they satisfy its allowlist — and being three precise
  types rather than one loose one makes the walk more informative, not less.
- **Root C** governs what shape may reach a generated file. `EdgeRef` is built from
  `NfIdentifier`, so C's validation is what makes E's discrimination sound; without it,
  `EdgeRef` would be another label.
- **Root H** applies the same `DecisionKind` to `Ambiguity` and `Resolution`. E must land first,
  or H invents a second kind vocabulary.

---

## Verification

Root I applies.

| probe | expected |
|---|---|
| a goal with `type_id: "PT-4471023 Jane Doe, /data/…"` | **refused by `resolve()`**, naming the undeclared type |
| the same via `required_states` key | refused |
| a bundle carrying it, through `mendel upgrade` | refused — the stranger's-file path |
| the shipped `examples/rnaseq-goal.yml` | **still resolves**; byte-identical emission |
| `ProducerDecision(chosen="not-a-contract")` | refused |
| `SourceDecision(chosen="run.cram")` | refused — not `<identifier>.<identifier>` |
| `SourceDecision(chosen="dual.bam")` | **accepted** — the A3 collision, now legal by type rather than by exemption |
| `DataProfile` via an aliased import and `model_construct` | flagged by the construction guard |
| a `DataProfile` with an undeclared measurement reaching `resolve()` | still refused (A2 regression) |
| a published bundle read back | round-trips through the discriminated union |

The `dual.bam` row is the point of the whole spec: it is *accepted because it is declared*, not
tolerated because a blocklist was narrowed around it.

---

## Blast radius

The largest after root B.

- `comeni_core/decision.py` — three record types, the discriminator, `EdgeRef`.
- `comeni_core/marks.py` — `EdgeRef`; `HumanParamValue` narrows to one field.
- `comeni_core/ir.py` — `PipelineIR.decisions` is the union.
- `mendel_resolver/resolve.py`, `router.py` — construct the right kind; `resolve()` takes a
  vocabulary; twelve-plus call sites, as A2's correction found.
- `mendel_resolver/replay.py` — matches on `key`, which is unchanged, but must round-trip the
  union.
- `tests/test_construction.py`, `tests/test_egress.py`.
- **Bundle shape changes**: every `DecisionRecord` gains a `kind`. Nothing is published, so this
  is free now and expensive later.

---

## What this spec does not cover

- **A parameter's value domain.** `ParamValue` remains open, and `_reject_path_shaped` survives
  on `ParamDecision.human_override` alone. Plan 2 Task 11 is where a `Param` declares its legal
  values; this spec deliberately does not invent that.
- **Root A's leaf allowlist** — separate, and E's new types are written to satisfy it.
- **Whether `Subject` should also be discriminated.** It becomes redundant with `kind` for two of
  three cases; leaving it is the smaller change and it still carries the *which* (`producer:` of
  what).
