# Samples 4 — inspecting an upload, in the API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person answering a gap can upload one sample (a file or a pair); the API checks the protection level, finds the format that confirms it, runs the inspection in its own process with hard limits, and records every decided fact as **measured**, naming its pieces — and the vocabulary endpoint says, for every measurement, who can measure it and where that runs.

**Architecture:** `services/protection.py` answers *may this cross?* from the `privacy.protection` setting, whose level 0 is now built. `services/measurers.py` builds the who-measures-what index from inspector pieces (trusted layers only) and profiler contracts. `services/inspect.py` matches a file to its pieces by extension, launches `comeni_inspect.run` as a subprocess (time, memory and unpacked-size limits; bytes on stdin; one JSON report back) and turns every failure into an answer. `authoring.answer_with_sample` records the facts the way a click records one. The route `POST …/samples` ties them together. Sample bytes live only in memory for the inspection.

**Tech Stack:** FastAPI (multipart `UploadFile`), `subprocess` + `resource` (Linux `RLIMIT_AS`), pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-samples-and-inspectors-design.md` §2 (trusted layers), §7, §8, §9, §10 (the route, the protection setting). Part 14.7.6.4 of #134. Depends on parts 2 and 3.

## Global Constraints

- **An inspection never fails the request:** a timeout, a crash, a bomb, a non-zero exit, an unparseable report are each an `unreadable` answer with a reason, never a 500 (spec §8).
- **Nothing guessed:** no extension match → *nothing reads this type yet*; several formats confirm → a tie the person decides; an undetermined fact is shown and not recorded (spec §5, §7).
- **The file's name never enters the goal or `pipeline.yml`**, and is never sent to a model (it can name a patient). `Fact.sample` stays `None`.
- **Only level 0's row is implemented.** Every other level refuses the crossing with a declared code (spec §6 of the consultant spec, unchanged).
- **Pieces run only from trusted layers** (spec §2): the base layer by default; `MENDEL_TRUSTED_LAYERS` names more.
- Diagnostics declared in `diagnostics.yml`, emitted with `coded()`; the page regenerated.
- Run Python tests from the repository root; database tests need the throwaway Postgres (`CLAUDE.md` *Gotchas*).
- Comments and docstrings match the repository's style. A loop is not an assertion.

## Rulings against the spec, for the operator

1. **Sample bytes are not stored.** The spec (§10) stores the head under `workspace/samples/<session>/` and deletes it *with the session* — but nothing deletes a session today (`services/authoring.py` has no delete, and `models.py` forbids cascades), so "with the session" would mean *forever*. This plan keeps the bytes in memory for the inspection only. 14.7.7 (the characteriser reads the head) decides whether and how a head is kept, with a real deletion. Cost if wrong: a write to disk and a sweep, added in 14.7.7.
2. **The steps the card shows are the steps taken, returned with the answer**, not streamed while they happen: an inspection is one short request (the speed budget is under a second), so the card shows *inspecting…* and then the steps that ran. Streaming is a later change if a slow format arrives. Cost if wrong: a progress channel.

## Review Focus

1. **An upload of three files**, or of zero: refused with a declared code before anything is read. Pinned in Task 5.
2. **A 2 GB file**: only the first 4 MB is ever read from the request stream; the rest is never buffered. Pinned in Task 5.
3. **A sample answering a gap that was already answered** (two tabs): the second upload is refused like a duplicate click (MI0203), its facts not recorded twice. Pinned in Task 4.
4. **A measured fact for a measurement the session already knows** (the person said 150, the file says 151): the person's word stays; the inspection reports the disagreement and records nothing over it. Pinned in Task 4.
5. **The runner process left behind** after a timeout: it is killed, never orphaned. Pinned in Task 3.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `packages/comeni-core/src/comeni_core/settings/declare.py` | `ChoiceOption.designed` |
| Modify `packages/comeni-core/src/comeni_core/settings/catalogue.py` | `PROTECTION` built at level 0, env `COMENI_PROTECTION_LEVEL` |
| Modify `packages/comeni-core/src/comeni_core/settings/installation.py` | refuse a designed option (MI0303) |
| Modify `frontend/src/preferences/SettingRow.tsx` | a designed option drawn greyed with its reason |
| Create `packages/mendel-api/src/mendel_api/services/protection.py` | `Crossing`, `allows()` |
| Modify `packages/comeni-core/src/comeni_core/declared/inspection.py` | `InspectionCatalogue.origin` (layer index per piece) |
| Modify `packages/mendel-api/src/mendel_api/settings.py` | `trusted_layers` |
| Create `packages/mendel-api/src/mendel_api/services/measurers.py` | `Measurer`, `index()`, `trusted()` |
| Create `packages/mendel-api/src/mendel_api/services/inspect.py` | `match()`, `launch()`, `inspect_sample()`, `Inspection` |
| Modify `packages/mendel-api/src/mendel_api/authoring/types.py` | `Fact.pieces`, `Fact.evidence` |
| Modify `packages/mendel-api/src/mendel_api/services/authoring.py` | `upload` option; `answer_with_sample`; `_SOURCE[MEASURED]`; pieces into `compose_goal` |
| Modify `packages/mendel-api/src/mendel_api/routes/authoring.py` | `POST /{session_id}/samples`; `measurers` on the vocabulary |
| Modify `packages/comeni-core/src/comeni_core/diagnostics.yml` | MI0213–MI0215, MI0303 |
| Tests: `packages/comeni-core/tests/test_settings_*.py`, `packages/mendel-api/tests/test_protection.py`, `test_measurers.py`, `test_inspect.py`, `test_authoring_samples.py` | |

---

### Task 1: Protection level 0 is built

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/settings/declare.py:66-70`, `catalogue.py:194-210`, `installation.py` (`put`)
- Create: `packages/mendel-api/src/mendel_api/services/protection.py`
- Modify: `frontend/src/preferences/SettingRow.tsx` (the choice control)
- Test: `packages/comeni-core/tests/test_settings_catalogue.py`, `packages/comeni-core/tests/test_settings_installation.py`, `packages/mendel-api/tests/test_protection.py`, `frontend/src/preferences/SettingRow.test.tsx`

