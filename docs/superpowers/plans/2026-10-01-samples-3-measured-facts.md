# Samples 3 — a measured fact says what measured it — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fact an inspector measured enters the goal as `measured`, naming the pieces and versions that measured it and how much they read, and `paired` stops claiming nothing can measure it.

**Architecture:** Most of this exists already: `ValueSource.MEASURED` ("a tool produced this value by looking at the data, and named itself"), `Measured.by` (a contract id, for profilers) and `MeasurementRegistry.profile_of()` (a profile whose entries carry their own sources). This plan adds what an inspector needs beside them: `Measured.pieces` (a list of `<piece>@<version>`, a new declared id alias), `Measured.evidence` (typed counts, never free text, because the goal is reachable from the doors), a `MeasuredEntry` for `profile_of`, the meta reason a reader sees, and the vocabulary check that now counts inspector pieces as measuring.

**Tech Stack:** Python 3.12, pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-samples-and-inspectors-design.md` §9 (*Admitting*, *assertion_only*, *Into the goal*). Part 14.7.6.3 of #134. Depends on part 2 (`Layers.inspection`).

## Global Constraints

- **The goal is reachable from the doors** (invariant 14): every new string field is a declared id alias (`Mark`), never a bare `str`, and no mapping. `tests/guards/test_egress.py` must stay green with `FREE_TEXT_FIELDS` unchanged.
- **`DataProfile` is built only by `MeasurementRegistry.profile()` / `.profile_of()`** (`tests/guards/test_construction.py`).
- **Same goal in, same `.nf` out** (invariant 10), and **artifacts do not change for goals that did not change**: a `Measured` with no pieces and no evidence serialises exactly as today.
- An undetermined fact is **not** admitted: it never reaches the profile, so it stays open (tier 4 where read).
- Comments and docstrings match the repository's style. A loop is not an assertion.

## Ruling against the spec, for the operator

The spec (§9) names a new `ValueSource.INSPECTED`. The code already has `ValueSource.MEASURED` with exactly that meaning, consumed by `artifact/materialise.py` and mapped to `PremiseOrigin.MEASURED`. A second member would split one meaning across two names and every consumer would have to learn both. **This plan uses `MEASURED`**; an inspector is told apart from a profiler by `pieces` (set) versus `by` (a contract id). Cost if wrong: one enum member and its mappings, added later. Record this in the execution record and in the spec's §9 when the plan lands.

## Review Focus

1. **A pipeline.yml golden that pins a profile**: adding two fields must not change its bytes when they are empty. Pinned in Task 1.
2. **`by` and `pieces` both set** (a contract *and* inspector pieces): refuse; a value has one measurer. Pinned in Task 1.
3. **A piece ref with no version** (`fastq`): refused by the alias, like a contract id with no `@`. Pinned in Task 1.
4. **A `paired` value of `"yes"`** arriving from a person through `profile_of`: still refused by `check`, unchanged. Pinned in Task 2.
5. **A measurement both `assertion_only` and measured by an inspector piece**: the vocabulary test refuses the registry. Pinned in Task 3.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `packages/comeni-core/src/comeni_core/spell/marks.py` | `Mark.PIECE_REF`, `PieceRef` alias |
| Modify `packages/comeni-core/src/comeni_core/goal/profile.py` | `Evidence`; `Measured.pieces`, `Measured.evidence`; omitted when empty |
| Modify `packages/comeni-core/src/comeni_core/declared/measurement.py` | `MeasuredEntry`; `profile_of(entries: Sequence[MeasuredEntry])`; `profile()` through it |
| Modify `packages/mendel-api/src/mendel_api/services/authoring.py:1449` | the one other caller of `profile_of` |
| Modify `packages/comeni-core/src/comeni_core/artifact/materialise.py:167` | the reason: *measured by fastq@1.0.0 + read_length@1.0.0, on 8,412 reads* |
| Modify `docs/handbook/reference/pipeline-schema.md` | the two fields |
| Modify `tests/registry/test_measurement_vocabulary.py` | inspector pieces count as measuring |
| In `registry/vocabulary/measurements/paired.yml` | `assertion_only` removed |
| Tests: `packages/comeni-core/tests/test_measured_pieces.py` | the fields, the alias, the serialisation |

---

### Task 1: `Measured` names its pieces and its evidence

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/spell/marks.py`
- Modify: `packages/comeni-core/src/comeni_core/goal/profile.py`
- Test: `packages/comeni-core/tests/test_measured_pieces.py`

