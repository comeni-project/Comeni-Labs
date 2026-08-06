# Root A — the egress boundary declares what may cross

**Spec, 2026-08-07.** Closes A19, A20, A30, and the unnumbered marker-set hole found while
writing this. Root A in [`../audits/2026-08-07-root-causes.md`](../audits/2026-08-07-root-causes.md).

Every number and claim below was verified against the code at `dc76752`, not inferred.

---

## The problem

The egress boundary is three things: `EgressPayload` (a base class that sets
`extra="forbid", frozen=True` and nothing else), the `DOORS` dict, and `tests/test_egress.py`,
which **reconstructs the intent by reflection** and applies four *negative* rules.

All the safety lives in the test. The types declare nothing. And because the test is inferring
intent rather than reading a declaration, every rule it can express is a prohibition — you can
only forbid what you can name. Three consequences, all verified:

| | |
|---|---|
| a shape it does not recognise passes | `leak_any: object` on `Lockfile` → **8 passed**, and it serialises `{'patient_id': …, 'ssn': …}` (A19). Same for `Path` (A30). |
| a shape its walker cannot express is inert | `_mentions(typing.Any, typing.Any)` is `False`, and so are `dict[str, Any]` and `list[Any]`. The rule has never been able to fire (A20). |
| **the marker vocabulary is itself open** | `_has_bare_str` exempts anything with *any* metadata. `Annotated[str, "clinical-notes"]` and `Annotated[str, 42]` both pass as declared identifiers. |

The third is new, and it is why "just invert the blocklist" is not the fix. An allowlist whose
rule is *"a leaf may be `Annotated[str, <a declared marker>]`"* **rebuilds the same hole**, because
"declared" currently means "somebody wrote a string here". It is A3's sentence — *the guard
treats "has a label" as "has a domain"* — one level deeper than A3 stated it.

---

## What the graph actually contains

Measured, not assumed. A walk from the five payload roots:

- **22 reachable models** (`Goal`, `PipelineIR`, `Lockfile`, `IRNode`, `ResolvedValue`, …)
- **containers used: `list` and `frozenset`. Only those.** No `dict`, no `tuple`, anywhere.
- **terminal kinds: 8** — `int`, `float`, `bool`, `NoneType`, `str`, plus `enum` members and the
  models themselves. `Tier` is an **`IntEnum`**; `ValueSource`, `ErrorCategory` and `Gate` are
  `StrEnum`.
- **metadata found: 13 string markers, `FreeText`, `ParamLiteral`, and `AfterValidator`** — the
  last arriving through `HumanParamValue`.

Two of those facts change the design. `Tier` being an `IntEnum` means the rule must permit
`enum.Enum`, not `StrEnum`. `AfterValidator` appearing as legitimate metadata means the rule must
be *some* metadata element is a marker, never *all* — requiring all would break A3's fix.

---

## The design

### Move 1 — one closed marker vocabulary

`comeni_core/marks.py` gains:

```python
class Mark(StrEnum):
    """Every kind of thing a declared string may be. Closed, on purpose.

    A `StrEnum` so the metadata still reads as itself in a repr, and an enum so the guard can
    ask `isinstance(meta, Mark)` — which is a question with an answer, unlike "is there a
    string here", which was the previous test and which `Annotated[str, "clinical-notes"]`
    passed.
    """
    CONTRACT_ID = "contract-id"
    TYPE_ID = "type-id"
    NODE_ID = "node-id"
    SUBJECT = "subject"
    PORT_NAME = "port-name"
    STATE_NAME = "state-name"
    DECISION_KEY = "decision-key"
    RESOLVER_ID = "resolver-id"
    MEASUREMENT_ID = "measurement-id"
    DIGEST = "digest"
    LAYER_NAME = "layer-name"
    CONTAINER_REF = "container-ref"
    MODULE_KEY = "module-key"
    FREE_TEXT = "free-text"
    PARAM_LITERAL = "param-literal"
```

All 15 aliases rewrite to `Annotated[str, Mark.<X>]`. `FreeText` and `ParamLiteral` fold in as
members: **one vocabulary, so there is exactly one question to ask of any metadata element.**
Keeping content-kind markers as classes and identifier markers as strings is the split that
produced this finding.

