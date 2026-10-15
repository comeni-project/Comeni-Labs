# Explain the inputs (Part I.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every question about a researcher's data says what the thing is (curated), why this
analysis needs it (engine), and what a sample would settle, and calls the thing by its name.

**Architecture:** Two optional registry fields (`name`, `explain`) are read by `comeni-core` and
never reach the resolver or emitter. The gap walk (`mendel_api/services/gaps.py`) records who
consumes each leaf and which rule reads each measurement; a new `services/explain.py` turns a gap
into an `Explanation` that gathering stores on the gap's offer (`GapOffer.explain`). The browser
draws it under the question, open or collapsed by a browser-kept setting.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, Postgres (throwaway on :5442), React 19, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-13-part-i1-explain-the-inputs-design.md`

## Global Constraints

- Neither `name` nor `explain` reaches the resolver, the router or the emitter: same goal →
  byte-identical `.nf` (invariant 10).
- Registry fields are optional; nothing refuses for their absence. Fallbacks: a type's name → its
  id; a measurement's name → its `description`, else its id.
- No sub-fields under `explain`, no lint rule, no `TypeExtension` override (`add_states` with
  anything else already refuses, MD0007; leave that as is).
- Card copy contains no *MB*, *KB*, *bytes* or mention of the AI read (spec §2, operator). The
  measured result's step trail, which the server writes after a measurement, is a record and is
  not card copy; it is untouched.
- Every new string follows `docs/design/voice.md` (Task 7): confident, slightly caring,
  professional, scientific.
- Marks are the two words `curated` and `engine` (`mendel_authoring.brief.TextSource`).
- Work on `stage-four-the-consultant-build`. Nothing is pushed. Registry edits are a local branch
  in the `registry/` submodule, `explain-the-inputs`, with the pointer moved here.
- Python tests run through the test database: `make test-db` once, then
  `MENDEL_DATABASE_URL=postgresql+psycopg://comeni:comeni@127.0.0.1:5442/mendel_test uv run pytest …`
  (read the exact URL `make test-db` prints; Part H's wrapper `$SP/part-h-run` did the same).

## Where this plan departs from the spec

Each is a ruling the executor carries; none changes what the spec decided.

- **The steps line** reads *Steps that can read it: STAR, HISAT2, featureCounts. Which of them
  run depends on choices still to come.*, not *Read by STAR_ALIGN or HISAT2_ALIGN (whichever is
  chosen), then FEATURECOUNTS*: the walk knows the candidate consumers but not their order or
  which are alternatives, and tools have declared names and descriptions where processes do
  not. Cost if wrong: one sentence in `Explain.tsx`.
- **What a sample settles** is named by each measurement's `description`, lower-cased
  (*sequenced read length*), not hand-phrased (*your read length*): a new inspector must change
  the copy with no edit (spec §4). Cost if wrong: better `description`s in the registry.
- **Names reach** the question and the goal card's *You have* / *You get*. The wrap-up's *To run
  it you need* keeps ids: it is built in the pure `mendel-authoring` behind the `Declared` port,
  and widening the port belongs with I.2, which rewrites what the wrap-up says.
- **The setting is kept by the browser** (`Where.BROWSER`, like the theme): it is how one person
  likes to read, not a rule of the installation.

## Review Focus

1. **A proposal stored before this change** (no `explain` in its payload) still opens: the card
   draws no panel and no error. Test in Task 4 and Task 6.
2. **A lab layer's type with no `name`/`explain`**: the question reads with the id and the panel
   shows only the engine half. Test in Task 4.
3. **A sample that would settle nothing still open** (read length and pairing already answered):
   the generic headline, never a promise of questions that will not come. Test in Task 4 and 6.
4. **Storage refused** (private window): the panel opens, the default. Covered by
   `useBrowserSetting`'s memory fallback; asserted in Task 6.
5. **A measurement two rules read**: both reasons, in rule-table order, no duplicate. Test in
   Task 3.

---

### Task 1: `name` and `explain` in the declared kinds

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/vocabulary.py` (`TypeDeclaration`,
  `Vocabulary`, `Vocabulary.of`)
- Modify: `packages/comeni-core/src/comeni_core/declared/measurement.py` (`Measurement`)
- Test: `packages/comeni-core/tests/test_explanations_declared.py`

**Interfaces:**
- Produces: `TypeDeclaration.name: str | None`, `TypeDeclaration.explain: str | None`;
  `Vocabulary.names: dict[str, str]`, `Vocabulary.explains: dict[str, str]` (only types that
  declare one); `Measurement.explain: str | None`.

- [ ] **Step 1: Write the failing test**

```python
"""A type may say its name and what it is; a measurement may say what it is (Part I.1 §3).
Both optional, and neither is read by anything that builds a pipeline."""

import pytest
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.vocabulary import Vocabulary


def _write(root, rel, body):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_a_type_carries_its_name_and_explanation(tmp_path):
    _write(tmp_path, "vocabulary/annotation.gtf.yml",
           "declares: vocabulary\nid: annotation.gtf\nscope: run\n"
           "name: gene annotation (GTF)\nexplain: Where each gene lies.\n")
    _write(tmp_path, "vocabulary/genome.fasta.yml",
           "declares: vocabulary\nid: genome.fasta\nscope: run\n")
    vocabulary = Vocabulary.load(tmp_path)
    assert vocabulary.names == {"annotation.gtf": "gene annotation (GTF)"}
    assert vocabulary.explains == {"annotation.gtf": "Where each gene lies."}


def test_an_extension_cannot_rename_a_type(tmp_path):
    _write(tmp_path, "vocabulary/x.yml",
           "declares: vocabulary\nid: annotation.gtf\nadd_states: [sorted]\nname: other\n")
    with pytest.raises(ValueError, match="MD0007"):
        Vocabulary.load(tmp_path)


def test_a_measurement_carries_its_explanation(tmp_path):
    _write(tmp_path, "measurements/read_length.yml",
           "declares: measurement\nid: read_length\nkind: integer\nminimum: 1\n"
           "description: Sequenced read length\nexplain: Bases per read.\n")
    _write(tmp_path, "measurements/organism.yml",
           "declares: measurement\nid: organism\nkind: string\n")
    registry = MeasurementRegistry.load(tmp_path)
    assert registry.get("read_length").explain == "Bases per read."
    assert registry.get("organism").explain is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_explanations_declared.py -v`
Expected: FAIL — `extra fields not permitted` for `name` / `explain`, and `Vocabulary` has no
`names`. If `MeasurementRegistry.load` or the `kind: string` spelling differ from the fixture,
read `test_measurement.py`'s `_layer` and correct the fixture, not the code.

- [ ] **Step 3: Implement**

In `TypeDeclaration`, after `test_data`:

```python
    name: str | None = Field(default=None, min_length=1, max_length=80)
    """What a person calls it, as it reads mid-sentence: *gene annotation (GTF)*. Shown wherever a
    person reads the type; absent, the id is shown. **Read by nothing that builds**: the
    resolver, the router and the emitter never see it (Part I.1)."""
    explain: str | None = Field(default=None, min_length=1, max_length=600)
    """What it is and where it usually comes from, one short paragraph, written to
    `docs/design/voice.md`. Shown under a question about it, marked *curated*, and handed to the
    AI as a source (protocol rule 12)."""
```

(Import `Field` from pydantic if the module does not already.) In `Vocabulary`, beside
`params`:

```python
    names: dict[str, str] = {}
    """Type id → its declared `name`, for the types that declare one."""
    explains: dict[str, str] = {}
    """Type id → its declared `explain`, for the types that declare one."""
```

In `Vocabulary.of`, collect `names`/`explains` in the loop the way `params` is collected
(`if entry.name: names[type_id] = entry.name`, same for `explain`) and pass them to `cls(...)`.
If `with_proposals` or any other constructor of `Vocabulary` copies fields one by one, carry the
two maps through it (grep `cls(` and `Vocabulary(` in the file).

In `Measurement`, after `cite`:

```python
    explain: str | None = None
    """What it is and how a person finds it out, one short paragraph (Part I.1). Its name is
    `description`. Read by nothing that builds."""
```

- [ ] **Step 4: Run the test and the package**

Run: `uv run pytest packages/comeni-core -q`
Expected: PASS. Then `uv run python tools/generate_types.py --check`; if it reports a stale
stub, run it without `--check` and include the regenerated `.pyi`.

- [ ] **Step 5: Commit**

```bash
git add packages/comeni-core
git commit -m "feat: a type may declare its name and what it is; a measurement what it is (#293)"
```

---

### Task 2: The shipped registry's names and explanations

**Files:**
- Modify (in `registry/`, branch `explain-the-inputs`): `vocabulary/types/*.yml` (8 files),
  `vocabulary/measurements/{read_length,paired,strandedness}.yml`
- Test: `tests/registry/test_explanations.py`

**Interfaces:**
- Consumes: Task 1's fields; `mendel_api.services.gaps.gaps(want, facts, stack)`.

- [ ] **Step 1: Write the failing test**

```python
"""Every question the shipped registry can ask says what it is about (Part I.1 §3).

A test of our own data, not a rule a lab's layer must pass: a lab's type with no explanation
still loads, and its question shows the engine's half alone."""

from mendel_api.services import gaps, registry


def _askable():
    stack = registry.stack()
    found = {}
    for type_id in sorted(stack.vocabulary.types):
        result = gaps.gaps([type_id], [], stack)
        if isinstance(result, gaps.Unreachable):
            continue
        for gap in result:
            found[(gap.kind.value, gap.subject)] = gap
    assert found, "no want in the shipped registry produced a gap — measuring nothing"
    return stack, found


def test_every_type_has_a_name():
    stack = registry.stack()
    assert stack.vocabulary.types
    assert sorted(set(stack.vocabulary.types) - set(stack.vocabulary.names)) == []


def test_every_question_the_registry_can_ask_is_explained():
    stack, found = _askable()
    missing = [subject for (kind, subject) in found
               if (kind == "input" and subject not in stack.vocabulary.explains)
               or (kind == "measurement" and not stack.measurements.get(subject).explain)]
    assert missing == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/registry/test_explanations.py -v`
Expected: FAIL — every type is missing a name; `fastq.reads`, `genome.fasta`, `annotation.gtf`,
`read_length`, `paired`, `strandedness` are unexplained.

- [ ] **Step 3: Write the registry text**

```bash
git -C registry switch -c explain-the-inputs
```

Add to each type file (append; keep everything else):

| File | `name:` | `explain:` |
|---|---|---|
| `fastq.reads.yml` | `sequencing reads (FASTQ)` | `The reads your sequencer produced, one file per sample, or two when the reads are paired. Your sequencing facility delivers them, usually compressed (.fastq.gz).` |
| `genome.fasta.yml` | `reference genome (FASTA)` | `The genome sequence of your organism, which your reads are aligned against. Take it from Ensembl, GENCODE or UCSC, and note the release: your gene annotation must come from the same one.` |
| `annotation.gtf.yml` | `gene annotation (GTF)` | `A table of where each gene and its exons lie on the genome. It comes from the same source and release as your reference genome (Ensembl, GENCODE or UCSC), so that the two agree.` |
| `alignment.bam.yml` | `aligned reads (BAM)` | — |
| `alignment.bai.yml` | `BAM index (BAI)` | — |
| `counts.matrix.yml` | `gene counts matrix` | — |
| `qc.report.yml` | `quality-control report` | — |
| `profile.yml.yml` | `data profile` | — |

Measurements (append `explain:`):

| File | `explain:` |
|---|---|
| `read_length.yml` | `How many bases each read holds, such as 50, 100 or 150. Your sequencing facility's run report states it, and so does any read in your FASTQ files.` |
| `paired.yml` | `Whether each fragment was read from both ends, giving two files per sample, or from one end only. Two files named _R1 and _R2, or _1 and _2, mean paired.` |
| `strandedness.yml` | `Whether your library preparation kept track of which DNA strand each read came from. The kit's name decides it: most current Illumina kits (TruSeq Stranded, for example) are reverse-stranded.` |

Write each `explain` as a folded scalar (`explain: >-` with the text indented on the next lines),
wrapped under 100 columns, the way `adapter_content.yml` writes `assertion_only_because`.

```bash
git -C registry add vocabulary
git -C registry commit -m "Vocabulary: names, and what each asked-for input and measurement is (comeni-labs #293)"
```

- [ ] **Step 4: Run the test, and the determinism suite**

Run: `uv run pytest tests/registry/test_explanations.py tests/registry -q`
Expected: PASS. Then `make check` (the emit and determinism tests prove no `.nf` changed).

- [ ] **Step 5: Commit the pointer**

```bash
git add registry tests/registry/test_explanations.py
git commit -m "feat: the shipped registry names every type and explains every question it can ask (#293)"
```

---

### Task 3: The gap walk says who reads each input and which rule reads each measurement

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/gaps.py`
- Test: `packages/mendel-api/tests/test_gaps.py` (append)

**Interfaces:**
- Produces: `Gap.used_by: tuple[str, ...]` (contract ids, walk order, deduplicated; default
  `()`), `Gap.decides: tuple[Decision, ...]` (`mendel_resolver.rules.format.Decision`, rule-table
  order; default `()`). `_premise_measurements(stack) -> dict[str, list[Decision]]`.

- [ ] **Step 1: Write the failing tests**

```python
def _by_subject(result):
    return {gap.subject: gap for gap in result}


def test_an_input_names_every_candidate_step_that_reads_it():
    found = _by_subject(g.gaps(["counts.matrix"], [], registry.stack()))
    readers = found["annotation.gtf"].used_by
    assert readers, "nothing reads the annotation — the walk recorded nothing"
    assert len(readers) == len(set(readers))
    assert any("featurecounts" in c for c in readers)


def test_a_premise_measurement_names_the_rule_that_reads_it():
    found = _by_subject(g.gaps(["counts.matrix"], [], registry.stack()))
    decides = found["read_length"].decides
    assert [d.because for d in decides] == ["read length determines which aligner is appropriate"]
    assert decides[0].cite.startswith("Dobin et al. 2013")


def test_a_carried_measurement_names_the_steps_that_read_its_type():
    found = _by_subject(g.gaps(["counts.matrix"], [], registry.stack()))
    assert found["paired"].used_by == found["fastq.reads"].used_by
    assert found["paired"].decides == ()


def test_the_same_want_gives_the_same_context_in_the_same_order():
    first = g.gaps(["counts.matrix"], [], registry.stack())
    assert first == g.gaps(["counts.matrix"], [], registry.stack())


def test_a_measurement_two_rules_read_lists_both_once(monkeypatch):
    """Review Focus 5."""
    stack = registry.stack()
    decision = stack.rules.decisions[0]
    doubled = stack.rules.model_copy(update={"decisions": [decision, decision]})
    stack = stack.model_copy(update={"rules": doubled})
    found = _by_subject(g.gaps(["counts.matrix"], [], stack))
    assert len(found["read_length"].decides) == 2
```

(Rule: two *distinct* rules both listed; the same rule object twice in the table is two
entries in the table and is listed twice — the test pins table order, not deduplication by
content. If `RuleTable` refuses a duplicate on `model_copy`, build the second decision with
`decision.model_copy(update={"because": "a second reason"})` and assert both `because`s in order.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest packages/mendel-api/tests/test_gaps.py -v`
Expected: the new tests FAIL with `AttributeError: 'Gap' object has no attribute 'used_by'`.

- [ ] **Step 3: Implement**

```python
from mendel_resolver.rules.format import Decision


class Gap(NamedTuple):
    kind: FactKind
    subject: str
    why: str
    used_by: tuple[str, ...] = ()
    """For an input, or a measurement carried in its type's `meta`: every candidate contract on
    the walk that consumes the type, in walk order (Part I.1 §4)."""
    decides: tuple[Decision, ...] = ()
    """For a measurement a rule reads: each decision whose `when` reads it, in table order."""
```

`_premise_measurements` returns `dict[str, list[Decision]]`: inside the `for decision in
stack.rules.decisions` loop, for each measurement `m` the row keys resolve to, append `decision`
to `read.setdefault(m, [])` once per decision (track with a per-decision set so two rows of one
decision append it once).

In `gaps()`:
- add `consumers: dict[str, list[str]] = {}`; in `walk`, inside `for port in contract.consumes`,
  before recursing: `if port.type_id and contract.id not in consumers.setdefault(port.type_id, []):
  consumers[port.type_id].append(contract.id)`;
- `premises = _premise_measurements(stack)`; the measurement set becomes
  `set(premises) | {…meta_key ones…}`;
- inputs: `Gap(FactKind.INPUT, t, "…", used_by=tuple(consumers.get(t, ())))`;
- measurements: `m_decl = stack.measurements.get(m)`;
  `used_by=tuple(consumers.get(m_decl.describes, ())) if m_decl.meta_key and m_decl.describes in
  leaves else ()`, `decides=tuple(premises.get(m, ()))`.

Grep for other callers of `_premise_measurements` (`grep -rn _premise_measurements packages`)
and give each the keys (`set(...)`).

- [ ] **Step 4: Run them**

Run: `uv run pytest packages/mendel-api/tests/test_gaps.py packages/mendel-api/tests/test_authoring_gathering.py -q`
Expected: PASS (the gathering suite still passes: `why` is unchanged and the new fields default).

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-api/src/mendel_api/services/gaps.py packages/mendel-api/tests/test_gaps.py
git commit -m "feat: each gap says which steps read it and which rule reads it (#293)"
```

---

### Task 4: The explanation on every question, and names in the engine's words

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/explain.py`
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (`Reason`, `Explanation`)
- Modify: `packages/mendel-api/src/mendel_api/authoring/envelopes.py` (`GapOffer.explain`)
- Modify: `packages/mendel-api/src/mendel_api/stages/gathering.py` (`_gap_question`,
  `offer_gap_or_card`, `_gap_options` labels, the goal card's `have`/`get`)
- Test: `packages/mendel-api/tests/test_gap_explain.py` (create)
- Modify tests pinning old words: `test_authoring_gathering.py:281`,
  `test_authoring_samples.py:235` (docstring only), `test_authoring_prompts.py:335` if it reads
  `_gap_question`'s output (it is a fixture string: leave it unless it fails)

**Interfaces:**
- Consumes: `Gap.used_by`, `Gap.decides` (Task 3); `Vocabulary.names/explains`,
  `Measurement.explain` (Task 1); `gathering._inspectable(stack) -> (measured, read)`.
- Produces:

```python
class Reason(_Shape):
    text: Prose
    detail: Prose | None = None   # a tool's description, or a rule's citation

class Explanation(_Shape):
    name: Prose                   # what the question is about, by its name
    what: Prose | None = None     # curated; absent when the registry says nothing
    needed: list[Reason] = []     # engine: who reads it, or what it decides
    reads: Literal["steps", "rule"] | None = None   # how to label `needed`
    settles: list[Prose] = []     # for an input: what a sample of it would answer, by name
    read_by: Literal["inspector", "ai"] | None = None  # who would read a sample

# services/explain.py
def name_of(stack, kind: FactKind, subject: str) -> str
def explanation(gap: Gap, found: list[Gap], stack, *, measured: dict[str, set[str]],
                read: set[str], characterisable: bool) -> Explanation
```

`GapOffer.explain: Explanation | None = None`.

- [ ] **Step 1: Write the failing tests**

```python
"""Each question says what it is about and why it is asked (Part I.1 §4)."""

import pytest
from mendel_api.authoring.envelopes import GapOffer
from mendel_api.authoring.types import FactKind
from mendel_api.services import explain, gaps, registry


@pytest.fixture
def scene():
    stack = registry.stack()
    found = gaps.gaps(["counts.matrix"], [], stack)
    return stack, found, {g.subject: g for g in found}


def _explained(scene, subject, *, measured=None, read=frozenset(), ai=False, found=None):
    stack, all_found, by = scene
    return explain.explanation(by[subject], found if found is not None else all_found, stack,
                               measured=measured or {}, read=set(read), characterisable=ai)


def test_an_input_says_what_it_is_and_which_steps_read_it(scene):
    got = _explained(scene, "annotation.gtf")
    assert got.name == "gene annotation (GTF)"
    assert got.what.startswith("A table of where each gene")
    assert got.reads == "steps" and got.needed
    assert all(r.text for r in got.needed)
    assert len({r.text for r in got.needed}) == len(got.needed)


def test_a_measurement_says_which_rule_it_decides(scene):
    got = _explained(scene, "read_length")
    assert got.name == "Sequenced read length"
    assert got.reads == "rule"
    assert got.needed[0].text == "read length determines which aligner is appropriate"
    assert got.needed[0].detail.startswith("Dobin et al. 2013")


def test_a_sample_settles_only_what_is_still_open(scene):
    """Review Focus 3."""
    measured = {"read_length": {"fastq.reads"}, "paired": {"fastq.reads"},
                "quality_encoding": {"fastq.reads"}}
    got = _explained(scene, "fastq.reads", measured=measured, read={"fastq.reads"})
    assert got.read_by == "inspector"
    assert got.settles == ["whether the library was sequenced paired-end",
                           "sequenced read length"]
    stack, found, by = scene
    without = [g for g in found if g.subject not in ("read_length", "paired")]
    none_left = _explained(scene, "fastq.reads", measured=measured, read={"fastq.reads"},
                           found=without)
    assert none_left.settles == [] and none_left.read_by == "inspector"


def test_a_type_no_inspector_reads_is_read_by_the_ai_when_it_may(scene):
    assert _explained(scene, "annotation.gtf", ai=True).read_by == "ai"
    assert _explained(scene, "annotation.gtf", ai=False).read_by is None


def test_a_type_with_nothing_declared_falls_back_to_its_id(scene, monkeypatch):
    """Review Focus 2: a lab's type with no name or explanation."""
    stack, found, by = scene
    bare = stack.vocabulary.model_copy(update={"names": {}, "explains": {}})
    stack = stack.model_copy(update={"vocabulary": bare})
    got = explain.explanation(by["annotation.gtf"], found, stack, measured={}, read=set(),
                              characterisable=False)
    assert got.name == "annotation.gtf" and got.what is None and got.needed


def test_an_offer_stored_before_explanations_still_reads():
    """Review Focus 1: a payload with no `explain` key."""
    block = {"kind": "question", "id": "gap-1", "asks": "x?", "why_open": "y",
             "options": [{"id": "have_it", "label": "I have it"}]}
    offer = GapOffer.model_validate({
        "offer": "gap", "subject": "genome.fasta", "kind": "input", "why": "y",
        "options": {"have_it": "I have it"}, "block": block,
        "context": {"draft_revision": 0, "decision_revision": 0, "session_version": 1,
                    "registry": ""}})
    assert offer.explain is None
```

Append to `test_authoring_gathering.py`, using its `_gathering` and `_payload` helpers:

```python
def test_a_gap_is_offered_with_its_name_and_explanation(clean):
    sid = _gathering(["counts.matrix"])
    payload = _payload(_pending_for(sid, "fastq.reads"))
    assert payload["block"]["asks"] == (
        "This analysis needs sequencing reads (FASTQ). Do you have one?")
    assert payload["explain"]["name"] == "sequencing reads (FASTQ)"
    assert payload["explain"]["needed"]
```

(If `GapOffer`'s `context` field differs from the fixture above, copy the shape from
`frontend/src/build/living/GapCard.test.tsx`'s `envelope`, which is generated from it.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest packages/mendel-api/tests/test_gap_explain.py packages/mendel-api/tests/test_authoring_gathering.py -k "explain or name" -v`
Expected: FAIL — `ModuleNotFoundError: mendel_api.services.explain`.

- [ ] **Step 3: Implement**

`authoring/types.py`, beside `Question`: the `Reason` and `Explanation` classes of the
Interfaces block, each with a one-line docstring (`Reason`: *one line of why, and where it comes
from*; `Explanation`: *what a question is about and why it is asked: `what` is curated, the rest
the engine's (Part I.1)*).

`authoring/envelopes.py`, `GapOffer`: `explain: Explanation | None = None` with the comment
*absent on offers made before Part I.1; the card then draws no panel*.

`services/explain.py`:

```python
"""What a question is about and why it is asked, from declared data only (Part I.1 §4).

`what` is curated (the registry's `explain`); `needed` and `settles` are the engine's, derived
from the gap walk. Nothing here calls a model; I.3 hands the same fields to one as sources.
"""

from mendel_authoring.brief import tool_of

from mendel_api.authoring.types import Explanation, FactKind, Reason
from mendel_api.services.gaps import Gap


def name_of(stack, kind: FactKind, subject: str) -> str:
    """A type by its declared name, a measurement by its description; the id when neither."""
    if kind is FactKind.INPUT:
        return stack.vocabulary.names.get(subject, subject)
    return stack.measurements.get(subject).description or subject


def _what(stack, gap: Gap) -> str | None:
    if gap.kind is FactKind.INPUT:
        return stack.vocabulary.explains.get(gap.subject)
    return stack.measurements.get(gap.subject).explain


def _steps(stack, contracts) -> list[Reason]:
    """One reason per tool, in walk order: its declared name and description, else its key."""
    seen, out = set(), []
    for contract_id in contracts:
        key = tool_of(contract_id)
        if key in seen:
            continue
        seen.add(key)
        tool = stack.tools.tools.get(key)
        out.append(Reason(text=tool.name if tool else key,
                          detail=tool.description if tool else None))
    return out


def _lower(text: str) -> str:
    return text[:1].lower() + text[1:]


def explanation(gap: Gap, found: list[Gap], stack, *, measured: dict[str, set[str]],
                read: set[str], characterisable: bool) -> Explanation:
    if gap.decides:
        needed = [Reason(text=d.because or f"decides the {d.targets()[0].of}", detail=d.cite)
                  for d in gap.decides]
        reads = "rule"
    else:
        needed = _steps(stack, gap.used_by)
        reads = "steps" if needed else None
    settles, read_by = [], None
    if gap.kind is FactKind.INPUT:
        open_measurements = [g.subject for g in found if g.kind is FactKind.MEASUREMENT]
        settles = [_lower(name_of(stack, FactKind.MEASUREMENT, m)) for m in open_measurements
                   if gap.subject in measured.get(m, set())]
        read_by = "inspector" if gap.subject in read else ("ai" if characterisable else None)
    return Explanation(name=name_of(stack, gap.kind, gap.subject), what=_what(stack, gap),
                       needed=needed, reads=reads, settles=settles, read_by=read_by)
```

(Check the name of `Decision`'s list accessor at `rules/format.py:173` — the plan calls it
`targets()`; use whatever that method is named. The `settles` order is the order of `found`,
which is sorted by measurement id: `paired` before `read_length`, as the test expects.)

`stages/gathering.py`:
- `_gap_question(gap, options, stack, seq)`: the input sentence becomes
  `f"This analysis needs {explain.name_of(stack, gap.kind, gap.subject)}. Do you have one?"`;
  the measurement sentence uses `explain.name_of(...)` too (same text as today).
- `_gap_options`: `(UPLOAD, "Yes — I'll upload a sample")` and
  `UPLOAD: "Not sure — measure it from a sample"` (voice: no first-person engine).
- `offer_gap_or_card`: after `options = …`, compute
  `measured, read = _inspectable(stack)` and
  `explained = explain.explanation(gap, found, stack, measured=measured, read=read,
  characterisable=_characterisable())`; add `"explain": explained.model_dump(mode="json")` to the
  proposed payload.
- the goal card: `have=f"You have: {', '.join(explain.name_of(stack, FactKind.INPUT, h.type_id)
  for h in goal.have) or 'nothing'}."` and `get` likewise over `goal.want`.
- import: `from mendel_api.services import explain` (add to the existing services import line).

Update the pinned words: `test_authoring_gathering.py:281` → `"This analysis needs sequencing
reads (FASTQ). Do you have one?"`. Grep both suites for the two old upload labels and update.

- [ ] **Step 4: Run them, then the mendel-api suite**

Run: `uv run pytest packages/mendel-api/tests/test_gap_explain.py packages/mendel-api/tests/test_authoring_gathering.py packages/mendel-api/tests/test_authoring_samples.py -q`
Expected: PASS. Then `uv run pytest packages/mendel-api -q -x` → PASS (the two #303 gzip tests
fail only under Python 3.14; note them, they are not this task's).

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-api
git commit -m "feat: every question says what it is about, by its name, and why it is asked (#293)"
```

---

### Task 5: *Explain each question* in Settings → Building

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/settings/catalogue.py` (`EXPLAIN`, `BUILDING`)
- Test: `packages/comeni-core/tests/test_settings_catalogue.py` (append)

**Interfaces:**
- Produces: setting key `building.explain`, `where=Where.BROWSER`, options `open` / `collapsed`,
  default `open`. The browser reads it with `useBrowserSetting("building.explain", "open")`.

- [ ] **Step 1: Write the failing test**

```python
def test_explain_each_question_is_kept_by_the_browser_and_starts_open():
    from comeni_core.settings.catalogue import BUILDING
    from comeni_core.settings.declare import Where

    setting = next(s for s in BUILDING.settings if s.key == "building.explain")
    assert setting.where is Where.BROWSER
    assert setting.default == "open"
    assert [o[0] if isinstance(o, tuple) else o.value for o in setting.options] == [
        "open", "collapsed"]
```

(Read how `Setting.choice` stores `options` — tuple or object — from `THEME` and adjust the
last assertion's accessor; the values and order are what matter.)

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_settings_catalogue.py -v -k explain`
Expected: FAIL — `StopIteration`.

- [ ] **Step 3: Implement**

```python
EXPLAIN = Setting.choice(
    key="building.explain",
    label="Explain each question",
    help=(
        "Under each question about your data: what it is, where it usually comes from, and why "
        "this analysis needs it. Kept by this browser. Each explanation can still be opened or "
        "folded on its own."
    ),
    options=[("open", "Open"), ("collapsed", "Collapsed")],
    default="open",
    where=Where.BROWSER,
)
```

`BUILDING.settings=(PACING, EXPLAIN, TIER4_ANSWERS)`, and its lede, which says *Neither choice
is read yet* and is no longer true, becomes `"How the build walks you through a pipeline, and
how much it explains on the way."`. If a catalogue test pins the old lede or the settings
count, update it.

- [ ] **Step 4: Run the settings tests**

Run: `uv run pytest packages/comeni-core -q -k setting`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/comeni-core
git commit -m "feat: Settings → Building → Explain each question, open by default (#293)"
```

---

### Task 6: The card: the explanation, the upload headline, the upload copy

**Files:**
- Run: `make client` (regenerates `frontend/src/api/`; never hand-edit)
- Create: `frontend/src/build/living/blocks/Explain.tsx`
- Modify: `frontend/src/build/living/blocks/GapCard.tsx`
- Modify: `frontend/src/build/living/blocks/SampleUpload.tsx`
- Test: `frontend/src/build/living/blocks/Explain.test.tsx` (create),
  `frontend/src/build/living/GapCard.test.tsx`, `frontend/src/build/living/SampleUpload.test.tsx`,
  `frontend/src/build/living/LivingSurface.test.tsx` (labels only)

**Interfaces:**
- Consumes: `proposal.envelope.explain` when `proposal.envelope.offer === "gap"` (generated type
  `Explanation`), the setting `building.explain`.
- Produces: `<Explain explanation={…} />`; `uploadHeadline(e: Explanation): string | null`
  exported from `Explain.tsx`.

- [ ] **Step 1: Regenerate the client**

Run: `make client`
Expected: `frontend/src/api/` gains `Explanation` and `Reason`, and `GapOffer.explain`.

- [ ] **Step 2: Write the failing tests**

`Explain.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { Explanation } from "../../../api/types";
import { storageName } from "../../../preferences/useBrowserSetting";
import { Explain, uploadHeadline } from "./Explain";

const GTF: Explanation = {
  name: "gene annotation (GTF)",
  what: "A table of where each gene and its exons lie on the genome.",
  needed: [{ text: "STAR", detail: "Aligns reads." }, { text: "featureCounts", detail: null }],
  reads: "steps", settles: [], read_by: "ai",
};

describe("what a question is about", () => {
  beforeEach(() => localStorage.clear());

  it("is open by default, with the curated and engine halves marked", () => {
    render(<Explain explanation={GTF} />);
    expect(screen.getByText(/A table of where each gene/)).toBeVisible();
    expect(screen.getByText("curated")).toBeInTheDocument();
    expect(screen.getByText("engine")).toBeInTheDocument();
    expect(screen.getByText(/STAR/)).toBeInTheDocument();
  });

  it("starts collapsed when the setting says so, and still opens by hand", () => {
    localStorage.setItem(storageName("building.explain"), "collapsed");
    render(<Explain explanation={GTF} />);
    expect(screen.queryByText(/A table of where each gene/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /What is this/ }));
    expect(screen.getByText(/A table of where each gene/)).toBeVisible();
  });

  it("draws only the engine half when the registry says nothing", () => {
    render(<Explain explanation={{ ...GTF, what: null }} />);
    expect(screen.queryByText("curated")).toBeNull();
    expect(screen.getByText("engine")).toBeInTheDocument();
  });

  it("draws nothing when there is nothing to say", () => {
    const { container } = render(
      <Explain explanation={{ ...GTF, what: null, needed: [], reads: null }} />);
    expect(container.textContent).toBe("");
  });

  it("names a rule and its citation for a measurement", () => {
    render(<Explain explanation={{ ...GTF, name: "Sequenced read length", reads: "rule",
      needed: [{ text: "read length determines which aligner is appropriate",
                 detail: "Dobin et al. 2013" }] }} />);
    expect(screen.getByText(/read length determines which aligner/)).toBeInTheDocument();
    expect(screen.getByText(/Dobin et al. 2013/)).toBeInTheDocument();
  });
});

describe("the upload headline", () => {
  it("names what a measured sample settles", () => {
    expect(uploadHeadline({ ...GTF, read_by: "inspector",
      settles: ["whether the library was sequenced paired-end", "sequenced read length"] }))
      .toBe("Have a sample to hand? Upload it and we'll measure the rest: whether the library "
        + "was sequenced paired-end, and sequenced read length. You won't need to answer those "
        + "yourself.");
  });
  it("promises nothing when nothing is left to settle (Review Focus 3)", () => {
    expect(uploadHeadline({ ...GTF, read_by: "inspector", settles: [] }))
      .toBe("Have a sample to hand? Upload it and we'll measure it.");
  });
  it("says the AI reads it, and says nothing about bytes", () => {
    const said = uploadHeadline({ ...GTF, read_by: "ai" })!;
    expect(said).toBe("Have a sample to hand? Upload it and the AI will read it for you. It "
      + "shows you what it found, and nothing is used until you've confirmed it.");
    expect(said).not.toMatch(/KB|MB|bytes/);
  });
  it("is absent when nothing would read a sample", () => {
    expect(uploadHeadline({ ...GTF, read_by: null })).toBeNull();
  });
});
```

In `GapCard.test.tsx`, add:

```tsx
  it("draws the explanation under the question, and none for an offer made before it", () => {
    const explained = { ...PAIRED, envelope: { ...PAIRED.envelope, explain: {
      name: "Whether the library was sequenced paired-end", what: "Read from both ends.",
      needed: [], reads: null, settles: [], read_by: null } } } as AuthoringProposal;
    const { unmount } = render(<GapCard proposal={explained} busy={false} onAnswer={vi.fn()} />);
    expect(screen.getByText("Read from both ends.")).toBeInTheDocument();
    unmount();
    render(<GapCard proposal={PAIRED} busy={false} onAnswer={vi.fn()} />);
    expect(screen.queryByText("curated")).toBeNull();
  });
```

In `SampleUpload.test.tsx`, replace the assertion at line 211 (the 8 KB sentence) with:

```tsx
    expect(screen.getByText(/Choose one file, or both files if your reads are paired/))
      .toBeTruthy();
    expect(document.body.textContent).not.toMatch(/4 MB|8 KB|the AI to read/);
```

and line 64's refusal assertion with `/3 files: choose one file, or both files if your reads
are paired/`. Update the labels in `GapCard.test.tsx:126`, `SampleUpload.test.tsx:12` and
`LivingSurface.test.tsx:376,420` to the Task 4 labels.

- [ ] **Step 3: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/build/living/blocks/Explain.test.tsx src/build/living/GapCard.test.tsx src/build/living/SampleUpload.test.tsx`
Expected: FAIL — `Explain.tsx` does not exist; the copy assertions fail on the old text.

- [ ] **Step 4: Implement**

`blocks/Explain.tsx`:

```tsx
import { useState } from "react";

import type { Explanation } from "../../../api/types";
import { useBrowserSetting } from "../../../preferences/useBrowserSetting";

/** What a question is about and why it is asked (Part I.1). `what` is the registry's words,
 *  marked *curated*; why it is needed is the engine's, marked *engine*. Open or collapsed as
 *  Settings → Building → *Explain each question* says; each one can still be folded by hand. */
export function Explain({ explanation }: { explanation: Explanation }) {
  const [start] = useBrowserSetting("building.explain", "open");
  const [open, setOpen] = useState(start !== "collapsed");
  const { what, needed, reads } = explanation;
  if (!what && needed.length === 0) return null;
  return (
    <div data-testid="explain" className="mb-3 border-l pl-[10px]"
         style={{ borderColor: "var(--line-2)" }}>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
              className="text-[11.5px] text-link bg-transparent border-0 p-0 cursor-pointer">
        What is this? {open ? "▾" : "›"}
      </button>
      {open && (
        <div className="mt-1 flex flex-col gap-2">
          {what && <Half mark="curated"><p className="m-0">{what}</p></Half>}
          {needed.length > 0 && (
            <Half mark="engine">
              <p className="m-0">
                {reads === "rule" ? "It decides: " : "Steps that can read it: "}
                {needed.map((reason, i) => (
                  <span key={reason.text}>
                    {i > 0 && (reads === "rule" ? "; " : ", ")}
                    <span title={reason.detail ?? undefined}>{reason.text}</span>
                    {reads === "rule" && reason.detail && (
                      <span className="text-ink-3"> ({reason.detail})</span>
                    )}
                  </span>
                ))}
                {reads === "steps" && needed.length > 1 && (
                  <span className="text-ink-3">. Which of them run depends on choices still to come.</span>
                )}
              </p>
            </Half>
          )}
        </div>
      )}
    </div>
  );
}

function Half({ mark, children }: { mark: "curated" | "engine"; children: React.ReactNode }) {
  return (
    <div className="text-[12px] text-ink-2">
      {children}
      <span className="font-data text-[9.5px] text-ink-4">{mark}</span>
    </div>
  );
}

const and = (items: string[]) =>
  items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")}, and ${items.at(-1)}`;

/** The line above *Upload a sample*: what a sample answers, never how it is read. */
export function uploadHeadline(e: Explanation): string | null {
  if (e.read_by === "ai") {
    return "Have a sample to hand? Upload it and the AI will read it for you. It shows you what "
      + "it found, and nothing is used until you've confirmed it.";
  }
  if (e.read_by !== "inspector") return null;
  if (e.settles.length === 0) return "Have a sample to hand? Upload it and we'll measure it.";
  return `Have a sample to hand? Upload it and we'll measure the rest: ${and(e.settles)}. `
    + "You won't need to answer those yourself.";
}
```

`GapCard.tsx`: `const explained = proposal.envelope.offer === "gap" ? proposal.envelope.explain
?? null : null;` (narrow on the generated union); render `{explained && <Explain
explanation={explained} />}` after the `why_open` line; in the upload `<div className="mb-3">`,
before `<SampleUpload`, render `{explained && uploadHeadline(explained) && <p className="m-0
mb-2 text-[12px] text-ink-2">{uploadHeadline(explained)}</p>}`.

`SampleUpload.tsx`:
- `PAIR` becomes `"choose one file, or both files if your reads are paired"`; delete `TO_AI`.
- The offered-stage line (line ~170) becomes, for both branches: `Choose one file, or both files
  if your reads are paired. Paired files are usually named _R1 and _R2, or _1 and _2.` (the
  `handBackGone` branch keeps no size claim either: `Choose the file again to measure it.`)
- The picked-stage line (line ~185) is removed.
- `reading the first 4 MB, then measuring…` becomes `Reading the sample, then measuring…`.
- The refusal stays `` `${files.length} files: ${PAIR}.` ``.
- Update the header comment's wording to match (it describes the card, not the bytes).

- [ ] **Step 5: Run the frontend suite and the type check**

Run: `cd frontend && npx vitest run && npx tsc -b`
Expected: PASS, no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: the question explains itself, and the upload says what a sample answers (#293)"
```

---

### Task 7: The voice page

**Files:**
- Create: `docs/design/voice.md`
- Modify: `docs/design/authoring-protocol.md` (rule 12: one sentence pointing at the page)

- [ ] **Step 1: Write the page**

```markdown
# The voice

How the product speaks: on its cards, in the registry's explanations, and through the AI in the
conversation. One voice, so a researcher cannot tell which of the three wrote a sentence by its
tone, only by its mark.

## Four words

The text between the markers below is quoted verbatim into prompts; keep it plain prose.

<!-- voice:start -->
Speak like a confident, slightly caring, professional scientist.

- Confident: state what is true without hedging. No "might", "perhaps", "please note", "just".
- Slightly caring: say what the person gets and what happens next. One kind clause at most;
  never cheerful, never effusive.
- Professional: no exclamation marks, no jokes, no emoji, no "we're excited".
- Scientific: use the right term, then say what it means. Never the term alone, never the
  meaning without the term.

Say what the person gets, not how the machine works. Leave out mechanics the person did not
ask about: sizes, bytes, internal names, where a process runs.

Prefer the person's words when they gave them. One idea per sentence. Short sentences.
<!-- voice:end -->

## Before and after

| Before | After |
|---|---|
| one file, or a pair (R1 and R2) | Choose one file, or both files if your reads are paired. Paired files are usually named _R1 and _R2, or _1 and _2. |
| This analysis needs annotation.gtf. Do you have one? | This analysis needs a gene annotation (GTF). Do you have one? |
| I have it, and I'll upload a sample | Yes — I'll upload a sample |
| Not sure: upload a sample and I'll measure it | Not sure — measure it from a sample |
| only the first 4 MB is read, on this server · if nothing here reads its type, about 8 KB of its text goes to the AI to read | Have a sample to hand? Upload it and we'll measure the rest: sequenced read length. You won't need to answer that yourself. |

## Where it applies

- every string the engine shows a person;
- every `name` and `explain` in the registry (`registry/vocabulary/`);
- every prompt that writes words a person reads: the text between the markers is inserted as
  the tone instruction (from Part I.3).
```

- [ ] **Step 2: Point rule 12 at it**

In `docs/design/authoring-protocol.md`, at the end of rule 12, add: *Its tone is
`docs/design/voice.md`.*

- [ ] **Step 3: Check the docs**

Run: `make check` (docs, links, doc-paths, doc-sizes run inside it)
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add docs/design/voice.md docs/design/authoring-protocol.md
git commit -m "docs: the voice the product speaks in (#293)"
```

---

### Task 8: Walk it, look at it, and record it

**Files:**
- Modify: `docs/notes/now.md`, a journal entry `docs/notes/journal/2026-10-13-part-i1.md`
- Modify: `tests/fixtures/guard-ledger.md` only if a guard was added (none planned)

- [ ] **Step 1: Run everything**

Run: `make verify`
Expected: PASS except the two #303 gzip tests under Python 3.14.

- [ ] **Step 2: Walk scenario 1 with no model**

On a throwaway database (`make test-db`, the API and Vite pointed at it as in Part H's walk):
describe *gene counts from paired-end RNA-seq*, and on each question check, in the browser:
the panel is open; *What is this?* reads in the voice; *Steps that can read it* names tools;
read length's panel names the rule and Dobin et al.; the upload headline names what a sample
settles and nothing about sizes; Settings → Building → *Explain each question* → *Collapsed*
folds the next question's panel. Screenshot each question; read the screenshots.

Expected: every check true. A defect found is a GitHub issue first (mechanical: fix test-first).

- [ ] **Step 3: Issue housekeeping**

- Comment on issue 135: the upload card no longer states the AI read or sizes (operator,
  2026-10-13, Part I.1 §2); Settings → Privacy still states where each purpose goes.
- Tick #268's Dev mode item, citing `0f231f0b`.
- Comment on #293 with I.1's commits; tick #267 items 1–3 there.

- [ ] **Step 4: Record**

`now.md`: under the living pipeline, one line — *Every question about your data says what it is
(curated `name`/`explain` in the registry), why it is asked (engine: the steps that read it, or
the rule it decides), and what a sample settles; open by default (Settings → Building →
Explain each question). The voice is `docs/design/voice.md`. (2026-10-13)* — and *Next* becomes
Part I.2. The journal entry: what was built, the rulings, the walk's findings.

```bash
git add docs/notes
git commit -m "docs: Part I.1 walked and recorded (#293)"
```