**Interfaces:**
- Produces: `ChoiceOption.designed: str | None = None` (why the option is not built); `protection.Crossing` (`UPLOAD`, `CHARACTERISE`, `DOOR_6`); `protection.level() -> str`; `protection.allows(crossing) -> bool`; `protection.refuse(crossing) -> str` (the coded MI0213 message).

- [x] **Step 1: Write the failing tests**

```python
# packages/comeni-core/tests/test_settings_catalogue.py (add)
def test_protection_level_0_is_built_and_the_others_are_designed():
    from comeni_core.settings.catalogue import PROTECTION

    assert PROTECTION.unavailable is None
    assert PROTECTION.env == "COMENI_PROTECTION_LEVEL"
    designed = {o.value for o in PROTECTION.options if o.designed}
    assert designed == {"open", "guarded", "sealed"}
    assert PROTECTION.default == "level_0"


def test_a_default_cannot_be_a_designed_option():
    import pytest
    from comeni_core.settings.declare import Setting

    with pytest.raises(ValueError):
        Setting.choice(key="x.y", label="Y", help="Helps. A lot.", default="b",
                       options=[("a", "A"), ("b", "B")], designed={"b": "issue 1"})
```

```python
# packages/comeni-core/tests/test_settings_installation.py (add, in the module's style)
def test_putting_a_designed_option_is_refused():
    inst = _installation()  # the module's existing helper over an in-memory store
    with pytest.raises(SettingLocked, match="MI0303"):
        inst.put("privacy.protection", "sealed", by="ana")
```

```python
# packages/mendel-api/tests/test_protection.py
from mendel_api.services import protection


def test_level_0_allows_every_crossing(monkeypatch):
    monkeypatch.setattr(protection, "level", lambda: "level_0")
    assert all(protection.allows(c) for c in protection.Crossing)


def test_any_other_level_refuses_with_a_code(monkeypatch):
    monkeypatch.setattr(protection, "level", lambda: "sealed")
    assert not protection.allows(protection.Crossing.UPLOAD)
    assert "MI0213" in protection.refuse(protection.Crossing.UPLOAD)
```

```tsx
// frontend/src/preferences/SettingRow.test.tsx (add, in the file's style)
it("draws a designed option greyed, with why", () => {
  renderRow(choiceEntry({ options: [
    { value: "level_0", label: "Level 0", designed: null },
    { value: "sealed", label: "Sealed", designed: "issue 71" },
  ] }));
  const sealed = screen.getByLabelText("Sealed") as HTMLInputElement;
  expect(sealed.disabled).toBe(true);
  expect(screen.getByText(/issue 71/)).toBeTruthy();
});
```

