"""The dispatcher (14.7.8.1): one place a session moves, read off the diagram."""

import secrets
from datetime import UTC, datetime
from pathlib import Path

import authoring_setup
import pytest
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import session
from mendel_api.services import session as facade
from mendel_authoring import commands
from mendel_authoring.interpret import Refused
from mendel_authoring.protocol import Actor, Edge, Node, Protocol, Stage
from mendel_authoring.types import Event
from sqlalchemy import text


@pytest.fixture
def sid():
    """One session on one draft, the tables emptied first (`test_authoring_service.py`'s way)."""
    with session_scope() as db:
        db.execute(text(
            "TRUNCATE TABLE pipeline_authoring_proposal, pipeline_authoring_turn, "
            "pipeline_authoring_session, pipeline_draft"
        ))
    draft_id = secrets.token_hex(16)
    with session_scope() as db:
        db.add(PipelineDraft(id=draft_id, who="tester", name="d",
                             graph={"nodes": [], "edges": []}, updated_at=datetime.now(UTC),
                             goal=None, provenance={}, revision=0))
    return facade.perform(commands.OpenSession(draft_id, "tester")).result


def _n(id, phase, **kw):
    return Node(id=id, stage="s", actor=Actor.ENGINE, label=id, phase=phase, built=True, **kw)


TOY = Protocol(
    stages=(Stage(id="s", title="s"),),
    nodes=(
        _n("say", Phase.UNDERSTANDING, waits=True),
        _n("work", Phase.GATHERING, acts=True),
        _n("card", Phase.GOAL_REVIEW, waits=True),
        _n("failed", Phase.FAILED, waits=True),
    ),
    edges=(
        Edge(source="say", target="work", on="describe", event=Event.WANT_RETURNED, built=True),
        Edge(source="work", target="card", on="done", event=Event.NOTHING_MISSING, built=True),
        Edge(source="work", target="say", on="same", event=Event.WANT_UNREACHABLE, built=True),
        Edge(source="work", target="failed", on="broke", event=Event.PROVIDER_FAILED,
             built=True),
    ),
)


def _row(sid):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        return row.at, row.phase, row.row_version, row.failed_from


def test_a_command_moves_the_session_and_the_phase_is_read_off_the_node(sid):
    seen = []

    def work(ctx):
        seen.append((ctx.command, ctx.payload))
        return "done"

    ran = session.perform_now(sid, "describe", protocol=TOY, handlers={"work": work}, said="x")
    assert ran.at == "card" and seen == [("describe", {"said": "x"})]
    at, phase, version, _ = _row(sid)
    assert (at, phase, version) == ("card", Phase.GOAL_REVIEW.value, 2)


def test_a_command_with_no_arrow_is_refused_and_nothing_moves(sid):
    with pytest.raises(Refused, match="MI0216"):
        session.perform_now(sid, "confirm_goal", protocol=TOY, handlers={})
    assert _row(sid)[:3] == ("say", Phase.UNDERSTANDING.value, 1)


def test_a_command_that_leaves_the_session_where_it_was_writes_nothing(sid):
    """Review focus 4, issue 226: the version is not moved by a command that moved nothing."""
    session.perform_now(sid, "describe", protocol=TOY, handlers={"work": lambda ctx: "same"})
    assert _row(sid)[:3] == ("say", Phase.UNDERSTANDING.value, 1)


def test_a_handler_that_raises_leaves_the_session_on_its_node(sid):
    """Spec §8."""
    def work(ctx):
        raise ValueError("no")

    with pytest.raises(ValueError, match="no"):
        session.perform_now(sid, "describe", protocol=TOY, handlers={"work": work})
    assert _row(sid)[0] == "say"


def test_a_handler_may_hand_back_an_exception_raised_once_the_session_moved(sid):
    """Review focus 5: the resolver's own failure lands on `failed`, and is raised as today."""
    def work(ctx):
        ctx.raised = RuntimeError("resolver broke")
        return "broke"

    with pytest.raises(RuntimeError, match="resolver broke"):
        session.perform_now(sid, "describe", protocol=TOY, handlers={"work": work})
    at, phase, _, failed_from = _row(sid)
    assert (at, phase, failed_from) == ("failed", "failed", Phase.UNDERSTANDING.value)


def test_a_session_moved_meanwhile_refuses_the_second_write(sid):
    """Review focus 3: the write is compare-and-swap on the node read."""
    def work(ctx):
        with session_scope() as db:
            db.get(PipelineAuthoringSession, sid).at = "card"  # another tab got there first
        return "done"

    with pytest.raises(ValueError, match="MI0201"):
        session.perform_now(sid, "describe", protocol=TOY, handlers={"work": work})


def test_resuming_enters_the_node_the_session_rests_on(sid):
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).at = "work"
    assert session.resume(sid, protocol=TOY, handlers={"work": lambda ctx: "done"}).at == "card"


def test_allows_and_check_read_the_diagram(sid):
    assert session.allows(sid, "describe", protocol=TOY)
    assert not session.allows(sid, "done", protocol=TOY)
    with pytest.raises(Refused, match="MI0216"):
        session.check(sid, "done", protocol=TOY)


# ── ① and ③ through the diagram (Task 5) ────────────────────────────────────────────────────

from mendel_api.services import authoring_jobs  # noqa: E402
from mendel_authoring.types import Command  # noqa: E402

WANT = {"want": ["counts.matrix"], "constraints": {}, "suggested": {}, "stated": []}


def test_saying_what_you_want_moves_to_where_the_model_works(sid):
    facade.perform(commands.Say(sid, "RNA-seq counts"))
    assert _row(sid)[:2] == ("family", Phase.UNDERSTANDING.value)


