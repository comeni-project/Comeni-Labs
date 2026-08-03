# Measurements, Rule Tables and Profiling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax for
> tracking. Do **not** farm the tasks out with subagent-driven-development — subagents are for
> review and design only. This matches the execution decision recorded in `CLAUDE.md`.

**Goal:** Make the declarative layer expressive enough to say what practitioners mean — measurements
become declared data, tier-3 rules become validated decision tables that can pin a module, ports gain
alternatives, and profiling becomes a build whose `want` is a set of measurements.

**Architecture:** Everything here is pure-package work in `comeni-core` and `mendel-resolver`, with
one emitter change. No AI, no network, no new dependency. The through-line is that a measurement is
*both* a declaration (kind, allowed values, citation) and a **type** modules can produce — which is
what lets profiling reuse the router instead of becoming a second subsystem.

**Tech Stack:** Python 3.12, Pydantic v2, Jinja2, pytest, ruff, `uv` workspace.

## Global Constraints

- `comeni-core` and `mendel-resolver` are under a **closed allowlist** in `tests/test_purity.py`.
  Adding an import to either means adding it to `CLOSED_PACKAGES` deliberately, in the same commit.
- Every model reachable from an egress payload must satisfy `tests/test_egress.py`: no `Any`, no bare
  `str`, no mapping, `extra="forbid"`. Check after any change to `comeni-core`.
- **Free text is allowlisted, never exempted.** A new prose field means editing `FREE_TEXT_FIELDS`.
- Determinism is a test: same `Goal` → byte-identical `.nf`. Anything serialising a `frozenset` needs
  a `field_serializer` that sorts.
- Tier 3 is a pure lookup. A rule miss demotes to tier 4 — it never reaches for a model.
- Ruff line length 100. `uv run ruff check` and `uv run pytest` pass before every commit.
- **Do not re-do layered loading.** `Vocabulary.load` and `RuleTable.load` already take
  `Path | Sequence[Path]`, and `--registry` already points at a layer directory holding
  `contracts/`, `rules/` and `vocabularies/`. That landed with the audit's D3.

---

## File Structure

```
packages/comeni-core/src/comeni_core/
├─ measurement.py          NEW — Measurement, MeasurementRegistry, MeasurementValue
├─ marks.py                MODIFY — MeasurementId alias
├─ contract.py             MODIFY — InputPort.accepts / prefer, Alternative
├─ ir.py                   MODIFY — IRNode.selection
├─ tiers.py                unchanged (Tier, ReviewLevel, ValueSource already exist)
packages/mendel-resolver/src/mendel_resolver/
├─ rules.py                REWRITE — Decision, DecisionRow, RuleTable with validation
├─ goal.py                 MODIFY — DataProfile becomes a validated map
├─ router.py               MODIFY — producer pinning, alternatives, prefer
├─ resolve.py              MODIFY — value_for, selection tiering
tools/generate_types.py    NEW — declarations → .pyi stub, golden-tested
examples/
├─ measurements/*.yml      NEW — the four current fields, declared
├─ rules/rnaseq.yml        REWRITE — decision tables
├─ contracts/comeni/*.yml  NEW — profiling contracts
tests/
├─ test_measurements.py    NEW
├─ test_construction.py    NEW — AST guard, single validated path
ARCHITECTURE.md            NEW — final task, written against real types
```

**Ordering rationale.** Measurements come first because rules validate against them and profiling
produces them. Ports and pinning are independent of measurements and could go anywhere; they sit
mid-plan so the rule rewrite has pinning available. `ARCHITECTURE.md` is last, deliberately — the
same reason `CLAUDE.md` defers Plan 2.5: a document written against predicted types drifts, and this
plan changes the rule format, the profile, ports and module tiering, which is most of what such a
document describes.

**Out of scope, and why.** The `sealed` protection profile blocking a tier-3 decision driven by an
asserted measurement (profiling spec §5.2) needs `ProfilePolicy`, which Plan 2 Task 1A builds. This
plan records provenance so that check becomes possible; it does not enforce it. The `.d.ts` target
and the `/measurements` endpoint need `mendel-api`, which is Plan 3.

---

### Task 1: Measurement declarations

Implements rule-tables spec §6.2–6.4. A measurement is declared data — kind, allowed values, unit,
citation — so a laboratory can add one without a release. `kind` is closed and there is deliberately
**no `string`**: a free-text measurement is exactly the hole `tests/test_egress.py` exists to close,
and a categorical declares its values instead.

**Files:**
- Create: `packages/comeni-core/src/comeni_core/measurement.py`
- Modify: `packages/comeni-core/src/comeni_core/marks.py`
- Create: `examples/measurements/read_length.yml`, `strandedness.yml`, `n_samples.yml`, `paired.yml`
- Test: `packages/comeni-core/tests/test_measurement.py`

**Interfaces:**
- Consumes: `marks.ParamValue`
- Produces: `MeasurementKind` StrEnum (`INTEGER, NUMBER, BOOLEAN, ENUM`);
  `Measurement(id, kind, values, minimum, maximum, unit, description, cite, edam, extensible, deprecated, replaced_by)`;
  `MeasurementRegistry.load(layers: Path | Sequence[Path]) -> MeasurementRegistry`;
  `MeasurementRegistry.get(id) -> Measurement`; `MeasurementRegistry.ids() -> list[str]`;
  `MeasurementRegistry.check(id, value) -> None` raising `UnknownMeasurementError` / `BadMeasurementValueError`;
  `MeasurementId` alias in `marks.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.measurement import (
    BadMeasurementValueError,
    MeasurementKind,
    MeasurementRegistry,
    UnknownMeasurementError,
)


def _layer(root, name, files):
    d = root / name
    d.mkdir(parents=True)
    for filename, body in files.items():
        (d / filename).write_text(body)
    return d


READ_LENGTH = """
kind: integer
minimum: 1
unit: bp
description: "Sequenced read length"
"""

STRANDEDNESS = """
kind: enum
values: [forward, reverse, unstranded]
description: "Library strandedness"
cite: "Signal et al. 2022, doi:10.1186/s12859-022-04572-7"
"""

ORGANISM = """
kind: enum
extensible: true
values: [homo_sapiens, mus_musculus]
description: "Source organism"
"""


@pytest.fixture
def base(tmp_path):
    return _layer(
        tmp_path,
        "base",
        {
            "read_length.yml": READ_LENGTH,
            "strandedness.yml": STRANDEDNESS,
            "organism.yml": ORGANISM,
        },
    )


def test_a_declaration_is_loaded_by_filename(base):
    registry = MeasurementRegistry.load(base)
    assert registry.get("read_length").kind is MeasurementKind.INTEGER
    assert registry.get("read_length").unit == "bp"


def test_an_enum_accepts_only_its_declared_values(base):
    registry = MeasurementRegistry.load(base)
    registry.check("strandedness", "reverse")
    with pytest.raises(BadMeasurementValueError, match="sideways"):
        registry.check("strandedness", "sideways")


def test_an_integer_respects_its_bounds(base):
    registry = MeasurementRegistry.load(base)
    registry.check("read_length", 150)
    with pytest.raises(BadMeasurementValueError, match="minimum"):
        registry.check("read_length", 0)


def test_a_wrong_type_is_refused(base):
    registry = MeasurementRegistry.load(base)
    with pytest.raises(BadMeasurementValueError):
        registry.check("read_length", "one hundred and fifty")


def test_an_undeclared_measurement_says_what_exists(base):
    registry = MeasurementRegistry.load(base)
    with pytest.raises(UnknownMeasurementError) as exc:
        registry.check("organsim", "homo_sapiens")
    message = str(exc.value)
    assert "organsim" in message
    assert "read_length" in message and "strandedness" in message


def test_there_is_no_string_kind(tmp_path):
    """A free-text measurement is the hole the egress guard exists to close."""
    layer = _layer(tmp_path, "bad", {"note.yml": "kind: string\ndescription: x\n"})
    with pytest.raises(ValueError, match="string"):
        MeasurementRegistry.load(layer)


def test_a_closed_enum_refuses_added_values(tmp_path, base):
    overlay = _layer(tmp_path, "lab", {"strandedness.yml": "add_values: [sideways]\n"})
    with pytest.raises(ValueError, match="not extensible"):
        MeasurementRegistry.load([base, overlay])


def test_an_extensible_enum_takes_the_union(tmp_path, base):
    overlay = _layer(tmp_path, "lab", {"organism.yml": "add_values: [ambystoma_mexicanum]\n"})
    registry = MeasurementRegistry.load([base, overlay])
    registry.check("organism", "ambystoma_mexicanum")
    registry.check("organism", "homo_sapiens")


def test_a_deprecated_measurement_names_its_replacement(tmp_path):
    layer = _layer(
        tmp_path,
        "d",
        {
            "read_length.yml": "kind: integer\ndeprecated: true\n"
            "replaced_by: read_length_median\ndescription: ambiguous\n",
            "read_length_median.yml": "kind: integer\ndescription: median\n",
        },
    )
    registry = MeasurementRegistry.load(layer)
    assert registry.get("read_length").deprecated is True
    assert registry.get("read_length").replaced_by == "read_length_median"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_measurement.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'comeni_core.measurement'`