(Read `SettingRow.test.tsx` first and use its existing render helper and entry builder; the names above stand for them.)

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest packages/comeni-core/tests/test_settings_catalogue.py packages/comeni-core/tests/test_settings_installation.py packages/mendel-api/tests/test_protection.py -q; cd frontend && npx vitest run src/preferences/SettingRow.test.tsx`
Expected: FAIL on each.

- [x] **Step 3: Implement**

`declare.py`: `ChoiceOption.designed: str | None = None`; `Setting.choice(..., designed: dict[str, str] | None = None)` sets it per option; the validator refuses a default whose option is designed (*"a default must be built"*).

`catalogue.py`:

```python
PROTECTION = Setting.choice(
    key="privacy.protection",
    label="Protection level",
    help=(
        "How much of your data a model may see. Level 0 lets you upload a sample, measured on "
        "this server, and a model may read it. Open, guarded and sealed send less, down to "
        "nothing at all."
    ),
    env="COMENI_PROTECTION_LEVEL",
    options=[
        ("level_0", "Level 0: a sample may be uploaded and read"),
        ("open", "Open"),
        ("guarded", "Guarded"),
        ("sealed", "Sealed"),
    ],
    designed={o: "designed, not built (issue 71)" for o in ("open", "guarded", "sealed")},
    default="level_0",
)
```

(Check how `Setting` names its env field — `env=` above stands for it; read the factory.) Regenerate the settings golden (`packages/comeni-core/tests/golden/settings-menu.json`) the way its test says, then `make client`.

`installation.py` `put`: for a choice whose option is `designed`, raise `SettingLocked(coded("MI0303", f"{key}: {value} is {option.designed}"))`. Declare `MI0303` in `diagnostics.yml` (MI0300's shape; says *"a setting's option is designed and cannot be chosen yet"*).

`protection.py`:

```python
"""May this cross? The protection level, asked at every crossing (spec §6, consultant spec §6).

**Only level 0's row is implemented.** Level 0 lets a sample be uploaded and a model read it;
every other level refuses each crossing with MI0213, so tightening is filling in a row, never a
crossing that forgot to ask.
"""

from enum import StrEnum

from comeni_core.diagnostics import coded
from comeni_core.settings.catalogue import PROTECTION

from mendel_api.services.installation import installation


class Crossing(StrEnum):
    UPLOAD = "upload"            # a sample's head reaches this server (14.7.6)
    CHARACTERISE = "characterise"  # a model reads a sample's head (14.7.7)
    DOOR_6 = "door_6"            # the characterise payload leaves (14.7.7)


_ALLOWED = {"level_0": frozenset(Crossing)}


def level() -> str:
    return str(installation().get(PROTECTION))


def allows(crossing: Crossing) -> bool:
    return crossing in _ALLOWED.get(level(), frozenset())


def refuse(crossing: Crossing) -> str:
    return coded("MI0213", f"the protection level is {level()}, which does not allow {crossing.value}")
```

Declare `MI0213` (*"the protection level does not allow this crossing"*, `refuses: true`).

`SettingRow.tsx`: in the segmented radiogroup, an option with `designed` is `disabled`, drawn with the greyed token, and its reason shown under the group (one line per designed option, or one joined line). `make client` first so the type carries `designed`.

- [x] **Step 4: Run them to see them pass**

Run: the Step 2 commands, then `uv run python tools/generate_diagnostics_doc.py`.
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add packages/comeni-core packages/mendel-api/src/mendel_api/services/protection.py packages/mendel-api/tests/test_protection.py frontend docs/handbook/reference/diagnostics.md
git commit -m "feat(settings): protection level 0 is built; the others say they are designed (#134)"
```

---

### Task 2: Who measures what, from trusted layers

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/inspection.py` (`origin`)
- Modify: `packages/mendel-api/src/mendel_api/settings.py` (`trusted_layers`)
- Create: `packages/mendel-api/src/mendel_api/services/measurers.py`
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py` (`AuthoringVocabulary.measurers`)
- Test: `packages/mendel-api/tests/test_measurers.py`

**Interfaces:**
- Produces:
  - `InspectionCatalogue.origin: dict[str, int]` keyed `"codec:<id>"`, `"format:<id>"`, `"measure:<id>"` → layer index (from each `Stacked.origin`).
  - `settings.trusted_layers: list[int] = [0]` (`MENDEL_TRUSTED_LAYERS`, JSON list of layer indexes; the base layer by default).
  - `measurers.Measurer(measurement: str, kind: Literal["inspector","profiler"], by: str, runs: Literal["server","lab","browser"], trusted: bool)`; `by` is `"fastq@1.0.0 + read_length@1.0.0"` or a contract id.
  - `measurers.index(stack) -> list[Measurer]` sorted by `(measurement, kind, by)`; `measurers.usable_pieces(stack) -> InspectionCatalogue` (trusted only).
  - `AuthoringVocabulary.measurers: list[MeasurerView]` (same fields).

- [x] **Step 1: Write the failing tests**

