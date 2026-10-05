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


def test_a_jobs_commands_queue_their_jobs_once_its_work_is_done(draft_id, monkeypatch):
    """A job performs its commands as it goes (`perform`); what they asked for is queued when
    the job's work ends, after every commit, and a refused one runs its ending (plan 1c)."""
    queued = []

    async def enqueue(job):
        queued.append((job.job_id, _seen(job.args[0])))
        return False

    monkeypatch.setattr(session, "_enqueue", enqueue)

    async def job():
        async with session.queued_after(recorders={Write: _write, Undo: _undo}):
            session.perform(Write(draft_id), recorders={Write: _write})
            assert queued == []

    asyncio.run(job())
    assert queued == [(f"noted:{draft_id}", True)] and not _seen(draft_id)


def test_a_failing_ending_never_hides_the_jobs_own_error(draft_id, monkeypatch):
    """Issue 251: queuing after a job that raised must not replace its error with its own."""

    async def refuse(job):
        return False

    def ending_breaks(ctx, cmd):
        raise LookupError("the ending broke too")

    monkeypatch.setattr(session, "_enqueue", refuse)

    async def job():
        async with session.queued_after(recorders={Write: _write, Undo: ending_breaks}):
            session.perform(Write(draft_id), recorders={Write: _write})
            raise RuntimeError("the job's own failure")

    with pytest.raises(RuntimeError, match="own failure"):
        asyncio.run(job())