- [ ] **Step 3: Add the `MeasurementId` alias**

Append to `packages/comeni-core/src/comeni_core/marks.py`:

```python
MeasurementId = Annotated[str, "measurement-id"]
```

- [ ] **Step 4: Write `measurement.py`**

```python
"""Measurements as declared data.

`DataProfile` used to be four hardcoded fields, so a rule could only ever reason about
four things and adding a fifth meant editing a pure package, bumping a version and cutting
a release — something a bioinformatician cannot do and a curator cannot approve. The
tier-3 promise is that rules are data a domain expert adds; this is what makes that true.

`kind` is closed and there is deliberately no `string`. A free-text measurement is exactly
the hole `tests/test_egress.py` exists to close — `organism: "patient 4471023's tumour"` is
a perfectly valid string. A categorical declares its values instead, which also lets a rule
over it be checked for exhaustiveness.
"""

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from comeni_core.marks import MeasurementId, ParamValue


class UnknownMeasurementError(KeyError):
    """Raised when nothing declares this measurement."""


class BadMeasurementValueError(ValueError):
    """Raised when a value does not satisfy its declaration."""


class MeasurementKind(StrEnum):
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: MeasurementId
    kind: MeasurementKind
    values: list[str] = Field(default_factory=list)
    extensible: bool = False
    """Whether an overlay may contribute `add_values`.

    Per measurement, because the semantics genuinely differ: `strandedness` has exactly
    three values and a fourth is a bug, while `organism` can never be enumerated and a
    registry that tries is wrong.
    """
    minimum: float | None = None
    maximum: float | None = None
    unit: str | None = None
    description: str = ""
    cite: str | None = None
    edam: str | None = None
    deprecated: bool = False
    replaced_by: MeasurementId | None = None
    """A meaning change gets a *new id*; this one stays forever, pointing at its successor.

    OBO practice, which the ontologies this registry cites have used for two decades: never
    reuse an identifier, keep obsolete terms indefinitely. Per-measurement `@version` was
    rejected — every rule condition would grow a version, and omitting one would silently
    mean *latest*, which is the ambiguity versioning was meant to remove.
    """


class MeasurementRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurements: dict[str, Measurement] = Field(default_factory=dict)

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "MeasurementRegistry":
        if isinstance(layers, Path):
            layers = [layers]
        found: dict[str, Measurement] = {}
        for layer in layers:
            if not layer.exists():
                continue
            for path in sorted(layer.glob("*.yml")):
                measurement_id = path.name.removesuffix(".yml")
                data = yaml.safe_load(path.read_text()) or {}
                added = data.pop("add_values", None)
                if added is not None:
                    found[measurement_id] = _extend(found, measurement_id, added, path)
                    continue
                if data.get("kind") == "string":
                    raise ValueError(
                        f"{path}: kind 'string' does not exist. A categorical measurement "
                        f"declares its values as an enum; free text has nowhere safe to go."
                    )
                found[measurement_id] = Measurement(id=measurement_id, **data)
        return cls(measurements=found)

    def get(self, measurement_id: str) -> Measurement:
        if measurement_id not in self.measurements:
            raise UnknownMeasurementError(self._unknown(measurement_id))
        return self.measurements[measurement_id]

    def ids(self) -> list[str]:
        return sorted(self.measurements)

    def _unknown(self, measurement_id: str) -> str:
        return (
            f"{measurement_id!r} is not a declared measurement.\n"
            f"  Declared: {', '.join(self.ids()) or '(none)'}\n"
            f"  To add one, declare <layer>/measurements/{measurement_id}.yml"
        )

    def check(self, measurement_id: str, value: ParamValue) -> None:
        """Raise unless `value` satisfies the declaration for `measurement_id`."""
        measurement = self.get(measurement_id)
        kind = measurement.kind
        if kind is MeasurementKind.ENUM:
            if value not in measurement.values:
                raise BadMeasurementValueError(
                    f"{value!r} is not a declared value for {measurement_id!r}; "
                    f"allowed: {', '.join(measurement.values)}"
                )
            return
        if kind is MeasurementKind.BOOLEAN:
            if not isinstance(value, bool):
                raise BadMeasurementValueError(f"{measurement_id!r} is a boolean, got {value!r}")
            return
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise BadMeasurementValueError(f"{measurement_id!r} is a {kind}, got {value!r}")
        if kind is MeasurementKind.INTEGER and not isinstance(value, int):
            raise BadMeasurementValueError(f"{measurement_id!r} is an integer, got {value!r}")
        if measurement.minimum is not None and value < measurement.minimum:
            raise BadMeasurementValueError(
                f"{measurement_id!r} has minimum {measurement.minimum}, got {value!r}"
            )
        if measurement.maximum is not None and value > measurement.maximum:
            raise BadMeasurementValueError(
                f"{measurement_id!r} has maximum {measurement.maximum}, got {value!r}"
            )


def _extend(
    found: dict[str, Measurement], measurement_id: str, added: list[str], path: Path
) -> Measurement:
    if measurement_id not in found:
        raise ValueError(f"{path}: add_values for {measurement_id!r}, which no layer declares")
    base = found[measurement_id]
    if not base.extensible:
        raise ValueError(
            f"{path}: {measurement_id!r} is not extensible. Shadow the whole declaration to "
            f"change it, or set `extensible: true` where it is declared."
        )
    return base.model_copy(update={"values": [*base.values, *added]})
```

- [ ] **Step 5: Declare the four current measurements**

`examples/measurements/read_length.yml`:

```yaml
kind: integer
minimum: 1
unit: bp
description: "Sequenced read length"
```

`examples/measurements/strandedness.yml`:

```yaml
kind: enum
values: [forward, reverse, unstranded]
description: "Library strandedness determined by the prep protocol"
cite: "Signal et al. 2022, doi:10.1186/s12859-022-04572-7"
```

`examples/measurements/n_samples.yml`:

```yaml
kind: integer
minimum: 1
description: "Number of samples in the study"
```

`examples/measurements/paired.yml`:

```yaml
kind: boolean
description: "Whether the library is paired-end"
```

- [ ] **Step 6: Run tests and lint**

Run: `uv run pytest packages/comeni-core/tests/test_measurement.py -v && uv run ruff check .`
Expected: PASS, 9 tests. If ruff complains that `comeni_core.measurement` imports something not
on the `comeni-core` allowlist in `tests/test_purity.py`, add it there in this commit — that guard
is closed on purpose.

- [ ] **Step 7: Commit**

```bash
git add packages/comeni-core/src/comeni_core/measurement.py \
        packages/comeni-core/src/comeni_core/marks.py \
        packages/comeni-core/tests/test_measurement.py examples/measurements/
git commit -m "feat(core): measurements as declared data"
```

---

### Task 2: `DataProfile` becomes a validated map

