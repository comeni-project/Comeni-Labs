# Characteriser 5 — every property carries its evidence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local model's reading gets through when its type is right. Each property it reads carries a quote, which the engine checks is really in the file, and an unproven property is dropped rather than sinking the reply. Where nothing is offered, nothing can be written.

**Architecture:** `comeni_ai.formats.with_choices` learns that an empty allowed list on an array means *none* (`maxItems: 0`), and `_call` stops dropping empty lists. `CharacteriseReply` v2 puts `evidence` on each state and measurement. `builder.characterise.v2` asks for it. `_admit_characterised` checks each quote against the excerpt and drops what it cannot find. Nothing downstream changes: facts and readings keep ids only.

**Tech Stack:** pydantic 2, `comeni_ai`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-04-the-characteriser-design.md` §14 (the amendment), decided on #244. It runs between plan 3's Task 3 and its Task 4, whose walk it unblocks.

## Global Constraints

- **Evidence never enters a fact, a `SampleReading`, or `pipeline.yml`**: those keep ids (spec §14).
- **A type or family not offered is still MI0204; a state or measurement id not offered is still MI0205.** Only an unproven or undetermined id is dropped.
- **Evidence matches** when it is at least 3 characters and appears in the excerpt once runs of whitespace (spaces, tabs, newlines) are compared as one space. The match is case-sensitive.
- A new prompt is a new file (`v2`), and `v1` is retired, kept loadable.
- Python tests always run with `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`; `make check` on its own before each commit.

## Review Focus

1. **A quote that is a single common token** (`"1"`, `"A"`) proves almost anything. The 3-character floor is the only defence, and a reviewer should say whether it is enough. Pinned in Task 2.
2. **A provider that ignores the schema** (the in-prompt reply format) can still write a state on a type with none: admission still refuses it as MI0205. Pinned in Task 2.
3. **An empty `choices` list on a scalar field** (`already_option` with no options) must stay unconstrained, as today. Pinned in Task 1.
4. **A tab-separated header quoted with spaces** (`@HD VN:1.6 SO:coordinate` against `@HD\tVN:1.6\tSO:coordinate`) must match. Pinned in Task 2.
5. **v1 rows in `ai_invocation`** still load their template. Pinned in Task 2 by `test_a_retired_template_is_still_reachable`.

---

### Task 1: An empty allowed list on an array allows nothing

**Files:**
- Modify: `packages/comeni-ai/src/comeni_ai/formats.py:144-190` (`with_choices`, a new `_array_on`)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_ai.py:655` (`held`)
- Test: `packages/comeni-ai/tests/test_formats.py`

**Interfaces:**
- Produces: `with_choices(schema, {"states": []})` sets `maxItems: 0` on the nearest array along the path. For a path with no array on it, an empty list leaves the field unconstrained.

- [ ] **Step 1: Write the failing tests**

```python
class _Read(BaseModel):
    type_id: str | None = None
    states: list[str] = []
    measurements: list[_Value] = []      # _Value: {id: str, value: int}


def test_an_empty_list_on_an_array_allows_no_items():
    out = with_choices(_Read.model_json_schema(), {"states": [], "measurements.id": []})
    assert out["properties"]["states"]["maxItems"] == 0
    assert out["properties"]["measurements"]["maxItems"] == 0


def test_an_empty_list_on_a_scalar_leaves_it_unconstrained():
    out = with_choices(_Read.model_json_schema(), {"type_id": []})
    assert "enum" not in str(out["properties"]["type_id"])
```

Declare `_Value(BaseModel): id: str; value: int` beside it, and import `BaseModel` if the file does not already.

- [ ] **Step 2: Run them; expected FAIL** (`KeyError`/no `maxItems`).

`uv run pytest packages/comeni-ai/tests/test_formats.py -q`

- [ ] **Step 3: Implement**

In `with_choices`, before the targets loop:

```python
    for path, values in choices.items():
        if not values:
            # **Nothing offered is nothing allowed** (#244): an array gets `maxItems: 0`. An enum
            # of nothing is a schema a server may reject, so a scalar is left as it was.
            array = _array_on(out, out, path.split("."))
            if array is not None:
                array["maxItems"] = 0
            continue
        for target in _targets(out, out, path.split("."), path):
            target["enum"] = list(values)
```

and:

```python
def _array_on(root: dict, node: dict, parts: list[str], found: dict | None = None):
    """The nearest array along `path`, or `None`: where *no items* can be said."""
    node = _deref(root, node)
    if node.get("type") == "array":
        found = node
        node = _deref(root, node["items"])
    if "anyOf" in node:
        branches = [b for b in node["anyOf"] if b.get("type") != "null"]
        return _array_on(root, branches[0], parts, found) if branches else found
    if not parts:
        return found
    properties = node.get("properties", {})
    if parts[0] not in properties:
        raise KeyError(f"{'.'.join(parts)}: no field {parts[0]!r} here")
    return _array_on(root, properties[parts[0]], parts[1:], found)
```

In `authoring_ai._call`, `held` keeps empty lists. Change it to `held = dict(choices) if choices else None`, and update the comment above it: an empty list now reaches `with_choices`, which allows no items on an array and leaves a scalar unconstrained.

- [ ] **Step 4: Run them; expected PASS.** Then run `uv run pytest packages/comeni-ai -q` and `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api -q`.

- [ ] **Step 5: `make check`, then commit.** `feat(ai): an empty allowed list on an array allows nothing (#244)`

---

### Task 2: Reply v2 with evidence, checked against the excerpt

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (`StateRead`; `ReadMeasurement.evidence`; `CharacteriseReply.states`)
- Create: `packages/mendel-api/src/mendel_api/authoring/prompts/builder.characterise.v2.md`
- Modify: `packages/mendel-api/src/mendel_api/authoring/prompts.py` (`CHARACTERISE` → v2; v1 to `RETIRED`)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_ai.py` (`characterise`, `_admit_characterised`, `_evidenced`)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py` (`answer_with_reading`: `reply.states` are objects now)
- Test: `packages/mendel-api/tests/test_authoring_characterise.py`, `test_characterise_reading.py`, `test_authoring_prompts.py`

**Interfaces:**
- Produces:
  - `types.StateRead(id: str, evidence: Prose)`;
  - `ReadMeasurement(id, value, evidence: Prose = "")`;
  - `CharacteriseReply.states: list[StateRead]`;
  - `authoring_ai._evidenced(quote: str, excerpt: str) -> bool`.

- [ ] **Step 1: Write the failing tests** (in `test_authoring_characterise.py`; `_reply` builds states as `[{"id": s, "evidence": "SO:coordinate"}]` from now on, so update it and every call that passes `states=` as a list of ids)

```python
def test_a_state_proven_by_a_line_of_the_file_is_admitted(stack, clean_forge):
    reply = _reply(states=[{"id": "coordinate_sorted", "evidence": "@HD VN:1.6 SO:coordinate"}])
    outcome = ai.characterise(_request(), stack=stack, families=["alignment"],
                              client=Choosing(reply))
    assert outcome.admitted and [s.id for s in outcome.reply.states] == ["coordinate_sorted"]


def test_a_state_whose_quote_is_not_in_the_file_is_dropped_and_the_type_stands(stack, clean_forge):
    reply = _reply(states=[{"id": "coordinate_sorted", "evidence": "SO:coordinate"},
                           {"id": "deduplicated", "evidence": "@PG ID:picard MarkDuplicates"}])
    outcome = ai.characterise(_request(), stack=stack, families=["alignment"],
                              client=Choosing(reply))
    assert outcome.admitted and outcome.reply.type_id == "alignment.bam"
    assert [s.id for s in outcome.reply.states] == ["coordinate_sorted"]


def test_a_quote_too_short_to_prove_anything_is_dropped(stack, clean_forge):
    reply = _reply(states=[{"id": "coordinate_sorted", "evidence": "SO"}])
    outcome = ai.characterise(_request(), stack=stack, families=["alignment"],
                              client=Choosing(reply))
    assert outcome.admitted and outcome.reply.states == []


def test_undetermined_ids_nothing_offered_are_dropped_not_refused(stack, clean_forge):
    reply = _reply(undetermined=["deduplicated", "chromosome_length"])
    outcome = ai.characterise(_request(), stack=stack, families=["alignment"],
                              client=Choosing(reply))
    assert outcome.admitted and outcome.reply.undetermined == []


def test_a_state_on_a_type_that_declares_none_is_still_refused(stack, clean_forge):
    reply = _reply(type_id="genome.fasta",
                   states=[{"id": "sorted by coordinate", "evidence": ">chr1"}])
    outcome = ai.characterise(_request(">chr1 test\nACGT\n" * 20, binary_before=False),
                              stack=stack, families=["genome"], client=Choosing(reply))
    assert not outcome.admitted and outcome.code == "MI0205"


def test_nothing_offered_is_nothing_the_server_allows(stack, clean_forge):
    client = Choosing(_reply(type_id="genome.fasta", states=[]))
    ai.characterise(_request(">chr1\nACGT\n" * 30, binary_before=False), stack=stack,
                    families=["genome"], client=client)
    assert client.choices[0]["states"] == []


def test_evidence_is_compared_with_whitespace_as_one_space():
    assert ai._evidenced("@HD VN:1.6  SO:coordinate", "@HD\tVN:1.6\tSO:coordinate\n")
    assert not ai._evidenced("SO:queryname", "@HD\tVN:1.6\tSO:coordinate\n")
```

