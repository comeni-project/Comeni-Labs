"""Connection setup never generates text, saves draft keys, or returns OAuth credentials."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services import chatgpt_signin, probe


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.mark.parametrize(
    "provider,endpoint,path,model,prefix",
    [
        ("openai", "https://api.openai.com/v1", "/v1/models", "test-gpt", "openai/"),
        ("openrouter", "https://openrouter.ai/api/v1/", "/api/v1/models", "lab/model", "openai/"),
        (
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "/v1beta/openai/models",
            "test-gemini",
            "openai/",
        ),
        ("anthropic", "https://api.anthropic.com", "/v1/models", "test-claude", "anthropic/"),
    ],
)
def test_discovery_preserves_provider_paths_and_auth(
    client, monkeypatch, provider, endpoint, path, model, prefix, settings_in_memory
):
    def handler(request):
        assert request.method == "GET" and request.url.path == path
        if provider == "anthropic":
            assert request.headers["x-api-key"] == "secret-test"
            assert "authorization" not in request.headers
        else:
            assert request.headers["authorization"] == "Bearer secret-test"
        return httpx.Response(200, json={"data": [{"id": model}]})

    monkeypatch.setattr(probe, "TRANSPORT", httpx.MockTransport(handler))
    response = client.post(
        "/api/settings/models/discover",
        json={"provider": provider, "server": "hosted", "endpoint": endpoint, "key": "secret-test"},
    )
    assert response.json()["values"] == [prefix + model]
    assert "secret-test" not in response.text
    assert settings_in_memory.rows == {}


def test_refused_key_has_actionable_error_without_provider_body(client, monkeypatch):
    monkeypatch.setattr(
        probe,
        "TRANSPORT",
        httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "secret-test"})),
    )
    body = client.post(
        "/api/settings/models/discover",
        json={"server": "hosted", "endpoint": "https://api.example/v1", "key": "secret-test"},
    ).json()
    assert body["ok"] is False and "key was not accepted" in body["says"]
    assert "secret-test" not in str(body)


def test_detects_only_known_local_addresses(client, monkeypatch):
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        return httpx.Response(
            200 if request.url.host == "ollama" else 404, json={"data": [{"id": "small"}]}
        )

    monkeypatch.setattr(probe, "TRANSPORT", httpx.MockTransport(handler))
    body = client.post("/api/settings/models/detect", json={"provider": "ollama"}).json()
    assert body == [{"endpoint": "http://ollama:11434", "models": ["ollama_chat/small"]}]
    assert set(hosts) == {"ollama", "host.docker.internal", "127.0.0.1"}


@pytest.mark.parametrize(
    "endpoint", ["file:///etc/passwd", "https://name:secret@example.com/v1", "no-server"]
)
def test_discovery_rejects_non_http_or_embedded_credentials(client, endpoint):
    assert (
        client.post(
            "/api/settings/models/discover", json={"server": "ollama", "endpoint": endpoint}
        ).status_code
        == 422
    )


@pytest.fixture
def auth(tmp_path, monkeypatch):
    fake = SimpleNamespace(
        token_dir=str(tmp_path),
        auth_file=str(tmp_path / "auth.json"),
        _request_device_code=lambda: {
            "device_auth_id": "private-device-id",
            "user_code": "ABCD",
            "interval": "5",
        },
        _exchange_code_for_tokens=lambda code: {
            "access_token": "private-access",
            "refresh_token": "private-refresh",
        },
        _build_auth_record=lambda tokens: tokens,
        _read_auth_file=lambda: (
            json.loads((tmp_path / "auth.json").read_text())
            if (tmp_path / "auth.json").exists()
            else None
        ),
        _is_token_expired=lambda data, token: False,
    )
    monkeypatch.setattr(chatgpt_signin, "authenticator", lambda: fake)
    return fake


def test_subscription_signin_exchanges_once_and_keeps_tokens_server_side(client, monkeypatch, auth):
    calls = []

    def handler(request):
        calls.append(request)
        assert json.loads(request.content)["device_auth_id"] == "private-device-id"
        return httpx.Response(
            200, json={"authorization_code": "private-code", "code_verifier": "private-verifier"}
        )

    monkeypatch.setattr(chatgpt_signin, "TRANSPORT", httpx.MockTransport(handler))
    assert client.get("/api/settings/models/chatgpt").json() == {"signed_in": False}
    started = client.post("/api/settings/models/chatgpt/sign-in").json()
    assert started["user_code"] == "ABCD" and "private-device-id" not in str(started)
    path = f"/api/settings/models/chatgpt/sign-in/{started['session']}"
    for _ in range(2):
        body = client.post(path).json()
        assert body == {"state": "connected"} and "private-access" not in str(body)
    assert len(calls) == 1
    assert client.get("/api/settings/models/chatgpt").json() == {"signed_in": True}
    assert json.loads(Path(auth.auth_file).read_text())["access_token"] == "private-access"
    assert os.stat(auth.auth_file).st_mode & 0o077 == 0


def test_pending_authorization_throttles_polls_and_expires(client, monkeypatch, auth):
    calls = []
    monkeypatch.setattr(
        chatgpt_signin,
        "TRANSPORT",
        httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(403)),
    )
    started = client.post("/api/settings/models/chatgpt/sign-in").json()
    path = f"/api/settings/models/chatgpt/sign-in/{started['session']}"
    assert client.post(path).json() == {"state": "pending"}
    assert client.post(path).json() == {"state": "pending"}
    assert len(calls) == 1
    monkeypatch.setattr(chatgpt_signin.time, "time", lambda: started["expires_at"] + 1)
    assert client.post(path).json() == {"state": "expired"}
    assert chatgpt_signin.poll("../../auth.json") == "expired"


def test_provider_exceptions_do_not_leak_credentials(client, monkeypatch, auth):
    def fail():
        raise RuntimeError("private-access private-refresh")

    monkeypatch.setattr(auth, "_request_device_code", fail)
    response = client.post("/api/settings/models/chatgpt/sign-in")
    assert response.status_code == 503 and "private-" not in response.text


def test_unwritable_signin_storage_is_reported_as_storage_failure(client, monkeypatch, auth):
    def fail():
        raise PermissionError("sensitive-path")

    monkeypatch.setattr(chatgpt_signin, "start", fail)
    response = client.post("/api/settings/models/chatgpt/sign-in")
    assert response.status_code == 503
    assert "folder ownership or permissions" in response.json()["detail"]
    assert "sensitive-path" not in response.text
