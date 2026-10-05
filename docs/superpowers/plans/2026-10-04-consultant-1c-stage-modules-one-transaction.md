# Consultant 1c — stage modules, one transaction per action — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each thing a person or a job does to an authoring session is a typed command, performed through one facade in one database transaction, with any jobs queued only after it commits. The code behind the commands lives in one module per stage, and `services/authoring.py` is gone. Everything a person sees behaves as before.

**Architecture:**
- `mendel_api/db.py` gains `transaction()`. Inside it, every `session_scope()` joins the open transaction as a savepoint, instead of committing on its own.
- `mendel_authoring/commands.py` (pure) declares one frozen dataclass per command, holding only plain values. Each names the arrows of the diagram it may take (`takes`).
- `mendel_api/services/session.py` becomes the facade:
  - `perform(command)` opens the transaction and runs the command's **recorder**, registered with `@records(CommandType)` in its stage module. The recorder may take an arrow of the diagram (`take`), and entering an acting node runs its handler, as in 1b.
  - Handlers and recorders add the jobs they want to the context (`ctx.queue(job)`).
  - `act(command)` is the async form the routes and jobs use: `perform` off the event loop, then queue.
  - The read model (`read`, `calls`, `pending_id`, `current_phase`) also lives here.
- The code moves out of `services/authoring.py` into:
  - `stages/describe.py`, `stages/gathering.py`, `stages/samples.py`, and a new `stages/goal.py`;
  - `stages/building.py`: the kept half of stage ④, as small functions part 3 calls;
  - `services/spawn.py`: Spawn and Mode, as they are, marked for deletion in part 3;
  - `stages/_rows.py`: the shared row helpers;
  - `stages/_jobs.py`: the job constructors.
- While the code moves (Tasks 4–8), `services/authoring.py` keeps thin forwarding functions under the old names, so the existing suite proves each move changed nothing. Task 10 then renames the tests' calls by a script and deletes the file.

**Tech Stack:** Python 3.12, pydantic 2, SQLAlchemy 2 (savepoints: `Session.begin_nested`), Starlette's `run_in_threadpool`, ARQ, pytest, Postgres (`127.0.0.1:5442`).

**Spec:** `docs/superpowers/specs/2026-10-04-the-consultant-build-design.md` §3.2, §8, §9, and **§11** (decided 2026-10-04 for this plan). It follows plan 1b (`docs/superpowers/plans/2026-10-04-consultant-1b-the-diagram-moves-the-session.md`, landed at `ad261bb7`). Issue #136.

**Estimate:** eleven tasks, a little larger than 1b. Tasks 4–8 are moves, and the existing suite is their test. Task 10 is one large commit made by a script.

## Global Constraints

- **`mendel-authoring` never imports `mendel-api`, FastAPI, SQLAlchemy, ARQ, a model client, or anything that reaches the network** (spec §3.1). A command's fields hold plain values only: `str`, `int`, `float`, `bool`, `None`, `dict`, `list`, `tuple`, `bytes`.
- **Behaviour unchanged** (spec §10). Tasks 1–9 leave every existing test untouched, except the few this plan names, which monkeypatch a helper that moves. Task 10 changes call sites and imports only, never an assertion.
- **Nothing that calls a model runs inside a transaction** (spec §11.2). A model is called only in a job; the job's result is its own command.
- **An exception rolls back; a refusal returned as a value commits** (spec §11.2). `ctx.raised` is raised by `perform` only after the commit.
- **Jobs are queued after the commit**, never inside a recorder or handler (spec §11.2).
- **A command never performs another command.** Inside a recorder, a further move is `take(ctx, arrow)`; `perform` refuses to start inside an open transaction.
- Python tests always run with `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel` on the command line, from the repository root. Never bare pytest. For make, the URL goes **after the target** (`make check MENDEL_DATABASE_URL=…`), never as an env prefix: the Makefile `-include`s the operator's `.env`.
- Run `make check` on its own before each commit, and read make's own exit code.
- Guards are watched failing and recorded in `tests/fixtures/guard-ledger.md`.
- Diagnostics come from `comeni_core/diagnostics.yml` through `coded()`, never a hand-written code. This plan adds none.

## Rulings against the spec, for the operator

1. **`perform(command)`, not `perform(session_id, command)`.** A command answering a proposal carries the proposal's id, and the recorder finds the session from it, as `answer_gap` does today. The routes already check that the proposal belongs to the session in the path (`_kind_in`). *Cost if wrong:* every command gains a `session_id` field.
2. **Reads are not commands.** Routes and jobs change a session only through `session.act`. To *read* a stage's own state (a turn's grounding, a question's context, a reading's state), a job calls that stage's read functions, which each stage lists in `READS`. A guard holds them to it. *Cost if wrong:* a `session.read_*` per read.
3. **Spawn bypasses the facade until part 3 deletes it.**
   - Its build job resolves with a model, so it cannot run inside a transaction.
   - `services/spawn.py` calls the building functions with their own scopes, as today.
   - The route still queues Spawn's build job.
   - *Cost if wrong:* none past part 3.
4. **Two forms of the facade:** `perform` (sync: the tests, and the thread `act` runs it on) and `act` (async: the routes and jobs; it queues). A test that calls `perform` gets the jobs back in `Performed.jobs`, unqueued, which is what today's tests see too. *Cost if wrong:* one rename.
5. **`family` queues the reading only when `describe` or `retry` brings the session there.** On `revised`, the job that read the correction answers inline, as today; queueing would answer twice. *Cost if wrong:* a duplicate job id, refused by the queue.
6. **Phrasing is queued when the session enters `ask`, and when a sample records facts but its question stays.**
   - The prefetch at the end of every gathering turn job goes. Every question it phrased had already been queued on entering `ask`, keyed by subject, so it was a duplicate the queue refused.
   - *Cost if wrong:* a question's words arrive later. Review Focus 5 watches it.
7. **The model's reply stays two commands, as today:** `AnswerTurn` fills the turn, then `Understood` moves the session. Merging them is part 3's call. *Cost if wrong:* none; two transactions, as today.
8. **A sample's inspection runs inside its command's transaction.** It is computation, not a model. The proposal's row is locked only after the inspection, as today. *Cost if wrong:* a request holds an open transaction for the inspection's length (a few hundred milliseconds).
9. **Temporary forwarding functions in `services/authoring.py`, Tasks 4–9.** Each is one line calling `session.perform(...)`. They exist so the untouched suite can test each move; Task 10 deletes them with the file. *Cost if wrong:* none past Task 10.
10. **Tests' setup helpers live in `packages/mendel-api/tests/authoring_setup.py`**: `move`, `offer_next_gap` and `start_building`. pytest's default import mode puts the tests folder on the path, and the name is unique across the workspace. *Cost if wrong:* a move into root `tests/support/`.
11. **Stage functions tests use as setup stay plain functions**, not commands: `_rows.propose`, `_rows.decide`, `samples.start_reading`, `samples.check_sample_question` and `gathering.compose_goal`. They open their own scopes, as today. *Cost if wrong:* each becomes a command.

## Review Focus

1. **An exception caught inside a command** must roll back only its own savepoint, never the command's earlier writes. Examples: a `Refused` swallowed by a sample's way out, or a job's `_perform` catching one. Pinned in Task 1.
2. **The queue down, or refusing a job, after the commit.** The action stands, and the response says `queued=False`. A sample reading whose job never queued ends as `no_answer` (MA0007), never pending. Pinned in Task 3 and Task 7.
3. **Two tabs racing on one session.** The second command is refused (MI0201) and leaves nothing behind, not even the answer it recorded before the refusal. Today that answer stood. Pinned in Task 5.
4. **The resolver failing in Build, through the facade.** The session lands on `failed` and stays there: committed before the error is raised, never rolled back with it. Pinned in Task 8.
5. **The phrasing prefetch without the end-of-turn enqueue** (ruling 6). The question on offer and the next one are both queued when the session enters `ask`. Pinned in Task 5.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `packages/mendel-api/src/mendel_api/db.py` | `transaction()`, `in_transaction()`, joined savepoint scopes |
| Create `packages/mendel-authoring/src/mendel_authoring/commands.py` | the typed commands, and what each may take |
| Modify `packages/mendel-api/src/mendel_api/services/session.py` | the facade: `perform`, `act`, `take`, `records`, `Job`, `Performed`; the read model |
| Create `packages/mendel-api/src/mendel_api/stages/_rows.py` | `now`, `new_id`, `next_seq`, `swap`, `engine_turn`, `note`, `say_engine`, `propose`, `decide`, `settlement`, `pending_of` |
| Create `packages/mendel-api/src/mendel_api/stages/_jobs.py` | job names and constructors (`turn`, `phrase`, `readback`, `characterise`) |
| Modify `stages/describe.py` | ① opening, beginning, saying, a turn answered, the model's reading, retry; handlers `read_goal`, `family` |
| Create `stages/goal.py` | ③ the card: accept, *not quite*, a correction in words, the read-back; handler `readback` |
| Modify `stages/gathering.py` | ② needs, questions, answers, phrasing, prefill; handlers `list_needs`, `next_gap`, `answered`, `ask`, `suggest` |
| Modify `stages/samples.py` | ②a an upload inspected, a reading started, read, failed, handed back; handler `upload` |
| Modify `stages/building.py` | ④ kept: resolve, offer a step, commit a step, re-resolve, the notes; `settle_step` as a thin recorder; `StartBuilding`, `RecordEdit`; handlers `resolve`, `offer` |
| Create `packages/mendel-api/src/mendel_api/services/spawn.py` | Spawn, Mode's policy, `spawn_forward`, `SpawnStop`, `mode_of`, the Spawn build: deleted in part 3 |
| Delete `packages/mendel-api/src/mendel_api/services/authoring.py` | (Task 10) |
| Modify `routes/authoring.py`, `services/authoring_jobs.py`, `services/characterise.py` | only the facade, and stage `READS` |
| Create `packages/mendel-api/tests/authoring_setup.py` | `move`, `offer_next_gap`, `start_building` for tests |
| Create `packages/mendel-api/tests/test_db_transaction.py`, `test_authoring_facade.py`, `test_authoring_commands.py`; `packages/mendel-authoring/tests/test_commands.py` | the new tests |
| Modify `test_authoring_binding.py` | recorders, the new acting nodes, the guards |
| Modify `docs/design/authoring-protocol.md`, `ARCHITECTURE.md`, `tests/fixtures/guard-ledger.md` | the docs |

---

### Task 1: One transaction, joined by every scope beneath it

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/db.py`
- Test: `packages/mendel-api/tests/test_db_transaction.py`
- Modify: `tests/fixtures/guard-ledger.md`

**Interfaces:**
- Produces: `db.transaction() -> ContextManager[Session]`; `db.in_transaction() -> bool`. `session_scope()` is unchanged outside a transaction. Inside one, it yields the open `Session` within a savepoint (`begin_nested`): an exception escaping the scope rolls back only that savepoint, and nothing commits until `transaction()` exits.

- [x] **Step 1: Write the failing tests**

```python
"""One transaction per action (spec §11.2): every scope beneath it joins it."""

import secrets
from datetime import UTC, datetime

import pytest
from mendel_api import db
from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft


def _draft(draft_id: str) -> PipelineDraft:
    return PipelineDraft(id=draft_id, who="tester", name="t", graph={"nodes": [], "edges": []},
                         updated_at=datetime.now(UTC), goal=None, provenance={}, revision=0)


def _seen_elsewhere(draft_id: str) -> bool:
    """Whether another connection sees the row: what a job on the worker would read."""
    other = db.SessionLocal()
    try:
        return other.get(PipelineDraft, draft_id) is not None
    finally:
        other.close()


@pytest.fixture
def ids():
    made: list[str] = []
    yield made
    with session_scope() as s:
        for i in made:
            if (row := s.get(PipelineDraft, i)) is not None:
                s.delete(row)


def test_outside_a_transaction_each_scope_commits_on_its_own(ids):
    ids.append(i := secrets.token_hex(8))
    with session_scope() as s:
        s.add(_draft(i))
    assert _seen_elsewhere(i)
    assert not db.in_transaction()


def test_inside_a_transaction_nothing_is_seen_until_it_commits(ids):
    ids.append(i := secrets.token_hex(8))
    with db.transaction():
        assert db.in_transaction()
        with session_scope() as s:
            s.add(_draft(i))
        assert not _seen_elsewhere(i)
    assert _seen_elsewhere(i)


def test_an_exception_out_of_the_transaction_rolls_back_every_scope(ids):
    ids.append(i := secrets.token_hex(8))
    with pytest.raises(RuntimeError), db.transaction():
        with session_scope() as s:
            s.add(_draft(i))
        raise RuntimeError("broke after the write")
    assert not _seen_elsewhere(i)


def test_an_exception_caught_inside_rolls_back_only_its_own_scope(ids):
    """Review Focus 1: a `Refused` swallowed inside a command undoes only what its scope wrote."""
    ids.extend([kept := secrets.token_hex(8), undone := secrets.token_hex(8)])
    with db.transaction():
        with session_scope() as s:
            s.add(_draft(kept))
        with pytest.raises(ValueError), session_scope() as s:
            s.add(_draft(undone))
            s.flush()
            raise ValueError("refused")
    assert _seen_elsewhere(kept)
    assert not _seen_elsewhere(undone)


def test_a_transaction_does_not_open_inside_another():
    with db.transaction(), pytest.raises(RuntimeError, match="already open"):
        with db.transaction():
            pass
```

- [x] **Step 2: Run them to see them fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_db_transaction.py -q`
Expected: the first passes, the other four fail with `AttributeError: module 'mendel_api.db' has no attribute 'transaction'`.