```python
# packages/mendel-api/tests/test_measurers.py
from mendel_api.services import measurers, registry


def test_read_length_is_measured_by_an_inspector_and_a_profiler():
    found = [m for m in measurers.index(registry.stack()) if m.measurement == "read_length"]
    kinds = {(m.kind, m.runs) for m in found}
    assert ("inspector", "server") in kinds and ("profiler", "lab") in kinds
    inspector = next(m for m in found if m.kind == "inspector")
    assert inspector.by == "fastq@1.0.0 + read_length@1.0.0" and inspector.trusted


def test_a_piece_from_an_untrusted_layer_is_listed_and_not_usable(monkeypatch):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "trusted_layers", [])
    stack = registry.stack()
    assert all(not m.trusted for m in measurers.index(stack) if m.kind == "inspector")
    assert measurers.usable_pieces(stack).formats == {}


def test_the_vocabulary_serves_the_index(client):
    body = client.get("/api/pipeline/authoring/vocabulary").json()
    assert any(m["measurement"] == "paired" and m["kind"] == "inspector" for m in body["measurers"])
```

(`client` is the API test client fixture the route tests use; read `test_authoring_routes.py` for its name.)

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest packages/mendel-api/tests/test_measurers.py -q`
Expected: FAIL — no module `measurers`.

- [x] **Step 3: Implement**

`inspection.py`: `InspectionCatalogue.origin: dict[str, int] = {}`, filled in `layers.py` from the three `Stacked.origin` maps when the catalogue is built (and carried through `check`).

`measurers.py`: for each trusted-or-not measure piece, pair it with every format whose `record` equals the measure's `record` (one row per format × measure), `by = f"{fmt.id}@{fmt.version} + {m.id}@{m.version}"`, `runs = fmt.runs`, `trusted = origin of both in settings.trusted_layers`. For each contract whose `produces` names `measurement.<id>`, a `profiler` row, `runs = "lab"`, `trusted = True`. `usable_pieces` returns a catalogue holding only trusted codecs, formats and measures.

Route: add `measurers: list[MeasurerView]` to `AuthoringVocabulary` and fill it in `vocabulary()`. `make client`.

- [x] **Step 4: Run them to see them pass**

Run: `uv run pytest packages/mendel-api/tests/test_measurers.py packages/mendel-api/tests/test_openapi.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add packages/comeni-core/src/comeni_core/declared/inspection.py packages/mendel-resolver/src/mendel_resolver/layers.py packages/mendel-api frontend/src/api frontend/openapi.json
git commit -m "feat(api): who measures what, and inspector pieces only from trusted layers (#134)"
```

---

### Task 3: The inspection service — match, launch with limits, answer

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/inspect.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (none: outcomes are answers, not codes)
- Test: `packages/mendel-api/tests/test_inspect.py`

**Interfaces:**
- Consumes: `measurers.usable_pieces(stack)`; `comeni_inspect.wire` (`Request`, `PieceRef`, `FileHead`, `Report`, `write_request`).
- Produces:
  - `HEAD_BYTES = 4 * 2**20`; `CAP_BYTES = 16 * 2**20`; `TIMEOUT_S = 5.0`; `MEMORY_BYTES = 512 * 2**20`.
  - `Inspection(outcome: Literal["measured","unreadable","no_inspector","tie"], type_id: str | None, facts: list[InspectedFact], reason: str | None, steps: list[str])` with `InspectedFact(measurement, value=None, undetermined: str | None = None, pieces: list[str], evidence: dict)`.
  - `match(names: list[str], pieces) -> tuple[CodecPiece | None, list[FormatPiece]]` — every file must give the same answer, else `no_inspector`.
  - `launch(request, payloads) -> wire.Report`.
  - `inspect_sample(files: list[tuple[str, bytes]], stack) -> Inspection`.

- [x] **Step 1: Write the failing tests**

```python
# packages/mendel-api/tests/test_inspect.py
"""Inspecting a sample: the right pieces, hard limits, and every failure an answer."""

import gzip
import sys

import pytest
from mendel_api.services import inspect, registry
from support.paths import ROOT

FIX = ROOT / "registry/inspectors/formats/fastq/piece/fixtures"


def _files(case):
    return [(p.name, p.read_bytes()) for p in sorted((FIX / case).iterdir()) if p.name != "expected.json"]


def test_a_gzipped_pair_is_measured():
    got = inspect.inspect_sample(_files("pair_150"), registry.stack())
    assert got.outcome == "measured" and got.type_id == "fastq.reads"
    facts = {f.measurement: f for f in got.facts}
    assert facts["paired"].value is True and facts["read_length"].value == 150
    assert facts["read_length"].pieces == ["fastq@1.0.0", "read_length@1.0.0"]