**Interfaces:**
- Produces: `PieceRef = Annotated[str, Mark.PIECE_REF, AfterValidator(_piece_ref)]` (`^[a-z0-9_]+@\d+\.\d+\.\d+$`); `Evidence(records: int | None = None, rows: int | None = None, share: float | None = None)` (frozen, `extra="forbid"`, all `ge=0`, `share ≤ 1`); `Measured.pieces: list[PieceRef] = []`, `Measured.evidence: Evidence | None = None`.

- [ ] **Step 1: Read how `Mark` members are registered and checked**

Run: `grep -n "CONTRACT_ID\|_contract_id" packages/comeni-core/src/comeni_core/spell/marks.py tests/guards/*.py | head -20`
Note every place a new `Mark` must also be named (a docstring table, a guard's list); the new member goes in each.

- [ ] **Step 2: Write the failing tests**

```python
# packages/comeni-core/tests/test_measured_pieces.py
"""A measured fact names what measured it: a contract (a profiler) or inspector pieces."""

import pytest
from pydantic import ValidationError

from comeni_core.goal.profile import Evidence, Measured
from comeni_core.plan.tiers import ValueSource

PIECES = ["fastq@1.0.0", "read_length@1.0.0"]


def test_a_measured_fact_names_its_pieces_and_evidence():
    m = Measured(measurement="read_length", value=151, source=ValueSource.MEASURED,
                 pieces=PIECES, evidence=Evidence(records=8412, share=0.97))
    assert m.pieces == PIECES and m.evidence.records == 8412


def test_a_piece_ref_without_a_version_is_refused():
    with pytest.raises(ValidationError):
        Measured(measurement="read_length", value=151, source=ValueSource.MEASURED, pieces=["fastq"])


def test_a_contract_and_pieces_together_are_refused():
    with pytest.raises(ValidationError, match="one measurer"):
        Measured(measurement="read_length", value=151, source=ValueSource.MEASURED,
                 by="comeni/profile/fastqc@0.12.1", pieces=PIECES)


def test_an_empty_measured_serialises_exactly_as_before():
    """Every pipeline.yml written so far must stay byte-identical."""
    m = Measured(measurement="strandedness", value="reverse")
    assert m.model_dump(mode="json") == {
        "measurement": "strandedness", "value": "reverse", "source": "goal", "by": None,
    }


def test_a_share_above_one_is_refused():
    with pytest.raises(ValidationError):
        Evidence(share=1.2)
```

(Run `grep -rn "source:" docs/handbook/reference/pipeline-schema.md` first: if the serialised `source` value differs from `"goal"`, use what the file shows.)

- [ ] **Step 3: Run them to see them fail**

Run: `uv run pytest packages/comeni-core/tests/test_measured_pieces.py -q`
Expected: FAIL — `cannot import name 'Evidence'`.

- [ ] **Step 4: Implement**

`marks.py`: `PIECE_REF = "piece-ref"` in `Mark` with a docstring (*"An inspector piece and its version, `fastq@1.0.0`: what a measured fact names when no contract measured it (#134)."*), and:

```python
def _piece_ref(value: str) -> str:
    """`<piece>@<major>.<minor>.<patch>` — an inspector piece, as a fact records it."""
    if not re.fullmatch(r"[a-z0-9_]+@\d+\.\d+\.\d+", value):
        raise ValueError(f"{value!r} is not a piece ref. They are `<piece>@<version>`, e.g. `fastq@1.0.0`.")
    return value


PieceRef = Annotated[str, Mark.PIECE_REF, AfterValidator(_piece_ref)]
```

(import `re` if the module does not; check `comeni-core`'s purity allowlist in `tests/guards/test_purity.py` — `re` is not in it for `comeni-core`. If so, validate with `str.partition` and `str.isdigit` instead and keep the allowlist closed.)

`profile.py`:

```python
class Evidence(BaseModel):
    """How much an inspector read to decide a fact. Counts only: the goal is reachable from the
    doors, so this carries no prose (the reason a fact was undetermined never reaches a goal)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    records: int | None = Field(default=None, ge=0)
    rows: int | None = Field(default=None, ge=0)
    share: float | None = Field(default=None, ge=0, le=1)
```

On `Measured`, after `by`:

```python
    pieces: list[PieceRef] = Field(default_factory=list)
    """The inspector pieces that measured this, `fastq@1.0.0` then `read_length@1.0.0` (#134).
    Empty for a profiler (it is `by`) and for anything a person asserted."""
    evidence: Evidence | None = None

    @model_validator(mode="after")
    def _one_measurer(self) -> "Measured":
        if self.by is not None and self.pieces:
            raise ValueError("a measured value has one measurer: a contract (`by`) or inspector pieces, not both")
        return self

    @model_serializer(mode="wrap")
    def _omit_when_empty(self, handler):
        """**Artifacts written before inspectors stay byte-identical.** Empty `pieces` and a
        missing `evidence` are left out rather than written as `[]` and `null`."""
        data = handler(self)
        if not self.pieces:
            data.pop("pieces", None)
        if self.evidence is None:
            data.pop("evidence", None)
        return data
```

- [ ] **Step 5: Run them, then the egress and construction guards**

Run: `uv run pytest packages/comeni-core/tests/test_measured_pieces.py tests/guards -q`
Expected: PASS. If the egress guard reports the new alias as unknown, add `Mark.PIECE_REF` wherever it lists declared aliases (that is a declared id, not free text: `FREE_TEXT_FIELDS` stays unchanged).

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/src/comeni_core/spell/marks.py packages/comeni-core/src/comeni_core/goal/profile.py packages/comeni-core/tests/test_measured_pieces.py tests/guards
git commit -m "feat(core): a measured fact names its inspector pieces and how much they read (#134)"
```

---

### Task 2: `profile_of` takes entries that say who measured them

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/measurement.py:376-409`
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py:1449-1456`
- Test: `packages/comeni-core/tests/test_measured_pieces.py`

**Interfaces:**
- Consumes: Task 1's `Measured.pieces`, `Evidence`.
- Produces: `MeasuredEntry(measurement: str, value: ParamValue | list[ParamValue], source: ValueSource, by: str | None = None, pieces: tuple[str, ...] = (), evidence: Evidence | None = None)` — a `NamedTuple` in `measurement.py`; `MeasurementRegistry.profile_of(entries: Sequence[MeasuredEntry]) -> DataProfile`.

- [ ] **Step 1: Write the failing tests**

```python
from comeni_core.declared.measurement import MeasuredEntry, MeasurementRegistry
from support.paths import ROOT


def _measurements():
    from mendel_resolver import layers

    return layers.load(ROOT / "registry").measurements


def test_profile_of_carries_pieces_and_evidence():
    profile = _measurements().profile_of([
        MeasuredEntry("read_length", 151, ValueSource.MEASURED,
                      pieces=("fastq@1.0.0", "read_length@1.0.0"), evidence=Evidence(records=8412, share=0.97)),
        MeasuredEntry("strandedness", "reverse", ValueSource.GOAL),
    ])
    measured = {m.measurement: m for m in profile.measurements}
    assert measured["read_length"].pieces == ["fastq@1.0.0", "read_length@1.0.0"]
    assert measured["strandedness"].source is ValueSource.GOAL


def test_profile_of_still_checks_every_value():
    import pytest

    with pytest.raises(Exception):
        _measurements().profile_of([MeasuredEntry("paired", "yes", ValueSource.GOAL)])
```

(If `packages/comeni-core/tests` cannot import `mendel_resolver` or `support`, put these two tests in `tests/registry/test_measured_entries.py` instead — `comeni-core`'s own tests may not depend on the resolver.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/registry/test_measured_entries.py packages/comeni-core/tests/test_measured_pieces.py -q`
Expected: FAIL — `cannot import name 'MeasuredEntry'`.

- [ ] **Step 3: Implement**

```python
class MeasuredEntry(NamedTuple):
    """One fact for `profile_of`: its value, who settled it, and what measured it."""

    measurement: str
    value: ParamValue | list[ParamValue]
    source: ValueSource
    by: str | None = None
    pieces: tuple[str, ...] = ()
    evidence: Evidence | None = None
```

`profile()` builds `[MeasuredEntry(k, v, source, by) for k, v in mapping.items()]`. `profile_of` checks each value as now and builds `Measured(measurement=e.measurement, value=e.value, source=e.source, by=e.by, pieces=list(e.pieces), evidence=e.evidence)` sorted by measurement. `typing.NamedTuple` — confirm `typing` is on `comeni-core`'s allowlist (it is).

In `authoring.py`'s `compose_goal`, build `MeasuredEntry(f.subject, f.value, _SOURCE[f.source])` in place of the 4-tuple, unchanged in meaning; part 4 adds the pieces and evidence it learns from an inspection.

- [ ] **Step 4: Run them, and every caller's tests**

Run: `uv run pytest tests/registry packages/comeni-core packages/mendel-api -q -x`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/comeni-core/src/comeni_core/declared/measurement.py packages/mendel-api/src/mendel_api/services/authoring.py tests/registry/test_measured_entries.py packages/comeni-core/tests/test_measured_pieces.py
git commit -m "feat(core): profile_of takes entries that say what measured them (#134)"
```

---

### Task 3: The reader sees what measured it; `paired` is measurable

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py:155-175`
- Modify: `tests/registry/test_measurement_vocabulary.py:30-52`
- Modify (registry): `vocabulary/measurements/paired.yml`
- Modify: `docs/handbook/reference/pipeline-schema.md`
- Test: `tests/registry/test_measured_entries.py`

**Interfaces:**
- Consumes: `Measured.pieces`, `Measured.evidence`; `Layers.inspection.measures` (part 2) — each `MeasurePiece.measures` is a measurement id.

- [ ] **Step 1: Write the failing tests**

In `tests/registry/test_measured_entries.py` (Task 2's file; `_meta_entry` has no unit test of its own today, only the pipeline goldens):

```python
def test_an_inspected_meta_value_says_which_pieces_measured_it_and_on_how_much():
    from comeni_core.artifact.materialise import _meta_entry

    measurements = _measurements()
    profile = measurements.profile_of([
        MeasuredEntry("read_length", 151, ValueSource.MEASURED,
                      pieces=("fastq@1.0.0", "read_length@1.0.0"), evidence=Evidence(records=8412)),
    ])
    entry = _meta_entry("read_length", measurements.get("read_length"), 151, profile)
    assert entry.why.reason.startswith("measured by fastq@1.0.0 + read_length@1.0.0, on 8,412 reads")


def test_a_profiled_meta_value_still_names_its_contract():
    from comeni_core.artifact.materialise import _meta_entry

    measurements = _measurements()
    profile = measurements.profile_of([
        MeasuredEntry("read_length", 151, ValueSource.MEASURED, by="comeni/profile/fastqc@0.12.1"),
    ])
    entry = _meta_entry("read_length", measurements.get("read_length"), 151, profile)
    assert entry.why.reason.startswith("measured by comeni/profile/fastqc@0.12.1")
```

In `test_measurement_vocabulary.py`, extend `measurable` with the inspector pieces and add:

```python
def test_paired_is_measured_by_an_inspector_piece():
    loaded = _loaded()
    assert any(p.measures == "paired" for p in loaded.inspection.measures.values())
    assert not loaded.measurements.get("paired").assertion_only
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/registry/test_measurement_vocabulary.py tests/registry/test_measured_entries.py -q`
Expected: FAIL — `paired` is `assertion_only`; the reason says `measured` only.

- [ ] **Step 3: Implement**

`test_measurement_vocabulary.py`: where `measurable` is computed from contracts producing `measurement.*`, add `| {p.measures for p in loaded.inspection.measures.values()}` and change the message to *"a contract or an inspector piece produces it"*.

`materialise.py`:

```python
    if source is ValueSource.MEASURED:
        measurer = " + ".join(entry.pieces) if entry is not None and entry.pieces else by
        reason = f"measured by {measurer}" if measurer else "measured"
        if entry is not None and entry.evidence is not None and entry.evidence.records:
            reason = f"{reason}, on {entry.evidence.records:,} reads"
```

Registry: in `vocabulary/measurements/paired.yml`, delete `assertion_only: true` and `assertion_only_because:` (its own text says *"Wiring it is a `comeni/profile-*` contract away"*; an inspector piece is what wired it). Commit in the registry: `Paired is measured: the paired inspector piece reads it (comeni-labs #134)`.

`pipeline-schema.md`: beside the profile example, document `pieces` and `evidence` (one sentence each: present only when an inspector measured the value).

- [ ] **Step 4: Run them, then `make verify`** (`materialise.py` and the goal feed every artifact)

Run: `uv run pytest tests/registry -q && make verify > /tmp/claude-1000/verify.log 2>&1; tail -20 /tmp/claude-1000/verify.log`
Expected: PASS; no golden changes (no shipped goal has pieces). If any golden changed, stop: the omission in Task 1 is not working.

- [ ] **Step 5: Commit, separately from the checks**

```bash
git add packages/comeni-core/src/comeni_core/artifact/materialise.py tests/registry/test_measurement_vocabulary.py docs/handbook/reference/pipeline-schema.md registry tests/registry/test_measured_entries.py
git commit -m "feat(core): a reader sees which pieces measured a value; paired is measurable (#134)"
```

---

## Execution record

*(Filled in while executing: rulings, measurements, deviations.)*