- [x] **Step 3: Write the transaction**

Replace `session_scope` in `packages/mendel-api/src/mendel_api/db.py` with:

```python
_joined: ContextVar[Session | None] = ContextVar("mendel_db_joined", default=None)
"""The transaction an action opened (`transaction()`), which every scope beneath it joins."""


def in_transaction() -> bool:
    return _joined.get() is not None


@contextmanager
def transaction() -> Iterator[Session]:
    """**One action, one transaction** (spec §11.2 of the consultant build). Every
    `session_scope()` opened beneath this one joins it as a savepoint, and nothing commits until
    this exits. An exception out of it rolls back everything the action wrote."""
    if _joined.get() is not None:
        raise RuntimeError("a transaction is already open: an action never starts another")
    session = SessionLocal()
    token = _joined.set(session)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        _joined.reset(token)
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """A unit of work: its own transaction, or, inside an action's, a savepoint of it.

    **A savepoint, not a plain join**, so code that catches an exception from a scope (a refusal
    it expected) sees what it saw before: that scope wrote nothing, and earlier ones stand."""
    joined = _joined.get()
    if joined is not None:
        with joined.begin_nested():
            yield joined
        return
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Add `from contextvars import ContextVar` to the imports.

- [x] **Step 4: Run them to see them pass**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_db_transaction.py -q`
Expected: 5 passed.

- [x] **Step 5: Watch the join fail**

Temporarily change `if joined is not None:` to `if False:` in `session_scope`. Re-run the file.
Expected: `test_inside_a_transaction_nothing_is_seen_until_it_commits` and `test_an_exception_out_of_the_transaction_rolls_back_every_scope` FAIL. Restore. Then replace `with joined.begin_nested():` with a plain `if True:`, and re-run.
Expected: `test_an_exception_caught_inside_rolls_back_only_its_own_scope` FAILS. Restore. Add a `## 1c` section to `tests/fixtures/guard-ledger.md` with one row per revert: the test, the revert, and what failed.

- [x] **Step 6: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`
Expected: exit 0. Nothing opens a transaction yet, so nothing else changes.

```bash
git add packages/mendel-api/src/mendel_api/db.py packages/mendel-api/tests/test_db_transaction.py tests/fixtures/guard-ledger.md
git commit -m "feat(db): one transaction per action — scopes beneath it join as savepoints (#136)"
```

---

### Task 2: Typed commands, and acting nodes that pass straight on

**Files:**
- Create: `packages/mendel-authoring/src/mendel_authoring/commands.py`
- Modify: `packages/mendel-authoring/src/mendel_authoring/interpret.py` (`run`), `protocol.py` (`Node.acts`'s docstring)
- Test: `packages/mendel-authoring/tests/test_commands.py`, `test_interpret.py`

**Interfaces:**
- Consumes: `mendel_authoring.types.Command` (the arrow names), `mendel_authoring.protocol.PROTOCOL`.
- Produces: `interpret.run` passes an acting node that does not wait, and has one way straight on, straight on when its handler names nothing. That is how `ask`, `suggest` and `readback` can act (queue a job) without resting there (Tasks 5 and 6). An acting node that waits (`resolve`, `family`) still rests on `None`.
- Produces: the dataclasses below, each with `takes: ClassVar[frozenset[Command]]`, and `COMMANDS: tuple[type, ...]`, every one of them. Field names and order are what Task 10's rename script relies on: **each command's fields are in the same order as the parameters of the function it replaces.**

- [x] **Step 1: Write the failing tests**

```python
"""The commands a person or a job performs (spec §11.3): typed, plain, and naming their arrows."""

import dataclasses
import types
import typing

import pytest
from mendel_authoring import commands as c
from mendel_authoring.protocol import PROTOCOL
from mendel_authoring.types import Command

PLAIN = {str, int, float, bool, type(None), dict, list, tuple, bytes, object}


def _plain(hint) -> bool:
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        return all(_plain(a) for a in typing.get_args(hint))
    return (origin or hint) in PLAIN


def test_every_command_is_frozen_and_holds_plain_values_only():
    assert c.COMMANDS, "no command: the loop would hold vacuously"
    for kind in c.COMMANDS:
        assert dataclasses.is_dataclass(kind) and kind.__dataclass_params__.frozen, kind
        hints = typing.get_type_hints(kind)
        for f in dataclasses.fields(kind):
            assert _plain(hints[f.name]), f"{kind.__name__}.{f.name}: {hints[f.name]}"


def test_every_arrow_a_built_edge_names_is_taken_by_some_command():
    drawn = {e.on for e in PROTOCOL.edges if e.built} & {m.value for m in Command}
    assert drawn, "no command arrow drawn: the comparison would hold vacuously"
    taken = {a.value for kind in c.COMMANDS for a in kind.takes}
    assert drawn <= taken, sorted(drawn - taken)


def test_a_command_takes_only_arrows_the_core_names():
    for kind in c.COMMANDS:
        assert all(isinstance(a, Command) for a in kind.takes), kind


def test_a_command_cannot_be_changed_once_made():
    said = c.Say("s1", "hello")
    with pytest.raises(dataclasses.FrozenInstanceError):
        said.text = "other"  # type: ignore[misc]
```

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest packages/mendel-authoring/tests/test_commands.py -q`
Expected: FAIL at collection with `ImportError: cannot import name 'commands'`.

- [x] **Step 3: Write the commands**

```python
"""What a person or a job does to an authoring session, typed (spec §11.3 of the consultant
build). **Plain values only**, so the core holds no shell type: a goal edited on the card is its
JSON, a sample's files are bytes, a model's reply its dump. The shell's recorder for each
(`mendel_api.services.session.records`) validates what it needs.

`takes` names the arrows of the diagram a command's recorder may take; the binding test holds a
recorder to it. Field order matches the parameters of the function each replaces, which is what
let the tests' call sites be rewritten by a script (plan 1c, Task 10)."""

from dataclasses import dataclass
from typing import ClassVar

from mendel_authoring.types import Command

_NONE: frozenset[Command] = frozenset()


@dataclass(frozen=True, slots=True)
class OpenSession:
    draft_id: str
    mode: str
    who: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class Begin:
    prompt: str
    mode: str
    who: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.DESCRIBE})


@dataclass(frozen=True, slots=True)
class Say:
    session_id: str
    text: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.DESCRIBE, Command.REPLY_IN_WORDS})


@dataclass(frozen=True, slots=True)
class AnswerTurn:
    session_id: str
    seq: int
    blocks: list
    base_revision: int
    invocation_id: str | None = None
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class Understood:
    session_id: str
    goal: dict
    takes: ClassVar[frozenset[Command]] = frozenset({Command.UNDERSTOOD})


@dataclass(frozen=True, slots=True)
class AskedBack:
    session_id: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.ASKED_BACK})


@dataclass(frozen=True, slots=True)
class ProviderFailed:
    session_id: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.PROVIDER_FAILED})


@dataclass(frozen=True, slots=True)
class Retry:
    session_id: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.RETRY})


@dataclass(frozen=True, slots=True)
class DecideGoal:
    proposal_id: str
    decision: str
    expected_revision: int
    by: str
    edited: dict | None = None
    takes: ClassVar[frozenset[Command]] = frozenset({Command.CONFIRM_GOAL, Command.REVISE_GOAL})


@dataclass(frozen=True, slots=True)
class Revised:
    session_id: str
    by: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.REVISED})


@dataclass(frozen=True, slots=True)
class StoreReadback:
    session_id: str
    text: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class ReadbackFailed:
    session_id: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class Resume:
    session_id: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class AnswerGap:
    proposal_id: str
    option: str
    value: object
    by: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.ANSWER_GAP})


@dataclass(frozen=True, slots=True)
class PrefillGap:
    proposal_id: str
    option: str
    value: object
    note: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class StorePhrasing:
    session_id: str
    subject: str
    asked: dict
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class PhrasingFailed:
    session_id: str
    subject: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class UploadSample:
    session_id: str
    proposal_id: str
    files: tuple
    """`((name, head bytes), ...)`: one file, or a pair."""
    by: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.UPLOAD_SAMPLE})


@dataclass(frozen=True, slots=True)
class SampleInspected:
    proposal_id: str
    inspection: dict
    by: str
    takes: ClassVar[frozenset[Command]] = frozenset({Command.UPLOAD_SAMPLE})


@dataclass(frozen=True, slots=True)
class ReadingAnswered:
    proposal_id: str
    attempt: int
    reply: dict
    by: str
    handed_back: bool
    takes: ClassVar[frozenset[Command]] = frozenset({Command.UPLOAD_SAMPLE})


@dataclass(frozen=True, slots=True)
class ReadingFailed:
    proposal_id: str
    attempt: int
    state: str
    code: str | None
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class StartBuilding:
    session_id: str
    takes: ClassVar[frozenset[Command]] = _NONE


@dataclass(frozen=True, slots=True)
class SettleStep:
    proposal_id: str
    decision: str
    expected_revision: int
    by: str
    chosen_option: str | None = None
    takes: ClassVar[frozenset[Command]] = frozenset({Command.SETTLE_STEP})


@dataclass(frozen=True, slots=True)
class RecordEdit:
    session_id: str
    graph: dict
    by: str
    takes: ClassVar[frozenset[Command]] = _NONE


COMMANDS: tuple[type, ...] = (
    OpenSession, Begin, Say, AnswerTurn, Understood, AskedBack, ProviderFailed, Retry,
    DecideGoal, Revised, StoreReadback, ReadbackFailed,
    Resume, AnswerGap, PrefillGap, StorePhrasing, PhrasingFailed,
    UploadSample, SampleInspected, ReadingAnswered, ReadingFailed,
    StartBuilding, SettleStep, RecordEdit,
)
```

- [x] **Step 4: Run them to see them pass**

Run: `uv run pytest packages/mendel-authoring/tests/test_commands.py -q`
Expected: 4 passed. If `test_every_arrow_a_built_edge_names_is_taken_by_some_command` names an arrow, a built edge carries a command this list misses: add the command, not an exemption.

- [x] **Step 5: Watch the arrow guard fail**

Temporarily drop `Command.REPLY_IN_WORDS` from `Say.takes`. Expected: the arrow test FAILS naming `reply_in_words`. Restore, and add a ledger row.

- [x] **Step 6: Write the failing interpreter test**

Append to `packages/mendel-authoring/tests/test_interpret.py`:

```python
PASSING = Protocol(
    stages=(Stage(id="s", title="s"),),
    nodes=(_n("next_gap", acts=True), _n("ask", acts=True), _n("reply", waits=True),
           _n("family", acts=True, waits=True)),
    edges=(_e("next_gap", "ask", "a_gap"), _e("ask", "reply"),
           _e("reply", "family", Command.DESCRIBE.value), _e("family", "reply", "understood")),
)


def test_an_acting_node_that_does_not_wait_passes_straight_on_when_its_work_names_nothing():
    """`ask` queues the phrasing and the session goes on to the question (plan 1c)."""
    entered = []

    def enter(node):
        entered.append(node)
        return {"next_gap": "a_gap"}.get(node)

    ran = run(PASSING, "next_gap", None, enter)
    assert ran.at == "reply" and entered == ["next_gap", "ask"]


def test_an_acting_node_that_waits_still_rests_when_its_work_names_nothing():
    ran = run(PASSING, "reply", Command.DESCRIBE.value, lambda node: None)
    assert ran.at == "family"
```

Run: `uv run pytest packages/mendel-authoring/tests/test_interpret.py -q`
Expected: the first FAILS (`ran.at == "ask"`); the second passes. The existing `GATHER` protocol's `ask` both acts and waits, so 1b's tests keep their meaning.

- [x] **Step 7: Pass straight on**

In `interpret.run`, replace

```python
            outcome = enter(node.id)
            if outcome is None:
                return Ran(node.id, path)
            node = nodes[follow(protocol, node.id, outcome).target]
```

with

```python
            outcome = enter(node.id)
            if outcome is None:
                # **Work that names nothing**: a node that waits rests here (`resolve`); one that
                # does not, with one way on, goes on (`ask` queues a job and asks: plan 1c).
                if node.waits or not _one_way_on(protocol, node.id):
                    return Ran(node.id, path)
                node = nodes[follow(protocol, node.id, None).target]
            else:
                node = nodes[follow(protocol, node.id, outcome).target]
```

Update `run`'s docstring (*An acting node is entered, and its outcome names the arrow on; `None` rests there if it waits or has no single way on, and otherwise goes straight on*) and `Node.acts`'s docstring to match.

Run: `uv run pytest packages/mendel-authoring -q`
Expected: all passed.

- [x] **Step 8: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel` (the purity guards read the new module).
Expected: exit 0.

```bash
git add packages/mendel-authoring tests/fixtures/guard-ledger.md
git commit -m "feat(authoring): typed commands in the core; an acting node that does not wait passes straight on (#136)"
```

---

### Task 3: The facade

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/session.py`
- Create: `packages/mendel-api/src/mendel_api/stages/_jobs.py`
- Test: `packages/mendel-api/tests/test_authoring_facade.py`