Implements rule-tables spec §6.5. The goal file and every existing call site keep working — a
`model_validator(mode="before")` accepts the mapping form, because a mapping is the natural way to
write one even though a list is what the egress guard requires.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/goal.py`
- Test: `packages/mendel-resolver/tests/test_profile.py`

**Interfaces:**
- Consumes: `MeasurementRegistry` (Task 1)
- Produces: `Measured(measurement: MeasurementId, value: ParamValue, source: ValueSource, by: str | None)`;
  `DataProfile.measurements: list[Measured]`; `DataProfile.get(id) -> ParamValue | None`;
  `MeasurementRegistry.profile(mapping, *, source=ValueSource.GOAL) -> DataProfile`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.measurement import BadMeasurementValueError, MeasurementRegistry
from comeni_core.tiers import ValueSource
from mendel_resolver.goal import DataProfile, Goal
from pydantic import ValidationError


@pytest.fixture
def measurements(tmp_path):
    d = tmp_path / "measurements"
    d.mkdir()
    (d / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
    (d / "strandedness.yml").write_text("kind: enum\nvalues: [forward, reverse, unstranded]\n")
    return MeasurementRegistry.load(d)


def test_the_mapping_form_still_works():
    """Every existing call site and every goal file writes it this way."""
    profile = DataProfile(read_length=150, strandedness="reverse")
    assert profile.get("read_length") == 150
    assert profile.get("strandedness") == "reverse"


def test_an_unmeasured_value_is_none():
    assert DataProfile(read_length=150).get("paired") is None


def test_a_bare_scalar_is_an_assertion():
    """A human typed it, so it is asserted. The syntax matches the meaning."""
    profile = DataProfile(read_length=150)
    assert profile.measurements[0].source is ValueSource.GOAL


def test_a_registry_built_profile_validates(measurements):
    profile = measurements.profile({"read_length": 150, "strandedness": "reverse"})
    assert profile.get("read_length") == 150


def test_a_registry_built_profile_rejects_an_undeclared_measurement(measurements):
    with pytest.raises(Exception, match="organism"):
        measurements.profile({"organism": "homo_sapiens"})


def test_a_registry_built_profile_rejects_a_bad_value(measurements):
    with pytest.raises(BadMeasurementValueError, match="sideways"):
        measurements.profile({"strandedness": "sideways"})


def test_a_goal_still_carries_a_profile():
    goal = Goal(want=["counts.matrix"], profile={"read_length": 150})
    assert goal.profile.get("read_length") == 150


def test_the_profile_forbids_unknown_shapes():
    with pytest.raises(ValidationError):
        DataProfile(measurements="not a list")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-resolver/tests/test_profile.py -v`
Expected: FAIL — `DataProfile` has no `get`, and `MeasurementRegistry` has no `profile`.

- [ ] **Step 3: Rewrite `DataProfile` in `goal.py`**

Replace the `DataProfile` class with:

```python
class Measured(BaseModel):
    """One measurement and where its value came from.

    A generated profile records the tool; a hand-written goal records nothing, and that is
    an assertion by whoever wrote it. The shorthand is not an abbreviation of provenance —
    it *is* the provenance, which is why a bare scalar is allowed at all.
    """

    model_config = ConfigDict(extra="forbid")

    measurement: MeasurementId
    value: ParamValue
    source: ValueSource = ValueSource.GOAL
    by: str | None = None


class DataProfile(BaseModel):
    """Measured properties of the input data. A shape, never data.

    A list rather than a mapping because `tests/test_egress.py` forbids mappings in
    anything reachable from a payload: a typed key does not prove a *declared* key.
    """

    model_config = ConfigDict(extra="forbid")

    measurements: list[Measured] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_mapping(cls, data: object) -> object:
        if isinstance(data, dict) and "measurements" not in data:
            return {
                "measurements": [
                    {"measurement": k, "value": v} for k, v in sorted(data.items())
                ]
            }
        return data

    def get(self, measurement_id: str) -> ParamValue:
        return next(
            (m.value for m in self.measurements if m.measurement == measurement_id), None
        )
```

Add to the imports at the top of `goal.py`:

```python
from comeni_core.marks import MeasurementId, ParamValue, PortName, StateName, TypeId
from comeni_core.tiers import ValueSource
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator
```

- [ ] **Step 4: Add `MeasurementRegistry.profile`**

Append to `MeasurementRegistry` in `measurement.py`:

```python
    def profile(self, mapping: dict[str, ParamValue], *, source: str = "goal") -> object:
        """The one validated way to build a `DataProfile`.

        Validation needs this registry, which the model cannot hold, so it happens here.
        `tests/test_construction.py` asserts nothing else constructs a profile — a second
        path skipping validation would produce an unchecked profile flowing straight into
        routing, which is the class of bug that left `subject: aligner` dead for months.
        """
        from mendel_resolver.goal import DataProfile, Measured

        for measurement_id, value in mapping.items():
            self.check(measurement_id, value)
        return DataProfile(
            measurements=[
                Measured(measurement=k, value=v, source=source) for k, v in sorted(mapping.items())
            ]
        )
```

> **Note on the import direction.** `comeni-core` must not depend on `mendel-resolver`, so the
> import is function-local and deliberate. If that reads wrong to you it is because it is: the
> cleaner home for `DataProfile` is `comeni-core` beside the measurements it is made of. Moving it
> is a bigger change than this task, and Task 11 records it as the one piece of debt this plan
> knowingly leaves.

- [ ] **Step 5: Fix the call sites**

`rules.py` uses `getattr(profile, field)`. Change `Rule.matches` to use `profile.get(field)` — Task 4
rewrites this file entirely, so the change here is the minimum to keep tests green.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS. `examples/rnaseq-goal.yml` is unchanged and must still build.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-resolver/ packages/comeni-core/
git commit -m "feat(resolver): DataProfile becomes a validated map of declared measurements"
```

---

### Task 3: The single construction path

Implements rule-tables spec §6.5's enforcement clause. Validation moved out of the model, so the
risk is a second construction path that skips it. This is closed the way `test_purity.py` and
`test_egress.py` already close things — an AST test that reads like a sentence.

**Files:**
- Test: `tests/test_construction.py`

**Interfaces:**
- Consumes: `DataProfile` (Task 2), `MeasurementRegistry.profile` (Task 2)
- Produces: nothing — a guard

- [ ] **Step 1: Write the failing test**

```python
"""A `DataProfile` is built in exactly one place, and that place validates it.

Validation needs the measurement registry, which the model cannot hold, so it cannot live
in `__init__`. That makes an unvalidated profile constructible — and an unvalidated profile
with a nonsense measurement flows straight into routing. This is the third guard of its
kind, after `test_purity.py` and `test_egress.py`, and it exists for the same reason: the
alternative is a convention nobody notices breaking.
"""

import ast
import pathlib

ALLOWED = {
    # the one validated constructor
    "packages/comeni-core/src/comeni_core/measurement.py",
    # the model's own module, where the class is defined
    "packages/mendel-resolver/src/mendel_resolver/goal.py",
}


def test_data_profile_is_constructed_in_one_place():
    root = pathlib.Path(__file__).parent.parent
    offenders = []
    for package in ("comeni-core", "mendel-resolver", "mendel-compiler"):
        for py in sorted((root / "packages" / package / "src").rglob("*.py")):
            if str(py.relative_to(root)) in ALLOWED:
                continue
            for node in ast.walk(ast.parse(py.read_text())):
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                    if name == "DataProfile":
                        offenders.append(f"{py.relative_to(root)}:{node.lineno}")
    assert offenders == [], (
        "build a profile through MeasurementRegistry.profile(), which validates it; "
        "these construct one directly: " + ", ".join(offenders)
    )
