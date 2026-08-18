"""The queue's controls, over HTTP.

What is tested here is the wiring and the refusals — the filtering, ordering and grouping
have their own tests, without HTTP.
"""

from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services.queue import QueueResponse


def _client(monkeypatch, seen: list):
    def read(**kw):
        seen.append(kw)
        return QueueResponse(questions=[], total=0)

    monkeypatch.setattr("mendel_api.routes.questions.queue_read", read)
    return TestClient(create_app(), raise_server_exceptions=False)


def test_no_parameters_means_the_designed_defaults(monkeypatch):
    """Consequence order, collapsed by question, everything, no filter. A curator who opens
    the queue and touches nothing is looking at the design's screen."""
    seen: list = []
    assert _client(monkeypatch, seen).get("/api/questions").status_code == 200
    assert seen[0]["band"] is None
    assert seen[0]["group"].value == "question"
    assert seen[0]["sort"].value == "consequence"
    assert seen[0]["since_last_visit"] is False


def test_each_control_reaches_the_service(monkeypatch):
    seen: list = []
    r = _client(monkeypatch, seen).get(
        "/api/questions?band=cosmetic&group=module&sort=recent&since_last_visit=true"
    )
    assert r.status_code == 200
    assert seen[0]["band"].value == "cosmetic"
    assert seen[0]["group"].value == "module"
    assert seen[0]["sort"].value == "recent"
    assert seen[0]["since_last_visit"] is True


def test_a_value_that_is_not_a_control_is_refused_rather_than_defaulted(monkeypatch):
    """`?sort=recency` must fail loudly. Falling back to the default would give a curator a
    screen that is not the one their URL describes, and the URL is what they send to
    somebody else."""
    seen: list = []
    r = _client(monkeypatch, seen).get("/api/questions?sort=recency")
    assert r.status_code == 422
    assert seen == []


def test_marking_a_visit_returns_when(monkeypatch):
    monkeypatch.setattr("mendel_api.routes.questions.mark_visited", lambda who: __import__(
        "datetime").datetime(2026, 8, 19, tzinfo=__import__("datetime").UTC))
    r = TestClient(create_app()).post("/api/visits", json={})
    assert r.status_code == 200
    assert r.json()["seen_at"].startswith("2026-08-19")