**Interfaces:**
- Consumes: `db.transaction`, `db.in_transaction` (Task 1); `mendel_authoring.commands` (Task 2); 1b's `_dispatch`, `Ctx`, `HANDLERS`.
- Produces, in `services/session.py`:
  - `Job(name: str, args: tuple, job_id: str, queue: str, expires: float | None = None, unqueued: object | None = None)`, frozen. `unqueued` is a command performed when the queue refuses the job (`enqueue` returns `False`) or raises.
  - `Ctx` gains `jobs: list[Job]` and `queue(job) -> None`, which ignores a job id already queued in this action. `session_id` may be `None` until a recorder sets it.
  - `Performed(result: object, jobs: tuple[Job, ...] = (), queued: tuple[bool, ...] = ())`, frozen.
  - `RECORDERS: dict[type, Recorder]`, `Recorder = Callable[[Ctx, Any], object]`, and `records(kind) -> decorator`, which refuses a second recorder for one kind.
  - `perform(command, *, recorders=None) -> Performed`: refuses inside an open transaction (`RuntimeError`); opens `db.transaction()`; runs the recorder; commits; then raises `ctx.raised` if set.
  - `async act(command, *, recorders=None) -> Performed`: `perform` on a worker thread, then each job through `_enqueue`, performing `job.unqueued` for each that did not queue.
  - `take(ctx, arrow: str, **payload) -> interpret.Ran`: the arrow from where `ctx.session_id` rests, sharing `ctx` (jobs, `raised`) with every handler on the way.
  - `perform_now` and `resume` keep their 1b signatures, for 1b's tests. They gain `ctx: Ctx | None = None`, and raise `ctx.raised` only when they made the context themselves.
- Produces, in `stages/_jobs.py`: `ANSWER`, `PHRASE`, `READ_BACK`, `CHARACTERISE` (the job function names, moved from `authoring_jobs`, which re-imports them) and `turn(session_id, seq) -> Job`, `phrase(session_id, subject) -> Job`, `readback(session_id, proposal_id) -> Job`, `characterise(session_id, proposal_id, attempt, excerpt, *, unqueued, expires) -> Job`, each with the job id and queue `authoring_jobs.enqueue_*` uses today.

- [x] **Step 1: Write the failing tests**

```python
"""The facade (spec §11): one command, one transaction, jobs after the commit."""

import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from mendel_api import db
from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft
from mendel_api.services import session
from mendel_api.services.session import Job


@dataclass(frozen=True)
class Write:
    draft_id: str


@dataclass(frozen=True)
class Undo:
    draft_id: str


def _seen(draft_id: str) -> bool:
    other = db.SessionLocal()
    try:
        return other.get(PipelineDraft, draft_id) is not None
    finally:
        other.close()


def _write(ctx, cmd, *, then=None):
    with session_scope() as s:
        s.add(PipelineDraft(id=cmd.draft_id, who="t", name="t", graph={"nodes": [], "edges": []},
                            updated_at=datetime.now(UTC), goal=None, provenance={}, revision=0))
    ctx.queue(Job("noted", (cmd.draft_id,), f"noted:{cmd.draft_id}", "q",
                  unqueued=Undo(cmd.draft_id)))
    if then is not None:
        then(ctx)
    return "written"


def _undo(ctx, cmd):
    with session_scope() as s:
        s.delete(s.get(PipelineDraft, cmd.draft_id))


@pytest.fixture
def draft_id():
    i = secrets.token_hex(8)
    yield i
    with session_scope() as s:
        if (row := s.get(PipelineDraft, i)) is not None:
            s.delete(row)


def test_a_command_commits_once_and_hands_back_its_jobs_unqueued(draft_id):
    done = session.perform(Write(draft_id), recorders={Write: _write})
    assert done.result == "written" and _seen(draft_id)
    assert [j.job_id for j in done.jobs] == [f"noted:{draft_id}"] and done.queued == ()


def test_a_recorder_that_raises_leaves_nothing_and_queues_nothing(draft_id):
    def broke(ctx):
        raise RuntimeError("after the write")

    with pytest.raises(RuntimeError):
        session.perform(Write(draft_id), recorders={Write: lambda c, m: _write(c, m, then=broke)})
    assert not _seen(draft_id)


def test_an_exception_handed_back_is_raised_after_the_commit(draft_id):
    """Spec §11.2: the resolver failing lands the session on `failed`, and that stands."""

    def hand_back(ctx):
        ctx.raised = LookupError("the resolver broke")

    with pytest.raises(LookupError):
        session.perform(Write(draft_id),
                        recorders={Write: lambda c, m: _write(c, m, then=hand_back)})
    assert _seen(draft_id)


def test_a_command_never_performs_another(draft_id):
    with db.transaction(), pytest.raises(RuntimeError, match="never performs another"):
        session.perform(Write(draft_id), recorders={Write: _write})


def test_jobs_are_queued_only_once_the_command_committed(draft_id, monkeypatch):
    seen_when_queued = []

    async def enqueue(job):
        seen_when_queued.append(_seen(job.args[0]))
        return True

    monkeypatch.setattr(session, "_enqueue", enqueue)
    done = asyncio.run(session.act(Write(draft_id), recorders={Write: _write}))
    assert seen_when_queued == [True] and done.queued == (True,)


def test_a_job_the_queue_refuses_performs_its_ending(draft_id, monkeypatch):
    """Review Focus 2: a reading whose job never queued ends, rather than waiting forever."""

    async def refuse(job):
        return False

    monkeypatch.setattr(session, "_enqueue", refuse)
    done = asyncio.run(session.act(Write(draft_id), recorders={Write: _write, Undo: _undo}))
    assert done.queued == (False,) and not _seen(draft_id)


def test_one_job_id_is_queued_once_per_action():
    ctx = session.Ctx("s", None)
    ctx.queue(Job("a", (), "same", "q"))
    ctx.queue(Job("a", (), "same", "q"))
    assert len(ctx.jobs) == 1


def test_a_kind_has_one_recorder():
    @session.records(Undo)
    def first(ctx, cmd):
        return None

    try:
        with pytest.raises(ValueError, match="already has a recorder"):
            session.records(Undo)(first)
    finally:
        del session.RECORDERS[Undo]
```

- [x] **Step 2: Run them to see them fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_facade.py -q`
Expected: FAIL at collection with `ImportError: cannot import name 'Job'`.

- [x] **Step 3: Write the facade**

In `services/session.py`, extend `Ctx` and add, after `resume`:

```python
@dataclass(frozen=True)
class Job:
    """One job an action wants queued once it commits. `unqueued`: a command performed when the
    queue refused it or failed, so nothing waits on a job that will never run (issue 241)."""

    name: str
    args: tuple
    job_id: str
    queue: str
    expires: float | None = None
    unqueued: object | None = None


@dataclass
class Ctx:
    """What a recorder and every handler on its way are handed: the session (`None` until a
    recorder addressed by a proposal finds it), the arrow being taken (`None` when resumed), its
    payload, an exception to raise once the action committed (`raised`), and the jobs to queue
    then."""

    session_id: str | None
    command: str | None
    payload: dict = field(default_factory=dict)
    raised: BaseException | None = None
    jobs: list[Job] = field(default_factory=list)

    def queue(self, job: Job) -> None:
        if all(j.job_id != job.job_id for j in self.jobs):
            self.jobs.append(job)


@dataclass(frozen=True)
class Performed:
    result: object
    jobs: tuple[Job, ...] = ()
    queued: tuple[bool, ...] = ()


Recorder = Callable[[Ctx, Any], object]
RECORDERS: dict[type, Recorder] = {}
"""Each command's recorder, by its type. `test_authoring_binding.py` holds this to
`mendel_authoring.commands.COMMANDS`, both ways."""


def records(kind: type) -> Callable[[Recorder], Recorder]:
    def register(recorder: Recorder) -> Recorder:
        if kind in RECORDERS:
            raise ValueError(f"{kind.__name__} already has a recorder: "
                             f"{RECORDERS[kind].__name__}")
        RECORDERS[kind] = recorder
        return recorder

    return register


def _recorded() -> dict[type, Recorder]:
    import mendel_api.stages  # noqa: F401 — importing the stage modules registers them

    return RECORDERS


def perform(command: object, *, recorders: dict[type, Recorder] | None = None) -> Performed:
    """**One command, one transaction** (spec §11.2). The recorder records what arrived and takes
    its arrows (`take`); an exception rolls all of it back; `ctx.raised` is raised only once the
    action committed. The jobs come back unqueued: `act` queues them."""
    if db.in_transaction():
        raise RuntimeError("a command never performs another: take its arrow (`take`)")
    bound = _recorded() if recorders is None else recorders
    ctx = Ctx(getattr(command, "session_id", None), None)
    with db.transaction():
        result = bound[type(command)](ctx, command)
    if ctx.raised is not None:
        raise ctx.raised
    return Performed(result, tuple(ctx.jobs))


async def act(command: object, *, recorders: dict[type, Recorder] | None = None) -> Performed:
    """`perform` off the event loop, then its jobs queued: **after the commit**, so a job never
    reads what is not saved, nor runs for an action that rolled back."""
    from starlette.concurrency import run_in_threadpool

    done = await run_in_threadpool(lambda: perform(command, recorders=recorders))
    queued = []
    for job in done.jobs:
        ok = await _enqueue(job)
        if not ok and job.unqueued is not None:
            await run_in_threadpool(lambda j=job: perform(j.unqueued, recorders=recorders))
        queued.append(ok)
    return replace(done, queued=tuple(queued))


async def _enqueue(job: Job) -> bool:
    """The queue's seam. `False` when the queue refused the id or could not be reached."""
    try:
        return await jobs.enqueue(job.name, *job.args, job_id=job.job_id, queue=job.queue,
                                  expires=job.expires)
    except Exception:
        log.exception("queueing %s failed", job.job_id)
        return False


def take(ctx: Ctx, arrow: str, *, protocol: Protocol = PROTOCOL, **payload: object) -> interpret.Ran:
    """Inside a recorder: take `arrow` from where `ctx.session_id` rests, every handler on the way
    sharing `ctx`."""
    ctx.command, ctx.payload = arrow, dict(payload)
    return _dispatch(ctx.session_id, arrow, payload, protocol, None, ctx=ctx)
```

Change `_dispatch` to take `ctx: Ctx | None = None`. When it is `None`, make one as 1b did, and raise `ctx.raised` at the end as 1b did. When it is given, leave `ctx.raised` for `perform`. Pass `ctx` through `perform_now` and `resume`. Add imports: `import logging`, `from dataclasses import replace`, `from typing import Any`, `from mendel_api import db, jobs`, and `log = logging.getLogger(__name__)`.

Write `stages/_jobs.py`. Copy the four job names from `authoring_jobs.py`, and the job ids, queues and `expires` from its `enqueue_turn`, `enqueue_phrasing` (one job per subject; the read-back keyed on the pending card's id) and `enqueue_characterise`:

```python
"""The builder's jobs, as an action asks for them (spec §11.2): built here, queued by the facade
after the commit. `authoring_jobs` runs them; it imports their names from here."""

from mendel_api import jobs
from mendel_api.services.session import Job

ANSWER = "answer_authoring_turn"
PHRASE = "phrase_authoring_gap"
READ_BACK = "read_back_authoring_goal"
CHARACTERISE = "characterise_sample"


def turn(session_id: str, seq: int) -> Job:
    return Job(ANSWER, (session_id, seq), jobs.job_id_for("builder", "turn", session_id, str(seq)),
               jobs.AI_QUEUE)


def phrase(session_id: str, subject: str) -> Job:
    return Job(PHRASE, (session_id, subject),
               jobs.job_id_for("builder", "phrase", session_id, subject), jobs.AI_QUEUE)


def readback(session_id: str, proposal_id: str) -> Job:
    return Job(READ_BACK, (session_id,),
               jobs.job_id_for("builder", "readback", session_id, proposal_id), jobs.AI_QUEUE)


def characterise(session_id: str, proposal_id: str, attempt: int, excerpt, *, unqueued,
                 expires: float) -> Job:
    from mendel_api.services import characterise as ch

    return Job(
        CHARACTERISE,
        (session_id, proposal_id, attempt, ch.Sealed(excerpt.text), excerpt.binary_before),
        jobs.job_id_for("builder", "characterise", proposal_id, str(attempt)),
        jobs.AI_QUEUE,
        expires=expires,
        unqueued=unqueued,
    )
```

In `authoring_jobs.py`, replace the four name constants with `from mendel_api.stages._jobs import ANSWER, CHARACTERISE, PHRASE, READ_BACK`. `BUILD` stays there: it is Spawn's job.

- [x] **Step 4: Run the facade and 1b's dispatcher tests**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_facade.py packages/mendel-api/tests/test_authoring_dispatch.py -q`
Expected: all passed. 1b's dispatch tests are unchanged.