**Rule:** a `str` leaf is permitted iff **some** element of its metadata chain is a `Mark`
instance.

### Move 2 — the leaf rule becomes positive

A new `test_every_payload_field_is_a_declared_shape` walks each payload to its leaves. Permitted,
and nothing else:

| form | permitted when |
|---|---|
| terminal | `int`, `float`, `bool`, `NoneType`; any `enum.Enum` subclass; any `BaseModel` in the reachable set |
| `str` | only inside `Annotated[...]` whose metadata contains a `Mark` |
| `list[X]`, `frozenset[X]` | `X` permitted |
| `X \| Y` | every arm permitted |
| `Annotated[X, ...]` | `X` permitted; non-`Mark` metadata (validators) is allowed alongside |

Anything else fails, naming `Model.field` and the offending annotation. This closes `object`,
`Path`, `Any`, bare `dict`, `tuple`, `type`, `bytes`, `Mapping` — and the shapes nobody has
thought of — in one rule.

The table is a transcription of what the graph already holds, so it should pass on arrival. **If
it does not, that is a finding, not a reason to widen the table.**

### Move 3 — free text stays a named-field rule

`Mark.FREE_TEXT` is a legal *shape*; a field carrying it must additionally appear in
`FREE_TEXT_FIELDS`. Two rules over one vocabulary: *may this shape cross at all* and *is this
particular field allowed to be prose*. `FREE_TEXT_FIELDS` currently holds four entries while
CLAUDE.md invariant 14 says two — the guard is the honest one, and A33 records that the invariant
text is stale.

### Move 4 — the negative rules stay, and the inert one is repaired

The four existing rules remain as regression records of A6, A19, A20 and A30. They cost
milliseconds and they document why the positive rule exists.

**`Any` gets its own predicate** rather than reusing the marker walker:

```python
def _mentions_any(annotation: object) -> bool:
    if annotation is typing.Any:
        return True
    return any(_mentions_any(arg) for arg in typing.get_args(annotation))
```

Deleting `test_no_payload_carries_an_untyped_container` as redundant would erase A20's record
instead of closing it. It is repaired and kept.

---

## Verification

**Root I applies from this spec onward: every guard added here is reverted and watched failing
before the task is called done.** Nine probes, each added to a real payload, run, and reverted:

| probe | must fail | closes |
|---|---|---|
| `leak: object` on `Lockfile` | positive rule | A19 |
| `leak: Path \| None` on `PublishBundle` | positive rule | A30 |
| `leak: Any` on `PublishBundle` | positive rule **and** the repaired `Any` rule | A20 |
| `leak: dict[str, Any]` | both | A20 |
| `leak: tuple[str, str]` | positive rule | — |
| `leak: bytes` | positive rule and the binary rule | A6 regression |
| `leak: Mapping[MeasurementId, ParamValue]` | positive rule and the mapping rule | A6 regression |
| `leak: str` (unmarked) | positive rule and the bare-str rule | C3 regression |
| **`leak: Annotated[str, "invented-marker"]`** | **positive rule only** | the marker-set hole |

The last is the one that proves Move 1. It **passes today** and must not after.

Record each probe's observed failure message in the plan. A probe that fails with a message that
would not lead a reader to the defect is a finding, not a pass.

---

## Blast radius

Verified: **nothing reads the marker string values** — a grep across `packages`, `tests` and
`tools` for the 13 literals returns only `marks.py` itself. They are write-only labels, so
turning them into enum members changes no consumer. `profile.pyi` imports alias *names*
(`ContractId`, `MeasurementId`, `ParamValue`), not their definitions, so the generated stub is
unaffected and `tools/generate_types.py --check` should stay green.

Files: `packages/comeni-core/src/comeni_core/marks.py` (15 alias lines plus the enum) and
`tests/test_egress.py`. Nothing else.

---

## What this spec does not cover

**`Mark.TYPE_ID` still does not mean the value is a declared type.** A29's patient name remains a
shape-legal `TypeId`. That is root E — *declared IDs are labels, not domains* — and it is a
separate spec. This one answers **what shape may cross**; E answers **what value may a shape
hold**. Stated here so neither is later believed to have covered the other.

Root A also does not touch A17 (`ctypes` and the purity guards), which is deliberately
unclustered — see the root-causes document for why the purity banlist cannot become an allowlist.
