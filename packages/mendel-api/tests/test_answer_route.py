"""The write path, over HTTP.

Three lines of route. What is tested here is the wiring and the refusal contract — the logic
has its own tests, without HTTP.
"""

from fastapi.testclient import TestClient
from mendel_api.main import create_app


def _client(monkeypatch, answer):
    monkeypatch.setattr("mendel_api.routes.questions.answer_one", answer)
    return TestClient(create_app(), raise_server_exceptions=False)


def test_answering_returns_what_is_left(monkeypatch):
    from mendel_api.services.answers import Answered

    def answer(**kw):
        return Answered(draft=kw["draft"], subject=kw["subject"], remaining=["roles"])

    r = _client(monkeypatch, answer).post("/api/questions/answer", json={
        "draft": "fastqc", "subject": "consumes[0].type_id",
        "value": "fastq.reads", "why": "it reads FASTQs",
    })
    assert r.status_code == 200
    assert r.json()["remaining"] == ["roles"]


def test_a_refusal_comes_back_as_422_with_its_code_intact(monkeypatch):
    """The forge's own transport answers 422 for a coded refusal and this must match it:
    two transports over one operation that disagree on status codes is exactly what
    the forge spent Phase 1 avoiding."""
    def refuse(**kw):
        raise ValueError("MF0003: 'nonsense' is not legal for roles")

    r = _client(monkeypatch, refuse).post("/api/questions/answer", json={
        "draft": "fastqc", "subject": "roles", "value": "nonsense", "why": "w",
    })
    assert r.status_code == 422
    assert "MF0003" in r.json()["detail"]


def test_a_missing_reason_is_refused_before_the_forge_is_called(monkeypatch):
    called = []

    def answer(**kw):
        called.append(kw)
        raise AssertionError("should not have been called")

    r = _client(monkeypatch, lambda **kw: (_ for _ in ()).throw(
        ValueError("an answer needs a reason")))
    resp = r.post("/api/questions/answer", json={
        "draft": "fastqc", "subject": "roles", "value": "x", "why": "",
    })
    assert resp.status_code == 422
    assert "reason" in resp.json()["detail"]