def test_an_unknown_extension_has_no_inspector():
    got = inspect.inspect_sample([("reads.bam", b"BAM\x01")], registry.stack())
    assert got.outcome == "no_inspector" and "nothing reads" in got.reason


def test_fasta_named_fastq_is_unreadable_with_why():
    got = inspect.inspect_sample(_files("fasta_named_fastq"), registry.stack())
    assert got.outcome == "unreadable" and "does not start like" in got.reason


def test_a_hang_is_unreadable_and_the_process_is_gone(monkeypatch):
    monkeypatch.setattr(inspect, "TIMEOUT_S", 0.5)
    monkeypatch.setattr(inspect, "_command", lambda: [sys.executable, "-c", "import time; time.sleep(30)"])
    got = inspect.inspect_sample(_files("few"), registry.stack())
    assert got.outcome == "unreadable" and got.reason == "took too long"


def test_a_crash_is_unreadable(monkeypatch):
    monkeypatch.setattr(inspect, "_command", lambda: [sys.executable, "-c", "raise SystemExit(3)"])
    got = inspect.inspect_sample(_files("few"), registry.stack())
    assert got.outcome == "unreadable" and "stopped" in got.reason


def test_a_bomb_is_unreadable():
    bomb = gzip.compress(b"@r\n" + b"A" * (64 * 2**20))
    got = inspect.inspect_sample([("b.fq.gz", bomb[: inspect.HEAD_BYTES])], registry.stack())
    assert got.outcome == "unreadable" and got.reason == "too large unpacked"


def test_the_steps_taken_are_returned():
    got = inspect.inspect_sample(_files("pair_150"), registry.stack())
    assert got.steps[0].startswith("read the first") and any("FASTQ" in s for s in got.steps)
```

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest packages/mendel-api/tests/test_inspect.py -q`
Expected: FAIL — no module `inspect` in `mendel_api.services`.

- [x] **Step 3: Implement**

```python
def _command() -> list[str]:
    """The runner. A seam: the tests put a sleeping or crashing process here."""
    return [sys.executable, "-m", "comeni_inspect.run"]


def _limit_memory() -> None:
    """Run in the child before exec: a parser that allocates past this dies, alone (spec §8)."""
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))


def launch(request: wire.Request, payloads: list[bytes]) -> wire.Report:
    """One inspection in its own process. **Every failure is an answer**, never an exception."""
    buffer = io.BytesIO()
    wire.write_request(buffer, request, payloads)
    try:
        done = subprocess.run(
            _command(), input=buffer.getvalue(), capture_output=True,
            timeout=TIMEOUT_S, preexec_fn=_limit_memory, check=False,
        )
    except subprocess.TimeoutExpired:
        # `run` kills the child on timeout before raising, so nothing is left behind.
        return wire.Report(type_id=None, facts={}, unreadable="took too long")
    if done.returncode != 0:
        return wire.Report(type_id=None, facts={}, unreadable=f"the inspector stopped (exit {done.returncode})")
    try:
        return wire.Report.model_validate_json(done.stdout)
    except ValueError:
        return wire.Report(type_id=None, facts={}, unreadable="the inspector's report could not be read")
```

`match(names, pieces)`: for each name, strip a codec extension (`.gz` → the `gzip` codec) and find formats whose `extensions` contain the remaining suffix (`.fq`, `.fastq`; compare lower-cased, longest suffix first). Files that disagree, or none → `(None, [])`.

`inspect_sample(files, stack)`:
1. `steps = [f"read the first {HEAD_BYTES // 2**20} MB of {len(files)} file(s)"]`.
2. `pieces = measurers.usable_pieces(stack)`; `codec, formats = match(...)`; none → `no_inspector`, reason *"nothing reads this type yet"*.
3. For each candidate format, build a `Request` with every trusted measure whose `record` matches (`PieceRef.path` = the absolute entry path in the layer: `settings.registry_root / "inspectors/formats/<id>" / entry`), `cap_bytes=CAP_BYTES`, and `launch`. Append `"unpacked gzip"` when a codec ran and `f"confirmed {fmt.id.upper()}"` when the report is not unreadable.
4. Exactly one confirms → `measured`, `type_id = fmt.reads[0]`, facts from the report, `steps.append(f"measured {n} fact(s)")`. None → the first report's `unreadable` reason. Several → `tie`, reason naming them.

- [x] **Step 4: Run them to see them pass**

Run: `uv run pytest packages/mendel-api/tests/test_inspect.py -q`
Expected: PASS. Then record the measured wall time of `test_a_gzipped_pair_is_measured` in the execution record.