```

- [ ] **Step 2: Run test to verify it passes, then prove it can fail**

Run: `uv run pytest tests/test_construction.py -v`
Expected: PASS.

Now break it on purpose: add `DataProfile()` to `packages/mendel-resolver/src/mendel_resolver/router.py`,
re-run, and confirm the failure names `router.py` and its line number. Remove it.

**Run this step.** Every guard in this repository that was not watched failing turned out to have a
hole — three of three, found by an audit on 2026-08-03. A guard that passes its own break-test has
proven one thing, not the general property.

- [ ] **Step 3: Commit**

```bash
git add tests/test_construction.py
git commit -m "test: a DataProfile is built in exactly one validated place"
```

---

### Task 4: Rules become validated decision tables

Implements rule-tables spec §3–5. The load-bearing part is validation: a rule that cannot fire
refuses to load and says what the author *can* write. Two of the five rules shipped today have never
executed, and nothing said so.

**Files:**
- Rewrite: `packages/mendel-resolver/src/mendel_resolver/rules.py`
- Rewrite: `examples/rules/rnaseq.yml`
- Test: `packages/mendel-resolver/tests/test_rules.py`

**Interfaces:**
- Consumes: `MeasurementRegistry` (Task 1), `Registry`, `Vocabulary`, `DataProfile` (Task 2)
- Produces: `DecisionTarget(param: str | None, producer_of: str | None)`;
  `DecisionRow(when: dict[str, str | int | float | bool], then: ParamValue, because, cite)`;
  `Decision(decides, rows, because, cite)`;
  `RuleTable.load(layers, *, registry, vocabulary, measurements) -> RuleTable`;
  `RuleTable.value_for(param, profile) -> tuple[ParamValue, Decision, DecisionRow] | None`;
  `RuleTable.producer_for(type_id, profile) -> tuple[str, Decision, DecisionRow] | None`;
  `RuleValidationError`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import DataProfile
from mendel_resolver.rules import RuleTable, RuleValidationError

CONTRACT = """
id: nf-core/subread/featurecounts@2.0.6
nf_process: SUBREAD_FEATURECOUNTS
nf_include: modules/nf-core/subread/featurecounts/main
consumes: [{name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}]
produces: [{name: counts, type_id: counts.matrix, state: [gene_level]}]
params: [{name: strandedness, tier_hint: 3}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-03"}
"""

GOOD = """
version: 1
decisions:
  - decides: {param: strandedness}
    because: "featureCounts -s follows library strandedness"
    cite: "Liao et al. 2014, doi:10.1093/bioinformatics/btt656"
    rows:
      - when: {strandedness: reverse}     then: 2
      - when: {strandedness: forward}     then: 1
      - when: {strandedness: unstranded}  then: 0
"""


@pytest.fixture
def world(tmp_path):
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    (vocab_dir / "counts.matrix.yml").write_text("states: [gene_level]\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "fc.yml").write_text(CONTRACT)
    measurements = tmp_path / "measurements"
    measurements.mkdir()
    (measurements / "strandedness.yml").write_text(
        "kind: enum\nvalues: [forward, reverse, unstranded]\n"
    )
    (measurements / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
    vocabulary = Vocabulary.load(vocab_dir)
    return {
        "vocabulary": vocabulary,
        "registry": Registry.load(contracts, vocabulary),
        "measurements": MeasurementRegistry.load(measurements),
        "rules": tmp_path / "rules",
    }


def _rules(world, body):
    world["rules"].mkdir(exist_ok=True)
    (world["rules"] / "r.yml").write_text(body)
    return RuleTable.load(
        world["rules"],
        registry=world["registry"],
        vocabulary=world["vocabulary"],
        measurements=world["measurements"],
    )


def test_a_matching_row_yields_its_value_and_provenance(world):
    table = _rules(world, GOOD)
    value, decision, row = table.value_for("strandedness", DataProfile(strandedness="reverse"))
    assert value == 2
    assert "Liao" in decision.cite


def test_no_matching_row_falls_through(world):
    table = _rules(world, GOOD)
    assert table.value_for("strandedness", DataProfile()) is None


def test_row_order_decides(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {param: strandedness}
    rows:
      - when: {strandedness: reverse}  then: 99
      - when: {strandedness: reverse}  then: 2
""")
    value, _, _ = table.value_for("strandedness", DataProfile(strandedness="reverse"))
    assert value == 99


def test_a_comparison_string_works(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {param: strandedness}
    rows:
      - when: {read_length: ">= 70", strandedness: reverse}  then: 2
""")
    assert table.value_for("strandedness", DataProfile(read_length=150, strandedness="reverse"))
    assert table.value_for("strandedness", DataProfile(read_length=50, strandedness="reverse")) is None


def test_a_rule_for_a_parameter_no_contract_declares_will_not_load(world):
    """The bug this whole format exists to prevent: `subject: aligner` fired never."""
    with pytest.raises(RuleValidationError) as exc:
        _rules(world, """
version: 1
decisions:
  - decides: {param: aligner}
    rows:
      - when: {read_length: ">= 70"}  then: star
""")
    message = str(exc.value)
    assert "aligner" in message
    assert "strandedness" in message, "the error must say what the author *can* write"


def test_a_rule_naming_an_undeclared_measurement_will_not_load(world):
    with pytest.raises(RuleValidationError, match="organism"):
        _rules(world, """
version: 1
decisions:
  - decides: {param: strandedness}
    rows:
      - when: {organism: human}  then: 2
""")


def test_a_producer_rule_must_name_a_contract_that_exists(world):
    with pytest.raises(RuleValidationError, match="hisat2"):
        _rules(world, """
version: 1
decisions:
  - decides: {producer_of: counts.matrix}
    rows:
      - when: {read_length: "< 70"}  then: nf-core/hisat2/align@2.2.2
""")


def test_a_producer_rule_returns_the_pinned_contract(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {producer_of: counts.matrix}
    rows:
      - when: {read_length: ">= 70"}  then: nf-core/subread/featurecounts@2.0.6
""")
    pinned, _, _ = table.producer_for("counts.matrix", DataProfile(read_length=150))
    assert pinned == "nf-core/subread/featurecounts@2.0.6"


def test_two_decisions_for_one_target_in_one_layer_is_an_error(world):
    with pytest.raises(RuleValidationError, match="twice"):
        _rules(world, GOOD + """
  - decides: {param: strandedness}
    rows:
      - when: {strandedness: reverse}  then: 3
""")


def test_a_comparison_on_an_enum_will_not_load(world):
    with pytest.raises(RuleValidationError, match="enum"):
        _rules(world, """
version: 1
decisions:
  - decides: {param: strandedness}
    rows:
      - when: {strandedness: ">= 70"}  then: 2
""")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-resolver/tests/test_rules.py -v`
Expected: FAIL — `RuleValidationError` does not exist and `RuleTable.load` takes different arguments.

- [ ] **Step 3: Rewrite `rules.py`**

