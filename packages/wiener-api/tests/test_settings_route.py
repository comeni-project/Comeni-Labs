"""Wiener reports its own settings (spec §7)."""

from fastapi.testclient import TestClient
from wiener_api.main import create_app
from wiener_api.settings import settings


def test_running_is_reported_with_each_value(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(settings, "otlp_endpoint", "")
    body = TestClient(create_app()).get("/api/wiener/settings").json()
    assert [s["key"] for s in body["sections"]] == ["running"]
    rows = {e["setting"]["key"]: e["shown"] for e in body["sections"][0]["entries"]}
    assert rows["running.runtime"]["value"] == settings.container_profile
    assert rows["running.token"]["value"].startswith("open")
    assert rows["running.telemetry"]["value"] == "off"
    assert all(shown["locked"] for shown in rows.values())


def test_the_token_is_never_served(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "wiener-secret-token-5678")
    client = TestClient(create_app())
    answer = client.get(
        "/api/wiener/settings", headers={"Authorization": "Bearer wiener-secret-token-5678"}
    )
    assert answer.status_code == 200
    assert "wiener-secret-token-5678" not in answer.text
    assert client.get("/api/wiener/settings").status_code == 401