- [x] **Step 5: Commit**

```bash
git add packages/mendel-api/src/mendel_api/services/inspect.py packages/mendel-api/tests/test_inspect.py
git commit -m "feat(api): inspect a sample in its own process, every failure an answer (#134)"
```

---

### Task 4: An upload answers a gap

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py:211-226` (`Fact`)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py` (`_gap_options`, `_SOURCE`, `compose_goal`, new `answer_with_sample`)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (MI0214)
- Test: `packages/mendel-api/tests/test_authoring_samples.py`

**Interfaces:**
- Consumes: `inspect.Inspection`; `measurers.index`; part 3's `MeasuredEntry`, `Evidence`.
- Produces: `Fact.pieces: list[str] = []`, `Fact.evidence: dict | None = None`; option id `upload` on a gap whose subject a trusted inspector measures (measurement) or reads (input), replacing `not_sure` there; `authoring.answer_with_sample(proposal_id: str, inspection: Inspection, *, by: str) -> SampleAnswer(phase, recorded: list[str], kept: list[str], disagreed: list[str])`.

- [x] **Step 1: Write the failing tests** (database tests, in `test_authoring_gathering.py`'s style; copy its `clean` fixture and `_gathering` helper)

```python
# packages/mendel-api/tests/test_authoring_samples.py
def _measured(**values):
    return inspect.Inspection(
        outcome="measured", type_id="fastq.reads", reason=None, steps=[],
        facts=[inspect.InspectedFact(measurement=k, value=v, pieces=["fastq@1.0.0", f"{k}@1.0.0"], evidence={"records": 2000})
               for k, v in values.items()],
    )


def test_a_measurement_gap_offers_upload_in_place_of_not_sure(clean):
    sid = _gathering(["counts.matrix"])
    options = _payload(_pending_for(sid, "read_length"))["options"]
    assert "upload" in options and "not_sure" not in options


def test_an_upload_records_every_decided_fact_as_measured(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")  # answer gaps until read_length is offered
    answer = authoring.answer_with_sample(pid, _measured(read_length=150, paired=True), by="ana")
    facts = _facts(sid)
    rl = next(f for f in facts if f["subject"] == "read_length")
    assert rl["source"] == "measured" and rl["value"] == 150 and rl["pieces"] == ["fastq@1.0.0", "read_length@1.0.0"]
    assert set(answer.recorded) == {"read_length", "paired"}
    assert all(f.get("sample") is None for f in facts)


def test_what_the_person_said_is_kept_and_the_difference_reported(clean):
    sid = _gathering(["counts.matrix"])
    _say_fact(sid, "read_length", 151)  # a PERSON_SAID fact through answer_gap
    pid = _pending_for(sid, "paired")
    answer = authoring.answer_with_sample(pid, _measured(read_length=150, paired=True), by="ana")
    assert answer.disagreed == ["read_length"]
    assert next(f for f in _facts(sid) if f["subject"] == "read_length")["value"] == 151


def test_an_undetermined_answer_leaves_the_gap_open(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    undecided = _measured()
    undecided.facts.append(inspect.InspectedFact(measurement="read_length", undetermined="lengths vary: 100–151, trimmed?", pieces=[], evidence={}))
    authoring.answer_with_sample(pid, undecided, by="ana")
    assert _pending(sid) == pid


def test_a_second_upload_to_an_answered_gap_is_refused(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    authoring.answer_with_sample(pid, _measured(read_length=150), by="ana")
    with pytest.raises(ValueError, match="MI0203"):
        authoring.answer_with_sample(pid, _measured(read_length=150), by="ana")


def test_compose_goal_carries_the_pieces(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    authoring.answer_with_sample(pid, _measured(read_length=150), by="ana")
    goal = authoring.compose_goal(sid)
    m = next(m for m in goal.profile.measurements if m.measurement == "read_length")
    assert m.source.value == "measured" and m.pieces == ["fastq@1.0.0", "read_length@1.0.0"]
```

Write the helpers `_pending(sid)` (the session's pending gap proposal id), `_pending_for(sid, subject)` (answer each offered gap that is not `subject` with its first option until `subject` is offered), `_facts(sid)` and `_say_fact(sid, subject, value)` from `test_authoring_gathering.py`'s own helpers; reuse them where they exist.

- [x] **Step 2: Run them to see them fail**

Run (throwaway Postgres): `MENDEL_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5442/postgres uv run pytest packages/mendel-api/tests/test_authoring_samples.py -q`
Expected: FAIL — no `answer_with_sample`.

- [x] **Step 3: Implement**

`types.py` `Fact`: `pieces: list[str] = []` and `evidence: dict[str, int | float] | None = None` (stored session state, not a door payload; the goal gets the typed `Evidence`).

`authoring.py`:
- `_SOURCE[FactSource.MEASURED] = ValueSource.MEASURED`.
- `_gap_options(gap, stack)`: compute `inspectable = {m.measurement for m in measurers.index(stack) if m.kind == "inspector" and m.trusted}` and the input types trusted formats read. For a measurement in `inspectable`: return `{**options, "upload": "Not sure: upload a sample and I'll measure it", "cant_share": "I can't share it"}`. For an input a format reads: `{"upload": "I have it, and I'll upload a sample", **_INPUT_OPTIONS}`. Otherwise unchanged.
- `compose_goal`: `MeasuredEntry(f.subject, f.value, _SOURCE[f.source], pieces=tuple(f.pieces), evidence=Evidence(**{k: f.evidence[k] for k in ("records", "rows", "share") if k in f.evidence}) if f.evidence else None)` — only the counts the goal's `Evidence` declares; a measure's other evidence (`min`, `max`) stays on the session's fact and the card.
- `answer_with_sample(proposal_id, inspection, *, by)`:

```python
def answer_with_sample(proposal_id: str, inspection, *, by: str) -> SampleAnswer:
    """What one inspected sample settles, recorded the way a click records an answer.

    **The person's word stands.** A measurement the session already knows is not overwritten; a
    disagreement is reported back. **An undetermined fact is not recorded**, so if it was the gap
    being answered, the gap stays open with its reason on the card. The proposal is settled only
    when the inspection decided its subject (or, for an input gap, read the type).
    """
```

Inside one `session_scope`: load the proposal (MI0205 if not a gap, as `answer_gap` does); build `known = {f["subject"] for f in row.facts}`; for each decided fact not in `known` append `Fact(kind=MEASUREMENT, subject, value, source=MEASURED, pieces, evidence)`; for the input type append `Fact(kind=INPUT, subject=inspection.type_id, source=MEASURED)` when not known; if the proposal's subject is now decided, settle it with `st.settle` exactly as `answer_gap` does (a second settle raises MI0203) with `chosen_option = "upload"`, and advance `FACT_ADDED`; else only `_swap` the facts. After the scope: if settled, `offer_next_gap(session_id)`.

Declare **MI0214** (*"an upload was refused: one file or a pair, nothing else"*) for Task 5.

- [x] **Step 4: Run them, and the gathering suite**

Run: `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_authoring_samples.py packages/mendel-api/tests/test_authoring_gathering.py -q`
Expected: PASS. If a gathering test pinned `not_sure` on a measurement an inspector now measures, update it to `upload` here: the option changed on purpose.

- [x] **Step 5: Commit**

```bash
git add packages/mendel-api packages/comeni-core/src/comeni_core/diagnostics.yml docs/handbook/reference/diagnostics.md
git commit -m "feat(api): an uploaded sample answers a gap, the person's word stands (#134)"
```

---

### Task 5: The route

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py`
- Modify: `packages/mendel-api/pyproject.toml` (`python-multipart`, if FastAPI's `UploadFile` needs it and it is not already present)
- Test: `packages/mendel-api/tests/test_authoring_routes.py`

**Interfaces:**
- Produces: `POST /api/pipeline/authoring/{session_id}/samples` (`operation_id="uploadAuthoringSample"`), multipart: `proposal_id` (form field) and `files` (1 or 2). Response `SampleInspected(outcome, type_id, facts: list[InspectedFactView], reason, steps, recorded, kept, disagreed, session: AuthoringSessionView)`. Refusals: MI0213 (403, protection), MI0214 (422, file count), MI0205/MI0203 as `decide` returns them.

- [x] **Step 1: Write the failing tests** (route tests use the module's client and database fixtures)

```python
def test_an_upload_is_inspected_and_answers_the_gap(client, clean):
    sid, pid = _gathering_at(client, "read_length")
    fix = ROOT / "registry/inspectors/formats/fastq/piece/fixtures/pair_150"
    files = [("files", (p.name, p.read_bytes())) for p in sorted(fix.glob("*.gz"))]
    got = client.post(f"/api/pipeline/authoring/{sid}/samples", data={"proposal_id": pid}, files=files)
    assert got.status_code == 200
    body = got.json()
    assert body["outcome"] == "measured" and "read_length" in body["recorded"]


def test_three_files_are_refused(client, clean):
    sid, pid = _gathering_at(client, "read_length")
    files = [("files", (f"f{i}.fq", b"@r\nA\n+\nI\n")) for i in range(3)]
    got = client.post(f"/api/pipeline/authoring/{sid}/samples", data={"proposal_id": pid}, files=files)
    assert got.status_code == 422 and "MI0214" in got.text


def test_above_level_0_the_upload_is_refused(client, clean, monkeypatch):
    from mendel_api.services import protection

    monkeypatch.setattr(protection, "level", lambda: "sealed")
    sid, pid = _gathering_at(client, "read_length")
    got = client.post(f"/api/pipeline/authoring/{sid}/samples", data={"proposal_id": pid},
                      files=[("files", ("a.fq", b"@r\nA\n+\nI\n"))])
    assert got.status_code == 403 and "MI0213" in got.text


def test_only_the_head_is_read(client, clean, monkeypatch):
    from mendel_api.services import inspect

    seen = []
    real = inspect.inspect_sample
    monkeypatch.setattr(inspect, "inspect_sample", lambda files, stack: seen.extend(len(b) for _, b in files) or real(files, stack))
    sid, pid = _gathering_at(client, "read_length")
    big = b"@r\n" + b"A" * (10 * 2**20)
    client.post(f"/api/pipeline/authoring/{sid}/samples", data={"proposal_id": pid}, files=[("files", ("big.fq", big))])
    assert seen and max(seen) <= inspect.HEAD_BYTES
```

`_gathering_at(client, subject)`: begin a session through the service helper the route tests already use, move it to gathering, and answer gaps until `subject` is offered; return `(session_id, proposal_id)`.

- [x] **Step 2: Run them to see them fail**

Run: `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_authoring_routes.py -q -k "upload or files or level_0 or head"`
Expected: FAIL — 404/405 on the route.

- [x] **Step 3: Implement**

```python
@router.post(
    "/{session_id}/samples",
    operation_id="uploadAuthoringSample",
    summary="Answer a question about your data with a sample: one file, or a pair",
    responses=REFUSES,
)
async def upload_sample(
    session_id: str, proposal_id: Annotated[str, Form()], files: list[UploadFile]
) -> SampleInspected:
    """**Only the first 4 MB of each file is read**, and nothing is written to disk (14.7.6's
    ruling: nothing deletes a session yet, so nothing is kept). The protection level is asked
    before a byte is read."""
    if not protection.allows(protection.Crossing.UPLOAD):
        raise HTTPException(status.HTTP_403_FORBIDDEN, protection.refuse(protection.Crossing.UPLOAD))
    if not 1 <= len(files) <= 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, coded("MI0214", f"{len(files)} files: upload one file, or a pair"))
    heads = [(f.filename or "sample", await f.read(inspect.HEAD_BYTES)) for f in files]
    inspection = await run_in_threadpool(inspect.inspect_sample, heads, registry.stack())
    answer = authoring.answer_with_sample(proposal_id, inspection, by=identity.default_author())
    return SampleInspected(..., session=_view(session_id))
```

Map `ValueError` from `answer_with_sample` the way `decide` maps its refusals (read `decide`'s handler and reuse it). `make client`.

- [x] **Step 4: Run them, the routes suite and the OpenAPI pin**

Run: `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_authoring_routes.py packages/mendel-api/tests/test_openapi.py -q`
Expected: PASS (add `("/api/pipeline/authoring/{session_id}/samples", "post"): "uploadAuthoringSample"` to the OpenAPI pin if it lists operations).

- [x] **Step 5: Commit, then `make check` separately**

```bash
git add packages/mendel-api frontend/src/api frontend/openapi.json uv.lock
git commit -m "feat(api): upload a sample to answer a question about your data (#134)"
make check > /tmp/claude-1000/check.log 2>&1; tail -20 /tmp/claude-1000/check.log
```
Expected: PASS.

---

## Execution record

*(Filled in while executing: rulings, measurements, deviations.)*

- **Measured:** a gzipped pair (`pair_150`) inspected through a real child process takes 0.11 s.
- **The two rulings against the spec held:** sample bytes are not stored, and the steps come back with the answer.
- **A third, found executing:** FastAPI's `UploadFile` spools every upload past 1 MB to a temporary file after receiving all of it. That broke the first ruling and review focus 2, so the route streams the multipart body itself (`services/sample_upload.py`): each file's first 4 MB in memory, the rest read through and dropped.
- **Rulings:** a designed option is a `DesignedOption` (a `SettingLocked`), coded MI0303 by the API; for an input, `upload` comes after *I have it*; clicking `upload` is not an answer (MI0205); the duplicate check runs before anything is recorded; a fact's stored evidence keeps numbers only; `mendel-api` declares `comeni-inspect` and `python-multipart`; the request-body guard reads every content type; CLAUDE.md's invariant 15 says what level 0 reads.