```python
"""Tier 3: declared decision tables matched against measured data.

A miss is not an escalation to a model. It is a demotion to tier 4.

The format is grouped: one block per decision, rows underneath. The three strandedness
rules used to be three entries repeating their subject and citation; a reviewer should read
the justification once and then read the branches — and grouping is also what lets them
notice a *missing* branch, which flat rules actively hide.

Every table is validated against the registry, the vocabulary and the measurements at load.
That is the load-bearing part: `subject` used to be an unvalidated free string, and two of
the five rules shipped in `examples/` had never once executed.
"""

import operator
from collections.abc import Sequence
from pathlib import Path

import yaml
from comeni_core.marks import ParamValue
from comeni_core.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.goal import DataProfile

_OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt,
        "==": operator.eq, "!=": operator.ne}

_ORDERED = {MeasurementKind.INTEGER, MeasurementKind.NUMBER}


class RuleValidationError(ValueError):
    """Raised when a rule table cannot fire against the registry it was loaded with."""


class DecisionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    param: str | None = None
    producer_of: str | None = None

    def key(self) -> str:
        return f"param:{self.param}" if self.param else f"producer_of:{self.producer_of}"


class DecisionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    when: dict[str, ParamValue] = Field(default_factory=dict)
    then: ParamValue = None
    because: str | None = None
    cite: str | None = None

    def matches(self, profile: DataProfile) -> bool:
        for measurement_id, expected in self.when.items():
            actual = profile.get(measurement_id)
            if actual is None:
                return False
            if isinstance(expected, str) and expected[:2].strip() in _OPS:
                symbol, _, literal = expected.partition(" ")
                if not _OPS[symbol](actual, float(literal)):
                    return False
            elif actual != expected:
                return False
        return True


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decides: DecisionTarget
    rows: list[DecisionRow] = Field(default_factory=list)
    because: str | None = None
    cite: str | None = None


class RuleTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[Decision] = Field(default_factory=list)

    @classmethod
    def load(
        cls,
        layers: Path | Sequence[Path],
        *,
        registry: Registry,
        vocabulary: Vocabulary,
        measurements: MeasurementRegistry,
    ) -> "RuleTable":
        if isinstance(layers, Path):
            layers = [layers]
        by_target: dict[str, Decision] = {}
        for layer in layers:
            if not layer.exists():
                continue
            seen_here: set[str] = set()
            paths = [layer] if layer.is_file() else sorted(layer.glob("*.yml"))
            for path in paths:
                data = yaml.safe_load(path.read_text()) or {}
                for raw in data.get("decisions", []):
                    decision = Decision.model_validate(raw)
                    key = decision.decides.key()
                    if key in seen_here:
                        raise RuleValidationError(
                            f"{path}: {key} is decided twice in one layer. Two blocks for one "
                            f"target is a mistake; shadowing happens between layers."
                        )
                    seen_here.add(key)
                    _validate(decision, path, registry, vocabulary, measurements)
                    # A higher layer replaces the whole block, not row by row: a reviewer
                    # should read one block and see the entire effective decision.
                    by_target[key] = decision
        return cls(decisions=[by_target[k] for k in sorted(by_target)])

    def _for(self, key: str, profile: DataProfile):
        for decision in self.decisions:
            if decision.decides.key() != key:
                continue
            for row in decision.rows:
                if row.matches(profile):
                    return row.then, decision, row
        return None

    def value_for(self, param: str, profile: DataProfile):
        return self._for(f"param:{param}", profile)

    def producer_for(self, type_id: str, profile: DataProfile):
        return self._for(f"producer_of:{type_id}", profile)


def _validate(
    decision: Decision,
    path: Path,
    registry: Registry,
    vocabulary: Vocabulary,
    measurements: MeasurementRegistry,
) -> None:
    target = decision.decides
    if bool(target.param) == bool(target.producer_of):
        raise RuleValidationError(f"{path}: a decision decides exactly one of param, producer_of")

    if target.param:
        declared = sorted({p.name for c in registry.all() for p in c.params})
        if target.param not in declared:
            raise RuleValidationError(
                f"{path}, decision {target.key()}\n"
                f"  No contract in the registry declares a parameter named {target.param!r}.\n"
                f"  Parameters that do exist: {', '.join(declared) or '(none)'}"
            )
    else:
        if target.producer_of not in vocabulary.types:
            raise RuleValidationError(
                f"{path}: {target.producer_of!r} is not a declared type.\n"
                f"  Types that do exist: {', '.join(sorted(vocabulary.types))}"
            )
        for row in decision.rows:
            contract_id = str(row.then)
            if contract_id not in registry.contracts:
                raise RuleValidationError(
                    f"{path}: {contract_id!r} is not in the registry, so this row can never "
                    f"be applied. A rule table is only valid against a registry that can "
                    f"satisfy it."
                )
            produced = {p.type_id for p in registry.get(contract_id).produces}
            if target.producer_of not in produced:
                raise RuleValidationError(
                    f"{path}: {contract_id!r} does not produce {target.producer_of!r}"
                )

    for row in decision.rows:
        for measurement_id, expected in row.when.items():
            measurement = measurements.get(measurement_id)  # raises with what does exist
            if (
                isinstance(expected, str)
                and expected[:2].strip() in _OPS
                and measurement.kind not in _ORDERED
            ):
                raise RuleValidationError(
                    f"{path}: {measurement_id!r} is an {measurement.kind}, so it can only be "
                    f"compared with equality, not {expected!r}"
                )
```

- [ ] **Step 4: Rewrite the shipped rule table**

`examples/rules/rnaseq.yml`:

```yaml
version: 1
decisions:
  - decides: {param: strandedness}
    because: "featureCounts -s follows library strandedness"
    cite: "Liao et al. 2014, doi:10.1093/bioinformatics/btt656"
    rows:
      - when: {strandedness: reverse}     then: 2
      - when: {strandedness: forward}     then: 1
      - when: {strandedness: unstranded}  then: 0

  - decides: {producer_of: alignment.bam}
    because: "read length determines which aligner is appropriate"
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - when: {read_length: ">= 70"}  then: nf-core/star/align@1.11.0
      - when: {read_length: "< 70"}   then: nf-core/hisat2/align@2.2.2
```

Both aligner rows now fire. The `@2.2.2` pin is the vendored contract — the old table said `@2.2.1`,
which is exactly the class of error validation now refuses to load.

- [ ] **Step 5: Delete the dead-rule guard**

`tests/test_spine_contracts.py` holds `KNOWN_DEAD_RULES`. Its docstring says it deletes itself when
this format lands. Delete the constant and `test_no_new_dead_rules_are_shipped` — validation replaces
it, and a guard kept past its purpose is noise.

- [ ] **Step 6: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS. Tasks 5 and 6 wire `value_for` and `producer_for` into the resolver; until then
`resolve.py` still calls `rules.match`, so update that call in this task to use `value_for` and
unpack the tuple.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-resolver/ examples/rules/ tests/test_spine_contracts.py
git commit -m "feat(resolver): rules become validated decision tables"
```

---

### Task 5: Module pinning and a tier for every choice

Implements rule-tables spec §7. Closes the gap where spec §6.1 claims every module choice exits at a
tier while `IRNode` has no tier field.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/ir.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Test: `packages/mendel-resolver/tests/test_pinning.py`

**Interfaces:**
- Consumes: `RuleTable.producer_for` (Task 4)
- Produces: `IRNode.selection: ResolvedValue`; `route(goal, registry, rules=None, max_depth=10)`;
  `RouteStep.selection_tier: Tier`, `RouteStep.selection_reason: str`; `UnroutablePinError`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.ir import Tier
from mendel_resolver.router import UnroutablePinError


def test_a_sole_producer_is_structural(spine):
    ir = spine(want=["qc.report"])
    node = next(n for n in ir.nodes if n.id == "fastqc")
    assert node.selection.tier is Tier.STRUCTURAL


def test_a_rule_pinned_producer_is_data_profiled_and_cites(spine):
    ir = spine(want=["alignment.bam"], profile={"read_length": 150})
    node = next(n for n in ir.nodes if n.id == "star_align")
    assert node.selection.tier is Tier.DATA_PROFILED
    assert "Dobin" in node.selection.reason


def test_a_priority_resolved_choice_is_convention(spine):
    ir = spine(want=["alignment.bam"], profile={})
    node = next(n for n in ir.nodes if n.contract_id.startswith("nf-core/star"))
    assert node.selection.tier is Tier.CONVENTION


def test_a_pin_that_cannot_route_raises_naming_the_rule(spine_without_hisat2_index):
    with pytest.raises(UnroutablePinError, match="read_length"):
        spine_without_hisat2_index(want=["alignment.bam"], profile={"read_length": 50})
```

> The `spine` fixture builds a `Registry`, `Vocabulary`, `MeasurementRegistry` and `RuleTable` from
> `examples/` and calls `resolve`. Write it in `conftest.py` at
> `packages/mendel-resolver/tests/conftest.py` so Tasks 5–8 share it:
>
> ```python
> import pathlib
> import pytest
> from comeni_core.measurement import MeasurementRegistry
> from comeni_core.registry import Registry
> from comeni_core.vocabulary import Vocabulary
> from mendel_resolver.goal import Goal, GoalInput
> from mendel_resolver.resolve import resolve
> from mendel_resolver.rules import RuleTable
>
> ROOT = pathlib.Path(__file__).parents[3]
>
>
> @pytest.fixture
> def spine():
>     examples = ROOT / "examples"
>     vocabulary = Vocabulary.load(examples / "vocabularies")
>     registry = Registry.load(examples / "contracts", vocabulary)
>     measurements = MeasurementRegistry.load(examples / "measurements")
>     rules = RuleTable.load(
>         examples / "rules",
>         registry=registry,
>         vocabulary=vocabulary,
>         measurements=measurements,
>     )
>
>     def build(*, want, profile=None, have=("fastq.reads", "annotation.gtf")):
>         goal = Goal(
>             have=[GoalInput(type_id=t) for t in have],
>             want=want,
>             profile=profile or {},
>         )
>         return resolve(goal, registry, rules)
>
>     return build
> ```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-resolver/tests/test_pinning.py -v`
Expected: FAIL — `IRNode` has no `selection`.

- [ ] **Step 3: Add `selection` to `IRNode`**

In `ir.py`, add to `IRNode`:

```python
    selection: ResolvedValue = Field(
        default_factory=lambda: ResolvedValue(
            value=None, tier=Tier.STRUCTURAL, reason="only one contract can produce this"
        )
    )
    """How this module was chosen, at which tier, and why.

    Spec §6.1 has always said every module choice exits at exactly one tier; until this
    field existed only parameters were tiered, so a module selected because it was the sole
    producer was indistinguishable from one selected by priority.
    """
