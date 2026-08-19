"""The batch and the decline, over HTTP."""

from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services.answers import AnsweredAll, Proposed, RefusedDraft


def _client(monkeypatch, **stubs):
    for name, fn in stubs.items():
        monkeypatch.setattr(f"mendel_api.routes.questions.{name}", fn)
    return TestClient(create_app(), raise_server_exceptions=False)


def test_a_partial_batch_is_a_200_that_reports_what_refused(monkeypatch):
    """**Not a 422.** The operation did what it was asked and is reporting what it found;
    a 422 would say the request was wrong, and it was not. The refusals are in the body
    with their codes intact, and the UI renders them."""
    def batch(**kw):
        return AnsweredAll(
            subject=kw["subject"], settled=["samtools-index"],
            refused=[RefusedDraft(draft="samtools-faidx", detail="MF0003: not legal")],
        )

    r = _client(monkeypatch, answer_all=batch).post("/api/questions/answer-all", json={
        "subject": "consumes[0].type_id", "value": "alignment.bam", "why": "it takes a BAM",
    })
    assert r.status_code == 200
    assert r.json()["settled"] == ["samtools-index"]
    assert "MF0003" in r.json()["refused"][0]["detail"]


def test_a_batch_with_no_reason_is_refused(monkeypatch):
    def batch(**kw):
        raise ValueError("an answer needs a reason")

    r = _client(monkeypatch, answer_all=batch).post("/api/questions/answer-all", json={
        "subject": "roles", "value": "x", "why": "",
    })
    assert r.status_code == 422
    assert "reason" in r.json()["detail"]


def test_proposing_returns_that_the_hole_is_still_open(monkeypatch):
    def propose(**kw):
        return Proposed(draft=kw["draft"], subject=kw["subject"], still_open=True)

    r = _client(monkeypatch, propose_one=propose).post("/api/questions/propose", json={
        "draft": "fastqc", "subject": "produces[0].type_id", "id": "qc.report.html",
        "description": "an HTML QC report", "why": "nothing declared fits",
    })
    assert r.status_code == 200
    assert r.json()["still_open"] is True
