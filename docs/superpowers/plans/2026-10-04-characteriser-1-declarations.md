# Characteriser 1 — the declarations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everything the characteriser is made of exists, is typed and is tested, but nothing calls it yet. That means: the planned branch in the diagram, the fourth AI point, a premise read by AI that reads correctly in `pipeline.yml`, door 6 with its payload and its guard, the two prompts, the two reply shapes, and the two admitted calls.

**Architecture:** `comeni-core` declares the AI point, the premise origin, `Mark.SAMPLE` and door 6. `mendel-resolver` maps a model's value to its premise. `mendel-api` holds the prompts, the reply shapes (`authoring/types.py`) and the two calls (`services/authoring_ai.py`), which go through the existing `_call` (render, send, admit, record). The calls are written and tested against a fake transport; plan 2 wires them to a job.

**Tech Stack:** pydantic 2, `comeni_ai` (`Client`, `PromptTemplate`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-04-the-characteriser-design.md` §3, §6, §7, §11 (diagram). Part 14.7.7.1 of #135.

## Global Constraints

- **Door 6 carries no file name, no extension, no `session_id`, no question text and no conversation** (spec §6).
- The excerpt is at most **8 KB (8192 bytes, UTF-8) and 200 lines** (spec §5). The type enforces both.
- Every id a model returns is checked against the vocabulary: **MI0204** for an undeclared family or type, **MI0205** for a state or measurement the chosen type does not offer (spec §7).
- `unmatched` is never admitted, shown or queued (spec §7).
- A new prompt is a new file, and an existing `v1` is never edited (`authoring/prompts.py`).
- Diagnostics are declared in `diagnostics.yml` and emitted with `coded()`.
- Run Python tests from the repository root, **always** with `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel` on the command line. Never run bare `pytest`: database fixtures truncate.
- Guards must be watched failing and recorded in `tests/fixtures/guard-ledger.md`.
- Run `make check` on its own before each commit, never chained with `&&` into the commit.
- Comments and docstrings match the repository's style. A loop is not an assertion.

## Rulings against the spec, for the operator

1. **The vocabulary shown to the model is not in door 6's payload; it is rendered into the prompt from the registry.** Spec §6 lists `families` and `types` as payload fields. Door 1 already works the other way: `_vocabulary_text` and `_families_text` render the public registry into the prompt, and `AuthoringRequest` carries only what came from the person, plus ids the engine issued. The forge draws the same line: *who authored the string*. So `CharacteriseRequest` is `excerpt`, `binary_before` and `registry` (a digest, as on door 1). Nothing that comes from a person is lost; the payload test still holds the field set exactly. Cost if wrong: two list fields added to the payload.
2. **`Mark.SAMPLE` gets its own set in the guard, `SAMPLE_FIELDS`, beside `FREE_TEXT_FIELDS`.** Spec §6 says `FREE_TEXT_FIELDS` names it. But a sample is not free text: it is the only data in the system taken from a person's file. Mixing the two counts would hide that. A second literal set, and a test that only door 6 can reach `Mark.SAMPLE`, are stricter. Cost if wrong: one entry moves between two sets.
3. **No `SCHEMA_VERSION` bump.** `PremiseOrigin.MODEL_READ` adds an allowed value, not a field, so no existing `pipeline.yml` changes and no `emitted.from_digest` moves. `test_a_schema_change_bumps_the_version` checks fields, and it stays green with nothing moved. Cost if wrong: one bump, plus `SERIALISED_SHAPE` unchanged.

## Review Focus

1. **A model read reaching `build_premises`** today throws `KeyError`, because `_BY_SOURCE` has no `ValueSource.MODEL`. Once mapped, the premise reads *read by AI*, never *asserted*. Pinned in Task 2.
2. **An excerpt of 8193 bytes, or 201 lines**, is refused by the type itself, so no caller can build a bigger payload. Pinned in Task 3.
3. **A reply naming a state of a different type** (`coordinate_sorted` on `genome.fasta`) is MI0205, never silently dropped. Pinned in Task 4.
4. **A measurement value outside its declaration** (`quality_encoding: phred99`) is dropped, as an inspector's would be, and the rest of the reply is admitted. Pinned in Task 4.
5. **A reply that names no type and no families** (*none of these*) is an admitted answer meaning *couldn't tell*, not a refusal. Pinned in Task 4.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `packages/mendel-api/src/mendel_api/authoring/protocol.py` | the characteriser's branch as planned nodes; the overview's `read_ai` edges |
| Modify `packages/mendel-api/tests/test_authoring_protocol.py` | the branch is drawn, and planned |
| Regenerate `docs/design/diagrams/*.md` | `tools/generate_protocol_doc.py` |
| Modify `packages/comeni-core/src/comeni_core/artifact/pipeline.py` | `AiPoint.CHARACTERISE` |
| Modify `packages/comeni-core/src/comeni_core/plan/tiers.py` | `PremiseOrigin.MODEL_READ` |
| Modify `packages/comeni-core/src/comeni_core/goal/premise.py` | its sentence |
| Modify `packages/comeni-core/src/comeni_core/artifact/materialise.py` | the reason for a value read by AI |
| Modify `packages/mendel-resolver/src/mendel_resolver/premises.py` | `ValueSource.MODEL → MODEL_READ` |
| Modify `packages/comeni-core/src/comeni_core/spell/marks.py` | `Mark.SAMPLE`, `SampleText`, `EXCERPT_BYTES`, `EXCERPT_LINES` |
| Modify `packages/comeni-core/src/comeni_core/artifact/egress.py` | `CharacteriseRequest`; door 6 `"characterisation"` |
| Modify `tests/guards/test_egress.py` | the door, `SAMPLE_FIELDS`, the payload's exact fields |
| Modify `tests/artifact/test_ai_provenance.py` | four points |
| Create `packages/mendel-api/src/mendel_api/authoring/prompts/builder.characterise-family.v1.md` | call 1 |
| Create `packages/mendel-api/src/mendel_api/authoring/prompts/builder.characterise.v1.md` | call 2 |
| Modify `packages/mendel-api/src/mendel_api/authoring/prompts.py` | `CHARACTERISE_FAMILY`, `CHARACTERISE` |
| Modify `packages/mendel-api/src/mendel_api/authoring/types.py` | `CharacteriseFamilies`, `CharacteriseReply`, `ReadMeasurement`, `Unmatched` |
| Modify `packages/mendel-api/src/mendel_api/services/authoring_ai.py` | `Purpose` members; `compose_characterise`, `characterise_families`, `characterise`, admission; `_call`/`_record` take either payload |
| Modify `packages/mendel-api/src/mendel_api/services/models.py` | the two purposes → `MODEL_TALK` |
| Tests: `packages/mendel-resolver/tests/test_premises.py`, `packages/mendel-api/tests/test_authoring_prompts.py`, `packages/mendel-api/tests/test_authoring_characterise.py` (new) | |

---

### Task 1: The branch, drawn as planned

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/protocol.py` (the `INSPECTING` protocol, about lines 296–413; the `PROTOCOL` edges at about lines 626–633)
- Modify: `packages/mendel-api/tests/test_authoring_protocol.py`
- Regenerate: `docs/design/diagrams/inspecting-a-sample.md`, `docs/design/diagrams/authoring-protocol.md`

**Interfaces:**
- Produces: detail node ids `door`, `excerpt`, `families`, `types`, `ai_admit`, `ai_stamped`, `hand_back`, and stage `reading`, which plans 2 and 4 mark built. The overview node `read_ai` stays, with new edges.

- [x] **Step 1: Write the failing test**

Append to `packages/mendel-api/tests/test_authoring_protocol.py`:

```python
# ── the characteriser, planned (14.7.7.1) ───────────────────────────────────────────────────


CHARACTERISER = {"door", "excerpt", "families", "types", "ai_admit", "ai_stamped", "hand_back"}


def test_the_characteriser_is_drawn_step_by_step_and_planned():
    detail = {n.id: n for n in p.PROTOCOL.nodes}["read_engine"].detail
    nodes = {n.id: n for n in detail.nodes}
    assert CHARACTERISER <= set(nodes), CHARACTERISER - set(nodes)
    assert "characterise" not in nodes, "the single placeholder node is replaced, not kept"
    assert not any(nodes[n].built for n in CHARACTERISER)
    edges = {(e.source, e.target) for e in detail.edges}
    for edge in [
        ("claim", "door"), ("door", "nothing"), ("door", "excerpt"), ("excerpt", "nothing"),
        ("excerpt", "families"), ("families", "back"), ("families", "types"),
        ("types", "ai_admit"), ("ai_admit", "back"), ("ai_admit", "kept"),
        ("ai_admit", "ai_stamped"), ("ai_admit", "hand_back"), ("hand_back", "confirm"),
        ("ai_stamped", "back"),
    ]:
        assert edge in edges, f"{edge} is not drawn"


def test_the_model_reads_in_a_stage_that_names_its_door():
    detail = {n.id: n for n in p.PROTOCOL.nodes}["read_engine"].detail
    stages = {s.id: s.title for s in detail.stages}
    assert "door 6" in stages["reading"].lower()
    assert {n.stage for n in detail.nodes if n.id in {"families", "types"}} == {"reading"}


def test_the_overview_hands_a_type_nothing_reads_to_the_ai_and_back():
    edges = {(e.source, e.target): e for e in p.PROTOCOL.edges}
    assert ("read_engine", "read_ai") in edges and not edges[("read_engine", "read_ai")].built
    assert ("read_ai", "read_engine") in edges, "a type the engine reads goes back to it"
    assert ("safety", "read_ai") not in edges, "the level is asked inside the detail now"
```

In `test_reading_a_sample_has_its_detailed_diagram`, replace the last line:

```python
    assert detail.stages and all(s.title.startswith("On our server") for s in detail.stages)
```

with:

```python
    # Every stage says where it happens: on our server, or through the door the excerpt leaves by.
    assert detail.stages and all(
        s.title.startswith(("On our server", "Through door 6")) for s in detail.stages
    )
```

- [x] **Step 2: Run it to verify it fails**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_protocol.py -q`
Expected: the three new tests FAIL (`door` etc. are not nodes; `('read_engine', 'read_ai')` is not drawn).

- [x] **Step 3: Draw the branch**

In `INSPECTING`, add a stage after `receiving`:

```python
        Stage(id="reading", title="Through door 6: a model reads the start of it"),
```

Replace the node

```python
        _n("characterise", "receiving", _AI, "The characteriser reads it<br/>(14.7.7)"),
```

with:

```python
        # The characteriser (14.7.7): planned here, built part by part.
        _n(
            "door",
            "receiving",
            _SAFETY,
            "Does the protection level<br/>let a model read it?",
            shape=Shape.GATE,
        ),
        _n(
            "excerpt",
            "receiving",
            _ENGINE,
            "Keep up to 8 KB of its text<br/>(gzip unpacked by its first bytes)",
        ),
        _n("families", "reading", _AI, "AI: which families<br/>could it be?"),
        _n("types", "reading", _AI, "AI: which type,<br/>which states and facts?"),
        _n(
            "ai_admit",
            "admitting",
            _ENGINE,
            "Admit every id<br/>against the registry",
            shape=Shape.CHOICE,
        ),
        _n(
            "ai_stamped",
            "admitting",
            _ENGINE,
            "Stamped: read by AI<br/>(check the premise)",
            border=Border.TIER3,
        ),
        _n(
            "hand_back",
            "admitting",
            _ENGINE,
            "A type the engine reads:<br/>your browser sends it again",
        ),
```

Replace the edge `_e("claim", "characterise", "none, at 14.7.7"),` with:

```python
        _e("claim", "door", "none, at 14.7.7"),
        _e("door", "nothing", "above level 0"),
        _e("door", "excerpt", "level 0"),
        _e("excerpt", "nothing", "too little text, or no model"),
        _e("excerpt", "families", "queued for the AI"),
        _e("families", "back", "none fits: the AI couldn't tell"),
        _e("families", "types", "one or more"),
        _e("types", "ai_admit"),
        _e("ai_admit", "back", "an id nothing declares: refused, the question stays"),
        _e("ai_admit", "kept", "you already said it"),
        _e("ai_admit", "ai_stamped", "nothing here reads that type"),
        _e("ai_admit", "hand_back", "the engine reads that type"),
        _e("hand_back", "confirm", "claimed by the type the AI named"),
        _e("ai_stamped", "back"),
```

Remove the `style characterise` line only if the generator writes one from a node id: it doesn't, because styles are derived from `built`. Nothing else names `characterise`; confirm with `grep -n '"characterise"' packages/mendel-api/src/mendel_api/authoring/protocol.py`, which should print nothing.

In `PROTOCOL.edges`, replace

```python
        _e("safety", "read_ai", "it doesn't"),
        _e("read_engine", "next_gap", built=True),
        _e("read_ai", "next_gap"),
```

with:

```python
        _e("read_engine", "next_gap", built=True),
        # The characteriser (14.7.7): a type nothing reads goes to the AI; a type the engine
        # reads comes back to it. Planned until 14.7.7.2 builds the job.
        _e("read_engine", "read_ai", "nothing here reads its type"),
        _e("read_ai", "read_engine", "a type the engine reads"),
        _e("read_ai", "next_gap"),
```

and change the comment above `_e("reply", "upload", …)` from *the characteriser stays planned (14.7.7)* to *the characteriser is planned step by step inside the detail (14.7.7)*.

- [x] **Step 4: Run the tests and regenerate the diagrams**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_protocol.py -q`
Expected: PASS, including `test_the_machine_did_not_change`: no edge here carries an event.

Run: `uv run python tools/generate_protocol_doc.py && uv run python tools/generate_protocol_doc.py --check`
Expected: the two diagram pages change and the check passes. Open `docs/design/diagrams/inspecting-a-sample.md` and read the mermaid: the new nodes are dashed, and `reading` is its own subgraph.

- [x] **Step 5: Check, then commit**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel make check`
Expected: green.

```bash
git add packages/mendel-api/src/mendel_api/authoring/protocol.py packages/mendel-api/tests/test_authoring_protocol.py docs/design/diagrams
git commit -m "docs(protocol): the characteriser's branch, step by step, planned (#135)"
```

---

### Task 2: The fourth AI point, and a premise read by AI

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py:650-668` (`AiPoint`)
- Modify: `tests/artifact/test_ai_provenance.py:94`
- Modify: `packages/comeni-core/src/comeni_core/plan/tiers.py:88-108` (`PremiseOrigin`)
- Modify: `packages/comeni-core/src/comeni_core/goal/premise.py:56-62` (`_ORIGIN_PROSE`)
- Modify: `packages/mendel-resolver/src/mendel_resolver/premises.py:50-55` (`_BY_SOURCE`)
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py:160-180`
- Test: `packages/mendel-resolver/tests/test_premises.py`, `tests/artifact/test_pipeline_file.py`

**Interfaces:**
- Produces: `AiPoint.CHARACTERISE = "characterise"`; `PremiseOrigin.MODEL_READ = "model_read"`; a value with `ValueSource.MODEL` in a profile becomes a premise with origin `MODEL_READ`, whose sentence is `"<id> is <value>, read by AI"`. In `pipeline.yml`, its `Why.reason` begins `read by AI from the start of a sample`.

- [x] **Step 1: Write the failing tests**

In `tests/artifact/test_ai_provenance.py`, change line 94 to:

```python
    assert [point.value for point in AiPoint] == ["prompt", "tier-4", "repair", "characterise"]
```

Append to `packages/mendel-resolver/tests/test_premises.py` (read its imports first and reuse its own goal and registry helpers; the names below are the ones those helpers produce):

```python
def test_a_value_a_model_read_is_a_premise_read_by_ai():
    """14.7.7: `_BY_SOURCE` is total over `ValueSource` and read with `[]`, so `MODEL` reaching
    it threw `KeyError` the first time a characterised fact did."""
    from comeni_core.goal.premise import PremiseRecord
    from comeni_core.plan.tiers import PremiseOrigin, ValueSource
    from mendel_resolver.premises import _BY_SOURCE

    assert _BY_SOURCE[ValueSource.MODEL] is PremiseOrigin.MODEL_READ
    record = PremiseRecord(id="paired", value=True, origin=PremiseOrigin.MODEL_READ)
    assert record.prose() == "paired is True, read by AI"


def test_every_value_source_has_a_premise_origin():
    from comeni_core.plan.tiers import ValueSource
    from mendel_resolver.premises import _BY_SOURCE

    assert set(_BY_SOURCE) == set(ValueSource)
```

Append to `tests/artifact/test_pipeline_file.py` (it already imports what `materialise` needs; follow how the nearest test above line 1005 builds a goal with a profile, and give one measurement `source=ValueSource.MODEL`):

```python
def test_a_premise_read_by_ai_says_so_in_the_file():
    """14.7.7: the reason a reader checks says who read it, and never *asserted in the goal*."""
    why = _why_for_measured(source=ValueSource.MODEL)  # see the helper added in Step 3
    assert why.premise[0].origin is PremiseOrigin.MODEL_READ
    assert why.reason.startswith("read by AI from the start of a sample")
```

`_why_for_measured` does not exist yet. Before Step 2, write it beside the test that asserts `PremiseOrigin.MEASURED` at about line 1024. **Copy that test's body**, parameterised on the `ValueSource` of its one measurement, so the two tests share it:

```python
def _why_for_measured(*, source):
    """The `Why` of the step that reads one measured fact, with that fact's `source` given."""
    ...  # the body of the MEASURED test above, with `source=source` on its Measured entry
```

Then make the existing MEASURED test call `_why_for_measured(source=ValueSource.MEASURED)`, so there is only one copy of the setup.

- [x] **Step 2: Run them to verify they fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest tests/artifact/test_ai_provenance.py packages/mendel-resolver/tests/test_premises.py tests/artifact/test_pipeline_file.py -q`
Expected: FAIL. `AiPoint` has three members; `_BY_SOURCE` has no `MODEL` (`KeyError`); `PremiseOrigin` has no `MODEL_READ`.

- [x] **Step 3: Declare them**

`pipeline.py`, in `AiPoint`, change the docstring's first line to *The four declared runtime AI points. Invariant 3 says there are exactly these.* and add after `REPAIR`:

```python
    CHARACTERISE = "characterise"
    """A model reads the start of a sample nothing here reads (14.7.7), at protection level 0
    only: which declared type it is, and which declared states and facts it states. Every id
    it names is admitted against the vocabulary, and every fact it reads is marked *read by
    AI*. Door 6 is the only way its payload leaves."""
```

In `AiProvenance.available`'s docstring, change *three* to *four*.

`tiers.py`, in `PremiseOrigin`, after `MEASURED`:

```python
    MODEL_READ = "model_read"
    """A model read it from the start of a sample (14.7.7). Better evidence than an assertion,
    because something looked at the data; weaker than a measurement, because what looked was a
    model reading at most 8 KB. A tier-3 decision on it says *check the premise*."""
```

`premise.py`, in `_ORIGIN_PROSE`:

```python
    PremiseOrigin.MODEL_READ: "read by AI",
```

and change its docstring's *a sixth member* to *a new member*.

`premises.py`, in `_BY_SOURCE`:

```python
    ValueSource.MODEL: PremiseOrigin.MODEL_READ,
```

and add one line to its docstring: *`MODEL` is the characteriser (14.7.7): a model looked at the data, so it is not an assertion, and it is not a measurement either.*

`materialise.py`, in the branch that writes the reason (about line 167), add after the `if source is ValueSource.MEASURED:` block and before `else:`:

```python
    elif source is ValueSource.MODEL:
        # 14.7.7: a model read it from the sample's first 8 KB. Never *asserted*: something
        # looked at the data, and the reader is told what.
        reason = "read by AI from the start of a sample; check it"
```

- [x] **Step 4: Run them to verify they pass**

Run the Step 2 command.
Expected: PASS. Then run `MENDEL_DATABASE_URL=… uv run pytest tests/artifact packages/mendel-resolver -q`.
Expected: PASS, including `test_a_schema_change_bumps_the_version` (no field moved: ruling 3).

- [x] **Step 5: Check, then commit**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel make verify`. `make verify` is required here: `comeni_core/artifact/pipeline.py` is on CLAUDE.md's list.
Expected: green.

```bash
git add packages/comeni-core packages/mendel-resolver tests/artifact
git commit -m "feat(core): the fourth AI point, characterise; a premise read by AI says so (#135)"
```

---

### Task 3: Door 6, its payload, and its guard

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/spell/marks.py` (`Mark`; new `SampleText` beside `Text` at about line 301)
- Modify: `packages/comeni-core/src/comeni_core/artifact/egress.py` (module docstring; new `CharacteriseRequest` after `RepairRequest`; `DECLARED`)
- Modify: `tests/guards/test_egress.py`
- Modify: `tests/fixtures/guard-ledger.md`

**Interfaces:**
- Produces: `comeni_core.spell.marks.Mark.SAMPLE`, `SampleText`, `EXCERPT_BYTES = 8192`, `EXCERPT_LINES = 200`; `comeni_core.artifact.egress.CharacteriseRequest(excerpt: SampleText, binary_before: bool = False, registry: Digest | None = None)`; `egress.DOORS["characterisation"] is CharacteriseRequest`, on `DoorPath.PIPELINE`.

- [x] **Step 1: Write the failing tests**

In `tests/guards/test_egress.py`:

1. Change `PIPELINE_DOORS` to include the new door, with the reason:

```python
PIPELINE_DOORS = {
    "goal_extraction",
    "tier4_resolution",
    "compiler_repair",
    "publication",
    # Door 6, 14.7.7: the characteriser. The first door that carries data from a person's file,
    # at protection level 0 only. On the pipeline path because what it reads becomes the goal.
    "characterisation",
}
"""The pipeline path's doors, and *pipeline data leaves through these* stays checkable against
this set rather than against the whole list."""
```

2. Rename `test_pipeline_data_still_leaves_through_exactly_four` to `test_pipeline_data_leaves_through_exactly_the_pipeline_doors`. Keep its body, and in its docstring add: *Door 6 joined on 2026-10-04 (14.7.7); the sentence is now the set's.*

3. After `FREE_TEXT_FIELDS`, add:

```python
SAMPLE_FIELDS = {
    # The first, 14.7.7: the start of a sample, decoded to text, for the characteriser. **Not
    # free text, and counted apart on purpose**: free text is what a person typed or a tool
    # printed, and this is what a person's *file* holds. At most 8 KB and 200 lines, which the
    # type enforces (`marks.SampleText`), and only at protection level 0.
    ("CharacteriseRequest", "excerpt"),
}
"""Every field that may hold data from a person's file. This set is the count."""
```

4. Add the tests, after `test_free_text_lives_only_where_declared`:

```python
def test_sample_data_lives_only_where_declared():
    found: set[tuple[str, str]] = set()
    for payload in _payload_types():
        found |= _fields(payload, Mark.SAMPLE)
    assert found == SAMPLE_FIELDS


def test_only_the_characterisation_door_can_reach_a_sample():
    """A sample field nested in any other door's payload, through any path, fails here."""
    reaching = {
        name
        for name, payload in egress.DOORS.items()
        for model in reachable(payload)
        if _fields(model, Mark.SAMPLE)
    }
    assert reaching == {"characterisation"}


def test_the_characterisation_door_carries_the_excerpt_and_nothing_of_the_file():
    """Spec §6: no file name, no extension, no session, no question, no conversation."""
    door = egress.DOORS["characterisation"]
    assert list(door.model_fields) == ["excerpt", "binary_before", "registry"]
    models = reachable(door)
    assert models == {door}, "the payload holds no nested model that could grow a field"


@pytest.mark.parametrize(
    "text",
    ["x" * 8193, "a\n" * 201, "é" * 4097],  # bytes, lines, and bytes counted as UTF-8
)
def test_an_excerpt_over_its_bound_is_refused_by_its_type(text):
    with pytest.raises(ValidationError):
        egress.CharacteriseRequest(excerpt=text)


def test_an_excerpt_at_its_bound_is_accepted():
    assert egress.CharacteriseRequest(excerpt="a\n" * 199 + "a").excerpt
    assert egress.CharacteriseRequest(excerpt="x" * 8192).excerpt
```

5. Change the module docstring's first line to *Invariant 14: data leaves through six declared doors and no others.* and its first paragraph's *Five since 2026-09-05* to *Six since 2026-10-04 (door 6, the characteriser); five since 2026-09-05*.

- [x] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/guards/test_egress.py -q`
Expected: FAIL. `Mark` has no `SAMPLE`; `egress` has no `CharacteriseRequest`; `DOORS` lacks `characterisation`.

- [x] **Step 3: Declare the mark, the type and the door**

`marks.py`, in `Mark`, after `FREE_TEXT`:

```python
    SAMPLE = "sample"
    """**Data from a person's file.** The start of a sample, decoded to text, for the
    characteriser (14.7.7). Not `FREE_TEXT`: nobody typed it, and it is the one thing this
    system holds that came from inside someone's data. Bounded by its type (`SampleText`), and
    reachable from door 6 only (`tests/guards/test_egress.py`)."""
```

After `Line = …` (about line 306):

```python
EXCERPT_BYTES = 8 * 1024
"""The most of a sample a model may be shown, in bytes of UTF-8 (spec §5)."""
EXCERPT_LINES = 200
"""…and in lines, whichever comes first."""


def _sample_text(value: str) -> str:
    """At most `EXCERPT_BYTES` and `EXCERPT_LINES`. **A bound, not a shape**: what a sample says
    is not this code's to check, but how much of it may leave is."""
    if len(value.encode()) > EXCERPT_BYTES:
        raise ValueError(f"an excerpt is at most {EXCERPT_BYTES} bytes")
    if len(value.splitlines()) > EXCERPT_LINES:
        raise ValueError(f"an excerpt is at most {EXCERPT_LINES} lines")
    return value


SampleText = Annotated[str, Mark.SAMPLE, AfterValidator(_sample_text)]
```

`egress.py`: import `SampleText` with the other marks, and add after `RepairRequest`:

```python
class CharacteriseRequest(EgressPayload):
    """Door 6 — the characteriser (14.7.7). **The first door carrying data from a person's file.**

    The start of one sample, decoded to text, so a model can say which declared type it is and
    which declared states and facts it states. Open at protection level 0 only; above it the
    job refuses before this is built.

    **What is deliberately absent**: the file's name and extension (a name can carry a patient
    identifier, and a piece never decides on a name), the session, the question it answers, the
    conversation. The vocabulary the model chooses from is the public registry, rendered into the
    prompt as door 1's is; it is not here because nobody's data is in it.
    """

    excerpt: SampleText
    binary_before: bool = False
    """Binary bytes came before the text: a BAM's header, not a SAM file."""
    registry: Digest | None = None
```

In `DECLARED`, after `"publication"`:

```python
    # Door 6, 2026-10-04 (14.7.7). The characteriser: a model reads the start of a sample
    # nothing here reads. **The first door whose payload holds data from a person's file**
    # (`Mark.SAMPLE`), bounded to 8 KB and 200 lines, at protection level 0 only.
    "characterisation": Door(CharacteriseRequest, DoorPath.PIPELINE),
```

In the module docstring, change *There are **five**, on **two paths**. Four carry …* to: *There are **six**, on **two paths**. Five carry pipeline data — goal extraction, tier-4 resolution, compiler repair, publication and, since 14.7.7, characterisation, the one door that carries part of a person's file — and the sixth carries forge review*. Also update `DoorPath`'s *four doors* sentence to *the pipeline's doors*.

- [x] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/guards/test_egress.py -q`
Expected: PASS. If `test_every_mark_carries_a_validator_or_is_listed_as_a_label` fails, `SampleText` lost its validator; fix the alias, not the list.

- [x] **Step 5: Watch the guard fail against the defect it guards**

Temporarily add `note: Text = ""` to `CharacteriseRequest` and run `uv run pytest tests/guards/test_egress.py -q -k "characterisation_door_carries or free_text_lives"`.
Expected: both FAIL, naming `note`.

Temporarily add `sample: SampleText = ""` to `AuthoringRequest`, and run with `-k "sample_data_lives or only_the_characterisation"`.
Expected: both FAIL, naming `AuthoringRequest`/`goal_extraction`.

Revert both, then append a row to `tests/fixtures/guard-ledger.md` in its format, naming the four tests, the two reverts and their failures.

- [x] **Step 6: Check, then commit**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel make check`
Expected: green. If `make types` regenerates `.pyi` files, include them.

```bash
git add packages/comeni-core tests/guards/test_egress.py tests/fixtures/guard-ledger.md
git commit -m "feat(core): door 6, characterisation — the first payload holding a person's data, bounded (#135)"
```

---

### Task 4: The prompts, the replies, and the two admitted calls

**Files:**
- Create: `packages/mendel-api/src/mendel_api/authoring/prompts/builder.characterise-family.v1.md`
- Create: `packages/mendel-api/src/mendel_api/authoring/prompts/builder.characterise.v1.md`
- Modify: `packages/mendel-api/src/mendel_api/authoring/prompts.py`
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (after `FamilyChoice`, about line 537)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_ai.py`
- Modify: `packages/mendel-api/src/mendel_api/services/models.py:19-31`
- Modify: `packages/mendel-api/tests/test_authoring_prompts.py`
- Create: `packages/mendel-api/tests/test_authoring_characterise.py`

**Interfaces:**
- Consumes: `CharacteriseRequest` (Task 3).
- Produces, all in `mendel_api.services.authoring_ai`:
  - `Purpose.CHARACTERISE_FAMILY = "characterise_family"`, `Purpose.CHARACTERISE = "characterise"`
  - `compose_characterise(excerpt: str, *, binary_before: bool, registry: str | None) -> CharacteriseRequest`
  - `characterise_families(request: CharacteriseRequest, *, stack, client: Client | None = None, session_id: str | None = None) -> Outcome`, whose reply is a `CharacteriseFamilies`
  - `characterise(request: CharacteriseRequest, *, stack, families: Sequence[str] | None, client: Client | None = None, session_id: str | None = None) -> Outcome`, whose reply is an admitted `CharacteriseReply` with measurements outside their declaration already dropped. `families=None` shows every type, as when the family step is switched off.
  - `offered(stack, type_id: str) -> tuple[set[str], set[str]]`: the states and measurement ids a type offers.
- Produces, in `mendel_api.authoring.types`: `CharacteriseFamilies(families: list[str])`, `ReadMeasurement(id: str, value: HumanParamValue)`, `Unmatched(kind: Literal["type", "state", "measurement"], name: str, cite: str)`, `CharacteriseReply(type_id: str | None, states: list[str], measurements: list[ReadMeasurement], undetermined: list[str], unmatched: list[Unmatched])`.

- [x] **Step 1: Write the failing tests**

Create `packages/mendel-api/tests/test_authoring_characterise.py`:

```python
"""The characteriser's two calls (14.7.7), against a fake transport and a real database.

Same seam as `test_authoring_ai.py`: `Client` takes a transport, and each test hands one a
committed body. What is under test is what comes back in: which ids are admitted, which refused,
and what is recorded.
"""

import json

import pytest
from comeni_ai import Client, ModelAccess, ModelUnavailableError
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation
from mendel_api.services import authoring_ai as ai
from mendel_api.services import registry
from sqlalchemy import select

ACCESS = ModelAccess(model="fake/test", base_url="http://localhost:1")
BAM_HEAD = "@HD\tVN:1.6\tSO:coordinate\n@SQ\tSN:chr1\tLN:248956422\n"


class Answers:
    def __init__(self, *bodies):
        self.bodies, self.sent = list(bodies), []

    def send(self, access, prompt):
        self.sent.append(prompt)
        body = self.bodies.pop(0) if len(self.bodies) > 1 else self.bodies[0]
        if isinstance(body, Exception):
            raise body
        return body


class Choosing(Client):
    def __init__(self, *bodies):
        self.answers = Answers(*bodies)
        super().__init__(ACCESS, transport=self.answers)
        self.choices = []

    def chat(self, system, user, shape, choices=None):
        self.choices.append(choices)
        return super().chat(system, user, shape, choices=choices)


@pytest.fixture
def stack():
    return registry.stack()


def _rows():
    with session_scope() as db:
        return list(db.scalars(select(AiInvocation)).all())


def _request(text=BAM_HEAD, binary_before=True):
    return ai.compose_characterise(text, binary_before=binary_before, registry="0" * 64)


def _reply(**over):
    body = {"type_id": "alignment.bam", "states": ["coordinate_sorted"], "measurements": [],
            "undetermined": [], "unmatched": []}
    return json.dumps(body | over)


# ── call 1: the families ──────────────────────────────────────────────────────────────


def test_the_family_call_is_held_to_the_declared_families(stack, clean_forge):
    client = Choosing(json.dumps({"families": ["alignment"]}))
    outcome = ai.characterise_families(_request(), stack=stack, client=client)
    assert outcome.admitted and outcome.reply.families == ["alignment"]
    assert client.choices == [{"families": sorted(stack.families.families)}]
    [row] = _rows()
    assert row.purpose == "characterise_family"
    assert row.prompt_id == "builder.characterise-family.v1"


def test_no_family_is_an_answer_meaning_the_ai_could_not_tell(stack, clean_forge):
    outcome = ai.characterise_families(
        _request(), stack=stack, client=Choosing(json.dumps({"families": []}))
    )
    assert outcome.admitted and outcome.reply.families == []


def test_a_family_nothing_declares_is_refused(stack, clean_forge):
    outcome = ai.characterise_families(
        _request(), stack=stack, client=Choosing(json.dumps({"families": ["variants"]}))
    )
    assert not outcome.admitted and outcome.code == "MI0204"


def test_the_excerpt_reaches_the_model_and_the_name_never_does(stack, clean_forge):
    client = Choosing(json.dumps({"families": ["alignment"]}))
    ai.characterise_families(_request(), stack=stack, client=client)
    sent = client.answers.sent[0]
    assert "SO:coordinate" in sent
    assert "binary bytes came before this text" in sent


# ── call 2: the type, its states, its facts ─────────────────────────────────────────


def test_the_type_call_is_shown_only_the_chosen_families_types(stack, clean_forge):
    client = Choosing(_reply())
    outcome = ai.characterise(_request(), stack=stack, families=["alignment"], client=client)
    assert outcome.admitted and outcome.reply.type_id == "alignment.bam"
    assert outcome.reply.states == ["coordinate_sorted"]
    shown = sorted(t for t in stack.vocabulary.types if t.startswith("alignment."))
    assert client.choices[0]["type_id"] == shown
    assert "fastq.reads" not in client.answers.sent[0]
    assert _rows()[0].prompt_id == "builder.characterise.v1"


def test_with_the_family_step_off_every_type_is_shown(stack, clean_forge):
    client = Choosing(_reply())
    ai.characterise(_request(), stack=stack, families=None, client=client)
    assert client.choices[0]["type_id"] == sorted(stack.vocabulary.types)


def test_a_type_outside_the_chosen_families_is_refused(stack, clean_forge):
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"],
        client=Choosing(_reply(type_id="genome.fasta", states=[])),
    )
    assert not outcome.admitted and outcome.code == "MI0204"


def test_a_state_of_another_type_is_refused(stack, clean_forge):
    outcome = ai.characterise(
        _request(">chr1\nACGT\n", binary_before=False), stack=stack, families=["genome"],
        client=Choosing(_reply(type_id="genome.fasta", states=["coordinate_sorted"])),
    )
    assert not outcome.admitted and outcome.code == "MI0205"


def test_a_measurement_the_type_does_not_offer_is_refused(stack, clean_forge):
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"],
        client=Choosing(_reply(measurements=[{"id": "library_prep", "value": "poly_a"}])),
    )
    assert not outcome.admitted and outcome.code == "MI0205"


def test_a_value_outside_its_declaration_is_dropped_and_the_rest_admitted(stack, clean_forge):
    # `paired` and `quality_encoding` declare `describes: fastq.reads`; `read_length` does not,
    # so a model is never offered it (spec §2's rule A, as the registry stands).
    assert {"paired", "quality_encoding"} <= ai.offered(stack, "fastq.reads")[1]
    reply = _reply(type_id="fastq.reads", states=[],
                   measurements=[{"id": "quality_encoding", "value": "phred99"},
                                 {"id": "paired", "value": True}])
    outcome = ai.characterise(
        _request("@r1\nACGT\n+\nIIII\n", binary_before=False), stack=stack,
        families=["fastq"], client=Choosing(reply),
    )
    assert outcome.admitted
    assert [m.id for m in outcome.reply.measurements] == ["paired"]


def test_no_type_is_an_answer_meaning_the_ai_could_not_tell(stack, clean_forge):
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"],
        client=Choosing(_reply(type_id=None, states=[])),
    )
    assert outcome.admitted and outcome.reply.type_id is None


def test_unmatched_is_kept_in_the_reply_and_never_admitted_into_anything(stack, clean_forge):
    unmatched = [{"kind": "state", "name": "unsorted", "cite": "SAM v1.6 §1.3"}]
    outcome = ai.characterise(
        _request(), stack=stack, families=["alignment"],
        client=Choosing(_reply(unmatched=unmatched)),
    )
    assert outcome.admitted and outcome.reply.unmatched[0].name == "unsorted"
    assert "unsorted" in (_rows()[0].response or "")


def test_a_provider_that_does_not_answer_is_recorded_as_failed(stack, clean_forge):
    outcome = ai.characterise_families(
        _request(), stack=stack, client=Choosing(ModelUnavailableError("down"))
    )
    assert not outcome.admitted and outcome.code == "MA0007"
    assert _rows()[0].state == "failed"


def test_states_and_measurements_offered_come_from_the_registry(stack):
    states, measurements = ai.offered(stack, "alignment.bam")
    assert "coordinate_sorted" in states
    assert all(stack.measurements.get(m).describes == "alignment.bam" for m in measurements)
```

In `packages/mendel-api/tests/test_authoring_prompts.py`:
- change `assert len(prompts.TEMPLATES) == 7` to `== 9`;
- add to `PER_CALL`: `"excerpt": ("@HD\tSO:coordinate", ">chr1")` and `"binary_before": ("binary bytes came before this text", "(no binary bytes before this text)")`;
- in `test_every_builder_prompt_has_a_system_part_identical_across_sessions`, add `"types": "alignment.bam — coordinate_sorted"` to `fixed`;
- append:

```python
def test_the_characteriser_reads_only_what_the_excerpt_states():
    """Spec §6: never what would need the whole file; *none* and *undetermined* are answers."""
    for prompt_id in (prompts.CHARACTERISE_FAMILY, prompts.CHARACTERISE):
        body = prompts.template(prompt_id).body
        assert "only what the excerpt states" in body, prompt_id
        assert "{{excerpt}}" in body.split("<!-- then, per call -->")[1], prompt_id
    body = prompts.template(prompts.CHARACTERISE).body
    assert "would need the whole file" in body
    assert "`undetermined`" in body and "`unmatched`" in body
```

- [x] **Step 2: Run them to verify they fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_characterise.py packages/mendel-api/tests/test_authoring_prompts.py -q`
Expected: FAIL (`compose_characterise` and `prompts.CHARACTERISE` do not exist).

- [x] **Step 3: Write the prompts**

`builder.characterise-family.v1.md`:

```markdown
You are helping a researcher describe an analysis. You do not build the pipeline — a
deterministic engine does, from the goal you write down. Use only the declared vocabulary and
the ids supplied below; never invent a type, state, measurement, step, option or setting id.
When something is genuinely unclear, ask one typed question rather than assuming an answer.
Never write a filename, a path, a sample identifier, or a count nobody measured. Output only
the declared JSON shape.

# What you are doing

A researcher gave a file that nothing here reads by its name. Below is the start of it, decoded
to text. Your only job is to say which **families** of data it could belong to, so the engine
can show you every type in those families next. Use only the family ids listed below.

Read only what the excerpt states. Recognise a file by its content: a header line, a record's
layout, a magic word. If none of the families fits, or you cannot tell, answer with no families:
that is an answer, not a failure. Never pick the nearest family to have picked something.

# The families

{{families}}

# What to write

**`families`**: the ids of the families this file could belong to. Usually one; more only when
the excerpt genuinely fits more than one. An empty list when none fits or you cannot tell.

<!-- then, per call -->

# The start of the file

({{binary_before}})

{{excerpt}}
```

`builder.characterise.v1.md`:

```markdown
You are helping a researcher describe an analysis. You do not build the pipeline — a
deterministic engine does, from the goal you write down. Use only the declared vocabulary and
the ids supplied below; never invent a type, state, measurement, step, option or setting id.
When something is genuinely unclear, ask one typed question rather than assuming an answer.
Never write a filename, a path, a sample identifier, or a count nobody measured. Output only
the declared JSON shape.

# What you are doing

A researcher gave a file that nothing here reads by its name. Below is the start of it, decoded
to text. Say which declared **type** it is, which of that type's declared **states** the excerpt
states, and which of its declared **measurements** the excerpt states.

Read only what the excerpt states: a header that says `SO:coordinate` states that a BAM is
sorted by coordinate. Never answer what would need the whole file — a genome's length, how many
reads there are, whether the first records are typical. When the excerpt does not state a
measurement, list it in `undetermined`. When you cannot tell the type, answer `type_id: null`.

# The types you may choose from

Each type with its declared states, then the measurements that describe it, with what each can
hold.

{{types}}

# What to write

- **`type_id`**: one of the type ids above, or `null`.
- **`states`**: only states declared for that type, and only those the excerpt states.
- **`measurements`**: `{id, value}` for each declared measurement of that type whose value the
  excerpt states, in the kind and range declared.
- **`undetermined`**: the declared measurements of that type the excerpt does not state.
- **`unmatched`**: anything the excerpt clearly states that none of the declared ids can hold —
  `{kind: "type" | "state" | "measurement", name, cite}`, where `cite` names a public
  specification a reviewer can check (for example *SAM v1.6 §1.3*). Never quote the file.

<!-- then, per call -->

# The start of the file

({{binary_before}})

{{excerpt}}
```

In `prompts.py`, after `READBACK`:

```python
CHARACTERISE_FAMILY: PromptId = "builder.characterise-family.v1"
"""The start of a sample in, the families it could belong to out (14.7.7). Egress door 6.
The first of the characteriser's two calls, the family step goal extraction takes (#194)."""

CHARACTERISE: PromptId = "builder.characterise.v1"
"""The start of a sample in, its declared type, the states and measurements it states, and
what it states that nothing declares (`unmatched`, stored only) out (14.7.7). Egress door 6."""
```

and add both to `TEMPLATES`.

- [x] **Step 4: Declare the replies**

In `authoring/types.py`, after `FamilyChoice`:

```python
class CharacteriseFamilies(_Shape):
    """The characteriser's first call (14.7.7): the families a sample could belong to. Empty
    means *none fits, or it cannot tell* — an answer, never a refusal."""

    families: list[str] = []


class ReadMeasurement(_Shape):
    """One declared measurement a sample's start states, as a model read it."""

    id: str
    value: HumanParamValue


class Unmatched(_Shape):
    """Something a sample states that no declared id can hold (14.7.7). **Stored only**:
    never admitted, never shown, never queued. #236 reads these to propose vocabulary."""

    kind: Literal["type", "state", "measurement"]
    name: Prose
    cite: Prose


class CharacteriseReply(_Shape):
    """The characteriser's second call (14.7.7). Every id is admitted against the chosen
    type's declarations before anything reads it."""

    type_id: str | None = None
    states: list[str] = []
    measurements: list[ReadMeasurement] = []
    undetermined: list[str] = []
    unmatched: list[Unmatched] = []
```

- [x] **Step 5: Write the calls**

In `authoring_ai.py`:

1. Import `CharacteriseRequest` from `comeni_core.artifact.egress`, and `CharacteriseFamilies` and `CharacteriseReply` from `mendel_api.authoring.types`. Add both reply types to `Outcome.reply`'s union.
2. Add to `Purpose`:

```python
    CHARACTERISE_FAMILY = "characterise_family"
    CHARACTERISE = "characterise"
```

3. Widen `_call`'s and `_record`'s `request` parameter to `AuthoringRequest | CharacteriseRequest`. `_record` reads only `request.registry`, which both carry.
4. Add, after `read_back`:

```python
# ── the characteriser (14.7.7) ─────────────────────────────────────────────────────────────


def compose_characterise(
    excerpt: str, *, binary_before: bool, registry: str | None
) -> CharacteriseRequest:
    """Door 6's payload. The excerpt is bounded by its own type (`marks.SampleText`)."""
    return CharacteriseRequest(excerpt=excerpt, binary_before=binary_before, registry=registry)


def _excerpt_values(request: CharacteriseRequest) -> dict[str, str]:
    return {
        "excerpt": request.excerpt,
        "binary_before": (
            "binary bytes came before this text"
            if request.binary_before
            else "no binary bytes before this text"
        ),
    }


def offered(stack, type_id: str) -> tuple[set[str], set[str]]:
    """The states a type declares, and the measurements whose `describes:` names it (spec §2:
    the registry decides which facts a model may read; a bench fact can never be offered)."""
    states = set(stack.vocabulary.types.get(type_id, ()))
    measurements = {
        m_id for m_id, m in stack.measurements.measurements.items() if m.describes == type_id
    }
    return states, measurements


def _types_text(stack, types: Sequence[str]) -> str:
    """Each type with its states, then the measurements describing it. **Each family whole.**"""
    lines = []
    for type_id in sorted(types):
        states, measured = offered(stack, type_id)
        lines.append(f"  {type_id} — states: {', '.join(sorted(states)) or '(none)'}")
        for m_id in sorted(measured):
            m = stack.measurements.get(m_id)
            holds = ", ".join(str(v) for v in m.values) if m.values else m.kind.value
            unit = f" {m.unit}" if m.unit else ""
            lines.append(f"      {m_id} ({holds}{unit}) — {m.description}")
    return "\n".join(lines)


def characterise_families(
    request: CharacteriseRequest,
    *,
    stack,
    client: Client | None = None,
    session_id: str | None = None,
) -> Outcome:
    """The start of a sample in, the families it could be out (14.7.7). An empty list is an
    answer: none fits, or the model cannot tell."""
    return _call(
        request,
        purpose=Purpose.CHARACTERISE_FAMILY,
        prompt_id=prompts.CHARACTERISE_FAMILY,
        shape=CharacteriseFamilies,
        values={"families": _families_text(stack), **_excerpt_values(request)},
        admit=lambda reply: _admit_families(reply, stack),
        client=client,
        session_id=session_id,
        choices={"families": sorted(stack.families.families)},
    )


def characterise(
    request: CharacteriseRequest,
    *,
    stack,
    families: Sequence[str] | None,
    client: Client | None = None,
    session_id: str | None = None,
) -> Outcome:
    """The start of a sample in, its type, states and facts out, admitted (14.7.7).

    `families` from the first call shows each family whole; `None`, with the family step off,
    shows every type. A value outside its declaration is dropped, as an inspector's would be;
    an id outside what was offered refuses the whole reply.
    """
    shown = (
        sorted(stack.vocabulary.types)
        if families is None
        else stack.families.types_of(families, stack.vocabulary.types)
    )
    return _call(
        request,
        purpose=Purpose.CHARACTERISE,
        prompt_id=prompts.CHARACTERISE,
        shape=CharacteriseReply,
        values={"types": _types_text(stack, shown), **_excerpt_values(request)},
        admit=lambda reply: _admit_characterised(reply, shown, stack),
        client=client,
        session_id=session_id,
        choices={"type_id": list(shown)},
    )


def _admit_characterised(
    reply: CharacteriseReply, shown: Sequence[str], stack
) -> CharacteriseReply:
    """MI0204 for a type not shown; MI0205 for a state or measurement that type does not offer.
    A value outside its declaration is dropped, never refused (spec §7)."""
    if reply.type_id is None:
        return reply.model_copy(update={"states": [], "measurements": [], "undetermined": []})
    if reply.type_id not in shown:
        raise ValueError(
            coded("MI0204", f"the answer names a type it was not shown: {reply.type_id}")
        )
    states, measured = offered(stack, reply.type_id)
    named = set(reply.states) | {m.id for m in reply.measurements} | set(reply.undetermined)
    foreign = sorted(named - states - measured)
    if foreign:
        raise ValueError(
            coded("MI0205", f"{reply.type_id} offers none of: {', '.join(foreign)}")
        )
    kept = []
    for m in reply.measurements:
        try:
            stack.measurements.check(m.id, m.value)
        except (ValueError, KeyError):
            continue
        kept.append(m)
    return reply.model_copy(update={"measurements": kept})
```

`_admit_families` takes a `FamilyChoice` today and reads only `.families`. Widen its annotation to `FamilyChoice | CharacteriseFamilies`; the body is unchanged.

In `services/models.py`, add to `PURPOSES`:

```python
    ("builder", "characterise_family"): c.MODEL_TALK,
    ("builder", "characterise"): c.MODEL_TALK,
```

- [x] **Step 6: Run them to verify they pass**

Run the Step 2 command.
Expected: PASS. If `client.choices[0]["type_id"]` holds the ids in a different order, the server-side `choices` list is sorted; `shown` comes from `types_of` sorted. Sort it in `characterise` and keep the test.

Then run: `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api -q`
Expected: PASS. If a test holds `Purpose` to the `PURPOSES` map or to the settings catalogue, follow what it says. A purpose with no setting is a call nobody can route.

- [x] **Step 7: Check, then commit**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel make check`
Expected: green.

```bash
git add packages/mendel-api
git commit -m "feat(api): the characteriser's two calls — families, then the type, its states and facts, admitted (#135)"
```

---

## Execution record

Executed 2026-10-04, in one hand.

- **Task 1** (1b0376ec, lint fixed in acec32a6): the branch drawn as planned nodes; 31 protocol tests. *Lint was not read before the commit*: the background job's exit status was `echo`'s, not `make`'s. Fixed in its own commit; since then `make`'s own code is read.
- **Task 2** (a07c6978): `AiPoint.CHARACTERISE`, `PremiseOrigin.MODEL_READ`, `_BY_SOURCE[MODEL]` (the build died on `KeyError: model` before it), the `meta` reason. `make verify` green.
  - *Ruling:* the planned test *every value source has a premise origin* was dropped. `_BY_SOURCE` was never total: `DERIVED` is absent and no profile carries it.
  - *Ruling:* the materialise reason belongs to a `meta` entry, not `Why.reason`. The file test asserts both the premise sentence and `single_end`'s reason; `_build_measured` gained `source` and `paired` parameters. Watched failing without the new branch.
- **Task 3** (9289c9ba): door 6, `Mark.SAMPLE`, `SampleText`, `SAMPLE_FIELDS`. Both guards watched failing (recorded in the guard ledger). 59 egress tests.
- **Task 4** (8f2b116b): two prompts, the reply shapes and the two admitted calls. 43 tests; `make check` 3353 passed.
  - *Ruling:* test fixtures corrected. A digest needs `sha256:`, and the transport receives chat messages, so `_text()` joins them. The plan's `in sent[0]` checks would have passed vacuously on a list.
