"""Who may submit. §12.1: Wiener executes what it is handed, so this is the trust boundary."""

import pytest
from fastapi.testclient import TestClient
from wiener_api.main import create_app, create_ingest_app
from wiener_api.settings import settings


@pytest.fixture
def guarded(monkeypatch, session):
    monkeypatch.setattr(settings, "api_token", "a-real-token")
    return TestClient(create_app())


def test_a_request_without_a_token_is_refused(guarded):
    assert guarded.get("/api/runs").status_code == 401


def test_a_wrong_token_is_refused(guarded):
    assert guarded.get("/api/runs", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_the_right_token_is_let_through(guarded):
    response = guarded.get("/api/runs", headers={"Authorization": "Bearer a-real-token"})
    assert response.status_code == 200


def test_health_needs_no_token(guarded):
    """A probe has no credential, and whether Wiener is up is not a fact worth protecting."""
    assert guarded.get("/api/health").status_code == 200


def test_submitting_a_run_is_behind_the_token(guarded):
    """**The one that matters.** Running a pipeline is running code — every other route being
    guarded would be beside the point if this one were not."""
    body = {"artifact_id": "0" * 32, "params": {}}
    assert guarded.post("/api/runs", json=body).status_code == 401


def test_the_ingest_app_does_not_read_the_token(monkeypatch, session, a_run):
    """**Nextflow cannot be given a bearer header.** Its credential is the per-run secret in
    the URL — §13.1 — and putting the API's token in front of ingest would mean either handing
    a shared secret to every head process or losing every event."""
    import json
    from pathlib import Path

    monkeypatch.setattr(settings, "api_token", "a-real-token")
    fixture = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"
    body = json.loads(fixture.read_text().splitlines()[0])

    ingest = TestClient(create_ingest_app())
    posted = ingest.post(f"/events/{a_run.id}/{a_run.ingest_secret}", json=body)
    assert posted.status_code == 204, "the head process was refused by a token it cannot send"


def test_an_unset_token_leaves_the_api_open_and_says_so(monkeypatch, session, caplog):
    """Empty means open, which is right for a laptop and wrong for anything else. The warning
    is what stops that being discovered rather than decided."""
    monkeypatch.setattr(settings, "api_token", "")
    with caplog.at_level("WARNING"):
        client = TestClient(create_app())
    assert client.get("/api/runs").status_code == 200
    assert "accepts every request" in caplog.text
