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
