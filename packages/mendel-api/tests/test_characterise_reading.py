"""A reading on a question (14.7.7): started, waited on, refused while out, aged, offered."""

from datetime import UTC, datetime, timedelta

import pytest
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal
from mendel_api.services import authoring, characterise
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
