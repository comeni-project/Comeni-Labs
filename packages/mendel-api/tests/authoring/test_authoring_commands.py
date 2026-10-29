"""The commands, through the facade (plan 1c): what each records, and the jobs it asks for."""

import pytest
from comeni_flow.interpret import Refused
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import session
from mendel_api.stages import _jobs
from mendel_api_tests.database import truncate
from mendel_authoring import commands as c
from sqlalchemy import text


@pytest.fixture(autouse=True)
def empty():
    with session_scope() as db:
        db.execute(
            truncate(
                "TRUNCATE TABLE pipeline_authoring_proposal, pipeline_authoring_turn, "
                "pipeline_authoring_session, pipeline_draft, gate_run"
            )
        )


def _at(sid):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        return row.at, row.row_version


def test_beginning_queues_the_reading_of_what_you_said_after_the_commit():
    done = session.perform(c.Begin("gene counts from paired reads", "t"))
    sid, seq = done.result
    assert _at(sid)[0] == "family"
    assert [j.job_id for j in done.jobs] == [_jobs.turn(sid, seq).job_id]


def test_a_chat_turn_queues_its_answer_and_moves_nothing():
    sid, _ = session.perform(c.Begin("x", "t")).result
    before = _at(sid)
    done = session.perform(c.Say(sid, "and another thing"))
    assert _at(sid) == before
    assert [j.job_id for j in done.jobs] == [_jobs.turn(sid, done.result).job_id]


def test_retry_into_understanding_writes_a_turn_and_queues_it():
    sid, _ = session.perform(c.Begin("x", "t")).result
    session.perform(c.ProviderFailed(sid))
    done = session.perform(c.Retry(sid))
    phase, seq = done.result
    assert phase is Phase.UNDERSTANDING and seq is not None
    assert [j.job_id for j in done.jobs] == [_jobs.turn(sid, seq).job_id]


def test_a_late_reading_is_refused_and_writes_nothing():
    """Spec §8: the model's reading for a session that moved on is ignored."""
    sid, _ = session.perform(c.Begin("x", "t")).result
    session.perform(c.ProviderFailed(sid))
    before = _at(sid)
    with pytest.raises(Refused):
        session.perform(c.Understood(sid, {"heard": [{"kind": "want", "subject": "counts.gene"}]}))
    assert _at(sid) == before


def _gathering(monkeypatch, configured=True):
    from mendel_api.stages import gathering

    monkeypatch.setattr(gathering, "_model_configured", lambda: configured)
    sid, _ = session.perform(c.Begin("gene counts", "t")).result
    done = session.perform(
        c.Understood(sid, {"heard": [{"kind": "want", "subject": "counts.matrix"}]})
    )
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
    sid, _ = _gathering(monkeypatch, configured=False)
    pending = session.read(sid)["pending_proposal"]
    facts = session.read(sid)["facts"]
    from comeni_flow import interpret

    real = interpret.run

    def moved_meanwhile(*a, **k):
        # Between the dispatcher reading where the session rests and writing where it comes to
        # rest: another request moves it (issue 251, a named seam rather than a call count).
        ran = real(*a, **k)
        with session_scope() as db:
            db.execute(
                text("UPDATE pipeline_authoring_session SET at = 'card' WHERE id = :i"), {"i": sid}
            )
        return ran

    monkeypatch.setattr(interpret, "run", moved_meanwhile)
    with pytest.raises(ValueError, match="MI0201"):
        session.perform(c.AnswerGap(pending["id"], "have_it", None, "t"))
    monkeypatch.setattr(interpret, "run", real)
    after = session.read(sid)
    assert after["facts"] == facts and after["pending_proposal"]["id"] == pending["id"]


def _to_card(monkeypatch):
    """Answer every question until the card is on offer. Returns the session, the card, and the
    last answer's `Performed` (whose action offered the card)."""
    from mendel_api.stages import gathering

    monkeypatch.setattr(gathering, "_model_configured", lambda: True)
    sid, _ = session.perform(c.Begin("gene counts", "t")).result
    session.perform(c.Understood(sid, {"heard": [{"kind": "want", "subject": "counts.matrix"}]}))
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
    """If recording the confirmation breaks, the card is still pending: the decision rolled back
    with it. (An unedited card only records *That's right*, Part I.0 §6.2.)"""
    from mendel_api.services import decisions

    sid, card, _ = _to_card(monkeypatch)
    revision = session.read(sid)["revision"]

    def broke(*a, **k):
        raise RuntimeError("store failed")

    monkeypatch.setattr(decisions, "confirm", broke)
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
    done = session.perform(
        c.UploadSample(
            sid, pending["id"], (("notes.txt", b"just words, nothing reads this\n" * 40),), "t"
        )
    )
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
    asyncio.run(
        session.act(
            c.UploadSample(
                sid, pending["id"], (("notes.txt", b"just words, nothing reads this\n" * 40),), "t"
            )
        )
    )
    assert samples.reading_of(pending["id"]).state == "no_answer"


def _confirmed(monkeypatch):
    from mendel_api.stages import gathering

    monkeypatch.setattr(gathering, "_model_configured", lambda: False)
    sid, _ = session.perform(c.Begin("gene counts", "t")).result
    session.perform(c.Understood(sid, {"heard": [{"kind": "want", "subject": "counts.matrix"}]}))
    while (pending := session.read(sid)["pending_proposal"])["kind"] == "gap":
        options = pending["payload"]["options"]
        ordinary = [o for o in options if o not in ("dont_have", "value", "not_sure", "upload")]
        option = ordinary[0] if ordinary else "not_sure"
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

    monkeypatch.setattr(building.cards, "offer", broke)
    with pytest.raises(RuntimeError):
        session.perform(c.SettleStep(first, revision, "t"))
    after = session.read(sid)
    assert after["revision"] == revision and after["pending_proposal"]["id"] == first


def test_no_stage_mentions_spawn():
    from pathlib import Path

    stages = Path(session.__file__).resolve().parents[1] / "stages"
    files = sorted(stages.rglob("*.py"))
    assert files
    assert not [f.name for f in files if "spawn" in f.read_text()]


def test_a_sample_whose_session_moved_on_queues_no_phrasing(monkeypatch):
    """Issue 251: the arrow refused (the session moved on), so nothing is phrased for it."""
    from mendel_api import db
    from mendel_api.stages import samples

    sid, _ = _gathering(monkeypatch)
    with session_scope() as s:  # another request moved the session meanwhile
        s.execute(
            text("UPDATE pipeline_authoring_session SET at = 'card' WHERE id = :i"), {"i": sid}
        )
    ctx = session.Ctx(sid, None)
    with db.transaction():
        samples._moves(ctx, False, ["read_length"], [])
    assert ctx.jobs == []