```

- [ ] **Step 4: Teach the router to pin**

In `router.py`, add `rules` to the signature and consult it before ranking:

```python
def route(goal, registry, rules=None, max_depth: int = 10) -> RoutePlan:
    ...
        candidates = [c for c in registry.producers_of(type_id, states) if c.id not in visiting]
        if not candidates:
            raise UnroutableError(f"nothing produces {type_id} with states {sorted(states)}")

        pinned = rules.producer_for(type_id, goal.profile) if rules else None
        if pinned is not None:
            contract_id, decision, row = pinned
            match = [c for c in candidates if c.id == contract_id]
            if not match:
                # Falling back would mean the rule said one thing and the pipeline did
                # another, silently — the failure this product exists to remove.
                raise UnroutablePinError(
                    f"a rule pins {contract_id} for {type_id}, but its inputs are "
                    f"unreachable from this goal. Rule condition: {row.when}"
                )
            chosen, tier, reason = match[0], Tier.DATA_PROFILED, (
                f"rule {decision.decides.key()}: {decision.cite or decision.because or ''}"
            )
        else:
            ...  # existing surplus ranking; tier is CONVENTION when several candidates
                 # existed, STRUCTURAL when exactly one did, AMBIGUOUS on a tie
```

Add `UnroutablePinError(UnroutableError)` to the same module, and carry `tier` and `reason` on
`RouteStep` so `resolve.py` can put them in `IRNode.selection`.

- [ ] **Step 5: Populate `selection` in `resolve.py`**

```python
        node = IRNode(
            id=step.node_id,
            contract_id=contract.id,
            selection=ResolvedValue(
                value=contract.id, tier=step.selection_tier, reason=step.selection_reason
            ),
        )
```

`resolve` passes `rules` through to `route`.

- [ ] **Step 6: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS. `needs_review()` already covers anything at `REQUIRED`, so a tied selection now shows
up in the CLI's review list without further change — verify that by building a registry with two
equal producers and checking the count.

- [ ] **Step 7: Commit**

```bash
git add packages/comeni-core/ packages/mendel-resolver/
git commit -m "feat(resolver): rules pin producers, and every module choice carries a tier"
```

---

### Task 6: Ports in disjunctive normal form

Implements rule-tables spec §8. A port can only express AND today; practitioners routinely mean
*"coordinate-sorted BAM or CRAM"*.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/contract.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Test: `packages/comeni-core/tests/test_alternatives.py`

**Interfaces:**
- Consumes: `InputPort`
- Produces: `Alternative(type_id: TypeId, states: frozenset[StateName])`;
  `InputPort.accepts: list[Alternative]`; `InputPort.prefer: frozenset[StateName]`;
  `InputPort.alternatives() -> list[Alternative]`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.contract import Alternative, InputPort
from comeni_core.vocabulary import Vocabulary


def test_the_single_form_is_one_alternative():
    """Existing contracts must not change. `type_id` + `state_required` is sugar."""
    port = InputPort(name="bam", type_id="alignment.bam", state_required=frozenset({"sorted"}))
    assert port.alternatives() == [
        Alternative(type_id="alignment.bam", states=frozenset({"sorted"}))
    ]


def test_accepts_declares_several_alternatives_in_order():
    port = InputPort(
        name="bam",
        accepts=[
            {"type_id": "alignment.bam", "states": ["coordinate_sorted"]},
            {"type_id": "alignment.cram", "states": ["coordinate_sorted"]},
        ],
    )
    assert [a.type_id for a in port.alternatives()] == ["alignment.bam", "alignment.cram"]


def test_a_port_declaring_both_forms_is_refused():
    with pytest.raises(ValueError, match="both"):
        InputPort(name="bam", type_id="alignment.bam", accepts=[{"type_id": "alignment.cram"}])


def test_alternatives_are_validated_against_the_vocabulary(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    vocab = Vocabulary.load(tmp_path)
    port = InputPort(
        name="bam", accepts=[{"type_id": "alignment.bam", "states": ["sorted_by_coord"]}]
    )
    with pytest.raises(Exception, match="sorted_by_coord"):
        for alternative in port.alternatives():
            vocab.validate(alternative.type_id, alternative.states)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_alternatives.py -v`
Expected: FAIL — `Alternative` does not exist.

- [ ] **Step 3: Add `Alternative` and rework `InputPort`**

```python
class Alternative(BaseModel):
    """One acceptable shape for a port: a type, and states that must all hold."""

    model_config = ConfigDict(extra="forbid")

    type_id: TypeId
    states: frozenset[StateName] = frozenset()

    @field_serializer("states")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class InputPort(BaseModel):
    name: str
    type_id: str = ""
    state_required: frozenset[str] = frozenset()
    accepts: list[Alternative] = Field(default_factory=list)
    """Ordered alternatives, ANDed within each. One level of DNF, deliberately.

    Full boolean logic would express more and cost the thing the product sells: today
    "why is SAMTOOLS_SORT here?" answers itself in a sentence, and under a general
    constraint language it becomes a solver trace.
    """
    prefer: frozenset[str] = frozenset()
    """Tiebreak *within* a matched alternative. Never causes insertion or failure.

    Does not promote a later alternative over an earlier one: alternative order is the
    author's statement of preference between kinds of input, the same way decision-table
    rows are ordered and first-match-wins.
    """
    cardinality: str = "1"

    @model_validator(mode="after")
    def _one_form(self) -> "InputPort":
        if self.type_id and self.accepts:
            raise ValueError(
                f"port {self.name!r} declares both `type_id` and `accepts`; use one"
            )
        return self

    def alternatives(self) -> list[Alternative]:
        if self.accepts:
            return self.accepts
        return [Alternative(type_id=self.type_id, states=self.state_required)]
```

Keep `state_preferred` as a deprecated alias that populates `prefer`, so no vendored contract breaks.

- [ ] **Step 4: Route over alternatives**

In `router.py`'s `satisfy`, try each alternative in declaration order and take the first that can be
satisfied; record which in the `RouteStep`. In `resolve.py`'s `_source_for`, a source qualifies if it
satisfies *any* alternative, and `prefer` breaks ties among sources satisfying the same one.

- [ ] **Step 5: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS. `ModuleContract.check_against` must validate every alternative, not just `type_id`.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/ packages/mendel-resolver/
git commit -m "feat(core): ports accept alternatives, and prefer earns its keep"
```

---

### Task 7: Measurements are types

Implements profiling spec §3. This is the step that makes profiling free: a measurement is a type
modules produce, so a profiling build is a build and the router needs no changes at all.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/vocabulary.py`
- Create: `examples/contracts/comeni/profile-fastqc.yml`, `profile-collect.yml`
- Test: `packages/comeni-core/tests/test_measurement_types.py`

**Interfaces:**
- Consumes: `MeasurementRegistry` (Task 1), `Vocabulary`
- Produces: `Vocabulary.with_measurements(registry) -> Vocabulary` adding a stateless
  `measurement.<id>` type per declaration

- [ ] **Step 1: Write the failing test**

```python
def test_every_declared_measurement_becomes_a_type(tmp_path):
    """A measurement is a type modules produce, which is what makes profiling routable."""
    from comeni_core.measurement import MeasurementRegistry
    from comeni_core.vocabulary import Vocabulary

    (m := tmp_path / "measurements").mkdir()
    (m / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
    (v := tmp_path / "vocabularies").mkdir()
    (v / "fastq.reads.yml").write_text("states: []\n")

    vocab = Vocabulary.load(v).with_measurements(MeasurementRegistry.load(m))
    assert vocab.states_for("measurement.read_length") == frozenset()
    assert vocab.states_for("fastq.reads") == frozenset()


def test_a_measurement_type_carries_no_states(tmp_path):
    from comeni_core.measurement import MeasurementRegistry
    from comeni_core.vocabulary import Vocabulary

    (m := tmp_path / "measurements").mkdir()
    (m / "strandedness.yml").write_text("kind: enum\nvalues: [forward, reverse]\n")
    vocab = Vocabulary.load([]).with_measurements(MeasurementRegistry.load(m))
    with pytest.raises(Exception):
        vocab.validate("measurement.strandedness", ["forward"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_measurement_types.py -v`
