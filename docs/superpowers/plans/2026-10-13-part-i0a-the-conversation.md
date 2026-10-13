# Intent, facts and steps — Plan A, the conversation (Part I.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The model hands over commands that write intent and facts through the decision store —
*heard* when they quote the person, *suggested* otherwise — and every conversational prompt is
told what is known, so the chat remembers and never asks again.

**Architecture:** The store already holds intent and facts (`services/decisions.py`). This plan
adds the quote and confirmation columns, one writer (`services/changes.py`) that every caller
uses, a pure quote check and memory renderer in `mendel-authoring`, one command `c.Change` that
takes the existing correction edges, a suggestions table, flat reply lists the model fills, and
new prompt versions that carry the memory. `session.extraction` is retired: the rows are the
only home of intent and facts.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy + Alembic (Postgres, throwaway on :5442),
FastAPI, arq jobs, React 19 + Vitest.

**Spec:** `docs/superpowers/specs/2026-10-13-part-i0-intent-facts-steps-design.md` (§5, §6, §7,
§9, and §10's conversation tests). Plan B (the save file, §8) is separate.

## Global Constraints

- **Heard** = the command carries a `quote` of **at least 3 characters** found in one of the
  person's own turns in this session, compared case-folded with whitespace runs as one space.
  Anything else is **suggested**. `not_offered` is heard only; one without a checking quote is
  dropped.
- **Before the goal is confirmed**, heard commands are recorded at once; **after**, every model
  command (heard or not) is a suggestion the person applies with one click (spec §5.3).
- **A want is always written** when the model reads one (heard if quoted, otherwise as the
  model's), because gathering needs it; the goal card's *That's right* confirms it (spec §2).
- Reply shapes are **lists of flat items, one list per command, no tagged unions**; each call's
  format carries only the lists it may fill (spec §7.1). Item ids are constrained through
  `_call(..., choices={...})` with dotted paths (`"wants.type"`), as `stated.subject` is today.
- Every undeclared id is refused at admission with **`MI0204`**; nothing is recorded.
- A prompt change is **a new version file**; superseded files go to `prompts.RETIRED`, never edited
  or deleted.
- The memory is rendered by a **pure** function in `mendel-authoring`; `mendel-authoring` stays in
  both purity guards.
- `FREE_TEXT_FIELDS` and `SAMPLE_FIELDS` in `tests/guards/test_egress.py` do not change: quotes
  live in the database and in prompts (door 1 already carries the person's words), never in a
  payload.
- DB tests: `make test-db`, then
  `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest …`.
- Work on `stage-four-the-consultant-build`; nothing pushed. Commit messages end with the
  `Co-Authored-By` line.

## Where this plan departs from the spec

Rulings the executor carries; each was forced by code the spec did not look at closely enough.

- **Suggestions are rows in their own table, not proposals** (spec §6.1 said a `suggestion`
  proposal kind). A session holds **one** pending proposal — the open question or the goal card —
  and `AuthoringView.pending_proposal` is singular; suggestions sit beside it. Cost if wrong: a
  table instead of a kind.
- **The goal card's payload keeps a display copy of the goal** (spec §6.2 said it carries none).
  The card is a block in the transcript and must still read correctly once the rows move on; it
  is **never imported** — *That's right* confirms the rows, and an edited card is imported as the
  person's change. Truth is the rows; the copy is a rendering. Cost if wrong: one field.
- **`confirmed()` is "a confirmation was recorded"** (`confirmed_revision is not None`), not "and
  nothing changed since" (spec §6.2). Whether a later change re-offers the card is already the
  correction section's job (*check again*), keyed on the phase. Cost if wrong: one comparison.
- **A suggestion card mid-build says what will change; it does not preview the re-resolved
  pipeline** (spec §5.3 says *previewed*). The alternative preview (`preview_views`) previews a
  tool swap, not an arbitrary fact; extending it is I.3's ask-anything work. Cost if wrong: a
  person applies a fact change seeing its words, not its consequences, and the steps it touches
  are re-reviewed after (the cascade already does that).
- **`ask.v2` keeps `AskedGap`'s stored shape**; it simply never fills `already_option` /
  `already_value`, and the engine stops reading them. Changing the stored shape would need a
  `pipeline_phrasing` version bump for two dead fields. Cost if wrong: two unused optional fields.
- **The one-step path (`MENDEL_FAMILY_STEP_FROM`, `goal.v6`) uses `goal.v8` shown every type**,
  with `say` as its acknowledgement, so both paths return the same shape. Cost if wrong: the
  benchmark (#198) compares the new shape one-step against two-step.

## Review Focus

1. **A quote that is a substring of a negation** (*"not paired-end"* holds *"paired-end"*): heard,
   recorded `paired: true`, and the goal card must show the quote so the person sees the misread.
   Test in Task 9 (the card carries `heard`).
2. **A reply arriving after the session moved** (the person answered the gap by click while the
   model read their typed words): its heard commands must not be applied over the click. Test in
   Task 8.
3. **The same subject twice in one reply with different values**: both become suggestions,
   neither recorded. Test in Task 5.
4. **A session started before this plan** (its `extraction` set, no want rows): it opens on the
   same question or card it was on. Test in Task 10.
5. **A retract of something never recorded**: nothing changes, the reply says so, no error.
   Test in Task 3.

---

### Task 1: The store gains quotes, the `asked` family, suggestions and recorded confirmation

**Files:**
- Create: `packages/mendel-api/migrations/versions/b4e8c2a6d917_heard_and_confirmed.py`
- Modify: `packages/mendel-api/src/mendel_api/decision_models.py` (revision and observation
  columns; `PipelineAsked`, `PipelineAskedRevision`)
- Modify: `packages/mendel-api/src/mendel_api/models.py` (`PipelineDraft.confirmed_revision`;
  `PipelineAuthoringSuggestion`)
- Modify: `packages/mendel-api/src/mendel_api/shape_versions.py`, `shapes.py`,
  `tests/golden/shapes/` (the suggestion table's JSON column)
- Modify: `packages/mendel-api/src/mendel_api/services/decisions.py`
- Test: `packages/mendel-api/tests/test_decisions_heard.py` (create)

**Interfaces:**
- Produces, in `services/decisions.py` (each `who=`, `actor_kind=ActorKind.PERSON`,
  `heard: str | None = None`, `heard_seq: int | None = None`, `proposal_id=None` keyword-only,
  joining the dispatcher's transaction like every writer there):
  - `set_want(draft_id, type_id)`, `retract_want(draft_id, type_id)`
  - `require_states(draft_id, type_id, states: list[str])`
  - `set_parameter(draft_id, name, value)` (`release_parameter` exists for the retract)
  - `pin_producer(draft_id, site: Site, contract: str)` (`release_producer` exists)
  - `set_asked(draft_id, phrase)`, `retract_asked(draft_id, phrase)`,
    `read_asked(draft_id) -> list[Asked]` where `Asked(phrase: str, heard_seq: int | None)`
  - `heard_of(draft_id) -> dict[tuple[str, str], tuple[str, int | None]]` — `(family, key)` →
    `(quote, seq)` for every current revision that has one
  - `confirm(draft_id) -> int` sets `confirmed_revision = decision_revision`, returns it
  - existing `set_fact`, `set_input`, `observe` gain the `heard`, `heard_seq` keywords
- Produces: `authoring_decisions.confirmed(draft_id)` → `confirmed_revision is not None`.

- [ ] **Step 1: Read the head.** `cd packages/mendel-api && MENDEL_DATABASE_URL=… uv run alembic
  heads` → expected `a3f7c9e1b246 (head)`. Use the printed head as `down_revision`; ledger a
  ruling if it differs.

- [ ] **Step 2: Write the failing tests** (`test_decisions_heard.py`; copy the `clean` fixture
  and a draft-making helper from `test_decision_constraints.py`):

```python
"""Intent and facts carry the person's words when they were heard (Part I.0 spec §6.1)."""

def test_a_heard_fact_keeps_its_quote_and_turn(clean):
    draft = _draft()
    decisions.set_fact(draft, "paired", True, who="model", actor_kind=ActorKind.MODEL,
                       heard="paired-end", heard_seq=1)
    assert decisions.heard_of(draft)[("fact", "paired")] == ("paired-end", 1)

def test_a_want_and_its_retraction(clean):
    draft = _draft()
    decisions.set_want(draft, "counts.matrix", who="ana", heard="gene counts", heard_seq=1)
    assert [w.type_id for w in decisions.read(draft).wants if w.present] == ["counts.matrix"]
    decisions.retract_want(draft, "counts.matrix", who="ana")
    assert not [w for w in decisions.read(draft).wants if w.present]

def test_required_states_a_pin_and_a_parameter_reach_the_goal(clean):
    draft = _draft()
    decisions.set_want(draft, "counts.matrix", who="ana")
    decisions.require_states(draft, "counts.matrix", ["gene_level"], who="ana")
    decisions.pin_producer(draft, Site(type_id="alignment.bam", states=frozenset()),
                           "nf-core/hisat2/align@2.2.2", who="ana")
    decisions.set_parameter(draft, "seq_platform", "ILLUMINA", who="ana")
    goal = decisions.goal(draft)
    assert goal.constraints.required_states[0].states == ["gene_level"]
    assert goal.constraints.producers[0].contract == "nf-core/hisat2/align@2.2.2"
    assert goal.constraints.params[0].value == "ILLUMINA"

def test_asked_is_kept_and_never_reaches_the_goal(clean):
    draft = _draft()
    decisions.set_asked(draft, "differential expression", who="model",
                        actor_kind=ActorKind.MODEL, heard="differential expression", heard_seq=1)
    assert [a.phrase for a in decisions.read_asked(draft)] == ["differential expression"]
    assert "differential" not in decisions.goal(draft).model_dump_json()

def test_confirmation_is_recorded_not_inferred(clean):
    draft = _draft()
    decisions.set_want(draft, "counts.matrix", who="model", actor_kind=ActorKind.MODEL)
    assert not authoring_decisions.confirmed(draft)
    decisions.confirm(draft)
    assert authoring_decisions.confirmed(draft)

def test_retracting_what_was_never_recorded_changes_nothing(clean):
    """Review Focus 5."""
    draft = _draft()
    before = _decision_revision(draft)
    decisions.retract_want(draft, "counts.matrix", who="ana")
    decisions.retract_asked(draft, "anything", who="ana")
    assert _decision_revision(draft) == before
```

- [ ] **Step 3: Run them.** Expected: FAIL — `set_fact() got an unexpected keyword argument
  'heard'`, `module has no attribute 'set_want'`.

- [ ] **Step 4: Models and migration.**
  - `heard = mapped_column(Text, nullable=True)`, `heard_seq = mapped_column(Integer,
    nullable=True)` on `PipelineObservation` and on `PipelineInputRevision`,
    `PipelineWantRevision`, `PipelineProducerRevision`, `PipelineParameterRevision`.
  - `PipelineAsked` / `PipelineAskedRevision`: copy `PipelineWant` / `PipelineWantRevision`'s
    shape (subject with `subject_key`, `current_id`, `position`; revision with `seq`, `at`,
    `action`, `actor_kind`, `who`, `legacy`, `proposal_id`) with fields `phrase` (Text),
    `present` (bool), `heard`, `heard_seq`. Register `"asked"` in `decisions._FAMILIES` and its
    `_FIELDS` entry (`("phrase", "present", "heard", "heard_seq")`).
  - `PipelineDraft.confirmed_revision = mapped_column(Integer, nullable=True)`.
  - `PipelineAuthoringSuggestion`: `id` String(32) pk, `session_id` FK → session (CASCADE),
    `change` Json (a `p.Change` dump, Task 2), `heard` bool, `state` closed column
    (`pending`/`applied`/`dismissed`/`stale`, via `_one_of`), `invocation_id` String(32) null,
    `created_at`, `settled_at`, and the `stamp("pipeline_authoring_suggestion")` shape column.
    Register the JSON column in `shapes.SHAPES` as `Shape("pipeline_authoring_suggestion",
    "change", Change)`, add it to `VERSIONS` at 1, and write its golden with
    `COMENI_WRITE_GOLDEN=1` (read the file before committing).
  - Migration `b4e8c2a6d917`: the columns and tables above; **backfill**
    `confirmed_revision = decision_revision` for every draft with a present want revision (the
    old inference, made a record). `downgrade` drops them. Draft-deletion's subject+revision CTE
    (`services/deletion.py`) gains the `asked` pair and the suggestion table (deleted with the
    session).

- [ ] **Step 5: The service.** `_write` already takes arbitrary `fields`; pass
  `{"heard": heard, "heard_seq": heard_seq}` merged into each family's fields (only when
  `heard` is not None, so an unquoted write compares equal to its predecessor exactly as today).
  `_observe` writes `heard`/`heard_seq` onto the observation. The new functions are one `_write`
  each; `set_want` writes `{"type_id", "states": <current states or []>, "present": True,
  "states_order": <current or None>}` keyed by `type_id`; `retract_want` writes `present: False`
  only if a current present revision exists (else returns `None`). `require_states` rewrites the
  want's `states` (refuse `MI0204` if the type is not a current want). `pin_producer` writes the
  `producer` family keyed `_site_key(site)` with `contract`. `set_parameter` keys by `name`.
  `confirm` locks the draft (`_draft`), sets the column, flushes. Rewrite
  `authoring_decisions.confirmed` and `decisions.confirmed_goal` to read `confirmed_revision`.

- [ ] **Step 6: Run** `test_decisions_heard.py`, then `test_decision_*.py`, `test_draft_deletion.py`,
  `test_shapes.py`, `test_migrations.py`. Expected: PASS. Any test that relied on *any want present*
  meaning confirmed now needs `decisions.confirm(draft)` after its import — fix those call sites in
  test helpers (`tests/authoring_setup.py` first), never in production code.

- [ ] **Step 7: Commit** — `feat: the store keeps the words a fact was heard in, what was asked
  and not offered, and when the goal was confirmed (#307)`.

---

### Task 2: Pure — the quote check, the change payload, and the memory

**Files:**
- Create: `packages/mendel-authoring/src/mendel_authoring/heard.py`
- Create: `packages/mendel-authoring/src/mendel_authoring/memory.py`
- Modify: `packages/mendel-authoring/src/mendel_authoring/payloads.py` (`Change`)
- Test: `packages/mendel-authoring/tests/test_heard.py`, `test_memory.py`,
  `packages/mendel-authoring/tests/golden/memory-*.txt`
- Modify: `tests/fixtures/guard-ledger.md`

**Interfaces:**
- Produces `heard.QUOTE_FLOOR = 3` and
  `heard.find(quote: str | None, turns: Sequence[tuple[int, str]]) -> int | None` — the `seq` of
  the first person turn holding the quote, or `None`.
- Produces `payloads.Change`:

```python
class Change(_Payload):
    """One change to intent or facts, from any caller (Part I.0 §5.1)."""
    kind: Literal["want", "input", "measurement", "require", "pin", "parameter", "asked",
                  "producer", "retain", "observation"]
    subject: str = Field(min_length=1, max_length=256)
    value: HumanParamValue | list[HumanParamValue] | None = None
    states: list[str] = Field(default_factory=list)
    retract: bool = False
    heard: str | None = Field(default=None, max_length=500)
    heard_seq: int | None = None
    actor: Literal["person", "model"] = "person"
    invocation_id: str | None = None
```

  `Correction` gains `change: Change | None = None` and keeps its fields, so the correction
  handlers read one or the other while Task 4 moves them.
- Produces `memory.render(known: Known) -> str` with

```python
class KnownItem(_Payload):
    label: str          # a name: "paired-end reads (FASTQ)", "read length"
    value: str | None   # "yes", "150 bp", None for an input held
    source: Literal["said", "measured", "read_by_ai", "open", "model"]
    heard: str | None = None

class Known(_Payload):
    wants: list[KnownItem]
    constraints: list[KnownItem]
    not_offered: list[str]
    inputs: list[KnownItem]
    facts: list[KnownItem]
    suggested: list[str]
    open: list[str]
    confirmed: bool
```

- [ ] **Step 1: The failing tests.**

```python
# test_heard.py
from mendel_authoring import heard

TURNS = [(1, "Gene counts from my  Paired-End Illumina reads, 150 bp"), (3, "use HISAT2")]

def test_a_quote_in_a_turn_is_heard_case_and_spacing_folded():
    assert heard.find("paired-end illumina", TURNS) == 1
    assert heard.find("Use hisat2", TURNS) == 3

def test_a_quote_nobody_typed_is_not_heard():
    assert heard.find("single-end", TURNS) is None

def test_a_quote_too_short_to_prove_anything_is_not_heard():
    assert heard.find("15", TURNS) is None
    assert heard.find(None, TURNS) is None
    assert heard.find("   ", TURNS) is None

def test_a_quote_cannot_join_two_turns():
    assert heard.find("150 bp use HISAT2", TURNS) is None
```

```python
# test_memory.py — golden texts, written once with COMENI_WRITE_GOLDEN=1 and read before commit
def test_before_the_goal_is_confirmed(golden):
    golden("memory-gathering.txt", memory.render(Known(
        wants=[KnownItem(label="gene counts matrix", value=None, source="said",
                         heard="gene counts")],
        constraints=[], not_offered=["differential expression"],
        inputs=[KnownItem(label="sequencing reads (FASTQ)", value=None, source="said",
                          heard="Illumina reads")],
        facts=[KnownItem(label="read length", value="150 bp", source="said", heard="150 bp"),
               KnownItem(label="paired", value="yes", source="measured")],
        suggested=["strandedness: reverse"], open=["gene annotation (GTF)"], confirmed=False)))

def test_same_known_same_text():
    k = Known(wants=[], constraints=[], not_offered=[], inputs=[], facts=[], suggested=[],
              open=[], confirmed=True)
    assert memory.render(k) == memory.render(k)
```

  The `golden` fixture: copy the pattern of an existing golden test in `packages/mendel-authoring/
  tests` (`grep -rl golden packages/mendel-authoring/tests`).

- [ ] **Step 2: Run.** Expected: FAIL — `cannot import name 'heard'`.

- [ ] **Step 3: Implement `heard.py`:**

```python
"""Whether the person said it: a quote of their own words (Part I.0 §5.3).

A quote proves the words were typed, not that they were read right — *"not paired-end"* holds
*"paired-end"* — which is why a heard fact is still shown with its quote on the goal card."""

from collections.abc import Sequence

QUOTE_FLOOR = 3
"""The shortest quote that proves anything: `bp` and `PE` are in too many sentences."""


def _fold(text: str) -> str:
    return " ".join(text.split()).casefold()


def find(quote: str | None, turns: Sequence[tuple[int, str]]) -> int | None:
    if quote is None:
        return None
    wanted = _fold(quote)
    if len(wanted) < QUOTE_FLOOR:
        return None
    return next((seq for seq, text in turns if wanted in _fold(text)), None)
```

  `memory.py`: render fixed English, one line per item, sections in this order and only when
  non-empty: `What you want`, `Asked for but not offered here`, `Constraints`, `Inputs you have`,
  `Facts about your data`, `Suggested, waiting for you`, `Still open`; each item
  `- <label>[: <value>] · <source words>[ · "<heard>"]` where source words are `you said`,
  `measured from your sample`, `read by AI from your sample`, `unknown`, `the model's reading`.
  First line: `What is known (recorded; do not ask for it again):`; last line, when
  `confirmed`: `The goal is confirmed; changes are offered to the person before they apply.`

- [ ] **Step 4: The guard, watched failing.** Temporarily change `find` to
  `return turns[0][0] if turns else None` and run `test_heard.py`: expected
  `test_a_quote_nobody_typed_is_not_heard` FAILS. Restore; PASS. Record in
  `tests/fixtures/guard-ledger.md`: *heard quote guard — `test_a_quote_nobody_typed_is_not_heard`
  — revert: `find` returning the first turn — failed as expected (2026-10-13)*, in the ledger's
  existing row format.

- [ ] **Step 5: Run** `uv run pytest packages/mendel-authoring -q` and `make guards`. Expected:
  PASS (both purity guards hold `mendel-authoring`).

- [ ] **Step 6: Commit** — `feat: the quote check and the memory, pure (#307)`.

---

### Task 3: One writer for every change

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/changes.py`
- Modify: `packages/mendel-api/src/mendel_api/stages/correcting.py` (`select_correction` calls it)
- Test: `packages/mendel-api/tests/test_changes.py` (create)

**Interfaces:**
- Consumes: Task 1's store functions; Task 2's `Change`.
- Produces: `changes.apply(draft_id: str, change: Change, *, who: str) -> bool` — writes one
  change, returns whether the decision revision moved; refuses undeclared ids with `MI0204` and
  values a measurement refuses with `MI0208`. `changes.describe(change) -> str` — the receipt's
  words (*read length is 150*, *released the tool choice for alignment.bam*,
  *forgot that you have the reference genome (FASTA)*).

- [ ] **Step 1: The failing tests** — one per `kind`, plus retract for each, plus refusals:

```python
@pytest.mark.parametrize("change, check", [
    (Change(kind="want", subject="counts.matrix"),
     lambda d: [w.type_id for w in d.wants if w.present] == ["counts.matrix"]),
    (Change(kind="input", subject="genome.fasta"),
     lambda d: [i.type_id for i in d.inputs if i.present] == ["genome.fasta"]),
    (Change(kind="measurement", subject="paired", value=True),
     lambda d: [(f.subject, f.value) for f in d.facts] == [("paired", True)]),
    (Change(kind="pin", subject="alignment.bam", value="nf-core/hisat2/align@2.2.2"),
     lambda d: d.producers[0].contract == "nf-core/hisat2/align@2.2.2"),
    (Change(kind="parameter", subject="seq_platform", value="ILLUMINA"),
     lambda d: d.parameters[0].value == "ILLUMINA"),
])
def test_each_change_writes_its_family(clean, change, check):
    draft = _draft()
    assert changes.apply(draft, change, who="ana")
    assert check(decisions.read(draft))

def test_a_heard_change_keeps_its_words(clean):
    draft = _draft()
    changes.apply(draft, Change(kind="measurement", subject="paired", value=True,
                                heard="paired-end", heard_seq=1, actor="model"), who="model")
    assert decisions.heard_of(draft)[("fact", "paired")] == ("paired-end", 1)

def test_an_undeclared_type_is_refused_and_nothing_written(clean):
    draft = _draft()
    with pytest.raises(ValueError, match="MI0204"):
        changes.apply(draft, Change(kind="want", subject="made.up"), who="ana")
    assert decisions.read(draft).wants == []

def test_a_value_the_measurement_refuses_is_refused(clean):
    with pytest.raises(ValueError, match="MI0208"):
        changes.apply(_draft(), Change(kind="measurement", subject="read_length", value=-4),
                      who="ana")

def test_retracting_each_kind_removes_it(clean): ...   # write then retract each of the five
def test_retracting_what_was_never_there_changes_nothing(clean):  # Review Focus 5
    assert changes.apply(_draft(), Change(kind="input", subject="genome.fasta", retract=True),
                         who="ana") is False
```

  Write `test_retracting_each_kind_removes_it` out in full (five apply/retract pairs, one
  assertion each), not as a placeholder.

- [ ] **Step 2: Run.** Expected: FAIL — no module `changes`.

- [ ] **Step 3: Implement `changes.apply`** by moving the per-kind body of
  `correcting.select_correction` (measurement, input, producer, retain, observation) into it and
  adding want, require, pin, parameter, asked, and `retract` for each:
  - measurement: `set_fact(draft, subject, None if retract else value, …)`
  - input: `retract` → `withdraw_input(draft, key)`; else `set_input(InputDecision(present=True,
    origin=PERSON_SAID, …))` — **`value is False` keeps today's meaning, *I don't have one***;
  - want / require / pin / parameter / asked: Task 1's functions, `release_producer` /
    `release_parameter` / `retract_want` / `retract_asked` on retract;
  - every write passes `heard`, `heard_seq`, `actor_kind=ActorKind(change.actor)`.
  Vocabulary checks: types against `stack.vocabulary.types`, tools against
  `stack.registry` (`registry.get(contract)` raising → `MI0204`), parameters against the
  parameter names the current blueprint's steps declare (`MI0204` when none does), measurements
  through `measurements.get` / `check` (`MI0208`). Return `draft.decision_revision != before`.
  `select_correction` becomes: build a `Change` from the `Correction` (or take `change`), call
  `changes.apply`, keep its continuation logic unchanged.

- [ ] **Step 4: Run** `test_changes.py`, `test_fact_corrections.py`, `test_correction_forks.py`,
  `test_fact_disagreements.py`. Expected: PASS — the correction suite unchanged proves the move.

- [ ] **Step 5: Commit** — `refactor: one writer for every change to intent and facts (#307)`.

---

### Task 4: `c.Change` — a change from anyone, at any waiting node

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/commands.py` (`Change`, `COMMANDS`)
- Modify: `packages/mendel-api/src/mendel_api/stages/correcting.py` (`@records(c.Change)`)
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py`
  (`POST /{session_id}/changes`)
- Test: `packages/mendel-api/tests/test_change_command.py` (create); the binding test

**Interfaces:**
- Produces `commands.Change(session_id: str, change: dict, by: str, expected_decision_revision:
  int, expected_draft_revision: int, expected_session_version: int)` with
  `takes = frozenset({Command.CORRECT_FACT, Command.FORK_CORRECTION})`. `change` is a
  `payloads.Change` dump (commands hold plain values).
- Produces route `POST /api/authoring/{session_id}/changes` (operation `changeAuthoring`), body
  `{change, expected_decision_revision, expected_draft_revision, expected_session_version}`,
  answering the correction result (`correcting.result`).

- [ ] **Step 1: Failing tests.** At `reply` (gathering), a `Change` measurement goes through
  `correct_fact` → `gather_again` and the gap it answered is no longer asked; at `card`, a want
  change re-offers the card; at `step_card`, a measurement change re-resolves (copy the setup of
  `test_fact_corrections.py::test_a_missing_requirement_is_asked_by_its_exact_type_and_states`);
  a `Change` with stale revisions is refused `MI0201`; the route answers the same as the command.

- [ ] **Step 2: Run.** Expected: FAIL — `module has no attribute 'Change'`.

- [ ] **Step 3: Implement.** The recorder is `_begin(ctx, cmd, Command.CORRECT_FACT,
  subject=change.subject, kind=change.kind)` with the `Correction` carrying `change=Change(...)`.
  Add `Change` to `COMMANDS`. Run the binding test (`grep -rl "binding" packages/mendel-api/tests`)
  and make it pass by declaring the arrows, not by loosening it.

- [ ] **Step 4: Run** the new tests, the binding test and `test_authoring_protocol*.py`. PASS.

- [ ] **Step 5: Commit** — `feat: a change to intent or facts is one command, from anyone (#307)`.

---

### Task 5: The model's reply — flat lists, admitted, sorted into heard and suggested

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (items, `Understanding`,
  `ChatReply`)
- Create: `packages/mendel-api/src/mendel_api/services/replies.py`
- Test: `packages/mendel-api/tests/test_heard_replies.py` (create)

**Interfaces:**
- Produces in `authoring/types.py` (all `_Shape`, `quote: Prose | None = None` on every item):
  `WantItem(type)`, `InputItem(type)`, `FactItem(subject, value)`,
  `RequireItem(type, states: list[str])`, `PinItem(type, tool)`, `ParameterItem(name, value)`,
  `RetractItem(subject)`, `NotOfferedItem(quote: Prose)` (required).
  `Understanding(say: Prose | None, wants: list[WantItem] = Field(min_length=1), inputs, facts,
  requires, not_offered, questions: list[AskedQuestion])` for `goal.v8`.
  `ChatReply(say, wants, inputs, facts, requires, pins, parameters, retract, not_offered,
  questions, proceed: bool = False)` for `chat.v3`.
- Produces in `services/replies.py`:

```python
@dataclass(frozen=True)
class Issued:
    heard: list[Change]
    suggested: list[Change]
    dropped: list[str]          # not_offered without a checking quote, for the call log

def issue(reply: Understanding | ChatReply, *, turns: Sequence[tuple[int, str]], stack,
          invocation_id: str | None) -> Issued
def person_turns(session_id: str) -> list[tuple[int, str]]   # every PERSON turn, seq order
```

- [ ] **Step 1: Failing tests** (pure-ish; no DB except `registry.stack()`):
  - a fact quoting the turn is heard, with `heard_seq`; one with no quote is suggested;
  - a want with no quote is **heard-or-not as its quote says, and always issued** (Global
    Constraints);
  - `not_offered` with a failing quote is in `dropped`, never in `suggested`;
  - **Review Focus 3:** `facts=[{paired: true, quote: "paired-end"}, {paired: false, quote:
    "single"}]` → both suggested, neither heard;
  - an undeclared type in any list raises `MI0204` (admission happens in `_call`'s `admit`, so
    `issue` is handed only admitted replies — test the admit function `replies.admit(reply, stack)`
    alongside);
  - a retract names a subject; it is a `Change(retract=True)` of the kind its subject implies
    (a type → `input` or `want` by which family holds it now, a measurement → `measurement`).

- [ ] **Step 2: Run.** Expected: FAIL (imports).

- [ ] **Step 3: Implement** `admit` (types in `vocabulary.types`, measurements declared and
  values passing `measurements.check`, tools in the registry, states declared for their type —
  reuse `authoring_ai.admit_goal`'s checks by building the same `Goal` from wants+requires) and
  `issue`: map each item to a `Change` (`actor="model"`, `invocation_id`), set `heard`/`heard_seq`
  from `mendel_authoring.heard.find`, demote both of any subject appearing twice with different
  values, drop failing `not_offered`.

- [ ] **Step 4: Run** the new tests. PASS.

- [ ] **Step 5: Commit** — `feat: a model's reply is a list of changes, heard or suggested (#307)`.

---

### Task 6: The prompts — memory everywhere, and the new reply shapes

**Files:**
- Create: `packages/mendel-api/src/mendel_api/authoring/prompts/builder.family.v4.md`,
  `builder.goal.v8.md`, `builder.chat.v3.md`, `builder.ask.v2.md`, `builder.readback.v2.md`
- Modify: `packages/mendel-api/src/mendel_api/authoring/prompts.py` (ids, `RETIRED`)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_ai.py` (`understand`,
  `follow_up`, `phrase_gap`, `read_back`, `choose_families` take `memory: str`)
- Create: `packages/mendel-api/src/mendel_api/services/known.py`
- Test: `packages/mendel-api/tests/test_authoring_prompts.py`, `test_authoring_ai.py`,
  `test_known.py` (create)

**Interfaces:**
- Produces `known.of(session_id) -> Known` (Task 2's type) from `decisions.read`,
  `decisions.heard_of`, `decisions.read_asked`, pending suggestions, `gaps.gaps` (open), and
  `explain.name_of` for labels; and `known.text(session_id) -> str = memory.render(known.of(…))`.
- `understand(request, *, stack, families, memory, client, session_id)` returns
  `Outcome[Understanding]`; `follow_up(request, *, stack, memory, client, session_id)` returns
  `Outcome[ChatReply]`; `phrase_gap(…, memory)`; `read_back(…, memory)`;
  `choose_families(…, memory)`.

- [ ] **Step 1: Write the templates.** Each copies its predecessor and changes only what is
  listed; every template keeps the shared block at the top (`test_every_template_carries_the_
  invariant_block_verbatim`) and the system/per-call split marker.
  - **All five:** a `# What is known` section with `{{memory}}`, placed **before** the per-call
    marker only if it is identical across a session's calls — it is not, so place it in the
    per-call part, first; and the sentence *"What is known is the record. If the conversation
    seems to say otherwise, the record wins; ask rather than contradict it."*
  - **`goal.v8`:** replaces `stated` with the lists `wants`, `inputs`, `facts`, `requires`,
    `not_offered`; *"Put in `quote` the exact words of theirs each item comes from, copied, not
    paraphrased. If they did not say it, leave `quote` empty: it is offered to them as your
    suggestion. Never put in `not_offered` anything they did not ask for in their own words."*
    Keeps the vocabulary-first order and the questions section. `say` is the acknowledgement
    only when no family call ran.
  - **`chat.v3`:** replaces the six intents with: `say` (an explanation, an answer, or what you
    cannot do); the change lists (`wants`, `inputs`, `facts`, `requires`, `pins`, `parameters`,
    `retract`, `not_offered`), each item quoting them; `proceed` when they want to go on;
    `questions` when what they want is unclear. *"You change nothing yourself: every change is
    recorded or offered by the engine."* Keeps the grounding on known step ids.
  - **`ask.v2`:** drops `already_option` / `already_value` and the paragraph about them; words
    only.
  - **`readback.v2`:** `{{memory}}` replaces `{{goal}}`.
  - **`family.v4`:** gains the memory section; otherwise `family.v3`.
  Register: `FAMILY = "builder.family.v4"`, `GOAL = "builder.goal.v8"`,
  `GOAL_ONE_STEP = GOAL`, `CHAT = "builder.chat.v3"`, `ASK = "builder.ask.v2"`,
  `READBACK = "builder.readback.v2"`; `GAP` is removed from the live ids; append
  `builder.family.v3`, `builder.goal.v6`, `builder.goal.v7`, `builder.chat.v2`, `builder.gap.v2`,
  `builder.ask.v1`, `builder.readback.v1` to `RETIRED` (each docstring line says why it retired).

- [ ] **Step 2: Failing prompt tests.** Add to `test_authoring_prompts.py`:
  `test_every_conversational_prompt_is_told_what_is_known` (each of the five has `{{memory}}`
  and the record-wins sentence); `test_the_goal_prompt_asks_for_quotes_and_never_invents_a_
  request`; `test_the_chat_prompt_names_every_list_and_changes_nothing_itself`. Update the tests
  that read `goal.v7` / `chat.v2` wording to the new ids (they test retired files only through
  `RETIRED`). Run: FAIL until Step 1's files exist; then PASS.

- [ ] **Step 3: Failing call tests.** In `test_authoring_ai.py`, with the `Answers` transport:
  `goal.v8` reply with a quoted fact → admitted `Understanding`; the rendered prompt contains the
  memory text; `chat.v3` reply with `pins` naming an unknown tool → refused `MI0204`. Retire the
  `stated`, `chose`, `revise`, `unsupported` tests (each replaced by a test of the list that
  supersedes it — write each replacement out).

- [ ] **Step 4: Implement** `known.py` and the call changes: `values` gain `"memory": memory`;
  `choices` gain `"wants.type"`, `"inputs.type"`, `"requires.type"`, `"pins.type"`:
  shown types; `"facts.subject"`, `"retract.subject"`: types + measurements; `"pins.tool"`:
  registry contract ids. Shapes: `Understanding`, `ChatReply`.

- [ ] **Step 5: Run** `test_authoring_prompts.py`, `test_authoring_ai.py`, `test_known.py`. PASS.

- [ ] **Step 6: Commit** — `feat: every conversational prompt is told what is known, and replies
  in changes (#307)`.

---

### Task 7: Suggestions — offered, applied by one click, or dismissed

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/suggestions.py`
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py`
  (`POST /{session_id}/suggestions/{suggestion_id}`), the session view (`services/session.py`
  `read`: `suggestions` list), `authoring/types.py` (`SuggestionView`, `BlockKind.SUGGESTION`
  block `SuggestionBlock(suggestion_id, says, heard)`)
- Test: `packages/mendel-api/tests/test_suggestions.py` (create)

**Interfaces:**
- `suggestions.offer(session_id, change: Change, *, heard: bool, invocation_id) -> str`
- `suggestions.pending(session_id) -> list[SuggestionView]`
  (`SuggestionView(id, change, heard, says)`, `says = changes.describe(change)`)
- `suggestions.apply(session_id, suggestion_id, *, by, expected_…) -> dict` — performs
  `c.Change` **as the person** (`actor="person"`), then marks the row `applied`
- `suggestions.dismiss(session_id, suggestion_id, *, by)`
- Any change recorded (`changes.apply` returning True) marks pending suggestions **for the same
  subject** `stale`.

- [ ] **Step 1: Failing tests:** offer then apply records the person's revision and the row is
  `applied`; dismiss records nothing; applying a stale one is refused `MI0201`; a suggested fact
  whose subject is the open gap pre-fills that gap's question (`PrefillGap`, note
  `"suggested by AI"`) instead of drawing a separate card; a suggested `require` before
  confirmation appears in the goal card's `suggested` chips (the card reads
  `suggestions.pending`, no longer `extraction.suggested`).

- [ ] **Step 2–4:** run (FAIL), implement, run (PASS).

- [ ] **Step 5: Commit** — `feat: the model's suggestions wait for one click (#307)`.

---

### Task 8: Describing — the want and what was said are written, not stored as an extraction

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_jobs.py` (`_understand`)
- Modify: `packages/mendel-authoring/src/mendel_authoring/payloads.py` (`GoalReturned` carries
  `heard: list[Change]`, `suggested: list[Change]` instead of `extraction`; `Extraction` removed)
- Modify: `packages/mendel-api/src/mendel_api/stages/describe.py` (`read_goal`),
  `stages/gathering.py` (`_gathered`, `need_listed`, `offer_gap_or_card`, `compose_goal`,
  `phrasing_context`, stated pre-fill), `stages/_rows.py` (`store_extraction` removed),
  `stages/goal.py` (`_decide_goal`), `stages/correcting.py` (fork copies no extraction),
  `services/authoring_decisions.py` (`extracted` removed)
- Modify: `packages/mendel-api/tests/authoring_setup.py` and every test that set
  `row.extraction` (`grep -rn "extraction" packages/mendel-api/tests`)
- Test: `packages/mendel-api/tests/test_authoring_describe_heard.py` (create)

**Interfaces:**
- `read_goal` applies `payload.heard` through `changes.apply` (actor model, who
  `"model"`), offers `payload.suggested` through `suggestions.offer`, records `not_offered`
  heard changes as `asked`, and returns `want_returned`.
- `_gathered(session_id)` returns the wants from `decisions.read(draft).wants` (present), the
  facts from `authoring_decisions.facts`, and the version — no `extraction`.
- `_decide_goal`: unedited accept → `decisions.confirm(draft)`; edited accept →
  `decisions.import_goal(edited, who=person)` then `confirm`; the card's `payload["goal"]` is
  display only (ruling above).

- [ ] **Step 1: Failing tests:**
  - *"Gene counts from my paired-end Illumina reads, 150 bp"* with a recorded `goal.v8` reply
    (wants counts.matrix quoting "Gene counts", facts paired/true quoting "paired-end",
    read_length/150 quoting "150 bp") → the want and both facts are rows with their quotes; the
    first gap offered is **not** `paired` or `read_length`;
  - a fact with no quote → a suggestion, and its gap is offered pre-filled `suggested by AI`;
  - `not_offered` "differential expression" quoted → `read_asked` holds it;
  - the dead end (nothing makes the want) retracts the want rows instead of clearing an
    extraction;
  - *That's right* on an unedited card sets `confirmed_revision` and imports nothing (the
    decision revision does not move);
  - **Review Focus 2:** the person answers `paired` by click while the model's reply for their
    typed words is out; the reply's heard `paired: false` does not overwrite the click — `read_goal`
    is not the path here; this is Task 9's, so put this test in Task 9 and leave a pointer.

- [ ] **Step 2: Run** (FAIL), **Step 3: implement**, **Step 4: run** the new tests and the whole
  `test_authoring_*.py` set; fix test helpers that wrote `extraction` to write want rows
  (`decisions.set_want`) — production code never reads `extraction` again.

- [ ] **Step 5: Commit** — `feat: what the person said is recorded from the first sentence (#307)`.

---

### Task 9: The chat — typed words anywhere are read once, into changes

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_jobs.py` (`_follow_up`,
  `_gap_reply` folded into it, `_block_for` removed, `answer_authoring_turn` dispatch)
- Modify: `packages/mendel-api/src/mendel_api/stages/gathering.py` (`suggest` queues the same
  turn job; `_phrased` stops reading `already_*`)
- Test: `packages/mendel-api/tests/test_authoring_chat_changes.py` (create); retire
  `test_a_typed_reply_pre_fills_the_gap_and_records_nothing` and
  `test_a_stated_fact_pre_fills_its_gap_and_waits_for_the_click` (decided #170/#171, superseded
  by #307) with a docstring line in their replacements naming the decision that replaced them

**Interfaces:**
- `_follow_up` calls `authoring_ai.follow_up(request, stack=…, memory=known.text(sid), …)`, then
  `replies.issue(reply, turns=replies.person_turns(sid), …)`, then:
  - **not confirmed** (`authoring_decisions.confirmed` false): each heard change is performed as
    `c.Change` with the revisions read **at the turn's start** (`context.revision` and the
    session version the context captured) — a stale one raises `MI0201` and is offered as a
    suggestion instead; suggested ones → `suggestions.offer`;
  - **confirmed:** every change → `suggestions.offer` (heard flag kept, so the card can show the
    quote);
  - `say` → a `Narrative`; `questions` → `Question` blocks (engine-minted ids, as today);
    `proceed` → when the pending proposal is a step card, `c.SettleStep(proposal_id,
    expected_revision, "person")`; otherwise nothing.
- The typed answer to an open gap is no longer `gap.v2`: `chat.v3` sees the open question in the
  memory and returns a `fact`.

- [ ] **Step 1: Failing tests:**
  - at `reply` on `read_length`, *"they're 150 bp"* with a reply `facts=[{read_length, 150,
    "150 bp"}]` → recorded, heard, the next gap offered;
  - the same with no quote → the gap pre-filled `suggested by AI`, nothing recorded;
  - after confirmation, *"actually the reads are 50 bp"* heard → a pending suggestion, the
    pipeline unchanged until `suggestions.apply`; applying it re-resolves (STAR → HISAT2 on the
    scenario-1 blueprint);
  - **Review Focus 2:** the context is captured, the person clicks `AnswerGap(paired, yes)`,
    then the job runs with a heard `paired: false` → `MI0201` caught, a suggestion offered, the
    clicked `true` stands;
  - `proceed` at a step card settles it; `proceed` at a gap does nothing;
  - `say` alone records nothing and narrates.

- [ ] **Step 2: Run** (FAIL), **Step 3: implement**, **Step 4: run** the new tests and
  `test_authoring_*.py`.

- [ ] **Step 5: Commit** — `feat: typed words anywhere become changes the engine records or
  offers (#307)`.

---

### Task 10: Sessions started before this plan

**Files:**
- Create: `packages/mendel-api/migrations/versions/c6a2e8d4f159_extraction_into_rows.py`
- Modify: `packages/mendel-api/src/mendel_api/models.py` (drop `extraction`), `shapes.py`,
  `tests/golden/shapes/` (remove `pipeline_authoring_session.extraction.v1.json`)
- Test: `packages/mendel-api/tests/test_migrations.py` (a case), Review Focus 4

**Interfaces:** none produced.

- [ ] **Step 1: Failing migration test** — at the previous head, insert a draft and a session in
  `gathering` with `extraction = {"want": ["counts.matrix"], "constraints": {}, "suggested":
  {"required_states": [{"type_id": "counts.matrix", "states": ["gene_level"]}]}, "stated":
  [{"kind": "measurement", "subject": "paired", "value": true}]}` and no want rows; upgrade;
  assert: a present want revision `counts.matrix` (actor `model`, no quote); two pending
  suggestion rows (the required state, the stated fact); the session's phase and pending proposal
  unchanged; `extraction` column gone. Follow `test_migrations.py`'s existing populated-head
  pattern (`test_populated_previous_head_upgrades…`).

- [ ] **Step 2: Run** (FAIL). **Step 3: Implement** the data migration with `sa.text` reads and
  inserts (never today's models), then drop the column; remove the shape registration and its
  golden. **Step 4: Run** `test_migrations.py`, `test_shapes.py`. PASS.

- [ ] **Step 5: Commit** — `feat: sessions begun before the change carry on from the rows (#307)`.

---

### Task 11: The cards — the quote beside each fact, and suggestions to apply

**Files:**
- Run: `make client`; alias new names in `frontend/src/api/types.ts`
- Create: `frontend/src/build/living/blocks/SuggestionCard.tsx` (+ test)
- Modify: `frontend/src/build/living/blocks/GoalCard.tsx` (each fact and input: source and, when
  heard, `· "<quote>"`; suggested chips from the view's `suggestions`), `LivingSurface.tsx`
  (pending suggestions drawn above the composer), `api/client` (the two routes)
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` `Fact` gains `heard: Prose |
  None = None`; `authoring_decisions.facts` fills it from `heard_of`
- Test: `GoalCard.test.tsx`, `SuggestionCard.test.tsx`, `LivingSurface.test.tsx`

- [ ] **Step 1: Failing tests:**
  - the goal card shows `paired: yes · you said · "paired-end"` (Review Focus 1: the quote is
    what lets the person see *"not paired-end"* misread);
  - a suggestion card says what it would change, marks *suggested by AI* (or *you said "…"* when
    heard), and *Apply* calls the route; *Dismiss* calls it with `dismiss`;
  - the gap pre-fill note reads `suggested by AI`.

- [ ] **Step 2–4:** run (FAIL), implement, `npx vitest run && npx tsc -b` (PASS).

- [ ] **Step 5: Commit** — `feat: the goal card shows the words each fact was heard in, and
  suggestions wait for a click (#307)`.

---

### Task 12: Every command has a reader; the docs; the walk

**Files:**
- Create: `packages/mendel-api/tests/test_change_readers.py`
- Modify: `docs/design/authoring-protocol.md` (heard and suggested; the memory; rule 5's *nothing
  is guessed* now reads *nothing is recorded from a model unless it quotes you*),
  `ARCHITECTURE.md` (the writer, the memory, the suggestion table), `docs/notes/now.md`, a journal
  entry, `docs/superpowers/specs/…i0…` status line

- [ ] **Step 1: The reader test** — for each `kind` in `Change`, apply it and assert each reader
  named in spec §5.1 sees it: `gaps.gaps` (the gap closes), `decisions.goal` (the resolver's
  input), `known.text` (the memory), the goal card block (`gathering.offer_gap_or_card` →
  `GoalSummary`), and for `asked`, `known.text` and `read_asked`. Assert the kinds list is
  non-empty first.

- [ ] **Step 2: Run** `make check`. Expected: PASS except #303 and anything the operator's audit
  leaves open; name each remaining failure.

- [ ] **Step 3: Walk with a model** (`make ai-up OLLAMA_GPU=rocm` or a key; throwaway database):
  scenario 1 in one sentence stating pairing and read length → neither asked; the goal card shows
  both quotes; *"also I want differential expression"* → recorded as asked, never promised;
  mid-build *"actually the reads are 50 bp"* → a suggestion, applied by one click, STAR → HISAT2.
  Screenshot each; read them. A defect is an issue first.

- [ ] **Step 4: Docs and notes**; commit — `docs: Part I.0 A walked and recorded (#307)`.