def test_the_models_reading_is_a_command_that_runs_to_the_first_question(sid):
    facade.perform(commands.Say(sid, "RNA-seq counts"))
    ran = session.perform_now(sid, Command.UNDERSTOOD.value, goal=WANT)
    assert ran.path[:3] == ["read_goal", "list_needs", "next_gap"]
    assert _row(sid)[:2] == ("reply", Phase.GATHERING.value)


def test_a_provider_failure_after_the_session_moved_on_is_ignored(sid):
    """Review focus 1: the job's command has no arrow from the question; nothing moves."""
    facade.perform(commands.Say(sid, "RNA-seq counts"))
    session.perform_now(sid, Command.UNDERSTOOD.value, goal=WANT)
    before = _row(sid)
    authoring_jobs._failed(sid)
    assert _row(sid) == before


# ── ② gathering and samples (Task 6) ────────────────────────────────────────────────────────


def _gathering(sid):
    facade.perform(commands.Say(sid, "RNA-seq counts"))
    session.perform_now(sid, Command.UNDERSTOOD.value, goal=WANT)


def test_an_answer_runs_through_answered_to_the_next_question(sid):
    _gathering(sid)
    pending = facade.pending_id(sid)
    options = facade.read(sid)["pending_proposal"]["payload"]["options"]
    facade.perform(commands.AnswerGap(pending, next(iter(options)), None, "tester"))
    assert _row(sid)[0] in {"reply", "card"}
    assert facade.pending_id(sid) != pending


def test_typed_words_on_a_question_leave_the_session_and_its_version(sid):
    """Review focus 4: `reply_in_words` passes through `suggest` back to `reply`."""
    _gathering(sid)
    before = _row(sid)
    facade.perform(commands.Say(sid, "I have them"))
    assert _row(sid) == before


def test_a_sample_that_answered_nothing_moves_nothing(sid):
    """Review focus 4, issue 226."""
    _gathering(sid)
    before = _row(sid)
    session.perform_now(sid, Command.UPLOAD_SAMPLE.value, answered=False)
    assert _row(sid) == before


# ── ④ and retry (Task 7) ────────────────────────────────────────────────────────────────────


def _confirmed(sid):
    from comeni_core import yaml_strict
    from mendel_authoring import state as st
    from mendel_resolver.goal import Goal

    root = Path(__file__).resolve().parents[3]
    goal = Goal.model_validate(yaml_strict.load(root / "examples" / "rnaseq-goal.yml"))
    authoring_setup.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring_setup.move(sid, st.Event.NOTHING_MISSING, row_version=2)
    authoring_setup.move(
        sid, st.Event.GOAL_ACCEPTED, row_version=3, goal=goal.model_dump(mode="json")
    )


def test_a_command_arriving_at_resolve_rests_there(sid):
    """Ruling 9: accepting a goal and building it are two calls."""
    from mendel_api.stages import building

    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).at = "card"
    calls = []

    def spy(ctx):
        calls.append(ctx.command)
        return building.resolve(ctx)

    session.perform_now(sid, Command.CONFIRM_GOAL.value,
                        handlers={**session._bound(), "resolve": spy})
    assert _row(sid)[0] == "resolve" and calls == ["confirm_goal"]


def _broken(*args, **kwargs):
    raise RuntimeError("resolver broke")


def test_a_resolver_that_crashes_lands_on_failed_and_raises(sid, monkeypatch):
    """Review focus 5."""
    from mendel_api.services import blueprint

    _confirmed(sid)
    monkeypatch.setattr(blueprint, "resolve", _broken)
    with pytest.raises(RuntimeError, match="resolver broke"):
        authoring_setup.start_building(sid)
    assert _row(sid)[:2] == ("failed", Phase.FAILED.value)


def test_retry_returns_to_the_phase_that_failed(sid, monkeypatch):
    from mendel_api.services import blueprint

    _confirmed(sid)
    monkeypatch.setattr(blueprint, "resolve", _broken)
    with pytest.raises(RuntimeError):
        authoring_setup.start_building(sid)
    phase, seq = facade.perform(commands.Retry(sid)).result
    assert (phase, seq, _row(sid)[0]) == (Phase.RESOLVING, None, "resolve")


# ── from the final review of 1b ─────────────────────────────────────────────────────────────


def test_a_resolver_refusing_with_a_value_error_still_lands_on_failed(sid, monkeypatch):
    """Final review, finding 1: `NoCandidatesError` is a `ValueError`, and is the resolver's own
    failure, not a refusal of the request: the session fails, and retry is offered."""
    from mendel_api.services import blueprint
    from mendel_resolver.ports import NoCandidatesError

    def no_candidates(*args, **kwargs):
        raise NoCandidatesError("nothing to choose from")

    _confirmed(sid)
    monkeypatch.setattr(blueprint, "resolve", no_candidates)
    with pytest.raises(NoCandidatesError):
        authoring_setup.start_building(sid)
    assert _row(sid)[:2] == ("failed", Phase.FAILED.value)


def test_a_row_from_before_at_takes_its_first_answer(sid):
    """Final review, finding 2: the node is derived before the answer is recorded, not after."""
    _gathering(sid)
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).at = None
    pending = facade.pending_id(sid)
    options = facade.read(sid)["pending_proposal"]["payload"]["options"]
    facade.perform(commands.AnswerGap(pending, next(iter(options)), None, "tester"))
    assert _row(sid)[0] in {"reply", "card"}
    assert facade.pending_id(sid) not in {None, pending}


def test_pinning_writes_the_derived_node_once(sid):
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).at = None
    before = _row(sid)
    assert session.pin(sid) == "say"
    assert _row(sid) == ("say", *before[1:])