Expected: FAIL — `Vocabulary` has no `with_measurements`.

- [ ] **Step 3: Add `with_measurements`**

```python
    def with_measurements(self, registry: "MeasurementRegistry") -> "Vocabulary":
        """Derive a stateless `measurement.<id>` type per declaration.

        Derived rather than declared twice: the measurement file already says what the
        measurement is, and a second vocabulary file saying it again is a thing to drift.
        """
        types = dict(self.types)
        for measurement_id in registry.ids():
            types[f"measurement.{measurement_id}"] = frozenset()
        return Vocabulary(types=types, entry_channels=dict(self.entry_channels))
```

Import `MeasurementRegistry` under `TYPE_CHECKING` to avoid a cycle.

- [ ] **Step 4: Write two profiling contracts**

`examples/contracts/comeni/profile-fastqc.yml`:

```yaml
id: comeni/profile/fastqc@0.12.1
nf_process: FASTQC
nf_include: modules/nf-core/fastqc/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces:
  - {name: read_length, type_id: measurement.read_length, state: []}
params: []
priority: 0
nf_inputs: [{ports: [reads]}]
container: quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0
provenance: {source: hand, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-03"}
```

`examples/contracts/comeni/profile-collect.yml`:

```yaml
id: comeni/profile/collect@0.1.0
nf_process: MULTIQC
nf_include: modules/nf-core/multiqc/main
consumes: [{name: measurements, type_id: measurement.read_length, state_required: []}]
produces: [{name: profile, type_id: profile.yml, state: []}]
params: []
priority: 0
nf_inputs: [{ports: [measurements]}]
container: community.wave.seqera.io/library/multiqc:1.35--c17fb751507e9dfc
provenance: {source: hand, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-03"}
```

Add `examples/vocabularies/profile.yml.yml` containing `states: []`.

- [ ] **Step 5: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS. `test_spine_contracts.py` checks every contract against a vendored module — the two
new contracts reuse `fastqc` and `multiqc`, which are already vendored, so arity and container
assertions must still hold.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/ examples/
git commit -m "feat(core): a measurement is a type, so profiling is routable"
```

---

### Task 8: `mendel profile`

Implements profiling spec §4. Sugar over `mendel build --want measurement.*`, sharing one code path.

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Test: `tests/test_profiling.py`

**Interfaces:**
- Consumes: everything above
- Produces: CLI `mendel profile --have <type_id> --out <dir>`; a profiling build resolves with an
  **empty** `DataProfile`

- [ ] **Step 1: Write the failing test**

```python
import json
import pathlib

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent


def test_profile_emits_a_pipeline_that_measures(tmp_path):
    code = main([
        "profile", "--have", "fastq.reads",
        "--out", str(tmp_path / "p"), "--root", str(ROOT),
    ])
    assert code == 0
    source = (tmp_path / "p" / "main.nf").read_text()
    assert "FASTQC" in source


def test_profile_is_the_same_operation_as_a_measurement_build(tmp_path):
    """`mendel profile` is sugar. One resolver, one emitter, one set of records."""
    main(["profile", "--have", "fastq.reads", "--out", str(tmp_path / "a"), "--root", str(ROOT)])
    main([
        "build", "--goal", str(_goal_file(tmp_path)),
        "--out", str(tmp_path / "b"), "--root", str(ROOT),
    ])
    assert (tmp_path / "a" / "main.nf").read_text() == (tmp_path / "b" / "main.nf").read_text()


def _goal_file(tmp_path):
    path = tmp_path / "g.yml"
    path.write_text(
        "have: [{type_id: fastq.reads}]\nwant: [measurement.read_length]\n"
    )
    return path


def test_a_profiling_build_resolves_against_an_empty_profile(tmp_path):
    """Otherwise profiling needs a profile, which is the regress this rule stops."""
    main(["profile", "--have", "fastq.reads", "--out", str(tmp_path / "p"), "--root", str(ROOT)])
    ir = json.loads((tmp_path / "p" / "pipeline.ir.json").read_text())
    tiers = {b["value"]["tier"] for n in ir["nodes"] for b in n["params"]}
    assert 3 not in tiers, "a profiling build must not resolve anything at tier 3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_profiling.py -v`
Expected: FAIL — argparse rejects `profile` as a command.

- [ ] **Step 3: Add the verb**

In `cli.py`, add `"profile"` to the command choices and `--have` (repeatable). When the command is
`profile`, construct the goal in memory rather than reading one:

```python
    if args.command == "profile":
        # Sugar for `build --want measurement.*`. One resolver, one emitter, one set of
        # decision records — the verb exists for discoverability, not as a second path.
        #
        # An empty profile is the rule that stops the regress: a build resolves tier-3
        # parameters against a profile, and a profiling build is a build. Profiling
        # contracts therefore resolve at tiers 1, 2 and 4 only.
        goal = Goal(
            have=[GoalInput(type_id=t) for t in args.have],
            want=[f"measurement.{m}" for m in measurements.ids()],
            profile={},
        )
```

- [ ] **Step 4: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-compiler/ tests/test_profiling.py
git commit -m "feat(compiler): mendel profile, sugar over a measurement build"
```

---

### Task 9: Generated type stubs

Implements rule-tables spec §6.6. Derived, never authoritative, and safe when stale — which is what
makes generation acceptable here when it was not before.

**Files:**
- Create: `tools/generate_types.py`
- Create: `packages/mendel-resolver/src/mendel_resolver/goal.pyi`
- Test: `tests/test_generated_types.py`

**Interfaces:**
- Consumes: `MeasurementRegistry` (Task 1)
- Produces: `generate_stub(registry) -> str`

- [ ] **Step 1: Write the failing test**

```python
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent.parent