- [x] **Step 5: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`
Expected: exit 0.

```bash
git add packages/mendel-api
git commit -m "feat(authoring): the facade — perform in one transaction, act queues after the commit (#136)"
```

---

### Task 4: Stage ① — describing, and retry

**Files:**
- Create: `packages/mendel-api/src/mendel_api/stages/_rows.py`
- Modify: `packages/mendel-api/src/mendel_api/stages/describe.py`
- Modify: `packages/mendel-api/src/mendel_api/services/session.py` (the read model)
- Modify: `packages/mendel-authoring/src/mendel_authoring/protocol.py` (`family` acts), `docs/design/diagrams/` (regenerated)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py` (code out; forwarding in)
- Modify: `packages/mendel-api/tests/test_authoring_binding.py` (the phase-writer guard's file set)
- Test: `packages/mendel-api/tests/test_authoring_commands.py`

**Interfaces:**
- Consumes: `session.records`, `session.take`, `Ctx.queue` (Task 3); `_jobs.turn` (Task 3); commands `OpenSession`, `Begin`, `Say`, `AnswerTurn`, `Understood`, `AskedBack`, `ProviderFailed`, `Retry` (Task 2).
- Produces:
  - `stages/_rows.py`: `now()`, `new_id()`, `next_seq(db, session_id)`, `swap(db, session_id, version, **values)`, `engine_turn(session_id, blocks)`, `note(session_id, text, *, code)`, `say_engine(session_id, text)`, `propose(session_id, *, kind, payload, turn_id=None)`, `settlement(proposal_id, decision, expected_revision)`, `decide(proposal_id, decision, *, expected_revision, by, chosen_option=None)`, `pending_of(db, session_id)`, `store_goal(session_id, goal)`, and the proposal kinds `GOAL`, `GAP`, `STEP`. These are moved verbatim from `authoring._now`, `_id`, `_next_seq`, `_swap`, `_engine_turn`, `_note`, `_say`, `propose`, `_settlement`, `decide`, `store_goal`, `GOAL`, `GAP` and `STEP`. `pending_of` is the pending-proposal `select` repeated across the file. **`store_goal` and the kinds live here because gathering, the card and building all write or read them**, and Task 5 (gathering) lands before Task 6 (the card).
  - `stages/describe.py`: recorders for the eight commands, and handlers `read_goal` (as in 1b) and `family` (new); `READS = ("turn_context",)`; `turn_context`, `TurnContext`, `UNTITLED`.
  - Results: `OpenSession` → the session id; `Begin` → `(session_id, seq)`; `Say` → the pending turn's seq; `AnswerTurn` → `bool`; `Retry` → `(Phase, seq | None)`; the job commands → `None`.

- [x] **Step 1: Write the failing tests**

```python
"""The commands, through the facade (plan 1c): what each records, and the jobs it asks for."""

import pytest
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import session
from mendel_api.stages import _jobs
from mendel_authoring import commands as c
from mendel_authoring.interpret import Refused
from sqlalchemy import text


@pytest.fixture(autouse=True)
def empty():
    with session_scope() as db:
        db.execute(text("TRUNCATE TABLE pipeline_authoring_proposal, pipeline_authoring_turn, "
                        "pipeline_authoring_session, pipeline_draft"))


def _at(sid):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        return row.at, row.row_version


def test_beginning_queues_the_reading_of_what_you_said_after_the_commit():
    done = session.perform(c.Begin("gene counts from paired reads", "build", "t"))
    sid, seq = done.result
    assert _at(sid)[0] == "family"
    assert [j.job_id for j in done.jobs] == [_jobs.turn(sid, seq).job_id]


def test_a_chat_turn_queues_its_answer_and_moves_nothing():
    sid, _ = session.perform(c.Begin("x", "build", "t")).result
    before = _at(sid)
    done = session.perform(c.Say(sid, "and another thing"))
    assert _at(sid) == before
    assert [j.job_id for j in done.jobs] == [_jobs.turn(sid, done.result).job_id]


def test_retry_into_understanding_writes_a_turn_and_queues_it():
    sid, _ = session.perform(c.Begin("x", "build", "t")).result
    session.perform(c.ProviderFailed(sid))
    done = session.perform(c.Retry(sid))
    phase, seq = done.result
    assert phase is Phase.UNDERSTANDING and seq is not None
    assert [j.job_id for j in done.jobs] == [_jobs.turn(sid, seq).job_id]


def test_a_late_reading_is_refused_and_writes_nothing():
    """Spec §8: the model's reading for a session that moved on is ignored."""
    sid, _ = session.perform(c.Begin("x", "build", "t")).result
    session.perform(c.ProviderFailed(sid))
    before = _at(sid)
    with pytest.raises(Refused):
        session.perform(c.Understood(sid, {"want": ["counts.gene"]}))
    assert _at(sid) == before
```

- [x] **Step 2: Run them to see them fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_commands.py -q`
Expected: FAIL with `KeyError: <class 'mendel_authoring.commands.Begin'>` (no recorder yet).

- [x] **Step 3: Move the shared rows**

Create `stages/_rows.py`. Move the functions listed under Produces verbatim, renamed as listed. In `services/authoring.py`, import them back under their old names (`from mendel_api.stages._rows import now as _now, new_id as _id, …`), so every caller still in that file is unchanged. `propose` and `decide` keep their public names in `authoring`.

- [x] **Step 4: Move stage ①**

Move from `services/authoring.py` into `stages/describe.py`, verbatim: `open_session`, `UNTITLED`, `begin`, `say`, `answer`, `TurnContext`, `turn_context`, `_spoken`. Then register their recorders:

```python
@records(c.OpenSession)
def _open(ctx: Ctx, cmd: c.OpenSession) -> str:
    ctx.session_id = open_session(cmd.draft_id, mode=Mode(cmd.mode), who=cmd.who)
    return ctx.session_id


@records(c.Begin)
def _begin(ctx: Ctx, cmd: c.Begin) -> tuple[str, int]:
    from mendel_api.services import drafts

    ctx.session_id = open_session(drafts.create(DraftGraph(), UNTITLED, cmd.who),
                                  mode=Mode(cmd.mode), who=cmd.who)
    return ctx.session_id, _said(ctx, cmd.prompt)


@records(c.Say)
def _say(ctx: Ctx, cmd: c.Say) -> int:
    return _said(ctx, cmd.text)


def _said(ctx: Ctx, text: str) -> int:
    """Record the words and the pending turn that will answer them (`say`). **Typed words are a
    command only where the diagram draws one** (14.7.8.1): what you want at `say` (`family`
    queues its reading), an answer at `reply` (`suggest` queues it). Anywhere else they are a chat
    turn, which moves nothing, and its answer is queued here."""
    seq = record_said(ctx.session_id, text)
    for typed in (Command.DESCRIBE, Command.REPLY_IN_WORDS):
        if session.allows(ctx.session_id, typed.value):
            session.take(ctx, typed.value)
            return seq
    ctx.queue(_jobs.turn(ctx.session_id, seq))
    return seq
```

`record_said(session_id, text) -> int` is today's `say` body with its trailing `for typed …` loop removed, returning `seq + 1`.

```python
@records(c.AnswerTurn)
def _answer_turn(ctx: Ctx, cmd: c.AnswerTurn) -> bool:
    return answer(cmd.session_id, cmd.seq, blocks=cmd.blocks, base_revision=cmd.base_revision,
                  invocation_id=cmd.invocation_id)


@records(c.Understood)
def _understood(ctx: Ctx, cmd: c.Understood) -> None:
    session.take(ctx, Command.UNDERSTOOD.value, goal=cmd.goal)


@records(c.AskedBack)
def _asked_back(ctx: Ctx, cmd: c.AskedBack) -> None:
    session.take(ctx, Command.ASKED_BACK.value)


@records(c.ProviderFailed)
def _provider_failed(ctx: Ctx, cmd: c.ProviderFailed) -> None:
    session.take(ctx, Command.PROVIDER_FAILED.value)


@records(c.Retry)
def _retry(ctx: Ctx, cmd: c.Retry) -> tuple[Phase, int | None]:
    """Leave `failed` for whichever phase failed (`retry`). Into understanding, `family` writes
    the new pending turn and queues it: **a new turn rather than re-opening the failed one**,
    whose notice is the record that the call failed."""
    session.take(ctx, Command.RETRY.value)
    phase = session.current_phase(ctx.session_id)
    return phase, ctx.payload.get("seq")


@handles("family")
def family(ctx: Ctx) -> None:
    """The model reads what was said (ruling 5 of plan 1c). `describe` wrote the pending turn;
    `retry` writes a new one here. On `revised` the job reading the correction answers inline."""
    if ctx.command == Command.REVISED.value:
        return None
    seq = pending_turn(ctx.session_id) if ctx.command == Command.RETRY.value else newest_pending(
        ctx.session_id)
    ctx.payload["seq"] = seq
    ctx.queue(_jobs.turn(ctx.session_id, seq))
    return None
```

`pending_turn(session_id) -> int` is the turn-writing block of today's `retry` (after its `perform_now`), returning `seq`. `newest_pending(session_id) -> int` selects the highest `seq` of an assistant turn in state `pending`. `family` returns `None`: it waits. Mark `family` acting in `protocol.py` with `acts=True` (it already `waits`), and regenerate the diagram page with `uv run python tools/generate_protocol_doc.py`. Leave `revised`'s handling in place; Task 6 adds its recorder.

**The read model moves into `services/session.py` now**, since every later task's tests read through it: `read`, `_words_coming`, `calls`, `pending_id` and `current_phase`, verbatim. `read`'s helpers (`_placement`, `_answer_of`, `_aged`, `_reading`) have not moved yet. Import them inside `read` from `mendel_api.services.authoring` until their own tasks (5, 7, 8) move them, and switch the import in each of those tasks. A function-level import is what keeps this from being circular.

- [x] **Step 5: Forward the old names**

In `services/authoring.py`, each moved public function becomes one line, for Tasks 5–9 (ruling 9):

```python
def open_session(draft_id: str, *, mode: Mode, who: str) -> str:
    return session_mod.perform(c.OpenSession(draft_id, mode.value, who)).result


def begin(prompt: str, *, mode: Mode, who: str) -> tuple[str, int]:
    return session_mod.perform(c.Begin(prompt, mode.value, who)).result


def say(session_id: str, text: str) -> int:
    return session_mod.perform(c.Say(session_id, text)).result


def answer(session_id, seq, *, blocks, base_revision, invocation_id=None) -> bool:
    return session_mod.perform(
        c.AnswerTurn(session_id, seq, blocks, base_revision, invocation_id)).result


def retry(session_id: str) -> tuple[Phase, int | None]:
    return session_mod.perform(c.Retry(session_id)).result


read, calls = session_mod.read, session_mod.calls
current_phase, pending_id = session_mod.current_phase, session_mod.pending_id
turn_context = describe.turn_context
UNTITLED = describe.UNTITLED
```

`authoring_jobs._perform(session_id, command, **payload)` keeps calling `perform_now` until Task 9.

- [x] **Step 6: Update the phase-writer guard**

`open_session`'s constructor now writes `phase=` from `stages/describe.py`. In `test_only_the_dispatcher_writes_the_phase`, the expected file set becomes `{"services/session.py", "services/authoring.py", "stages/describe.py"}`, with exactly one writer in `services/authoring.py` (`move`'s `.values()`). Run it once before the edit and watch it fail naming `stages/describe.py`.

- [x] **Step 7: Run the stage, then everything once**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_commands.py -q`
Expected: 4 passed.

Run the whole suite once, collecting every failure in one run:
`MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api -q -p no:randomly > .superpowers/sdd/1c-task4.log 2>&1; tail -30 .superpowers/sdd/1c-task4.log`
Expected: all passed. A failure here is a behaviour that relied on a write committing on its own. Name it in the ledger, find its cause, and fix it in the moved code, never in the test. Two causes to look for first:
- **A stale attribute.** One transaction shares one identity map, and a row loaded before the dispatcher's `update()` may still show the old phase. SQLAlchemy 2's `synchronize_session="auto"` normally keeps it current; where it does not, `db.expire_all()` at the top of the reading scope is the fix, recorded as a ruling.
- **`RuntimeError: a command never performs another`.** Code still in `services/authoring.py` called a forwarding function from inside a recorder. Call the stage's function instead.

- [x] **Step 8: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`
Expected: exit 0.

```bash
git add packages/mendel-api packages/mendel-authoring tests/fixtures/guard-ledger.md
git commit -m "refactor(authoring): stage ① behind the facade — saying it, the model's reading, retry; family queues the reading (#136)"
```

---

### Task 5: Stage ② — gathering

**Files:**
- Modify: `stages/gathering.py`, `services/authoring.py`, `protocol.py` (`ask`, `suggest` act), `services/authoring_jobs.py` (the end-of-turn prefetch removed, ruling 6)
- Modify: `packages/mendel-api/tests/test_authoring_gathering.py`: its six `monkeypatch.setattr(authoring, "_model_configured", …)` become `monkeypatch.setattr(gathering, "_model_configured", …)`, importing `from mendel_api.stages import gathering`. This is the only edit.
- Test: `packages/mendel-api/tests/test_authoring_commands.py`

**Interfaces:**
- Consumes: `_rows.*`, including `_rows.GOAL` and `_rows.store_goal` (Task 4); `describe.newest_pending` (Task 4); `_jobs.phrase`, `_jobs.turn` (Task 3).
- Produces: in `stages/gathering.py`:
  - recorders: `AnswerGap` (result `Phase`), `PrefillGap`, `StorePhrasing`, `PhrasingFailed`, `Resume` (result `interpret.Ran`);
  - handlers: `list_needs`, `next_gap`, `answered` (as in 1b), and `ask` and `suggest` (new);
  - `READS = ("to_phrase", "gap_context", "compose_goal", "as_goal", "_inspectable")`;
  - re-bound: `GAP = _rows.GAP`; moved verbatim: `UPLOAD`, `STATED_NOTE`, `READ_NOTE`, `ALREADY_NOTE`, `UNREACHABLE_ASK`, `_INPUT_OPTIONS`, `_UNSURE`, `_SOURCE`, `_NOT_GOAL`, `_inspectable`, `_answer_of`, `_gap_options`, `_gap_question`, `_gathered`, `as_goal`, `_goal_evidence`, `compose_goal`, `need_listed`, `offer_gap_or_card`, `_candidate_option`, `_prefilled`, `prefill_gap`, `_characterisable`, `_model_configured`, `_phrased`, `store_phrasing`, `phrasing_failed`, `_pending_gap`, `to_phrase`, `gap_context`, `_fact_for`.

- [x] **Step 1: Write the failing tests**

Append to `test_authoring_commands.py`:

```python
def _gathering(monkeypatch, configured=True):
    from mendel_api.stages import gathering

    monkeypatch.setattr(gathering, "_model_configured", lambda: configured)
    sid, _ = session.perform(c.Begin("gene counts", "build", "t")).result
    done = session.perform(c.Understood(sid, {"want": ["counts.gene"], "constraints": {}}))
    return sid, done


def test_offering_a_question_queues_its_phrasing_and_the_next_ones(monkeypatch):
    """Review Focus 5 (ruling 6): entering `ask` queues the question on offer and the next."""
    from mendel_api.stages import gathering

    sid, done = _gathering(monkeypatch)
    wanted = {_jobs.phrase(sid, s).job_id for s in gathering.to_phrase(sid)}
    assert wanted and wanted <= {j.job_id for j in done.jobs}


def test_typed_words_on_a_question_queue_their_reading_and_move_nothing(monkeypatch):
    sid, _ = _gathering(monkeypatch)
    before = _at(sid)
    done = session.perform(c.Say(sid, "paired, 150 bp"))
    assert _at(sid) == before
    assert [j.job_id for j in done.jobs] == [_jobs.turn(sid, done.result).job_id]


def test_an_answer_and_the_next_question_are_one_transaction(monkeypatch):
    from mendel_api.stages import gathering

    sid, _ = _gathering(monkeypatch, configured=False)
    pending = session.read(sid)["pending_proposal"]
    facts = session.read(sid)["facts"]

    def broke(session_id):
        raise RuntimeError("offering the next question failed")

    monkeypatch.setattr(gathering, "offer_gap_or_card", broke)
    with pytest.raises(RuntimeError):
        session.perform(c.AnswerGap(pending["id"], "have_it", None, "t"))
    after = session.read(sid)
    assert after["pending_proposal"]["id"] == pending["id"] and after["facts"] == facts


def test_a_racing_second_answer_leaves_nothing_behind(monkeypatch):
    """Review Focus 3: the second tab's answer is refused, and its recording rolls back too."""
    from mendel_api.services import session as s

    sid, _ = _gathering(monkeypatch, configured=False)
    pending = session.read(sid)["pending_proposal"]
    facts = session.read(sid)["facts"]
    real = s._dispatch

    def moved_meanwhile(*a, **k):
        with session_scope() as db:  # another request moves the session first
            db.execute(text("UPDATE pipeline_authoring_session SET at = 'card' WHERE id = :i"),
                       {"i": sid})
        return real(*a, **k)

    monkeypatch.setattr(s, "_dispatch", moved_meanwhile)
    with pytest.raises(ValueError, match="MI0201"):
        session.perform(c.AnswerGap(pending["id"], "have_it", None, "t"))
    monkeypatch.setattr(s, "_dispatch", real)
    after = session.read(sid)
    assert after["facts"] == facts and after["pending_proposal"]["id"] == pending["id"]
```

The race test writes through a scope **joined** to the action's transaction. That makes the compare-and-swap see a node it did not read, which is the condition MI0201 refuses, and the whole action rolls back. If the dispatcher reads `at` after the patch point rather than before, adjust the patch to wrap `_where` instead, and record the ruling.

- [x] **Step 2: Run them to see them fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_commands.py -q`
Expected: the four new tests FAIL with `KeyError` for `AnswerGap`, or with no phrasing job.

- [x] **Step 3: Move stage ②**

Move the functions listed under Produces into `stages/gathering.py`, verbatim. `GAP = _rows.GAP`; `need_listed` calls `_rows.store_goal`; `offer_gap_or_card` proposes `kind=_rows.GOAL`. Then:

```python
@records(c.AnswerGap)
def _answer_gap(ctx: Ctx, cmd: c.AnswerGap) -> Phase:
    """Today's `answer_gap`, body unchanged, with `session_mod.perform_now(session_id,
    Command.ANSWER_GAP.value, answered=kind_of)` becoming
    `session.take(ctx, Command.ANSWER_GAP.value, answered=kind_of)`, after
    `ctx.session_id = proposal.session_id`."""


@records(c.PrefillGap)
def _prefill(ctx: Ctx, cmd: c.PrefillGap) -> None:
    prefill_gap(cmd.proposal_id, cmd.option, cmd.value, note=cmd.note)


@records(c.StorePhrasing)
def _store_phrasing(ctx: Ctx, cmd: c.StorePhrasing) -> None:
    store_phrasing(cmd.session_id, cmd.subject, AskedGap.model_validate(cmd.asked))


@records(c.PhrasingFailed)
def _phrasing_failed(ctx: Ctx, cmd: c.PhrasingFailed) -> None:
    phrasing_failed(cmd.session_id, cmd.subject)


@records(c.Resume)
def _resume(ctx: Ctx, cmd: c.Resume) -> interpret.Ran:
    return session.resume(cmd.session_id, ctx=ctx)


@handles("ask")
def ask(ctx: Ctx) -> None:
    """The question on offer and the next, phrased while the person reads (#167, #186; ruling 6
    of plan 1c). Passes straight through to `reply`."""
    queue_phrasing(ctx)
    return None


@handles("suggest")
def suggest(ctx: Ctx) -> None:
    """Typed words answering a question: the model reads them into a suggestion (#171). The turn
    `Say` wrote is queued. Passes straight back to `reply`."""
    ctx.queue(_jobs.turn(ctx.session_id, describe.newest_pending(ctx.session_id)))
    return None


def queue_phrasing(ctx: Ctx) -> None:
    for subject in to_phrase(ctx.session_id):
        ctx.queue(_jobs.phrase(ctx.session_id, subject))
```

The `_answer_gap` body is the whole of today's `answer_gap`, not the docstring shown. Copy it and make the two named substitutions; the docstring above only says what changes. `_say` becomes `_rows.say_engine`. Mark `ask` and `suggest` `acts=True` in `protocol.py`, and regenerate the diagram page.

In `authoring_jobs.answer_authoring_turn`, delete the trailing `if authoring.current_phase(session_id) is Phase.GATHERING: await enqueue_phrasing(session_id)` (ruling 6). `enqueue_phrasing` stays until Task 9; the routes still call it.

- [x] **Step 4: Forward the old names**

```python
def answer_gap(proposal_id: str, option: str, value, *, by: str) -> Phase:
    return session_mod.perform(c.AnswerGap(proposal_id, option, value, by)).result


def prefill_gap(proposal_id: str, option: str, value, *, note: str) -> None:
    session_mod.perform(c.PrefillGap(proposal_id, option, value, note))


def store_phrasing(session_id: str, subject: str, asked) -> None:
    session_mod.perform(c.StorePhrasing(session_id, subject, asked.model_dump(mode="json")))


def phrasing_failed(session_id: str, subject: str) -> None:
    session_mod.perform(c.PhrasingFailed(session_id, subject))


def offer_next_gap(session_id: str) -> str | None:
    ran = session_mod.perform(c.Resume(session_id)).result
    return session_mod.pending_id(session_id) if ran.at in {"reply", "card"} else None
```

The remaining gathering names (`GAP`, `UPLOAD`, `READ_NOTE`, `compose_goal`, `as_goal`, `to_phrase`, `gap_context`, `_gap_options`, `_inspectable`, `characterised`'s helper `_characterisable`, `need_listed`, `offer_gap_or_card`) are re-bound: `GAP = gathering.GAP`, and so on.

- [x] **Step 5: Fix the monkeypatches that follow the move**

Edit `test_authoring_gathering.py` as the Files block says. Run it and watch it pass.

- [x] **Step 6: Run everything once**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api -q > .superpowers/sdd/1c-task5.log 2>&1; tail -30 .superpowers/sdd/1c-task5.log`
Expected: all passed. A test asserting the end-of-turn phrasing enqueue (ruling 6) is a behaviour change. Rule on it in the ledger before touching it.

- [x] **Step 7: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`
Expected: exit 0.

```bash
git add packages docs/design/diagrams
git commit -m "refactor(authoring): stage ② behind the facade — an answer and the next question in one transaction; ask and suggest queue (#136)"
```

---

### Task 6: Stage ③ — the goal card

**Files:**
- Create: `packages/mendel-api/src/mendel_api/stages/goal.py`
- Modify: `stages/__init__.py` (imports `goal`), `services/authoring.py`, `services/authoring_jobs.py` (`_follow_up` only), `packages/mendel-authoring/src/mendel_authoring/protocol.py` (`readback` acts)
- Test: `packages/mendel-api/tests/test_authoring_commands.py`

**Interfaces:**
- Consumes: `_rows.settlement`, `_rows.decide`, `_rows.store_goal`, `_rows.GOAL` (Task 4); the `AnswerGap` recorder (Task 5); `_jobs.readback` (Task 3).
- Produces: in `stages/goal.py`, recorders for `DecideGoal` (result `(Settlement, Phase)`), `Revised`, `StoreReadback` and `ReadbackFailed`; handler `readback`; `READS = ("wants_readback", "readback_context")`; re-bound `GOAL = _rows.GOAL` and `store_goal = _rows.store_goal`; moved verbatim: `withdraw_pending`, `wants_readback`, `readback_context`, `_pending_card`, `_set_card`, `store_readback`, `readback_failed`.

- [x] **Step 1: Write the failing tests**

Append to `test_authoring_commands.py`:

```python
def _to_card(monkeypatch):
    """Answer every question until the card is on offer. Returns the session, the card, and the
    last answer's `Performed` (whose action offered the card)."""
    from mendel_api.stages import gathering

    monkeypatch.setattr(gathering, "_model_configured", lambda: True)
    sid, _ = session.perform(c.Begin("gene counts", "build", "t")).result
    session.perform(c.Understood(sid, {"want": ["counts.gene"], "constraints": {}}))
    done = None
    while (pending := session.read(sid)["pending_proposal"])["kind"] == "gap":
        option = "have_it" if "have_it" in pending["payload"]["options"] else "not_sure"
        done = session.perform(c.AnswerGap(pending["id"], option, None, "t"))
    assert pending["kind"] == "goal" and done is not None
    return sid, pending, done


def test_the_card_offered_queues_its_read_back(monkeypatch):
    sid, card, done = _to_card(monkeypatch)
    assert _jobs.readback(sid, card["id"]).job_id in [j.job_id for j in done.jobs]


def test_accepting_the_goal_is_one_transaction(monkeypatch):
    """If storing the goal breaks, the card is still pending: the decision rolled back with it."""
    from mendel_api.stages import goal

    sid, card, _ = _to_card(monkeypatch)
    revision = session.read(sid)["revision"]

    def broke(*a, **k):
        raise RuntimeError("store failed")

    monkeypatch.setattr(goal, "store_goal", broke)
    with pytest.raises(RuntimeError):
        session.perform(c.DecideGoal(card["id"], "accepted", revision, "t"))
    assert session.read(sid)["pending_proposal"]["id"] == card["id"]
```

- [x] **Step 2: Run them to see them fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_commands.py -q -k "card or goal"`
Expected: the read-back test FAILS (no `readback` job: `readback` does not act yet), and the transaction test FAILS with `KeyError` for `DecideGoal`.

- [x] **Step 3: Move stage ③**

Move into `stages/goal.py` the functions under Produces, verbatim, and re-bind `GOAL` and `store_goal` from `_rows`. The decide recorder calls `store_goal` through this module's name, so the transaction test's monkeypatch reaches it. Then:

```python
@records(c.DecideGoal)
def _decide_goal(ctx: Ctx, cmd: c.DecideGoal) -> tuple[st.Settlement, Phase]:
    """Accept or reject the card (`decide_goal`): its own refusal first (a duplicate is MI0203,
    an old picture MI0201), then the diagram, then the decision, the goal and the move, **in one
    transaction**."""
    decision = ProposalState(cmd.decision)
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, cmd.proposal_id)
        if row is None:
            raise KeyError(cmd.proposal_id)
        ctx.session_id, goal = row.session_id, row.payload.get("goal")
    accepted = decision is ProposalState.ACCEPTED
    if cmd.edited is not None and accepted:
        edited = Goal.model_validate(cmd.edited)
        authoring_ai.admit_goal(edited, registry.stack())
        goal = edited.model_dump(mode="json")
    arrow = Command.CONFIRM_GOAL if accepted else Command.REVISE_GOAL
    if _rows.settlement(cmd.proposal_id, decision, cmd.expected_revision).refusal is None:
        session.check(ctx.session_id, arrow.value)
    outcome = _rows.decide(cmd.proposal_id, decision, expected_revision=cmd.expected_revision,
                           by=cmd.by)
    if outcome.refusal is not None:
        return outcome, session.current_phase(ctx.session_id)
    if accepted:
        store_goal(ctx.session_id, goal)
    session.take(ctx, arrow.value)
    return outcome, session.current_phase(ctx.session_id)


@records(c.Revised)
def _revised(ctx: Ctx, cmd: c.Revised) -> None:
    """A correction in words on the card: the card is withdrawn and the model reads the new
    words. **Only where the diagram still draws it** (final review of 1b): checked first, so a
    card accepted meanwhile withdraws nothing."""
    session.check(cmd.session_id, Command.REVISED.value)
    withdraw_pending(cmd.session_id, by=cmd.by)
    session.take(ctx, Command.REVISED.value)


@records(c.StoreReadback)
def _store_readback(ctx: Ctx, cmd: c.StoreReadback) -> None:
    store_readback(cmd.session_id, cmd.text)


@records(c.ReadbackFailed)
def _readback_failed(ctx: Ctx, cmd: c.ReadbackFailed) -> None:
    readback_failed(cmd.session_id)


@handles("readback")
def readback(ctx: Ctx) -> None:
    """The card on offer is read back in the model's words, once per card (#176). Passes
    straight through to `card`."""
    if wants_readback(ctx.session_id):
        ctx.queue(_jobs.readback(ctx.session_id, session.pending_id(ctx.session_id) or ""))
    return None
```

Mark `readback` `acts=True` in `protocol.py`. Its single unnamed arrow stays the way straight through, so the validator's "at most one way straight through" holds. Regenerate the diagram page with `uv run python tools/generate_protocol_doc.py`.

In `authoring_jobs._follow_up`, replace the three lines `authoring.withdraw_pending(...)`, `_perform(session_id, Command.REVISED)` with `_perform_typed(c.Revised(session_id, "person"))`. Here `_perform_typed(command)` is `session.perform(command)`, ignoring `Refused` exactly as `_perform` does, and returning whether it ran. Keep the `allows` check that guards the branch.

- [x] **Step 4: Forward the old names**

```python
def decide_goal(proposal_id, decision, *, expected_revision, by, edited=None):
    return session_mod.perform(c.DecideGoal(
        proposal_id, decision.value, expected_revision, by,
        None if edited is None else edited.model_dump(mode="json"))).result


GOAL = goal.GOAL
store_goal, withdraw_pending = goal.store_goal, goal.withdraw_pending
store_readback, readback_failed = goal.store_readback, goal.readback_failed
wants_readback, readback_context = goal.wants_readback, goal.readback_context
```

- [x] **Step 5: Run the whole suite once**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api -q > .superpowers/sdd/1c-task6.log 2>&1; tail -30 .superpowers/sdd/1c-task6.log`
Expected: all passed.

- [x] **Step 6: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`
Expected: exit 0.

```bash
git add packages docs/design/diagrams
git commit -m "refactor(authoring): stage ③ behind the facade — the card in one transaction; readback queues the read-back (#136)"
```

---

### Task 7: Stage ②a — a sample

**Files:**
- Modify: `stages/samples.py`, `services/authoring.py`, `services/characterise.py` (its `authoring.` calls become commands and `samples` reads)
- Test: `packages/mendel-api/tests/test_authoring_commands.py`

**Interfaces:**
- Consumes: `gathering.GAP`, `gathering.UPLOAD`, `gathering._inspectable`, `gathering.queue_phrasing` (Task 5); `_jobs.characterise` (Task 3); `inspect.inspect_sample`, `characterise.available`, `characterise.excerpt`.
- Produces: in `stages/samples.py`:
  - recorders: `UploadSample` (result `Uploaded`, below), `SampleInspected` (result `SampleAnswer`), `ReadingAnswered` (result `SampleAnswer | None`), `ReadingFailed`;
  - the handler `upload`, as in 1b;
  - `READS = ("reading_of", "reading_open", "check_sample_question")`;
  - moved verbatim: `SampleAnswer`, `_counts`, `_sample_refusal`, `check_sample_question`, `_Found`, `_record_found`, `STALE_AFTER`, `_reading`, `_aged`, `_set_reading`, `reading_of`, `start_reading`, `reading_failed`, `end_hand_back`, `reading_open`.
  - `Uploaded(NamedTuple)`: `inspection: Inspection`, `answer: SampleAnswer | None` (`None` while the AI reads), `reading: bool`.

- [x] **Step 1: Write the failing tests**

Append to `test_authoring_commands.py`:

```python
def _sample_question(monkeypatch):
    """A session on the first question that takes a sample, the AI allowed to read one: with the
    characteriser available, every input question offers an upload."""
    from mendel_api.services import characterise
    from mendel_api.stages import gathering

    monkeypatch.setattr(characterise, "available", lambda: True)
    sid, _ = _gathering(monkeypatch, configured=False)
    while gathering.UPLOAD not in (pending := session.read(sid)["pending_proposal"])["payload"].get(
        "options", {}
    ):
        assert pending["kind"] == "gap", "no question takes a sample"
        option = "have_it" if "have_it" in pending["payload"]["options"] else "not_sure"
        session.perform(c.AnswerGap(pending["id"], option, None, "t"))
    return sid, pending


def test_a_sample_nothing_reads_starts_a_reading_with_an_ending_if_unqueued(monkeypatch):
    sid, pending = _sample_question(monkeypatch)
    done = session.perform(c.UploadSample(
        sid, pending["id"], (("notes.txt", b"just words, nothing reads this\n" * 40),), "t"))
    assert done.result.reading
    [job] = done.jobs
    assert job.name == _jobs.CHARACTERISE
    assert isinstance(job.unqueued, c.ReadingFailed) and job.unqueued.code == "MA0007"


def test_a_reading_whose_job_never_queued_ends_as_no_answer(monkeypatch):
    """Review Focus 2."""
    import asyncio

    from mendel_api.stages import samples

    sid, pending = _sample_question(monkeypatch)

    async def refuse(job):
        return False

    monkeypatch.setattr(session, "_enqueue", refuse)
    asyncio.run(session.act(c.UploadSample(
        sid, pending["id"], (("notes.txt", b"just words, nothing reads this\n" * 40),), "t")))
    assert samples.reading_of(pending["id"]).state == "no_answer"
```

- [x] **Step 2: Run them to see them fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_commands.py -q -k "sample or reading"`
Expected: FAIL with `KeyError` for `UploadSample`.

- [x] **Step 3: Move stage ②a, and the route's sequence into the recorder**

Move the functions listed under Produces into `stages/samples.py`, verbatim. `_pin_proposals_session` goes, because the recorders below call `session.pin` directly. `_sample_moves` becomes:

```python
def _moves(ctx: Ctx, answered: bool) -> None:
    """A sample's way out of section ②a: on to the next question, or staying on this one. **The
    session moved on meanwhile** (spec §8): what it measured stands, and nothing moves — the
    refusal is swallowed inside its own savepoint (Task 1)."""
    with contextlib.suppress(Refused):
        session.take(ctx, Command.UPLOAD_SAMPLE.value, answered=answered)
```

`record_inspection(ctx, proposal_id, inspection, *, by) -> SampleAnswer` is today's `answer_with_sample` with three changes:
- `ctx` comes first;
- `ctx.session_id = proposal.session_id`;
- it ends with `_moves(ctx, answered)`, then, when `recorded` and not `answered`, `gathering.queue_phrasing(ctx)`, which is the route's `enqueue_phrasing` after a sample that stays (ruling 6).

`record_reading(ctx, proposal_id, attempt, reply, *, by, handed_back)` is today's `answer_with_reading`, changed the same way.

```python
@records(c.SampleInspected)
def _inspected(ctx: Ctx, cmd: c.SampleInspected) -> SampleAnswer:
    return record_inspection(ctx, cmd.proposal_id, Inspection.model_validate(cmd.inspection),
                             by=cmd.by)


@records(c.ReadingAnswered)
def _read(ctx: Ctx, cmd: c.ReadingAnswered) -> SampleAnswer | None:
    reply = CharacteriseReply.model_validate(cmd.reply)  # mendel_api.authoring.types
    return record_reading(ctx, cmd.proposal_id, cmd.attempt, reply, by=cmd.by,
                          handed_back=cmd.handed_back)


@records(c.ReadingFailed)
def _reading_failed(ctx: Ctx, cmd: c.ReadingFailed) -> None:
    reading_failed(cmd.proposal_id, cmd.attempt, cmd.state, cmd.code)


@records(c.UploadSample)
def _upload(ctx: Ctx, cmd: c.UploadSample) -> Uploaded:
    """The route's sequence, unchanged, inside one action (ruling 8 of plan 1c): refused before a
    byte is inspected (issue 226); a hand-back claims the file by the recorded type only; a type
    nothing here reads is read by the AI, its job ending the reading if it never queues."""
    from mendel_api.services import characterise, inspect, registry

    check_sample_question(cmd.proposal_id)
    reading = reading_of(cmd.proposal_id)
    claimed = reading.type_id if reading is not None and reading.state == "hand_back" else None
    inspection = inspect.inspect_sample(list(cmd.files), registry.stack(), claimed)
    if claimed is not None:
        end_hand_back(cmd.proposal_id, confirmed=inspection.outcome == "measured")
    if inspection.outcome == "no_inspector" and claimed is None and characterise.available():
        found = characterise.excerpt(cmd.files[0][1])
        if found is not None:
            attempt = start_reading(cmd.proposal_id)
            ctx.queue(_jobs.characterise(
                cmd.session_id, cmd.proposal_id, attempt, found, expires=STALE_AFTER,
                unqueued=c.ReadingFailed(cmd.proposal_id, attempt, "no_answer", "MA0007")))
            return Uploaded(inspection, None, True)
    return Uploaded(inspection, record_inspection(ctx, cmd.proposal_id, inspection, by=cmd.by),
                    False)
```

`CharacteriseReply` is `mendel_api.authoring.types.CharacteriseReply`, the type of `authoring_ai.characterise(...).reply`. Its `model_dump(mode="json")` must round-trip through `model_validate`. If it does not (a validator that rejects its own dump), record the ruling and pass the fields `record_reading` reads (`type_id`, `states`, `measurements`).

In `services/characterise.py`:
- `authoring.reading_open` becomes `samples.reading_open`;
- `authoring._inspectable` becomes `gathering._inspectable`;
- `authoring.reading_failed(p, a, s, code)` becomes `session.perform(c.ReadingFailed(p, a, s, code))`;
- `authoring.answer_with_reading(...)` becomes `session.perform(c.ReadingAnswered(proposal_id, attempt, second.reply.model_dump(mode="json"), identity.default_author(), handed))`.

- [x] **Step 4: Forward the old names**

```python
def answer_with_sample(proposal_id: str, inspection, *, by: str):
    return session_mod.perform(
        c.SampleInspected(proposal_id, inspection.model_dump(mode="json"), by)).result


def answer_with_reading(proposal_id, attempt, reply, *, by, handed_back):
    return session_mod.perform(c.ReadingAnswered(
        proposal_id, attempt, reply.model_dump(mode="json"), by, handed_back)).result


def reading_failed(proposal_id, attempt, state, code) -> None:
    session_mod.perform(c.ReadingFailed(proposal_id, attempt, state, code))
```

The read and setup names (`reading_of`, `start_reading`, `check_sample_question`, `end_hand_back`, `reading_open`, `STALE_AFTER`, `SampleAnswer`) are re-bound to `samples`. The route keeps its own sequence until Task 9.

- [x] **Step 5: Run everything once**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api -q > .superpowers/sdd/1c-task7.log 2>&1; tail -30 .superpowers/sdd/1c-task7.log`
Expected: all passed. `test_authoring_upload_route.py` patches `authoring.answer_with_sample` and `authoring.read` on the route's path, and the route still calls those names, so it holds until Task 9.

- [x] **Step 6: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`
Expected: exit 0.

```bash
git add packages
git commit -m "refactor(authoring): stage ②a behind the facade — an upload is one action; a reading never queued ends (#136)"
```

---

### Task 8: Stage ④ — what part 3 keeps, and Spawn fenced off

**Files:**
- Modify: `stages/building.py`, `services/authoring.py`
- Create: `packages/mendel-api/src/mendel_api/services/spawn.py`
- Modify: `services/authoring_jobs.py` (`build_authoring_blueprint` calls `spawn`)
- Test: `packages/mendel-api/tests/test_authoring_commands.py`

**Interfaces:**
- Consumes: `_rows.*` (Task 4); `gathering.as_goal` (Task 5).
- Produces, in `stages/building.py` (the functions part 3 calls):
  - `STEP`, `StepOutcome`, `ResolverFailed`, `pending_step_tier`, `unbuildable(unroutable) -> str` (was `_unbuildable`);
  - `resolve_blueprint(session_id, *, client=None) -> str` (was `build_blueprint`): `"stored"` or `"cant_build"`, or it raises `ResolverFailed`;
  - `offer_step(db, session_id, blueprint, node_id, *, revision, registry) -> str` (was `_offer`);
  - `commit_step(db, proposal, draft, blueprint, node, *, option, by, registry) -> None`: the accept branch of `settle_step` (`bp.committed`, the draft's graph, provenance and revision, `chosen_option`);
  - `reresolve(session_id, *, node, accepted, was, goal, mode, version, revision, client=None) -> StepOutcome`: the registry-moved branch of `settle_step` (MI0206);
  - `settle(ctx, proposal_id, decision, *, expected_revision, by, chosen_option=None, client=None) -> StepOutcome`: `settle_step`'s envelope, calling the three above;
  - `start(ctx, session_id, *, client=None) -> str | None` (was `start_building`): the MI0200 guard, then `session.resume(session_id, ctx=ctx)`;
  - `record_edit`, `describe_edit`, `_placement`;
  - recorders for `StartBuilding` (result `str | None`), `SettleStep` (result `StepOutcome`) and `RecordEdit` (result `(int, str | None)`); handlers `resolve` and `offer`, as in 1b, now calling `resolve_blueprint` and `pending_step_tier` in this module.
- Produces, in `services/spawn.py`, moved verbatim and marked for deletion: `SPAWN_STOP`, `SpawnStop`, `spawn_forward`, `mode_of`; `start(session_id, *, client) -> str | None`, the outside-a-transaction path; and `build(session_id, client)`, which is the body of `authoring_jobs.build_authoring_blueprint`'s `try`. `spawn_forward` calls `session.perform(c.SettleStep(...))` once per step. `build` calls `building.start(session.Ctx(session_id, None), session_id, client=client)` **outside any transaction** (ruling 3), and raises `ctx.raised` itself.

- [ ] **Step 1: Write the failing tests**

Append to `test_authoring_commands.py`:

```python
def _confirmed(monkeypatch):
    from mendel_api.stages import gathering

    monkeypatch.setattr(gathering, "_model_configured", lambda: False)
    sid, _ = session.perform(c.Begin("gene counts", "build", "t")).result
    session.perform(c.Understood(sid, {"want": ["counts.gene"], "constraints": {}}))
    while (pending := session.read(sid)["pending_proposal"])["kind"] == "gap":
        option = "have_it" if "have_it" in pending["payload"]["options"] else "not_sure"
        session.perform(c.AnswerGap(pending["id"], option, None, "t"))
    session.perform(c.DecideGoal(pending["id"], "accepted", session.read(sid)["revision"], "t"))
    return sid


def test_a_resolver_failure_through_the_facade_lands_on_failed_and_stays(monkeypatch):
    """Review Focus 4: committed before it is raised."""
    from mendel_api.services import blueprint as bp

    sid = _confirmed(monkeypatch)

    def crash(*a, **k):
        raise LookupError("the resolver broke")

    monkeypatch.setattr(bp, "resolve", crash)
    with pytest.raises(LookupError):
        session.perform(c.StartBuilding(sid))
    assert _at(sid)[0] == "failed"


def test_settling_a_step_is_one_transaction(monkeypatch):
    from mendel_api.stages import building

    sid = _confirmed(monkeypatch)
    first = session.perform(c.StartBuilding(sid)).result
    revision = session.read(sid)["revision"]

    def broke(*a, **k):
        raise RuntimeError("offering the next step failed")

    monkeypatch.setattr(building, "offer_step", broke)
    with pytest.raises(RuntimeError):
        session.perform(c.SettleStep(first, "accepted", revision, "t"))
    after = session.read(sid)
    assert after["revision"] == revision and after["pending_proposal"]["id"] == first


def test_spawn_lives_in_one_file_and_no_stage_reaches_it():
    from pathlib import Path

    stages = Path(session.__file__).resolve().parents[1] / "stages"
    files = sorted(stages.glob("*.py"))
    assert files
    assert not [f.name for f in files if "spawn" in f.read_text()]
```

- [ ] **Step 2: Run them to see them fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_commands.py -q -k "resolver or settling or spawn"`
Expected: the first two FAIL with `KeyError` for `StartBuilding`. The third PASSES already. Watch it fail by adding `# spawn` to `stages/building.py`, then remove that line, and record it in the ledger.

- [ ] **Step 3: Split stage ④**

Move the functions under Produces into `stages/building.py`. `settle_step`'s body is split as named: the accept branch becomes `commit_step`, the `moved` branch after the first transaction becomes `reresolve`, and what is left is `settle`. `session_mod.check(...)` and `session_mod.perform_now(settled_in, SETTLE_STEP)` become `session.check(...)` and `session.take(ctx, Command.SETTLE_STEP.value)`. The `if not moved:` block keeps its order.

```python
@records(c.StartBuilding)
def _start(ctx: Ctx, cmd: c.StartBuilding) -> str | None:
    return start(ctx, cmd.session_id)


@records(c.SettleStep)
def _settle(ctx: Ctx, cmd: c.SettleStep) -> StepOutcome:
    return settle(ctx, cmd.proposal_id, ProposalState(cmd.decision),
                  expected_revision=cmd.expected_revision, by=cmd.by,
                  chosen_option=cmd.chosen_option)


@records(c.RecordEdit)
def _edit(ctx: Ctx, cmd: c.RecordEdit) -> tuple[int, str | None]:
    return record_edit(cmd.session_id, DraftGraph.model_validate(cmd.graph), by=cmd.by)
```

`resolve`'s handler keeps 1b's shape: `ctx.raised = failed.__cause__` on `ResolverFailed`. `perform` raises it after the commit (Task 3). In `resolve_blueprint`, the resolver now runs inside the action's transaction when it comes through the facade, and outside one for Spawn (ruling 3). The code is the same either way; its docstring's paragraph *The resolve happens outside any transaction* becomes: *Through the facade (Build) the resolver runs inside the action's transaction: it is computation, and a failure between resolving and storing leaves nothing half-written (spec §11.2). Spawn calls it outside any transaction, because its resolver may reach a model.*

Move Spawn into `services/spawn.py` with a module docstring that begins: *Deleted in part 3 of the consultant build (spec §11.1): Build/Spawn and `Mode` are retired.* In `authoring_jobs.build_authoring_blueprint`, the `try` body becomes `spawn.build(session_id, _client(authoring_ai.Purpose.TIER4))`.

- [ ] **Step 4: Forward the old names**

```python
def start_building(session_id: str, *, client=None) -> str | None:
    if client is not None:
        return spawn.start(session_id, client=client)
    return session_mod.perform(c.StartBuilding(session_id)).result


def settle_step(proposal_id, decision, *, expected_revision, by, chosen_option=None,
                client=None):
    return session_mod.perform(c.SettleStep(
        proposal_id, decision.value, expected_revision, by, chosen_option)).result


def record_edit(session_id, graph, *, by):
    return session_mod.perform(c.RecordEdit(session_id, graph.model_dump(mode="json"), by)).result


spawn_forward, SpawnStop, mode_of = spawn.spawn_forward, spawn.SpawnStop, spawn.mode_of
STEP, ResolverFailed, pending_step_tier = building.STEP, building.ResolverFailed, building.pending_step_tier
build_blueprint, describe_edit = building.resolve_blueprint, building.describe_edit
```

`spawn.start(session_id, *, client)` is the outside-a-transaction path `build` uses: `building.start(Ctx(session_id, None), session_id, client=client)`, then it raises `ctx.raised` if set.

- [ ] **Step 5: Run everything once**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api -q > .superpowers/sdd/1c-task8.log 2>&1; tail -30 .superpowers/sdd/1c-task8.log`
Expected: all passed, `test_authoring_spawn.py` included.

- [ ] **Step 6: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`, then `make verify MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel` (resolving moved).
Expected: exit 0 for both.

```bash
git add packages
git commit -m "refactor(authoring): stage ④ split — what part 3 keeps in building, Spawn fenced off in one file (#136)"
```

---

### Task 9: The routes and the jobs, on the facade only

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py`, `services/authoring_jobs.py`
- Move: `ai_for`, `characterised`, `ai_for_draft` into `services/session.py` (they are reads; the rest of the read model moved in Task 4)
- Modify: `test_authoring_routes.py`, `test_authoring_spawn.py`, `test_authoring_upload_route.py`: only their `monkeypatch.setattr(authoring_jobs, "enqueue_…")` and `monkeypatch.setattr(authoring, …)` lines, which now patch `session._enqueue` or the stage function the route reaches. No assertion changes.
- Test: `packages/mendel-api/tests/test_authoring_binding.py` (the facade guard)

**Interfaces:**
- Consumes: every recorder (Tasks 4–8); `session.act`.
- Produces: routes that call `session.act(command)` for every change and `session.read` for the view; jobs that call `session.perform(command)` for every write, through `_perform` and `_perform_typed`, both ignoring `Refused`; `authoring_jobs.enqueue_turn`, `enqueue_phrasing`, `enqueue_characterise` deleted; `enqueue_build` kept (Spawn, ruling 3).

- [ ] **Step 1: Write the failing guard**

Append to `test_authoring_binding.py`:

```python
CALLERS = ("routes/authoring.py", "services/authoring_jobs.py", "services/characterise.py")


def test_routes_and_jobs_change_a_session_only_through_the_facade():
    """Spec §11.3; ruling 2 of plan 1c: they may call `session`, `spawn` (until part 3) and a
    stage's declared `READS`; nothing else under `mendel_api.stages`, and no `authoring.`."""
    import mendel_api.stages as stages_pkg

    reads = {name for mod in ("describe", "goal", "gathering", "samples", "building")
             for name in getattr(getattr(stages_pkg, mod), "READS", ())}
    found = []
    for rel in CALLERS:
        tree = ast.parse((SRC / rel).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                owner, name = node.value.id, node.attr
                if owner == "authoring":
                    found.append(f"{rel}:{node.lineno} authoring.{name}")
                if owner in {"describe", "goal", "gathering", "samples", "building"} and (
                    name not in reads and not name.isupper()
                ):
                    found.append(f"{rel}:{node.lineno} {owner}.{name}")
    assert found == []
```

`name.isupper()` lets constants through (`GAP`, `STALE_AFTER`).

- [ ] **Step 2: Run it to see it fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_binding.py -q`
Expected: FAIL listing every `authoring.` call in the three files.

- [ ] **Step 3: Move the routes onto the facade**

Each route becomes its command through `act`. The response shapes are unchanged.

```python
async def begin(body: BeginAuthoring) -> AuthoringStarted:
    done = await session.act(c.Begin(body.prompt, body.mode.value, identity.default_author()))
    session_id, _ = done.result
    return AuthoringStarted(session=_view(session_id), queued=all(done.queued))


async def say(session_id: str, body: SayToAuthoring) -> AuthoringSaid:
    done = await session.act(c.Say(session_id, body.text))
    return AuthoringSaid(seq=done.result, queued=all(done.queued))
```

`queued=all(done.queued)` is `True` for an action that queued nothing, which matches today: the route always enqueued one turn. If a route test reads `queued=False` where no job was asked for, use `bool(done.queued) and all(done.queued)`, and record the ruling.

In `decide`:
- the GAP branch: `await session.act(c.AnswerGap(proposal_id, body.option, body.value, who))`. The `enqueue_phrasing` line goes, because `ask` queued the phrasing.
- the Spawn card branch and the GOAL branch: `await session.act(c.DecideGoal(...))`.
- the step branch: `await session.act(c.SettleStep(...))`. `spawn.spawn_forward` stays (ruling 3).

In `_after_goal`, Build calls `await session.act(c.StartBuilding(session_id))` inside the existing `try`, and Spawn calls `authoring_jobs.enqueue_build` as today. `retry` becomes `await session.act(c.Retry(session_id))`: `queued` is `all(done.queued)` when `seq` is set, otherwise it falls through to `_after_goal` as today. `edit` becomes `session.perform(c.RecordEdit(session_id, body.graph.model_dump(mode="json"), who))`; the route is sync, and an edit queues nothing.

`upload_sample` keeps its HTTP half: the protection check, `read_heads`, the file count, `_kind_in`. It then does:

```python
    done = await session.act(c.UploadSample(
        session_id, proposal_id, tuple(heads.files), identity.default_author()))
    up = done.result
    view = await run_in_threadpool(_view, session_id)
    if up.reading:
        return SampleInspected(outcome="reading", type_id=None, facts=[], reason=None,
                               steps=[*up.inspection.steps,
                                      "nothing here reads its type: the AI is reading it"],
                               recorded=[], kept=[], disagreed=[], session=view)
    return SampleInspected(outcome=up.inspection.outcome, type_id=up.inspection.type_id,
                           facts=[InspectedFactView(**f.model_dump()) for f in up.inspection.facts],
                           reason=up.inspection.reason, steps=up.inspection.steps,
                           recorded=up.answer.recorded, kept=up.answer.kept,
                           disagreed=up.answer.disagreed, session=view)
```

The early MI0205 for a non-gap proposal stays in the route, before the command. `_view`, `preview` and `list_calls` call `session.read`, `session.calls` and `session.characterised`.

- [ ] **Step 4: Move the jobs onto the facade**

In `authoring_jobs.py`:
- `authoring.answer(...)` becomes `session.perform(c.AnswerTurn(...)).result`;
- `_perform(session_id, Command.UNDERSTOOD, goal=…)` becomes `_perform_typed(c.Understood(session_id, goal))`, and likewise `AskedBack` and `ProviderFailed`;
- `authoring.store_phrasing` and `phrasing_failed` become `StorePhrasing` (`outcome.reply.model_dump(mode="json")`) and `PhrasingFailed`;
- the read-back's two writes become `StoreReadback` and `ReadbackFailed`;
- `authoring.prefill_gap` becomes `PrefillGap`;
- `authoring.reading_failed` becomes `ReadingFailed`;
- reads go to `describe.turn_context`, `gathering.gap_context`, `gathering.to_phrase`, `goal.wants_readback`, `goal.readback_context` and `session.read`.

Delete `enqueue_turn`, `enqueue_phrasing` and `enqueue_characterise`, and `_perform`, now that `_perform_typed` replaces it. Rename `_perform_typed` to `_perform`.

- [ ] **Step 5: Fix the three route tests' monkeypatches**

Each `monkeypatch.setattr(authoring_jobs, "enqueue_turn", fake)` becomes a fake `session._enqueue(job)` that records `job.name` and `job.args`, and returns what the old fake returned. Each test's assertions read what the old fake recorded, so the new fake records the same: `(session_id, seq)` for a turn. `monkeypatch.setattr(authoring_jobs, "enqueue_build", …)` stays (Spawn). In `test_authoring_upload_route.py`, `answer_with_sample` and `read` are patched where the route now reaches them: `samples.record_inspection` and `session.read`. `enqueue_characterise` is replaced by a `session._enqueue` fake. List each edited line in the ledger as `Task 9: test seam moved: <file>:<line>`.

- [ ] **Step 6: Run the guard and everything once**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api -q > .superpowers/sdd/1c-task9.log 2>&1; tail -30 .superpowers/sdd/1c-task9.log`
Expected: all passed, the facade guard included. Then watch the guard fail: add `authoring.read(session_id)` to one route, run it, see it named, and remove it. Record it in the ledger.

- [ ] **Step 7: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`, and `make client` to confirm the generated client does not change (`git status frontend/src/api` is clean).
Expected: exit 0; no client diff.

```bash
git add packages tests/fixtures/guard-ledger.md
git commit -m "refactor(authoring): the routes and jobs act only through the facade; jobs queued after the commit (#136)"
```

---

### Task 10: The tests renamed, the old file deleted

**Files:**
- Create: `packages/mendel-api/tests/authoring_setup.py`
- Modify: every test under `packages/mendel-api/tests/` that names `authoring.` (by the script)
- Delete: `packages/mendel-api/src/mendel_api/services/authoring.py`
- Modify: `test_authoring_binding.py` (recorders, the new acting nodes, the `move` guards)

**Interfaces:**
- Consumes: everything above.
- Produces: `authoring_setup.move(session_id, event, *, row_version, **values) -> Phase` (verbatim from `authoring.move`), `authoring_setup.offer_next_gap(session_id) -> str | None` and `authoring_setup.start_building(session_id) -> str | None`, each a one-line `session.perform`.

- [ ] **Step 1: Write the failing binding tests**

Replace 1b's `test_nothing_in_the_shell_moves_a_session_by_event` and `_outside_move` (now that `move` lives in the tests), and append:

```python
def test_every_command_has_one_recorder_and_every_recorder_a_command():
    from mendel_authoring.commands import COMMANDS

    bound = session._recorded()
    assert COMMANDS, "no command: the comparison would hold vacuously"
    assert set(bound) == set(COMMANDS)


def test_nothing_under_src_moves_a_session_by_event():
    """`move` is test setup (`tests/authoring_setup.py`); `forge_state.move` moves a forge
    adaptation, not a session."""
    assert [c for c in _calls("move") if not c.startswith("services/forge")] == []


def test_the_old_service_is_gone():
    assert not (SRC / "services" / "authoring.py").exists()
```

`_calls` drops its `_outside_move` filter and walks every node. `test_only_the_dispatcher_writes_the_phase` expects `{"services/session.py", "stages/describe.py"}`.

- [ ] **Step 2: Run them to see them fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_authoring_binding.py -q`
Expected: `test_the_old_service_is_gone` FAILS, and the phase-writer test FAILS naming `services/authoring.py`.

- [ ] **Step 3: Write the setup helpers**

`authoring_setup.py`: a module docstring (*Setup for the authoring tests: a session put in a phase by event, and the two resumes tests drive by hand. Nothing under `src/` may call these.*), then `move` verbatim from `services/authoring.py` with its imports, and:

```python
def offer_next_gap(session_id: str) -> str | None:
    ran = session.perform(c.Resume(session_id)).result
    return session.pending_id(session_id) if ran.at in {"reply", "card"} else None


def start_building(session_id: str, *, client=None) -> str | None:
    if client is not None:  # Spawn's path, outside any transaction (ruling 3)
        return spawn.start(session_id, client=client)
    return session.perform(c.StartBuilding(session_id)).result
```

- [ ] **Step 4: Rename the call sites by script**

Save this as `.superpowers/sdd/1c-rename.py`, in the workspace and not committed: the commit's diff is the record.

```python
"""Rewrite `authoring.<name>(...)` in the API's tests to the facade, a stage, or the setup
helpers. Call sites and imports only: an argument's source text is carried over unchanged."""

import ast
import sys
from pathlib import Path

PERFORM = {  # name -> (command, positional params in order, keyword params, how an arg is passed)
    "open_session": ("OpenSession", ["draft_id"], ["mode", "who"], {"mode": "{}.value"}),
    "begin": ("Begin", ["prompt"], ["mode", "who"], {"mode": "{}.value"}),
    "say": ("Say", ["session_id", "text"], [], {}),
    "answer": ("AnswerTurn", ["session_id", "seq"], ["blocks", "base_revision", "invocation_id"], {}),
    "retry": ("Retry", ["session_id"], [], {}),
    "decide_goal": ("DecideGoal", ["proposal_id", "decision"],
                    ["expected_revision", "by", "edited"],
                    {"decision": "{}.value", "edited": "({0} and {0}.model_dump(mode='json'))"}),
    "answer_gap": ("AnswerGap", ["proposal_id", "option", "value"], ["by"], {}),
    "prefill_gap": ("PrefillGap", ["proposal_id", "option", "value"], ["note"], {}),
    "store_phrasing": ("StorePhrasing", ["session_id", "subject", "asked"], [],
                       {"asked": "{}.model_dump(mode='json')"}),
    "phrasing_failed": ("PhrasingFailed", ["session_id", "subject"], [], {}),
    "store_readback": ("StoreReadback", ["session_id", "text"], [], {}),
    "readback_failed": ("ReadbackFailed", ["session_id"], [], {}),
    "answer_with_sample": ("SampleInspected", ["proposal_id", "inspection"], ["by"],
                           {"inspection": "{}.model_dump(mode='json')"}),
    "answer_with_reading": ("ReadingAnswered", ["proposal_id", "attempt", "reply"],
                            ["by", "handed_back"], {"reply": "{}.model_dump(mode='json')"}),
    "reading_failed": ("ReadingFailed", ["proposal_id", "attempt", "state", "code"], [], {}),
    "settle_step": ("SettleStep", ["proposal_id", "decision"],
                    ["expected_revision", "by", "chosen_option"], {"decision": "{}.value"}),
    "record_edit": ("RecordEdit", ["session_id", "graph"], ["by"],
                    {"graph": "{}.model_dump(mode='json')"}),
}
MOVED = {  # name -> new dotted owner
    "read": "session", "calls": "session", "pending_id": "session", "current_phase": "session",
    "move": "authoring_setup", "offer_next_gap": "authoring_setup",
    "start_building": "authoring_setup", "spawn_forward": "spawn", "mode_of": "spawn",
    "SpawnStop": "spawn", "propose": "_rows", "decide": "_rows",
    "start_reading": "samples", "reading_of": "samples", "check_sample_question": "samples",
    "end_hand_back": "samples", "reading_open": "samples", "STALE_AFTER": "samples",
    "SampleAnswer": "samples",
    "compose_goal": "gathering", "as_goal": "gathering", "to_phrase": "gathering",
    "gap_context": "gathering", "_gap_options": "gathering", "_inspectable": "gathering",
    "GAP": "gathering", "UPLOAD": "gathering", "READ_NOTE": "gathering",
    "STATED_NOTE": "gathering", "ALREADY_NOTE": "gathering", "UNREACHABLE_ASK": "gathering",
    "_model_configured": "gathering",
    "GOAL": "goal", "wants_readback": "goal", "readback_context": "goal",
    "store_goal": "goal", "withdraw_pending": "goal",
    "turn_context": "describe", "TurnContext": "describe", "UNTITLED": "describe",
    "STEP": "building", "ResolverFailed": "building", "StepOutcome": "building",
    "pending_step_tier": "building", "build_blueprint": "building", "describe_edit": "building",
    "ai_for": "session", "ai_for_draft": "session", "characterised": "session",
    "st": "st",
}
IMPORTS = {
    "session": "from mendel_api.services import session",
    "spawn": "from mendel_api.services import spawn",
    "authoring_setup": "import authoring_setup",
    "st": "from mendel_authoring import state as st",
    "c": "from mendel_authoring import commands as c",
    **{m: f"from mendel_api.stages import {m}"
       for m in ("_rows", "samples", "gathering", "goal", "describe", "building")},
}


def _args(src: str, call: ast.Call, positional: list[str], keywords: list[str]) -> dict[str, str]:
    seg = lambda n: ast.get_source_segment(src, n)  # noqa: E731
    got = {name: seg(a) for name, a in zip(positional + keywords, call.args)}
    got |= {k.arg: seg(k.value) for k in call.keywords}
    return got


def rewrite(path: Path) -> set[str]:
    src = path.read_text()
    tree = ast.parse(src)
    edits, needed = [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(
            node.func.value, ast.Name
        ) and node.func.value.id == "authoring" and node.func.attr in PERFORM:
            kind, pos, kw, how = PERFORM[node.func.attr]
            got = _args(src, node, pos, kw)
            unknown = sorted(set(got) - set(pos + kw))
            if unknown:
                sys.exit(f"{path}:{node.lineno}: authoring.{node.func.attr} passes {unknown}")
            parts = [how.get(n, "{}").format(got[n]) for n in pos + kw if n in got]
            new = f"session.perform(c.{kind}({', '.join(parts)})).result"
            edits.append((node, new))
            needed |= {"session", "c"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and (
            node.value.id == "authoring" and node.attr in MOVED
        ) and not any(e[0].func is node for e in edits if isinstance(e[0], ast.Call)):
            owner = MOVED[node.attr]
            edits.append((node, f"{owner}.{node.attr}" if owner != "st" else "st"))
            needed.add(owner)
    left = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name) and n.value.id == "authoring"
            and n.attr not in PERFORM and n.attr not in MOVED]
    if left:
        sys.exit(f"{path}: unmapped: {sorted({n.attr for n in left})}")
    lines = src.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    spans = sorted((offsets[n.lineno - 1] + n.col_offset,
                    offsets[n.end_lineno - 1] + n.end_col_offset, new, n.lineno)
                   for n, new in edits)
    nested = [b[3] for a, b in zip(spans, spans[1:]) if b[0] < a[1]]
    if nested:
        # An outer call's text is rebuilt from the original source, so an edit inside it would
        # be lost: those calls are rewritten by hand.
        sys.exit(f"{path}: nested rewrites at lines {nested}")
    out = src
    for start, end, new, _ in reversed(spans):
        out = out[:start] + new + out[end:]
    path.write_text(out)
    return needed


if __name__ == "__main__":
    for path in map(Path, sys.argv[1:]):
        needed = rewrite(path)
        print(path, sorted(needed))
```

Run it over the test files that name `authoring`:

```bash
grep -l "authoring\." packages/mendel-api/tests/*.py | grep -v authoring_setup | xargs uv run python .superpowers/sdd/1c-rename.py
```

Expected: each file is printed with the owners it needs. The script stops, writing nothing to that file, in two cases: a call it would rewrite holds another (`nested rewrites at lines …`), or a call passes a parameter its command does not have (`passes ['client']`). Rewrite those calls by hand, re-run the script on the file, and list each in the ledger.

Then, per file:
- replace `from mendel_api.services import authoring` (alone, or in a list) with the printed owners' lines from `IMPORTS`;
- add `from mendel_authoring import commands as c` where `c.` now appears;
- run `uv run ruff check --fix --select I,F401 packages/mendel-api/tests` to sort the imports and drop unused ones.

The forwarding functions took enums (`Mode`, `ProposalState`) and models (`Goal`, `AskedGap`, `Inspection`, `DraftGraph`), which the `how` column converts with `.value` and `.model_dump(mode='json')`. Where a test passed a plain string already, `.value` fails: fix that call by hand and list it in the ledger.

- [ ] **Step 5: Delete the old service**

```bash
git rm packages/mendel-api/src/mendel_api/services/authoring.py
grep -rn "services import authoring\b\|services\.authoring\b\|import authoring$" packages/mendel-api/src packages/mendel-api/tests tools
```

Expected: no matches outside `authoring_ai`, `authoring_jobs` and `mendel_api.authoring.types`. Fix any that remain to the owners in `MOVED`.

- [ ] **Step 6: Read the diff for assertions**

```bash
git diff -U0 -- packages/mendel-api/tests | grep -E "^[-+]\s*assert" | head -40
```

Expected: every `-assert` line has a `+assert` twin that differs only in a renamed call. Any other assertion change is a behaviour change: undo it, find the cause in the code, and fix it there.

- [ ] **Step 7: Run everything once**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api -q > .superpowers/sdd/1c-task10.log 2>&1; tail -30 .superpowers/sdd/1c-task10.log`
Expected: all passed.

- [ ] **Step 8: Watch the recorder binding fail**

Temporarily comment out `@records(c.RecordEdit)` in `stages/building.py`. Expected: `test_every_command_has_one_recorder_and_every_recorder_a_command` FAILS naming `RecordEdit`. Restore. Then temporarily drop `acts=True` from `ask` in `protocol.py`. Expected: `test_every_acting_node_has_a_handler_and_every_handler_a_node` FAILS naming `ask`. Restore. Record both in the ledger.

- [ ] **Step 9: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`, then `make verify MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`.
Expected: exit 0 for both.

```bash
git add -A packages tests/fixtures/guard-ledger.md
git commit -m "refactor(authoring): the tests call the facade and the stages; services/authoring.py deleted (#136)"
```

---

### Task 11: The docs

**Files:**
- Modify: `docs/design/authoring-protocol.md`, `ARCHITECTURE.md`, `docs/superpowers/plans/2026-10-04-consultant-1c-stage-modules-one-transaction.md` (the execution record)

- [ ] **Step 1: Find every stale sentence**

```bash
git grep -n -E "services/authoring\.py|authoring\.(say|answer_gap|decide_goal|settle_step|start_building|retry|move)\b|perform_now" -- ARCHITECTURE.md CLAUDE.md docs/design docs/handbook docs/internals
```

Expected: a list. Each line is fixed below, or left with a reason in the execution record.

- [ ] **Step 2: Write what is true now**

`docs/design/authoring-protocol.md`:
- the *session moves by it* bullet gains a sentence: *Every action is a typed command, performed in one transaction through `services/session.py`; its jobs are queued after the commit.*
- a changelog row: *2026-10-04, 14.7.8.1c: the stage modules behind one facade; one transaction per action; typed commands (spec §11).*

`ARCHITECTURE.md`, the authoring paragraph:
- `services/authoring.py` is replaced by `stages/` (one module per section, with what each holds) and `services/session.py` (the facade and the read model);
- `services/spawn.py` is marked *deleted in part 3*;
- `mendel_authoring.commands` is added to the core's list.

No counts, and no issue numbers on a task page.

- [ ] **Step 3: Fill in the execution record**

Under `## Execution record`: one bullet per task, with its commit(s) and every `Ruling:` from the ledger, each with what it costs if wrong.

- [ ] **Step 4: Check, then commit**

Run: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`
Expected: exit 0, including `doc-paths` and `doc-sizes`.

```bash
git add ARCHITECTURE.md docs
git commit -m "docs: the stage modules behind one facade, one transaction per action (#136)"
```

---

## Execution record

(Filled in as the plan executes.)