In `test_characterise_reading.py`, update every `CharacteriseReply(…, states=[…])` to `StateRead` objects (`StateRead(id="coordinate_sorted", evidence="SO:coordinate")`), and make the `_read` helper's type replies carry `"states": []`. In `test_authoring_prompts.py`, add `"builder.characterise.v1"` to nothing new (it carries the block), and assert v2's body says `"evidence"` and `"quote"`.

- [ ] **Step 2: Run them; expected FAIL.**

- [ ] **Step 3: The prompt v2**

Copy `builder.characterise.v1.md` to `v2`, and replace its *What to write* list with:

```markdown
- **`type_id`**: one of the type ids above, or `null`.
- **`states`**: `{id, evidence}` for each declared state of that type the excerpt states.
  `evidence` is the line of the excerpt that states it, **quoted exactly**. No line, no state:
  never list a state because it is possible, only because a line says so.
- **`measurements`**: `{id, value, evidence}` for each declared measurement of that type whose
  value a line of the excerpt states, in the kind and range declared, with that line quoted.
- **`undetermined`**: the declared measurements of that type the excerpt does not state.
- **`unmatched`**: anything the excerpt clearly states that none of the declared ids can hold —
  `{kind: "type" | "state" | "measurement", name, cite}`, where `cite` names a public
  specification a reviewer can check (for example *SAM v1.6 §1.3*). Never quote the file here.
```

In `prompts.py`, `CHARACTERISE = "builder.characterise.v2"`, with a docstring line: *v2 (#244): each state and measurement quotes the line that states it, and the engine checks the quote.* Add `"builder.characterise.v1"` to `RETIRED`.

- [ ] **Step 4: The shapes, admission and recording**

`types.py`:

```python
class StateRead(_Shape):
    """A declared state a sample's start states, and the line that states it (#244)."""

    id: str
    evidence: Prose
```

`ReadMeasurement` gains `evidence: Prose = ""`; `CharacteriseReply.states: list[StateRead] = []`.

`authoring_ai.py`:

```python
EVIDENCE_FLOOR = 3
"""The shortest quote that can prove anything (#244). A single character is in every file."""


def _evidenced(quote: str, excerpt: str) -> bool:
    """Whether `quote` is in the excerpt, runs of whitespace compared as one space (#244)."""
    squash = lambda text: " ".join(text.split())  # noqa: E731
    found = squash(quote)
    return len(found) >= EVIDENCE_FLOOR and found in squash(excerpt)
```

`characterise` passes `request.excerpt` to `_admit_characterised(reply, shown, stack, excerpt)`. In it:
- the `foreign` check reads `{s.id for s in reply.states}`;
- `undetermined` keeps only ids in `measured` and not read (no refusal);
- `states` keeps only those with `_evidenced(s.evidence, excerpt)`;
- `measurements` keeps only those that pass `measurements.check` **and** `_evidenced(m.evidence, excerpt)`.

`authoring.py`, in `answer_with_reading`: `states=[s.id for s in reply.states]` wherever `list(reply.states)` was. The reading and the fact hold ids, never evidence.

- [ ] **Step 5: Run them; expected PASS**, then the whole `packages/mendel-api` suite.

- [ ] **Step 6: `make check`, then commit.** `feat(api): the characteriser's reply v2 — each property quotes its line, and the engine checks it (#244)`

---

### Task 3: Walk it again

- [ ] Rebuild `ai-worker`; make four sessions as plan 3's Task 4 did; run `scratchpad/pp/ai.mjs`.
- [ ] Expected: FASTA → `genome.fasta · read by AI`, and the question closes. BAM on the genome question → `alignment.bam`, `coordinate_sorted · read by AI`, and the question stays. FASTQ `.txt` → handed back and measured.
- [ ] Read each reply in `ai_invocation`: the evidence quoted, and what was dropped. File any new defect as an issue first.
- [ ] Return to plan 3, Task 4: screenshots of A3, A4, A11, then the comparison with the artboards.

---

## Execution record

*(Filled in while executing.)*
