# Plan 2.5 — the shared question: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement
> this plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax
> for tracking. Do **not** farm the tasks out with `subagent-driven-development` — subagents are
> for review and design only. This matches the execution decision recorded in `CLAUDE.md`.

**Goal:** Give the forge and the build path one shared vocabulary for *a question a reviewer must
answer* and *the answer with its provenance*, without merging the one thing that genuinely
differs — whether an unanswered question blocks.

**Architecture:** A new `comeni_core/review/` subpackage holds two inert base classes,
`Question` and `Answer`, plus the `Candidate` and `Excerpt` types they need. `Hole` and
`FilledValue` (forge) and `Ambiguity` and `Resolution` (build) become their subclasses. All
behaviour stays where it already is — in the containers (`Scaffold`, the resolver) and the ports
(`HoleFiller` may return `None`, `AmbiguityResolver` may not). `Filler` is deleted and folded
into `ValueSource`.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, ruff (line length 100), `uv`.

**Spec:** [`notes/specs/2026-08-18-the-shared-question.md`](../specs/2026-08-18-the-shared-question.md) — read it before Task 1. The plan argues from the spec and a plan read alone loses the reasons.

## Global Constraints

- **Work in a git worktree**, not the main checkout. `CLAUDE.md` requires it. Suggested:
  `.worktrees/plan-2-5-shared-question`.
- **`comeni-core` and `mendel-resolver` are PURE.** No network, no `ctypes`, no `subprocess`.
  `tests/test_purity.py` and `tests/test_purity_runtime.py` enforce it.
- **The base classes are inert.** No methods on `Question` or `Answer` beyond Pydantic
  validators. Every behavioural difference lives in a container or a port. A method added to a
  base is a design smell here by construction — see spec §3.1.
- **No `Mark.FREE_TEXT` field on `Question` or `Answer`.** `Ambiguity` projects to
  `AmbiguityRequest`, a door-2 payload; a free-text field on a shared base widens door 2 without
  anybody editing `tests/test_egress.py`. Free text stays on the subclasses. Spec §5 Rule 1.
- **Import direction: `spell/ ← review/ ← plan/`.** `review/` must never import `plan/` — that
  is a circular import, because `plan/decision.py` imports `review/`. Spec §9.1.
- **`pipeline.yml` must not change.** Every existing `ValueSource` spelling is preserved, so
  there is no `SCHEMA_VERSION` bump. Task 8 proves it.
- **Verify with `make verify`, not `make check`.** This touches
  `comeni_core/artifact/pipeline.py` and the resolver, both on `CLAUDE.md`'s named list.
  `make check` deselects `tests/test_counts.py`, the only check exercising the v1 criterion.
- **Check the exit code before filtering output.** `make check` runs its prerequisites in
  parallel; a `grep | tail` tight enough to be readable is tight enough to hide a lint failure.
  This cost four tasks of a red suite on 2026-08-17.
- Ruff line length 100. `uv run ruff check .` clean before every commit.
- Every new diagnostic code is DECLARED in `comeni_core/diagnostics.yml` and EMITTED through
  `coded()`. Never write a code into a string by hand. This plan adds none.

---

## File Structure

**Create:**

| File | Responsibility |
|---|---|
| `packages/comeni-core/src/comeni_core/review/__init__.py` | the subpackage's own public surface |
| `packages/comeni-core/src/comeni_core/review/question.py` | `Excerpt`, `Candidate`, `Question` |
| `packages/comeni-core/src/comeni_core/review/answer.py` | `ValueSource`, `Answer` |
| `packages/comeni-core/tests/test_review_base.py` | the base classes' own tests |

**Modify:**

| File | Change |
|---|---|
| `packages/comeni-core/src/comeni_core/plan/tiers.py` | `ValueSource` moves out; re-exported |
| `packages/comeni-core/src/comeni_core/plan/decision.py` | `Ambiguity(Question)`, `Resolution(Answer)` |
| `packages/comeni-core/src/comeni_core/artifact/egress.py` | `AmbiguityRequest` gains the door-2 decision |
| `packages/comeni-core/src/comeni_core/__init__.py` | export `Question`, `Answer`, `Candidate`, `Excerpt` |
| `packages/mendel-forge/src/mendel_forge/scaffold.py` | `Hole(Question)`, `FilledValue(Answer)`, `Filler` deleted |
| `packages/mendel-forge/src/mendel_forge/observe.py` | `Excerpt` re-exported from core |
| `packages/mendel-forge/src/mendel_forge/assemble.py` | `Filler` → `ValueSource` |
| `packages/mendel-forge/src/mendel_forge/ops.py` | `Filler` → `ValueSource` |
| `packages/mendel-forge/src/mendel_forge/filler.py` | `Filler` → `ValueSource` |
| `packages/mendel-resolver/src/mendel_resolver/resolve.py` | populate `evidence` on `ProducerAsked` |
| `packages/mendel-forge/tests/golden/nf-core-fastqc.scaffold.json` | regenerate, then **read** |

