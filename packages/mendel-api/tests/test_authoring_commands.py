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


def _gathering(monkeypatch, configured=True):
    from mendel_api.stages import gathering

    monkeypatch.setattr(gathering, "_model_configured", lambda: configured)
    sid, _ = session.perform(c.Begin("gene counts", "build", "t")).result
    done = session.perform(c.Understood(sid, {"want": ["counts.matrix"], "constraints": {}}))
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
    real = s._where
    calls = []

    def moved_meanwhile(session_id):
        read = real(session_id)
        calls.append(read)
        if len(calls) == 2:  # the dispatcher's read, after `check`'s: then another request moves it
            with session_scope() as db:
                db.execute(text("UPDATE pipeline_authoring_session SET at = 'card' WHERE id = :i"),
                           {"i": sid})
        return read

    monkeypatch.setattr(s, "_where", moved_meanwhile)
    with pytest.raises(ValueError, match="MI0201"):
        session.perform(c.AnswerGap(pending["id"], "have_it", None, "t"))
    monkeypatch.setattr(s, "_where", real)
    after = session.read(sid)
    assert after["facts"] == facts and after["pending_proposal"]["id"] == pending["id"]


def _to_card(monkeypatch):
    """Answer every question until the card is on offer. Returns the session, the card, and the
    last answer's `Performed` (whose action offered the card)."""
    from mendel_api.stages import gathering

    monkeypatch.setattr(gathering, "_model_configured", lambda: True)
    sid, _ = session.perform(c.Begin("gene counts", "build", "t")).result
    session.perform(c.Understood(sid, {"want": ["counts.matrix"], "constraints": {}}))
    done = None
    while (pending := session.read(sid)["pending_proposal"])["kind"] == "gap":
        # The first ordinary option, as `test_authoring_gathering._pending_for` answers.
        options = pending["payload"]["options"]
        ordinary = [o for o in options if o not in ("dont_have", "value", "not_sure", "upload")]
        option = ordinary[0] if ordinary else "not_sure"
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
        options = pending["payload"]["options"]
        ordinary = [o for o in options if o not in ("dont_have", "value", "not_sure", "upload")]
        option = ordinary[0] if ordinary else "not_sure"
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
