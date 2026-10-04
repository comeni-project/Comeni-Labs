"""A reading on a question (14.7.7): started, waited on, refused while out, aged, offered."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from comeni_ai import Client, ModelAccess, ModelUnavailableError
from mendel_api.authoring.types import CharacteriseReply, ReadMeasurement, StateRead
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal
from mendel_api.services import authoring, characterise, protection
from test_authoring_samples import (  # noqa: F401
    _database_is_reachable,
    _gathering,
    _payload,
    _pending_for,
    clean,
)

pytestmark = pytest.mark.skipif(not _database_is_reachable(), reason="no database")


@pytest.fixture
def readable(monkeypatch):
    """Level 0 and a model configured: the characteriser is available."""
    monkeypatch.setattr(characterise, "available", lambda: True)
    # `conftest` switches the family step off for every test; the characteriser's two calls are
    # what is under test here, so it is switched back on (production's `0`).
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "family_step_from", 0)


def _at(subject):
    sid = _gathering(["counts.matrix"])
    return sid, _pending_for(sid, subject)


def test_an_input_nothing_reads_offers_an_upload_when_the_ai_can_read(clean, readable):  # noqa: F811
    _, pid = _at("genome.fasta")
    assert "upload" in _payload(pid)["options"]


def test_without_the_ai_an_input_nothing_reads_offers_no_upload(clean, monkeypatch):  # noqa: F811
    monkeypatch.setattr(characterise, "available", lambda: False)
    _, pid = _at("genome.fasta")
    assert "upload" not in _payload(pid)["options"]


def test_a_reading_is_pending_on_the_question_and_keeps_the_poll_running(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    assert authoring.start_reading(pid) == 1
    picture = authoring.read(sid)
    assert picture["pending_proposal"]["payload"]["block"]["reading"]["state"] == "pending"
    assert picture["usage"]["in_flight"]


def test_a_second_upload_while_one_is_read_is_refused(clean, readable):  # noqa: F811
    _, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    with pytest.raises(ValueError, match="MI0215"):
        authoring.check_sample_question(pid)


def test_a_reading_older_than_the_job_could_run_reads_as_no_answer(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, pid)
        payload = dict(row.payload)
        block = dict(payload["block"])
        old = datetime.now(UTC) - timedelta(seconds=authoring.STALE_AFTER + 1)
        block["reading"] = {**block["reading"], "started_at": old.isoformat()}
        payload["block"] = block
        row.payload = payload
    reading = authoring.read(sid)["pending_proposal"]["payload"]["block"]["reading"]
    assert reading["state"] == "no_answer"
    authoring.check_sample_question(pid)  # and the person may try again


def test_a_failed_reading_says_so_and_frees_the_question(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    authoring.reading_failed(pid, attempt, "no_answer", "MA0007")
    reading = authoring.reading_of(pid)
    assert reading.state == "no_answer" and reading.code == "MA0007"
    assert authoring.start_reading(pid) == 2


def test_a_late_failure_for_an_old_attempt_changes_nothing(clean, readable):  # noqa: F811
    _, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    authoring.reading_failed(pid, 1, "no_answer", "MA0007")
    authoring.start_reading(pid)
    authoring.reading_failed(pid, 1, "refused", "MI0204")
    assert authoring.reading_of(pid).state == "pending"


def test_available_needs_the_level_and_a_model(monkeypatch):
    import mendel_api.settings as s
    from mendel_api.services import protection

    monkeypatch.setattr(protection, "allows", lambda crossing: True)
    monkeypatch.setattr(s, "model_access", lambda *a, **k: None)
    assert not characterise.available()
    monkeypatch.setattr(s, "model_access", lambda *a, **k: object())
    assert characterise.available()
    monkeypatch.setattr(protection, "allows", lambda crossing: False)
    assert not characterise.available()




def _facts(sid):
    with session_scope() as db:
        from mendel_api.models import PipelineAuthoringSession
        return list(db.get(PipelineAuthoringSession, sid).facts)


def test_a_reading_answers_an_input_gap_and_is_marked_read_by_ai(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    answer = authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    assert answer.recorded == ["genome.fasta"]
    fact = next(f for f in _facts(sid) if f["subject"] == "genome.fasta")
    assert fact["source"] == "model_read" and fact["kind"] == "input"
    assert authoring.pending_id(sid) != pid, "the gap closed"


def test_a_reading_of_another_type_is_recorded_and_the_question_stays(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    reply = CharacteriseReply(
        type_id="alignment.bam",
        states=[StateRead(id="coordinate_sorted", evidence="SO:coordinate")],
    )
    answer = authoring.answer_with_reading(pid, attempt, reply, by="ana", handed_back=False)
    assert answer.recorded == ["alignment.bam"]
    bam = next(f for f in _facts(sid) if f["subject"] == "alignment.bam")
    assert bam["states"] == ["coordinate_sorted"] and bam["source"] == "model_read"
    assert authoring.pending_id(sid) == pid
    reading = authoring.reading_of(pid)
    assert reading.state == "read" and reading.recorded == ["alignment.bam"]


def test_the_persons_word_stands_over_a_reading(clean, readable):  # noqa: F811
    sid, pid = _at("paired")
    from mendel_api.models import PipelineAuthoringSession
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        row.facts = [*row.facts, {"kind": "measurement", "subject": "quality_encoding",
                                  "value": "phred33", "source": "person_said"}]
    attempt = authoring.start_reading(pid)
    reply = CharacteriseReply(
        type_id="fastq.reads",
        measurements=[ReadMeasurement(id="quality_encoding", value="phred64")],
    )
    answer = authoring.answer_with_reading(pid, attempt, reply, by="ana", handed_back=False)
    assert answer.disagreed == ["quality_encoding"]
    said = next(f for f in _facts(sid) if f["subject"] == "quality_encoding")
    assert said["value"] == "phred33"


def test_a_type_the_engine_reads_is_handed_back_and_nothing_is_recorded(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    before = _facts(sid)
    attempt = authoring.start_reading(pid)
    answer = authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="fastq.reads"), by="ana", handed_back=True
    )
    assert answer is not None and answer.recorded == []
    assert _facts(sid) == before
    reading = authoring.reading_of(pid)
    assert reading.state == "hand_back" and reading.type_id == "fastq.reads"


def test_a_reading_for_an_old_attempt_records_nothing(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    authoring.reading_failed(pid, 1, "no_answer", "MA0007")
    authoring.start_reading(pid)
    late = authoring.answer_with_reading(
        pid, 1, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    assert late is None and authoring.pending_id(sid) == pid


def test_a_reading_after_the_question_was_answered_by_a_click_records_nothing(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    authoring.answer_gap(pid, "have_it", None, by="ana")
    late = authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    assert late is None


class _Answers:
    def __init__(self, *bodies):
        self.bodies, self.sent = list(bodies), []

    def send(self, access, prompt):
        self.sent.append(prompt)
        body = self.bodies.pop(0)
        if isinstance(body, Exception):
            raise body
        return body


def _clients(*bodies):
    answers = _Answers(*bodies)
    client = Client(ModelAccess(model="fake/test", base_url="http://localhost:1"),
                    transport=answers)
    return (lambda purpose: client), answers


FASTA = ">chr1 a reference\n" + "ACGT" * 60 + "\n"


def _read(pid, sid, *bodies):
    client_for, answers = _clients(*bodies)
    attempt = authoring.start_reading(pid)
    state = characterise.read_sample(sid, pid, attempt, FASTA, False, client_for=client_for)
    return state, answers


def test_the_job_reads_families_then_the_type_and_records_it(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    state, answers = _read(
        pid, sid,
        json.dumps({"families": ["genome"]}),
        json.dumps({"type_id": "genome.fasta", "states": [], "measurements": [],
                    "undetermined": [], "unmatched": []}),
    )
    assert state == "read" and len(answers.sent) == 2
    assert authoring.pending_id(sid) != pid


def test_no_family_ends_as_could_not_tell_with_one_call(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    state, answers = _read(pid, sid, json.dumps({"families": []}))
    assert state == "could_not_tell" and len(answers.sent) == 1
    assert authoring.reading_of(pid).state == "could_not_tell"


def test_an_undeclared_id_ends_as_refused_with_its_code(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    _read(pid, sid, json.dumps({"families": ["variants"]}))
    reading = authoring.reading_of(pid)
    assert reading.state == "refused" and reading.code == "MI0204"


def test_a_provider_that_does_not_answer_ends_as_no_answer(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    state, _ = _read(pid, sid, ModelUnavailableError("down"))
    assert state == "no_answer" and authoring.reading_of(pid).code == "MA0007"


def test_a_type_the_engine_reads_is_handed_back(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    state, _ = _read(
        pid, sid,
        json.dumps({"families": ["fastq"]}),
        json.dumps({"type_id": "fastq.reads", "states": [], "measurements": [],
                    "undetermined": [], "unmatched": []}),
    )
    assert state == "hand_back"


def test_above_level_0_door_6_refuses_before_composing(clean, readable, monkeypatch):  # noqa: F811
    sid, pid = _at("genome.fasta")
    monkeypatch.setattr(protection, "allows", lambda crossing: False)
    state, answers = _read(pid, sid, json.dumps({"families": ["genome"]}))
    assert state == "refused" and answers.sent == []
    assert authoring.reading_of(pid).code == "MI0213"


def test_a_stale_delivery_spends_no_call(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    client_for, answers = _clients(json.dumps({"families": ["genome"]}))
    authoring.start_reading(pid)
    authoring.reading_failed(pid, 1, "no_answer", "MA0007")
    characterise.read_sample(sid, pid, 1, FASTA, False, client_for=client_for)
    assert answers.sent == []


def test_with_the_family_step_off_one_call_reads_the_type(clean, readable, monkeypatch):  # noqa: F811
    from mendel_api.settings import settings
    monkeypatch.setattr(settings, "family_step_from", 10_000)
    sid, pid = _at("genome.fasta")
    state, answers = _read(
        pid, sid,
        json.dumps({"type_id": "genome.fasta", "states": [], "measurements": [],
                    "undetermined": [], "unmatched": []}),
    )
    assert state == "read" and len(answers.sent) == 1


def test_the_job_keeps_no_result_so_the_excerpt_leaves_redis_with_it():
    from mendel_api import ai_worker
    from mendel_api.services import authoring_jobs

    [entry] = [f for f in ai_worker.AIWorkerSettings.functions
               if getattr(f, "name", None) == authoring_jobs.CHARACTERISE]
    assert entry.keep_result_s == 0 and not entry.keep_result_forever


def test_a_session_with_a_fact_read_by_ai_says_characterise_was_used(clean, readable, monkeypatch):  # noqa: F811
    """Spec §7: `Pipeline.ai` records the characteriser, for the preview and for Keep alike."""
    from comeni_core.artifact.pipeline import AiPoint
    from mendel_api.models import PipelineAuthoringSession

    monkeypatch.setenv("COMENI_AI_MODEL", "fake/test")
    sid, pid = _at("genome.fasta")
    before = authoring.ai_for_draft(authoring.read(sid)["draft_id"])
    assert AiPoint.CHARACTERISE in before.available
    assert AiPoint.CHARACTERISE not in before.used
    attempt = authoring.start_reading(pid)
    authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    with session_scope() as db:
        draft_id = db.get(PipelineAuthoringSession, sid).draft_id
    after = authoring.ai_for_draft(draft_id)
    assert AiPoint.CHARACTERISE in after.used


# ── the job against clicks, races and failures (issue 241) ────────────────────────────


def test_after_a_click_the_job_spends_no_call(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    client_for, answers = _clients(json.dumps({"families": ["genome"]}))
    attempt = authoring.start_reading(pid)
    authoring.answer_gap(pid, "have_it", None, by="ana")
    state = characterise.read_sample(sid, pid, attempt, FASTA, False, client_for=client_for)
    assert state == "stale" and answers.sent == []


def test_a_click_ends_the_reading_it_overtook(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    authoring.answer_gap(pid, "have_it", None, by="ana")
    row = next(h for h in authoring.read(sid)["history"] if h["id"] == pid)
    assert (row["block"] or {}).get("reading") is None


def test_a_reading_cannot_start_on_a_settled_question(clean, readable):  # noqa: F811
    _, pid = _at("genome.fasta")
    authoring.answer_gap(pid, "have_it", None, by="ana")
    with pytest.raises(ValueError, match="MI0203"):
        authoring.start_reading(pid)


def test_a_second_reading_cannot_start_while_one_is_out(clean, readable):  # noqa: F811
    _, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    with pytest.raises(ValueError, match="MI0215"):
        authoring.start_reading(pid)


def test_a_reading_that_answered_its_question_says_read(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    row = next(h for h in authoring.read(sid)["history"] if h["id"] == pid)
    assert row["block"]["reading"]["state"] == "read"
    assert row["block"]["reading"]["recorded"] == ["genome.fasta"]


def test_a_job_that_crashes_ends_the_reading_as_no_answer(clean, readable, monkeypatch):  # noqa: F811
    import asyncio

    from mendel_api.services import authoring_jobs

    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)

    def boom(*a, **k):
        raise RuntimeError("the database went away")

    monkeypatch.setattr(characterise, "read_sample", boom)
    asyncio.run(authoring_jobs.characterise_sample({}, sid, pid, attempt, FASTA, False))
    reading = authoring.reading_of(pid)
    assert reading.state == "no_answer" and reading.code == "MA0007"
    authoring.check_sample_question(pid)  # the person may try again at once


def test_the_excerpt_never_reaches_a_log_and_leaves_redis_with_the_reading(monkeypatch):
    import asyncio

    from mendel_api import jobs
    from mendel_api.services import authoring_jobs

    sent = {}

    async def enqueue(name, *args, **kwargs):
        sent.update(args=args, kwargs=kwargs)
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    found = characterise.Excerpt(text="@HD\tSO:coordinate PATIENT_0042", binary_before=True)
    asyncio.run(authoring_jobs.enqueue_characterise("s" * 32, "p" * 32, 1, found))
    assert "PATIENT" not in repr(sent["args"]), "ARQ logs a job's args by their repr"
    assert any(str(a) == found.text for a in sent["args"]), "the worker still gets the text"
    assert sent["kwargs"]["expires"] == authoring.STALE_AFTER


def test_the_log_says_an_answer_came_from_the_ai(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    row = next(h for h in authoring.read(sid)["history"] if h["id"] == pid)
    assert row["answer"] == "I have it · read by AI"