**Why `review/` and not `plan/`:** `comeni_core`'s subpackages are named for the lifecycle stage
(issue #41) — what is *declared*, *asked*, *planned*, *emitted*, *spelled*. A question awaiting a
human is its own stage: after derivation, before approval. It is also the only name that
describes both consumers, since the forge does not plan and the resolver does not author.

---

## Task 1: The `Question` base

**Files:**
- Create: `packages/comeni-core/src/comeni_core/review/__init__.py`
- Create: `packages/comeni-core/src/comeni_core/review/question.py`
- Test: `packages/comeni-core/tests/test_review_base.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Excerpt(locator: str, text: str)`; `Candidate(value: str, note: str = "")`;
  `Question(subject: str, what: str, why_open: str, candidates: list[Candidate],
  closed: bool, evidence: list[Excerpt])` with `Question.legal(value) -> bool`.

**`subject`, not `field`.** `Hole.field` and `Ambiguity.subject` are the same cell (spec §2), and
`subject` is the name that survives: it is already in `AmbiguityRequest`, already a declared mark
(`Subject`), and already serialised into `pipeline.yml` through the decision records. Renaming
the *forge's* side costs a golden file; renaming the *build's* side would cost an artifact.

- [ ] **Step 1: Write the failing test**

```python
# packages/comeni-core/tests/test_review_base.py
"""The shared question, and the properties the two subclasses both rely on."""

import pytest
from pydantic import ValidationError

from comeni_core.review.question import Candidate, Excerpt, Question


def _q(**kw) -> Question:
    base = {"subject": "produces[0].type_id", "what": "what this port carries"}
    return Question(**{**base, **kw})


def test_a_question_with_no_candidates_accepts_anything():
    """Nothing is known, so nothing can be refused."""
    assert _q().legal("anything at all")


def test_a_closed_question_refuses_a_value_it_did_not_offer():
    q = _q(candidates=[Candidate(value="qc.report")], closed=True)
    assert q.legal("qc.report")
    assert not q.legal("alignment.bam")


def test_an_open_question_accepts_a_value_it_did_not_offer():
    """`closed=False` means the candidates are guidance, not a vocabulary.

    Binding a port *name* to a list the forge invented is what made multiqc's `reports`
    unreachable — a legal name that simply was not offered.
    """
    q = _q(candidates=[Candidate(value="reads")], closed=False)
    assert q.legal("multiqc_files")


def test_a_list_value_is_checked_member_by_member():
    """`roles` holds several values from one closed set, so the candidates are the legal
    *members* rather than the legal *values*."""
    q = _q(candidates=[Candidate(value="qc_per_sample"), Candidate(value="bam_sorting")])
    assert q.legal(["qc_per_sample"])
    assert q.legal(["qc_per_sample", "bam_sorting"])
    assert not q.legal(["qc_per_sample", "not_a_role"])


def test_a_question_forbids_extra_fields():
    """A field misspelled at a call site must not vanish. A32."""
    with pytest.raises(ValidationError):
        _q(candidatez=[])


def test_the_base_carries_no_behaviour_beyond_legality():
    """Spec §3.1: every behavioural difference lives in a container or a port, so a
    `blocks()` or `is_open()` on the base is the design smell this guards against."""
    allowed = {"legal"}
    behaviour = {
        name
        for name in vars(Question)
        if callable(getattr(Question, name, None)) and not name.startswith("_")
    }
    assert behaviour <= allowed, f"unexpected behaviour on the base: {behaviour - allowed}"
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
uv run pytest packages/comeni-core/tests/test_review_base.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'comeni_core.review'`.

- [ ] **Step 3: Write `question.py`**

```python
# packages/comeni-core/src/comeni_core/review/question.py
"""A question a reviewer must answer, shared by the forge and the build path.

**Inert by design.** Whether an unanswered question *blocks* is not on this type and must
never be: `Scaffold` cannot assemble a contract while a hole is open, and the resolver flags
a tier-4 ambiguity and emits anyway. Putting that difference here — as a field or as an
overridden method — converts a structural guarantee into a runtime check on a value, which
is the mistake `CLAUDE.md` records about invariant 1. See the spec's §3.1.

**Closed vocabulary only.** `Ambiguity` subclasses this and projects to `AmbiguityRequest`, a
door-2 payload. A free-text field here widens door 2 without anybody editing
`tests/test_egress.py`, which is the file that says *these are all the ways data leaves*.
Free text belongs on the subclasses, where the field count already tracks it.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_NO_EXTRAS = ConfigDict(extra="forbid")


class Excerpt(BaseModel):
    """A span of source text and a resolvable pointer to it.

    `locator` is a `file:line` or a URL — never a bare claim. A reviewer approving something
    is approving that the quoted text supports it, and they cannot do that without the text.

    **A file locator is relative to the root it was read under, never absolute.** An absolute
    one carries the machine into every draft and every golden file — the defect issue #46
    found in `digest_of_directory`, and a golden file caught it here too.
    """

    model_config = _NO_EXTRAS

    locator: str
    text: str


class Candidate(BaseModel):
    """One thing that may be answered, and where it comes from.

    Not `CandidateRef` — that is `egress.py`'s alias for a *reference* that crosses door 2
    (`ContractId | EdgeRef | None`). This is the offered option a reviewer reads.
    """

    model_config = _NO_EXTRAS

    value: str
    note: str = ""
    """Where this candidate is declared, so a reviewer can check it without a second lookup."""


class Question(BaseModel):
    """What is being asked, what it is about, and what may be answered."""

    model_config = _NO_EXTRAS

    subject: str
    """What is being decided. `Hole` spelled this `field` and `Ambiguity` spelled it
    `subject`; `subject` survives because it is already a declared mark and already
    serialised into `pipeline.yml`."""

    what: str = ""
    """What the value is, in a sentence a reviewer can read."""

    why_open: str = ""
    """Why a human is being asked rather than a rule answering it."""

    candidates: list[Candidate] = Field(default_factory=list)
    """What may go here. Empty means nothing is known; see `closed` for whether it binds."""

    closed: bool = True
    """Whether `candidates` is the *whole* of what is legal, or only what is suggested.

    **Not everything with candidates is a closed vocabulary.** Invariant 7 closes
    *vocabularies* — types, states, roles. A port **name** is not one: `PortName` is a shape
    alias and `ModuleContract` accepts any valid identifier. Binding a name to an invented
    list is what made multiqc's `reports` unreachable.
    """

    evidence: list[Excerpt] = Field(default_factory=list)
    """What the answer rests on. The build path had none of this and the forge always did,
    which is the asymmetry the spec's §7.1 is about."""

    def legal(self, value: Any) -> bool:
        """Is this an allowed answer?

        **A list is checked member by member.** `roles` and `produces[].state` hold several
        values from one closed set, so the candidates are the legal *members* rather than the
        legal *values* — comparing the whole list against them rejects `["qc_per_sample"]`
        while accepting `"qc_per_sample"`, which is backwards for the field it guards.
        """
        if not self.candidates or not self.closed:
            return True
        allowed = {c.value for c in self.candidates}
        if isinstance(value, list | set | frozenset | tuple):
            return all(member in allowed for member in value)
        return value in allowed
```

```python
# packages/comeni-core/src/comeni_core/review/__init__.py
"""What is open, and how it gets closed.

The stage between derivation and approval: a question nobody has answered yet, and the
answer with the provenance of who settled it. Shared by `mendel-forge`, which asks about a
contract it is drafting, and by the resolver, which asks about a pipeline it is building.
"""

from comeni_core.review.answer import Answer, ValueSource
from comeni_core.review.question import Candidate, Excerpt, Question

__all__ = ["Answer", "Candidate", "Excerpt", "Question", "ValueSource"]
```

Note `__init__.py` imports `answer.py`, which Task 2 creates. Write `question.py` first and run
the tests with `__init__.py` importing only `question` — then extend it in Task 2. To keep Task 1
green on its own, write `__init__.py` as:

```python
from comeni_core.review.question import Candidate, Excerpt, Question

__all__ = ["Candidate", "Excerpt", "Question"]
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
uv run pytest packages/comeni-core/tests/test_review_base.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Confirm purity is unmoved**

```bash
uv run pytest tests/test_purity.py -q; echo "exit=$?"
```

Expected: `exit=0`. A new module in a pure package is exactly what that scan exists to see.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/src/comeni_core/review/ packages/comeni-core/tests/test_review_base.py
git commit -m "feat(core): a question a reviewer must answer, shared and inert"
```

---

## Task 2: The `Answer` base, and one provenance vocabulary

**Files:**
- Create: `packages/comeni-core/src/comeni_core/review/answer.py`
- Modify: `packages/comeni-core/src/comeni_core/review/__init__.py`
- Modify: `packages/comeni-core/src/comeni_core/plan/tiers.py`
- Test: `packages/comeni-core/tests/test_review_base.py` (append)

**Interfaces:**
- Consumes: nothing from Task 1 — `answer.py` and `question.py` are independent.
- Produces: `ValueSource` (now in `review/answer.py`, re-exported from `plan/tiers.py`) with a
  new `DERIVED` member; `Answer(value: Any, by: str, how: ValueSource, why: str)`.

**`ValueSource` moves rather than being imported.** `plan/decision.py` will import `Question`
from `review/`, so a `review → plan` import is a cycle. Moving it and re-exporting keeps every
existing `from comeni_core.plan.tiers import ValueSource` working and the package's public
surface unchanged. Spec §9.1.

- [ ] **Step 1: Write the failing test**

```python
# append to packages/comeni-core/tests/test_review_base.py

from comeni_core.review.answer import Answer, ValueSource


def test_derived_is_a_source_and_hand_is_not():
    """The forge's `Filler` folds in here: HAND was HUMAN under another name, and DERIVED
    (a fact read off a source file) is genuinely distinct from RESOLVER (the ladder settled
    it) and MEASURED (a tool looked at the data)."""
    assert ValueSource.DERIVED == "derived"
    assert ValueSource.HUMAN == "human"
    assert not hasattr(ValueSource, "HAND")


def test_every_pre_existing_spelling_is_preserved():
    """`pipeline.yml` carries these strings. Changing one is a SCHEMA_VERSION break, and
    this refactor is not allowed to be one."""
    assert {
        ValueSource.RESOLVER,
        ValueSource.GOAL,
        ValueSource.HUMAN,
        ValueSource.MODEL,
        ValueSource.MEASURED,
    } == {"resolver", "goal", "human", "model", "measured"}


def test_tiers_still_exports_value_source():
    """25 call sites import it from here, and the public surface must not move."""
    from comeni_core.plan.tiers import ValueSource as FromTiers

    assert FromTiers is ValueSource


def test_an_answer_records_who_settled_it_and_why():
    a = Answer(value="qc.report", by="rafael", how=ValueSource.HUMAN, why="it is a report")
    assert a.value == "qc.report"
    assert a.how is ValueSource.HUMAN


def test_an_answer_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Answer(value="x", by="y", how=ValueSource.HUMAN, why="z", confidence=1.0)
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
uv run pytest packages/comeni-core/tests/test_review_base.py -k "derived or spelling or tiers or answer" -v
```

Expected: `ModuleNotFoundError: No module named 'comeni_core.review.answer'`.

- [ ] **Step 3: Create `answer.py` by moving `ValueSource` out of `tiers.py`**

Cut the whole `class ValueSource` block — including every docstring on its members, which are
load-bearing — out of `packages/comeni-core/src/comeni_core/plan/tiers.py` and paste it into the
new file below. Do not retype it; the member docstrings explain distinctions the resolver
depends on.

```python
# packages/comeni-core/src/comeni_core/review/answer.py
"""An answer, and the provenance of it.

**One vocabulary, where there were two.** `mendel_forge.scaffold.Filler` was
`DERIVED / HAND / MODEL` and this was `RESOLVER / GOAL / HUMAN / MODEL / MEASURED`. `HAND` and
`HUMAN` were the same fact under two names; `MODEL` was in both. They are one enum now, and
`DERIVED` joins it.

**`DERIVED`, `RESOLVER` and `MEASURED` look mergeable and are not.** `DERIVED` is a fact read
off a source file, `MEASURED` is a tool that looked at data and named itself, and `RESOLVER`
is the deterministic ladder settling a question. A reviewer asking *why does this value say
what it says* gets three different answers.

**This module lives here rather than in `plan/` to break a cycle.** `plan/decision.py` imports
`Question` from `review/`, so `review/` importing `plan/` would be circular.
`plan.tiers` re-exports `ValueSource` so no call site moves.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ValueSource(StrEnum):
    """Who decided a value, recorded separately from how well it was decided.

    A tier says *how* something was settled; it should not also have to say *who*. A user
    who pins a parameter has legitimately removed the ambiguity, so the tier is still
    structural — but a reviewer needs to see that Mendel did not derive it. Same shape as
    measured-versus-asserted in the profiling spec, and for the same reason.
    """

    RESOLVER = "resolver"
    GOAL = "goal"
    HUMAN = "human"
    """<KEEP the existing 10-line docstring verbatim: goal pin is tier 1, override is
    tier 4 that stayed tier 4, collapsing them erases the question somebody answered.>"""
    MODEL = "model"
    """<KEEP the existing 14-line docstring verbatim: distinct from HUMAN, nothing writes
    it until Plan 2, it is a claim not a proof, A130.>"""
    MEASURED = "measured"
    """<KEEP the existing docstring verbatim: measured vs asserted, the clinical
    distinction, `sealed`.>"""
    DERIVED = "derived"
    """A fact read directly off a source file — a process name in `main.nf`, an emit channel.
    Was `Filler.DERIVED`. Distinct from `MEASURED`, which is a tool reporting on data, and
    from `RESOLVER`, which is the ladder choosing between options."""


class Answer(BaseModel):
    """What was answered, by whom, by what means, and why.

    `Resolution` narrows `value` to `ParamValue`; `FilledValue` leaves it `Any`. That is the
    one place the base is intentionally looser than a subclass.
    """

    model_config = ConfigDict(extra="forbid")

    value: Any
    by: str
    """A username, a model id, or the name of the source a fact was read from."""
    how: ValueSource
    why: str
```

Then in `plan/tiers.py`, where the class used to be:

```python
# ValueSource lives in `review/answer.py` so that `review/` need not import `plan/` —
# `plan/decision.py` imports `Question` from there, and the reverse edge would be a cycle.
# Re-exported because 25 call sites and the package's public surface name it here.
from comeni_core.review.answer import ValueSource

__all__ = ["ReviewLevel", "Tier", "ValueSource"]
```

- [ ] **Step 4: Extend `review/__init__.py`**

```python
from comeni_core.review.answer import Answer, ValueSource
from comeni_core.review.question import Candidate, Excerpt, Question

__all__ = ["Answer", "Candidate", "Excerpt", "Question", "ValueSource"]
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest packages/comeni-core/tests/test_review_base.py -v
uv run pytest packages/comeni-core packages/mendel-resolver -q; echo "exit=$?"
```

Expected: the new tests pass, and **nothing else breaks** — the re-export is what guarantees
that. If anything fails on `ValueSource`, the re-export is missing or `__all__` is wrong.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/src/comeni_core/review/ \
        packages/comeni-core/src/comeni_core/plan/tiers.py \
        packages/comeni-core/tests/test_review_base.py
git commit -m "feat(core): one provenance vocabulary, and an Answer to carry it"
```

---

## Task 3: Re-base the forge on `Question` and `Answer`

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/scaffold.py`
- Modify: `packages/mendel-forge/src/mendel_forge/observe.py`
- Modify: `packages/mendel-forge/src/mendel_forge/assemble.py`
- Modify: `packages/mendel-forge/src/mendel_forge/ops.py`
- Modify: `packages/mendel-forge/src/mendel_forge/filler.py`
- Modify: `packages/mendel-forge/tests/` (conftest and the tests listed below)
- Modify: `packages/mendel-forge/tests/golden/nf-core-fastqc.scaffold.json`

**Interfaces:**
- Consumes: `Question`, `Answer`, `ValueSource`, `Candidate`, `Excerpt` from Tasks 1–2.
- Produces: `Hole(Question)` keeping `after` and `channels`; `FilledValue(Answer)` with no extra
  fields; `Filler` deleted.

**The rename is `Hole.field` → `Hole.subject` and `FilledValue.filler` → `.how`.** Both are
mechanical and both move the golden scaffold. `Hole.what`, `.why_open`, `.candidates`, `.closed`,
`.evidence` and `FilledValue.value`, `.by`, `.why` all keep their names — they were already the
base's names, which is why the base was drawn there.

- [ ] **Step 1: Write the failing test**

```python
# packages/mendel-forge/tests/test_scaffold_rebase.py
"""The forge's types are the shared ones now, and the container still owns the blocking."""

from comeni_core.review import Answer, Question, ValueSource

from mendel_forge.scaffold import FilledValue, Hole, Scaffold


def test_a_hole_is_a_question():
    assert issubclass(Hole, Question)


def test_a_filled_value_is_an_answer():
    assert issubclass(FilledValue, Answer)


def test_a_hole_keeps_what_is_genuinely_its_own():
    """`after` orders holes whose candidates depend on another's answer; the resolver ladder
    handles that itself. `channels` is nf-core vocabulary. Neither belongs on the base."""
    own = set(Hole.model_fields) - set(Question.model_fields)
    assert own == {"after", "channels"}


def test_a_filled_value_adds_nothing_to_the_answer():
    """A signal that the base is drawn at about the right place — spec §4.2."""
    assert set(FilledValue.model_fields) == set(Answer.model_fields)


def test_the_scaffold_still_owns_the_blocking(fastqc_scaffold):
    """Spec §3.1: the guarantee is that the container refuses, not that the hole knows."""
    assert not fastqc_scaffold.is_complete()
    assert not hasattr(Hole, "blocks")


def test_filler_is_gone():
    import mendel_forge.scaffold as scaffold

    assert not hasattr(scaffold, "Filler")


def test_a_hand_fill_is_recorded_as_human(fastqc_scaffold):
    """`HAND` folded into `HUMAN`. Same fact, one name."""
    hole = fastqc_scaffold.holes[0]
    filled = fastqc_scaffold.fill(
        hole.subject, hole.candidates[0].value, ValueSource.HUMAN, by="rafael", why="because"
    )
    assert filled.filled[hole.subject].how is ValueSource.HUMAN
```

Add to `packages/mendel-forge/tests/conftest.py` if no such fixture exists:

```python
@pytest.fixture
def fastqc_scaffold():
    """The golden fastqc scaffold, loaded. Deliberately the same file the golden test pins,
    so a fixture drifting from the golden is impossible."""
    import json
    from pathlib import Path

    from mendel_forge.scaffold import Scaffold

    path = Path(__file__).parent / "golden" / "nf-core-fastqc.scaffold.json"
    return Scaffold.model_validate(json.loads(path.read_text()))
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-forge/tests/test_scaffold_rebase.py -v
```

Expected: `TypeError` or assertion failures — `Hole` is not a `Question` subclass yet.

- [ ] **Step 3: Re-base `scaffold.py`**

Replace the `Filler`, `FilledValue`, `Candidate` and `Hole` definitions with:

```python
from comeni_core.review import Answer, Candidate, Excerpt, Question, ValueSource


class FilledValue(Answer):
    """A settled hole. Adds nothing to `Answer` — see spec §4.2.

    `by` is `nf-core` for a derived fact, a username for a hand fill, a model id for a model
    one. `land` copies it verbatim into `Provenance.drafted_by`.
    """


class Hole(Question):
    """An unanswered question about a contract being drafted.

    **The blocking lives in `Scaffold`, not here.** `Scaffold.is_complete()` gates
    `contract_from`, so the forge cannot emit an invalid declared file. Putting that on this
    class — as a field or a method — would trade a structural guarantee for a runtime check.
    """

    after: str | None = None
    """A field that must be answered first, because this hole's candidates depend on it.

    **Holes were independent, and they never were.** A port's name comes from its type, so
    asking both from the same evidence produced a model that answered `gtf` for
    `consumes[1].name` and `genome.index.hisat2` for `consumes[1].type_id` — the same port,
    contradicted between two calls that could not see each other.
    """

    channels: tuple[str, ...] = ()
    """What the module calls this port, kept so candidates can be recomputed once `after`
    lands without re-reading the source."""
```

Delete `class Candidate` and `class Filler` from this module entirely; `Candidate` is imported
from core and `Filler` is gone. Keep the re-export of `Candidate` and `Excerpt` in
`scaffold.py`'s namespace so existing `from mendel_forge.scaffold import Candidate` call sites
keep working.

Then, throughout `scaffold.py`, rename `hole.field` → `hole.subject`. The affected methods are
`replacing`, `propose`, `hole`, `fill`, and the `_sorted_holes` serializer's sort key. In `fill`,
the signature's `filler: Filler` parameter becomes `how: ValueSource`, and the `FilledValue`
construction becomes `FilledValue(value=value, by=by, how=how, why=why)`.

- [ ] **Step 4: Point `observe.py` at the shared `Excerpt`**

```python
# packages/mendel-forge/src/mendel_forge/observe.py
# `Excerpt` moved to comeni_core.review.question in Plan 2.5 — a build-path question that
# quotes its evidence needs the same type. Re-exported so call sites here do not move.
from comeni_core.review.question import Excerpt
```

Delete the local `class Excerpt` definition — its docstring moved into
`comeni_core/review/question.py` in Task 1. If `observe.py` declares an `__all__`, leave
`"Excerpt"` in it; if it does not, add none — the module has not needed one so far and this
change does not make it need one.

- [ ] **Step 5: Sweep the four call-site modules**

```bash
grep -rn --include='*.py' 'Filler\.\|\.filler\|\.field\b' packages/mendel-forge/
```

Apply the mapping everywhere it appears:

| was | becomes |
|---|---|
| `Filler.DERIVED` | `ValueSource.DERIVED` |
| `Filler.HAND` | `ValueSource.HUMAN` |
| `Filler.MODEL` | `ValueSource.MODEL` |
| `FilledValue(..., filler=X, ...)` | `FilledValue(..., how=X, ...)` |
| `value.filler` | `value.how` |
| `hole.field` | `hole.subject` |

`assemble._drafted_by` needs one change and it is the one to read twice:

```python
def _drafted_by(scaffold: Scaffold) -> str:
    """`hand` when a person filled every non-derived hole; the model id when one did.

    **The literal `"hand"` stays a literal.** It is what `Provenance.drafted_by` carries into
    a landed contract, and no published registry artifact may move in this refactor — which
    is exactly why `Filler.HAND` folding into `ValueSource.HUMAN` costs nothing here.
    """
    sources = {v.how: v.by for v in scaffold.filled.values()}
    return sources.get(ValueSource.MODEL, "hand")
```

- [ ] **Step 6: Run the forge suite and fix what falls out**

```bash
uv run pytest packages/mendel-forge -q; echo "exit=$?"
```

Expected: the golden scaffold test fails, and only it, plus any test still naming `filler=` or
`.field`. **One diagnostic run, then one fix pass** — do not patch-and-rerun ten times.
`CLAUDE.md` records that loop costing three hours estimated at one.

- [ ] **Step 7: Regenerate the golden scaffold, then READ the diff**

```bash
uv run pytest packages/mendel-forge -k golden --snapshot-update 2>/dev/null || \
  uv run forge draft nf-core:fastqc --name fastqc --version 0.12.1 --out /tmp/regen
git diff packages/mendel-forge/tests/golden/nf-core-fastqc.scaffold.json
```

The diff must contain **only** `field:` → `subject:` and `filler:` → `how:` with `hand` →
`human`. Anything else — a candidate that moved, evidence that vanished, a hole that changed
order — is a real regression wearing a rename's clothes. This is the step that caught the block
facts citing their own header on 2026-08-17.

- [ ] **Step 8: Commit**

```bash
uv run ruff check packages/mendel-forge; echo "lint exit=$?"
git add packages/mendel-forge packages/comeni-core
git commit -m "refactor(forge): a hole is a question, and a fill is an answer"
```

---

## Task 4: Re-base the build path, and watch the egress guard fail

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/plan/decision.py`
- Test: `tests/test_egress.py` (run, not yet edited)

**Interfaces:**
- Consumes: `Question`, `Answer` from Tasks 1–2.
- Produces: `Ambiguity(Question)`, `Resolution(Answer)`. `Ambiguity.key()` and the three `*Asked`
  subclasses are unchanged in behaviour.

**This task is expected to end with a red guard.** That is the design working — see spec §5
Rule 2. Task 5 makes it green by answering the question it asks. Do not route around it, and do
not weaken the test.

- [ ] **Step 1: Write the failing test**

```python
# append to packages/comeni-core/tests/test_review_base.py

def test_an_ambiguity_is_a_question():
    from comeni_core.plan.decision import Ambiguity

    assert issubclass(Ambiguity, Question)


def test_a_resolution_is_an_answer():
    from comeni_core.plan.decision import Resolution

    assert issubclass(Resolution, Answer)


def test_a_resolution_still_narrows_its_value():
    """Spec §4.2: `Answer.value` is `Any` and `Resolution` narrows it to `ParamValue`.
    If the narrowing silently did not happen, this is the only thing that notices."""
    import pytest
    from pydantic import ValidationError

    from comeni_core.plan.decision import Resolution

    with pytest.raises(ValidationError):
        Resolution(value=object(), by="x", how=ValueSource.RESOLVER, why="y")


def test_a_resolution_keeps_its_confidence():
    """A forge fill has no confidence; inventing one on the base would be a field nothing
    writes."""
    from comeni_core.plan.decision import Resolution

    assert "confidence" in Resolution.model_fields
    assert "confidence" not in Answer.model_fields
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/comeni-core/tests/test_review_base.py -k "ambiguity or resolution" -v
```

Expected: `assert issubclass(Ambiguity, Question)` fails.

- [ ] **Step 3: Re-base `Ambiguity`**

```python
from comeni_core.review import Answer, Question, ValueSource


class Ambiguity(Question):
    """A question the deterministic ladder could not answer.

    **This is a door, and it was the only one with no type discipline.** A32: `candidates:
    list[Any]` and `context: dict[str, Any]`, no `model_config` at all. It projects to
    `AmbiguityRequest`, which is a closed payload; the closed half was downstream of the
    open half.

    **`subject` is inherited now.** It was declared here and is declared on `Question`, which
    is what lets a review screen render this and a forge hole with one component.
    """

    node_id: NodeId

    def key(self) -> str:
        return f"{self.node_id}.{self.subject}"
```

`subject` is deleted from `Ambiguity` (inherited) but its `Subject` mark typing is lost by doing
so — `Question.subject` is a plain `str`. **Re-narrow it here** the same way `Resolution` narrows
`value`:

```python
    subject: Subject
```

Then `Resolution`:

```python
class Resolution(Answer):
    """The answer coming back through the port. Also a boundary, in the other direction."""

    value: ParamValue
    by: ResolverId = "flag-only"
    """A declared id, not a bare `str`: written into every `DecisionRecord` and reaching a
    publish bundle, filled in by whatever implements the port."""
    how: ValueSource = ValueSource.RESOLVER
    why: Line
    confidence: float = 0.0
```

**`Resolution.chosen` → `value`, `.resolved_by` → `by`, `.source` → `how`, `.reason` → `why`.**
Sweep every call site:

```bash
grep -rn --include='*.py' '\.chosen\|resolved_by\|resolution\.source\|resolution\.reason' packages/ tests/
```

The known sites are `mendel_resolver/ports.py` (`FlagOnlyResolver`), `mendel_resolver/resolve.py`
(around lines 400 and 427), `mendel_resolver/replay.py` (around line 123), and their tests.

- [ ] **Step 4: Run the fast suite, then the egress guard specifically**

```bash
uv run pytest packages/ -q; echo "exit=$?"
uv run pytest tests/test_egress.py -q; echo "egress exit=$?"
```

Expected: `packages/` green. **`tests/test_egress.py` RED**, with a message naming a field:

```
AssertionError: ParamAsked.what has nowhere to go in AmbiguityRequest, so a
model behind door 2 would never be told it
```

- [ ] **Step 5: Record the red guard before fixing it**

Write the exact failure message into the commit body. This is the guard doing its job and the
record is worth more than the fix.

```bash
git add packages/
git commit -m "refactor(core): an ambiguity is a question, and a resolution is an answer

tests/test_egress.py is RED at this commit, deliberately. Inheriting Question
gives Ambiguity four fields with no slot in AmbiguityRequest, and the door
totality assertion refuses to let that pass unnoticed:

    ParamAsked.what has nowhere to go in AmbiguityRequest, so a model behind
    door 2 would never be told it

Whether evidence and why_open cross to a model is a real decision. Task 5
makes it."
```

---

## Task 5: Answer the door-2 question

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/egress.py`
- Modify: `tests/test_egress.py`
- Modify: `notes/audits/guard-ledger.md`

**Interfaces:**
- Consumes: the red guard from Task 4.
- Produces: an `AmbiguityRequest` whose fields are a decided superset of the four `*Asked` types.

**The decision, and the argument.** Four inherited fields need a verdict:

| field | crosses door 2? | why |
|---|---|---|
| `what` | **yes** | it says what is being decided in a sentence. A model told only `subject` and candidates is the exact defect the forge's prompt search measured — *"the question never said which port it was about"* cost 21 points |
| `why_open` | **yes** | same measurement: `Hole.why_open` was never sent, and it is where the scaffold explains the judgement. Three misses got exactly what it explains wrong |
| `candidates` | **already there** | as `list[CandidateRef]`; the base's `list[Candidate]` is richer. See the note below |
| `closed` | **yes** | whether the list binds. The forge measured that opening a closed field was the *worst* configuration tested — 76%, six points below closing it |
| `evidence` | **yes, and it is the point** | *"evidence must be readable"* was the second of seven durable findings. A model given candidates and no quoted source is the 69% configuration |

**Every one of these is a `Mark.FREE_TEXT` decision**, so `CLAUDE.md`'s literal count moves from
ten. Update that sentence in `CLAUDE.md` in the same commit, and say what the new authors are:
`Question.what` and `Question.why_open` are written by a *contract author or the scaffold*, and
`Excerpt.text` is quoted from a source file rather than composed. That is a weaker claim than
"somebody typed it" and worth stating.

**`candidates` needs care.** `AmbiguityRequest.candidates` is `list[CandidateRef]` and the base's
is `list[Candidate]`. The door's version is stricter — a `ContractId | EdgeRef | None` rather
than a free string — and A129 records that it accepted only one of three `*Asked` types until
their *values* were checked, not just their names. **Keep the door's stricter typing** and
project `Candidate.value` into it; do not widen the door to the base's shape.

- [ ] **Step 1: Extend the guard first, so the fix is testable**

```python
# append to tests/test_egress.py

def test_the_door_carries_what_the_forge_measured_a_model_needs():
    """Not a shape check — a content one. The forge's prompt search (2026-08-17) measured
    69% -> 88% from three fixes, and two of them were *the question did not say what it was
    about* and *the evidence was not readable*. A door that projects candidates and nothing
    else rebuilds the 69% configuration on the build path.
    """
    from comeni_core.artifact.egress import AmbiguityRequest

    for needed in ("what", "why_open", "closed", "evidence"):
        assert needed in AmbiguityRequest.model_fields, (
            f"{needed} does not cross door 2, so a tier-4 model call is the configuration "
            f"the forge measured at 69%"
        )
```

- [ ] **Step 2: Run both guards and watch them fail**

```bash
uv run pytest tests/test_egress.py -q; echo "exit=$?"
```

Expected: two failures — the totality assertion from Task 4, and the new content one.

- [ ] **Step 3: Widen `AmbiguityRequest`**

```python
class AmbiguityRequest(EgressPayload):
    """Door 2 — tier-4 resolution. Registry vocabulary and nothing else.

    **The union of what the four `*Asked` types carry**, asserted by `tests/test_egress.py`:
    a field added to an ambiguity that has nowhere to land here is a field a model would
    silently not be told, which is the quiet half of A32.

    **`what`, `why_open`, `closed` and `evidence` arrived with Plan 2.5**, when `Ambiguity`
    became a `Question`. They are not incidental: the forge measured a model at 69% without
    them and 88% with, and two of the three fixes behind that were *say what the question is
    about* and *make the evidence readable*.
    """

    node_id: NodeId
    subject: Subject
    what: Line = ""
    why_open: Line = ""
    candidates: list[CandidateRef] = []
    closed: bool = True
    evidence: list[Excerpt] = []
    states: list[StateName] = []
    tier_hint: int | None = None
    type_id: TypeId = ""
    required: list[StateName] = []
```

`Excerpt` must be importable here from `comeni_core.review.question`. Confirm
`test_every_payload_field_is_a_declared_shape` accepts it — it is a `BaseModel` of two declared
strings, so it needs to be added to the allowlist of permitted leaf shapes **explicitly**, which
is the whole point of that test being an allowlist rather than a blocklist.

- [ ] **Step 4: Run the full guard set**

```bash
uv run pytest tests/test_purity.py tests/test_purity_runtime.py \
  tests/test_egress.py tests/test_construction.py -q; echo "exit=$?"
```

Expected: `exit=0`.

- [ ] **Step 5: Watch the new guard fail on purpose, and record it**

Per A14, a guard never watched failing may be inert rather than merely weak.

```bash
# temporarily delete `evidence` from AmbiguityRequest
uv run pytest tests/test_egress.py -q 2>&1 | tail -20
# restore it
```

Append the printed message to `notes/audits/guard-ledger.md` as a new row.

- [ ] **Step 6: Update `CLAUDE.md`'s free-text count**

Edit the invariant 14 paragraph. The count moves from ten; state the new number, name the new
fields, and say that `Excerpt.text` is *quoted* rather than composed.

- [ ] **Step 7: Commit**

```bash
git add packages/comeni-core tests/test_egress.py notes/audits/guard-ledger.md CLAUDE.md
git commit -m "feat(core): door 2 carries what the forge measured a model needs"
```

---

## Task 6: Give the build path real evidence

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Test: `packages/mendel-resolver/tests/test_evidence.py` (create)

**Interfaces:**
- Consumes: `Ambiguity.evidence`, `Ambiguity.what`, `Ambiguity.why_open` from Task 4.
- Produces: a `ProducerAsked` whose `evidence` names each candidate contract and the layer it
  came from.

**Bounded deliberately.** `ProducerAsked` only — it is the ambiguity where a reviewer most needs
to know *where each candidate came from*, and the data is already in hand at the call site
(`producers_of` has the registry and the layers). `ParamAsked` and `SourceAsked` keep empty
evidence, which is honest: the field exists and nothing lies about being filled.

- [ ] **Step 1: Write the failing test**

```python
# packages/mendel-resolver/tests/test_evidence.py
"""A tier-4 producer question says where its candidates came from.

Before Plan 2.5 a reviewer got a list of contract ids and nothing to judge them on. The
forge had quoted evidence from its first day and the build path had none — spec §7.1.
"""


def test_a_producer_question_cites_each_candidate_s_layer(two_layer_registry):
    ambiguity = _producer_ambiguity_for("alignment.bam", two_layer_registry)

    assert len(ambiguity.evidence) == len(ambiguity.candidates)
    locators = {e.locator for e in ambiguity.evidence}
    assert any("registry/" in locator for locator in locators)
    for excerpt in ambiguity.evidence:
        assert excerpt.text, "an excerpt with no text is a citation a reviewer cannot read"


def test_a_producer_question_says_what_it_is_about(two_layer_registry):
    ambiguity = _producer_ambiguity_for("alignment.bam", two_layer_registry)

    assert "alignment.bam" in ambiguity.what
    assert ambiguity.why_open, "a tier-4 question with no stated reason is the 69% prompt"
```

Write `_producer_ambiguity_for` and `two_layer_registry` against the existing fixtures in
`packages/mendel-resolver/tests/` — `test_resolve.py` already builds layered registries and is
the shape to copy.

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-resolver/tests/test_evidence.py -v
```

Expected: `assert len(ambiguity.evidence) == len(...)` fails with `0 == 2`.

- [ ] **Step 3: Populate it where `ProducerAsked` is constructed**

Find the construction site in `resolve.py` and add:

```python
ProducerAsked(
    node_id=node_id,
    subject=f"producer:{type_id}",
    what=f"which contract produces {type_id}",
    why_open=(
        f"{len(candidates)} contracts produce it and no rule distinguishes them; "
        f"invariant 8 says a tie is ambiguity, not a coin flip"
    ),
    candidates=candidates,
    evidence=[
        Excerpt(
            locator=registry.path_of(contract_id),
            text=f"{contract_id} — priority {contract.priority}: {contract.priority_because}",
        )
        for contract_id in candidates
    ],
    states=states,
)
```

If `registry.path_of` does not exist, the layer path is on `layers.Layers.paths` — check
`layers.load()`'s return before inventing an accessor. **Do not add one to a pure package
without checking what is already there**; the plan is written against code and this line is the
one most likely to be wrong.

- [ ] **Step 4: Run the tests**

```bash
uv run pytest packages/mendel-resolver -q; echo "exit=$?"
```

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-resolver
git commit -m "feat(resolver): a tier-4 producer question cites where each candidate came from"
```

---

## Task 7: Public surface and documentation

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/__init__.py`
- Modify: `ARCHITECTURE.md`
- Modify: `CLAUDE.md` (the architecture block)

- [ ] **Step 1: Export the new types**

```python
from comeni_core.review import Answer, Candidate, Excerpt, Question, ValueSource
```

Keep `__all__` sorted, as the file already is.

- [ ] **Step 2: Add `review/` to the architecture block in `CLAUDE.md`**

```
  comeni-core/       types, contract schema, pipeline IR, registry     PURE
    declared/          what a registry layer holds, and how it stacks
    goal/              what is asked for, and what was measured
    review/            what is open, and how it gets closed
    plan/              what was decided — the IR, the tiers, the records
    artifact/          pipeline.yml, the lockfile, the gates, the doors
    spell/             how a value is spelled on its way to a tool
```

- [ ] **Step 3: Write the `ARCHITECTURE.md` section**

One section describing `Question`/`Answer`, the two subclass families, and — most importantly —
**why the blocking is not on the types**. Point at spec §3.1 rather than re-arguing it.

- [ ] **Step 4: Check every link still resolves**

```bash
make links; echo "exit=$?"
```

- [ ] **Step 5: Commit**

```bash
git add packages/comeni-core ARCHITECTURE.md CLAUDE.md
git commit -m "docs: review/ is a lifecycle stage, and the blocking is not on the types"
```

---

## Task 8: Verify, and prove the artifact did not move

**Files:** none modified unless something is wrong.

- [ ] **Step 1: Prove `pipeline.yml` is byte-identical**

The claim in the spec's §4.3 is that no published artifact changes. Prove it rather than assert
it — the same move that caught the machine-dependent layer digest on 2026-08-16, where
`make verify` was green throughout and building on both branches is what found it.

```bash
git stash list  # ensure clean
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/after/
git stash push -u 2>/dev/null; git checkout main -- . 2>/dev/null
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/before/
git checkout - -- . ; git stash pop 2>/dev/null
diff -u /tmp/before/pipeline.yml /tmp/after/pipeline.yml; echo "diff exit=$?"
```

Expected: `diff exit=0`. **Any difference is a `SCHEMA_VERSION` question**, and this refactor is
not allowed to be one. If the diff is non-empty, stop and report the number before continuing —
that is a decision point, not a hill to push through.

Simpler alternative if the stash dance is awkward: build on `main` in a second worktree and diff
across the two.

- [ ] **Step 2: Confirm the emitted digests are unmoved**

```bash
sha256sum /tmp/after/main.nf /tmp/after/nextflow.config
grep -n "main.nf\|nextflow.config" /tmp/after/pipeline.yml
```

`main.nf` and `nextflow.config` have carried `76355bbf9f10d6e6` and `72ddb081638edf76` since
issue #41, unmoved by everything since. A digest that moves here must be explained in the commit
message or reverted.

- [ ] **Step 3: Full verification**

```bash
make verify; echo "exit=$?"
```

**Read the exit code, then filter for detail.** Not the other way around — a `grep | tail` that
is readable is tight enough to hide a lint failure, which cost four tasks of a red suite on
2026-08-17.

Expected: `exit=0`.

- [ ] **Step 4: Residue and the guard ledger**

```bash
make residue
make residue ARGS=--list | head -20
```

The number should not have risen. A new guard added in Task 5 without a ledger row would show
here.

- [ ] **Step 5: Update the indexes**

Add a row to `notes/README.md`'s plan table between forge Phase 2 (row 15) and the rule drafter
(row 16), recording that Plan 2.5 ran and what it decided. Add the two specs to
`notes/specs/README.md`. Move the rule drafter to after Plan 3, with the argument recorded:
the original ordering optimised for queue size, and what the project was short of was feedback.

- [ ] **Step 6: Write the journal entry**

`notes/journal/2026-08-18-the-shared-question.md`. Follow the house shape — where things stand,
what was decided and rejected, **what a fresh reader gets wrong**, corrections to the plan, and
what is next. Two things belong in it specifically:

- **The spec was wrong about the migration cost** and reading `assemble._drafted_by` is what
  showed it. That is the "write plans against code" rule earning itself again.
- **The egress guard went red on purpose in Task 4 and green in Task 5.** That sequence is the
  evidence that door 2's widening was a decision rather than an accident.

- [ ] **Step 7: Commit and open the pull request**

```bash
git add notes/
git commit -m "docs: Plan 2.5 in the journal, and the indexes"
gh pr create --title "Plan 2.5 — one question, two behaviours" --body "$(cat <<'BODY'
The forge and the build path each grew their own vocabulary for *a question a
reviewer must answer*. `Hole`/`Ambiguity`, `FilledValue`/`Resolution` and
`Filler`/`ValueSource` are now one `Question`, one `Answer` and one provenance
enum in `comeni_core/review/`.

**What is deliberately NOT unified:** whether an unanswered question blocks. A
hole blocks (`Scaffold.is_complete()` gates `contract_from`); an ambiguity ships
flagged. That difference stays in the containers and the ports — `HoleFiller.fill()`
may return `None` and `AmbiguityResolver.resolve()` may not — because putting it on
the types would trade a structural guarantee for a runtime check.

**`pipeline.yml` does not change** and there is no `SCHEMA_VERSION` bump; Task 8
proves it by diffing a build against `main`.

**`tests/test_egress.py` went red on purpose** in the Ambiguity re-base commit and
green again once door 2's widening was decided rather than assumed.

Spec: `notes/specs/2026-08-18-the-shared-question.md`
Plan: `notes/plans/2026-08-18-the-shared-question.md`
BODY
)"
```

---

## Self-Review

Run before handing this plan to an executor.

**Spec coverage:**

| spec section | task |
|---|---|
| §2 the duplication | 1, 2, 3, 4 |
| §3 what is not unified | 3 (Step 1's `test_the_scaffold_still_owns_the_blocking`) |
| §3.1 no `blocks` field or method | 1 (`test_the_base_carries_no_behaviour_beyond_legality`), 3 |
| §4 the shape | 1, 2, 3, 4 |
| §4.1 what goes on `Question`; `after`/`channels` stay | 1, 3 |
| §4.2 `Answer`; narrowing; `confidence` stays | 2, 4 |
| §4.3 one provenance vocabulary; no artifact change | 2, 3, 8 |
| §5 Rule 1 no free text on the base | Global Constraints; 5 Step 6 |
| §5 Rule 2 the totality assertion | 4 (red), 5 (green) |
| §7.1 the build path has no evidence | 6 |
| §7.2 no `Proposal` on the build path | **not implemented, by design** — the spec requires only that the slot stay open, which `Question` does by not forbidding it |
| §9 testing and guards | 3 Step 7, 5 Step 5, 8 |
| §9.1 the import direction | 2 |

**Known weak points, stated rather than hidden:**

- **Task 6 Step 3 is the least certain code in this plan.** `registry.path_of` may not exist;
  the step says to check `layers.load()`'s return before inventing it. Expect a correction here.
- **Task 3 Step 7's regeneration command is a guess.** The forge's golden test may use a
  different update mechanism than `--snapshot-update`; read the test before running it.
- **Task 4's `Resolution` field renames touch `replay.py`**, which is invariant 9's replay path.
  If `make verify` goes red anywhere subtle, that is the first place to look.
