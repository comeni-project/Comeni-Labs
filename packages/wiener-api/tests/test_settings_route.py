"""Wiener reports its own settings (spec §7)."""

from fastapi.testclient import TestClient
from wiener_api.main import create_app
from wiener_api.settings import settings


def test_running_is_reported_with_each_value(monkeypatch, session):
    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(settings, "otlp_endpoint", "")
    body = TestClient(create_app()).get("/api/wiener/settings").json()
    assert [s["key"] for s in body["sections"]] == ["retention_runs", "running"]
    running = next(s for s in body["sections"] if s["key"] == "running")
    rows = {e["setting"]["key"]: e["shown"] for e in running["entries"]}
    assert rows["running.runtime"]["value"] == settings.container_profile
    assert rows["running.token"]["value"].startswith("open")
    assert rows["running.telemetry"]["value"] == "off"
    assert all(shown["locked"] for shown in rows.values())


def test_the_token_is_never_served(monkeypatch, session):
    monkeypatch.setattr(settings, "api_token", "wiener-secret-token-5678")
    client = TestClient(create_app())
    answer = client.get(
        "/api/wiener/settings", headers={"Authorization": "Bearer wiener-secret-token-5678"}
    )
    assert answer.status_code == 200
    assert "wiener-secret-token-5678" not in answer.text
    assert client.get("/api/wiener/settings").status_code == 401


def _entries(client) -> dict:
    menu = client.get("/api/wiener/settings").json()
    return {e["setting"]["key"]: e for s in menu["sections"] for e in s["entries"]}


def test_a_retention_limit_is_written_and_read_back(client):
    """Part H: the operator wanted every limit on the menu, Wiener's included, and changeable."""
    answer = client.put("/api/wiener/settings/retention_runs.work_failed_days",
                        json={"value": "30"})
    assert answer.status_code == 200
    shown = _entries(client)["retention_runs.work_failed_days"]["shown"]
    assert shown["value"] == "30" and shown["locked"] is False
    client.put("/api/wiener/settings/retention_runs.work_failed_days", json={"value": "90"})
    assert _entries(client)["retention_runs.work_failed_days"]["shown"]["value"] == "90"


def test_running_stays_read_only(client):
    answer = client.put("/api/wiener/settings/running.runtime", json={"value": "x"})
    assert answer.status_code == 409


def test_a_value_the_limit_cannot_hold_is_refused(client):
    answer = client.put("/api/wiener/settings/retention_runs.runs_days", json={"value": "12"})
    assert answer.status_code == 422


def test_an_env_variable_pins_a_retention_limit(client, monkeypatch):
    monkeypatch.setenv("WIENER_RETENTION_WORK_FAILED_DAYS", "1")
    shown = _entries(client)["retention_runs.work_failed_days"]["shown"]
    assert shown["value"] == "1" and shown["locked"] and shown["reason"]["kind"] == "pinned"
