"""The dispatcher (14.7.8.1): one place a session moves, read off the diagram."""

import secrets
from datetime import UTC, datetime

import pytest
from mendel_api.authoring.types import Mode, Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import authoring, session
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
    return authoring.open_session(draft_id, mode=Mode.BUILD, who="tester")


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