def test_the_committed_stub_matches_the_declarations():
    """Staleness is safe — a stale stub costs autocomplete, never correctness — which is
    exactly why nobody would notice it rotting. CI notices."""
    result = subprocess.run(
        [sys.executable, "tools/generate_types.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_stub_types_each_declared_measurement():
    stub = (ROOT / "packages/mendel-resolver/src/mendel_resolver/goal.pyi").read_text()
    assert 'Literal["read_length"]' in stub
    assert "-> int | None" in stub
    assert 'Literal["forward", "reverse", "unstranded"] | None' in stub
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_generated_types.py -v`
Expected: FAIL — `tools/generate_types.py` does not exist.

- [ ] **Step 3: Write the generator**

```python
"""Declarations to a typed stub. Derived, never authoritative.

`DataProfile.get` returns a union at runtime because the value type depends on the
measurement, and the declaration knows more than Python does. `Literal` overloads close
that gap for every editor and type checker — PEP 561 stubs work in mypy, pyright, Pylance
and PyCharm alike, where a mypy plugin would work only in mypy and therefore not in
Pylance, which is what most people actually use.

A stale stub costs autocomplete and never correctness, which is the property that makes
generation safe here. `--check` is what stops it rotting unnoticed.
"""

import sys
from pathlib import Path

from comeni_core.measurement import MeasurementKind, MeasurementRegistry

ROOT = Path(__file__).parent.parent
STUB = ROOT / "packages/mendel-resolver/src/mendel_resolver/goal.pyi"

_RETURN = {
    MeasurementKind.INTEGER: "int | None",
    MeasurementKind.NUMBER: "float | None",
    MeasurementKind.BOOLEAN: "bool | None",
}


def generate_stub(registry: MeasurementRegistry) -> str:
    lines = [
        "# Generated by tools/generate_types.py. Do not edit.",
        "# Derived from examples/measurements/. Stale costs autocomplete, never correctness.",
        "from typing import Literal, overload",
        "",
        "class DataProfile:",
    ]
    for measurement_id in registry.ids():
        measurement = registry.get(measurement_id)
        if measurement.kind is MeasurementKind.ENUM:
            values = ", ".join(f'"{v}"' for v in measurement.values)
            returns = f"Literal[{values}] | None"
        else:
            returns = _RETURN[measurement.kind]
        lines += [
            "    @overload",
            f'    def get(self, measurement_id: Literal["{measurement_id}"]) -> {returns}: ...',
        ]
    lines += [
        "    @overload",
        "    def get(self, measurement_id: str) -> int | float | bool | str | None: ...",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    registry = MeasurementRegistry.load(ROOT / "examples" / "measurements")
    generated = generate_stub(registry)
    if "--check" in sys.argv:
        current = STUB.read_text() if STUB.exists() else ""
        if current != generated:
            print("goal.pyi is stale — run: uv run python tools/generate_types.py")
            return 1
        return 0
    STUB.write_text(generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate and read the stub**

```bash
uv run python tools/generate_types.py
cat packages/mendel-resolver/src/mendel_resolver/goal.pyi
```

Read it before committing. A generated file committed without being read is the same mistake as a
golden file committed without being read — which produced two include statements on one line the
first time it happened here.

- [ ] **Step 5: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS. Add `tools/` to ruff's excludes only if it complains about the stub itself; the
generator is ordinary code and should lint.

- [ ] **Step 6: Commit**

```bash
git add tools/generate_types.py packages/mendel-resolver/src/mendel_resolver/goal.pyi \
        tests/test_generated_types.py
git commit -m "feat: generated type stubs for declared measurements"
```

---

### Task 10: Profile provenance end to end

Implements profiling spec §5.1. A generated profile records which tool produced each value; a
hand-written one records nothing, and that *is* the assertion.

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Test: `tests/test_profiling.py`

**Interfaces:**
- Consumes: `Measured` (Task 2)
- Produces: `mendel profile` writes `profile.yml` with `{value, source, by}` per measurement

- [ ] **Step 1: Write the failing test**

```python
def test_a_generated_profile_records_its_tool(tmp_path):
    import yaml

    main(["profile", "--have", "fastq.reads", "--out", str(tmp_path / "p"), "--root", str(ROOT)])
    profile = yaml.safe_load((tmp_path / "p" / "profile.yml").read_text())
    entry = profile["measurements"]["read_length"]
    assert entry["source"] == "measured"
    assert entry["by"].startswith("comeni/profile/")


def test_a_hand_written_profile_is_asserted():
    """A scalar in a file a person wrote is an assertion by that person."""
    from comeni_core.tiers import ValueSource
    from mendel_resolver.goal import DataProfile

    assert DataProfile(read_length=150).measurements[0].source is ValueSource.GOAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_profiling.py -v`
Expected: FAIL — no `profile.yml` is written.

- [ ] **Step 3: Add `MEASURED` and write the file**

Add `MEASURED = "measured"` to `ValueSource` in `tiers.py`, then in `cli.py`, after resolving a
profiling build, write `profile.yml` naming the contract that produces each measurement type:

```python
    if args.command == "profile":
        produced = {
            port.type_id.removeprefix("measurement."): registry.get(node.contract_id).id
            for node in ir.nodes
            for port in registry.get(node.contract_id).produces
            if port.type_id.startswith("measurement.")
        }
        (args.out / "profile.yml").write_text(
            yaml.safe_dump(
                {
                    "measurements": {
                        k: {"value": None, "source": "measured", "by": v}
                        for k, v in sorted(produced.items())
                    }
                },
                sort_keys=True,
            )
        )
```

> `value: None` is deliberate and honest: the pipeline has been *emitted*, not run. The laboratory
> runs it and the collector fills the values in. Anything else would be Mendel claiming to know a
> number it has never seen, which is the whole thing invariant 15 exists to prevent.

- [ ] **Step 4: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-compiler/ packages/comeni-core/ tests/test_profiling.py
git commit -m "feat(compiler): profile.yml carries provenance per measurement"
```

---

### Task 11: `ARCHITECTURE.md`, written against real types

Last on purpose. `CLAUDE.md` defers Plan 2.5 for the same reason — a document written against
predicted types drifts, and this plan changed the rule format, the profile, ports and module tiering,
which is most of what an architecture document describes.

**Files:**
- Create: `ARCHITECTURE.md`
- Modify: `CLAUDE.md`, `README.md`

**Interfaces:**
- Consumes: everything
- Produces: documentation

- [ ] **Step 1: Verify the whole thing works before describing it**

```bash
uv sync
uv run pytest -v
uv run ruff check .
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
uv run mendel profile --have fastq.reads --out profile-build/
```

Expected: all green, `gate stub: PASS`. Describe what this produced, not what the plan predicted.

- [ ] **Step 2: Write `ARCHITECTURE.md`**

Cover, with real type names read from the code:

1. **The five stages** — `Goal` → `RoutePlan` → `PipelineIR` → `main.nf` + `nextflow.config` →
   `GateResult`, and that `cli.py` is the only thing touching disk
2. **Declared data** — vocabularies, measurements, contracts, rule tables; what each declares and
   why closed vocabularies make routing provable
3. **Routing** — backward chaining, the three rules that make it terminate and stay honest (a
   contract cannot satisfy its own input; smallest surplus wins; a tie is ambiguity)
4. **The four tiers**, and that `selection` gives module choices one too
5. **Ports versus channels** — the distinction that made `nf_inputs` necessary, with the table
   showing only one of six spine processes matches its port count
6. **The guards** — `test_purity.py`, `test_egress.py`, `test_construction.py`: what each asserts,
   and that all three exist because an audit defeated their earlier versions
7. **Where Plan 2 plugs in** — the three ports, unchanged by this plan

- [ ] **Step 3: Update `CLAUDE.md` and `README.md`**

`CLAUDE.md`: the two specs move from "approved, unimplemented" to implemented; the tier table's claim
about module choices becomes true; add `ARCHITECTURE.md` to the reading table.

`README.md`: the "not built yet" list loses measurements and rule tables; link `ARCHITECTURE.md`.

- [ ] **Step 4: Commit**

```bash
git add ARCHITECTURE.md CLAUDE.md README.md
git commit -m "docs: ARCHITECTURE.md, written against the types that exist"
```

---

## Self-Review

**Spec coverage.**

| Spec section | Task |
|---|---|
| rules §3–4 format and matching | 4 |
| rules §5 validation against the registry | 4 |
| rules §6.2–6.4 measurement declarations | 1 |
| rules §6.5 `DataProfile` as a validated map | 2, 3 |
| rules §6.6 generated types | 9 |
| rules §6.7 layered vocabularies | **already done** — audit D3 |
| rules §7 module pinning and selection tiers | 5 |
| rules §8 ports in DNF | 6 |
| rules §9 layer composition for rules | 4 (whole-block replacement in `load`) |
| profiling §3 measurements as types | 7 |
| profiling §4 `mendel profile` | 8 |
| profiling §5.1 provenance | 2, 10 |
| profiling §5.2 `sealed` blocks asserted | **Plan 2** — needs `ProfilePolicy` |
| profiling §6 the regress | 8 |
| profiling §7 execution | nothing to build |

**Placeholder scan.** No TBDs. Every code step contains runnable code. Task 5's router step shows the
pinning branch and points at the existing ranking rather than repeating forty unchanged lines — the
one place I have relied on the reader looking at the current file.

**Type consistency.** `MeasurementRegistry.load` takes `Path | Sequence[Path]`, matching
`Vocabulary.load` and `Registry.load`. `RuleTable.load` gains keyword-only `registry`, `vocabulary`,
`measurements` and every caller in Tasks 5, 8 and the conftest passes all three. `ValueSource` gains
`MEASURED` in Task 10 and is used in Tasks 2 and 10 only. `DataProfile.get` is the accessor
throughout; `profile.read_length` appears nowhere after Task 2.

**Known debt, stated rather than hidden.** Task 2 puts `MeasurementRegistry.profile` in
`comeni-core` with a function-local import of `mendel_resolver.goal`, because `comeni-core` must not
depend on `mendel-resolver`. The clean fix is moving `DataProfile` into `comeni-core` beside the
measurements it is made of. That is a bigger change than this plan should carry, and it is the one
piece of debt knowingly left.

---

## Verification

```bash
uv sync
uv run pytest -v
uv run ruff check .
uv run python tools/generate_types.py --check
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
uv run mendel profile --have fastq.reads --out profile-build/
```

Complete when the stub gate passes, `mendel profile` emits a pipeline that measures, and both
aligner rows in `examples/rules/rnaseq.yml` can fire — which is the thing that has never been true.
