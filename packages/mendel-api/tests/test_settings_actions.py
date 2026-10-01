"""Record actions: test a connection, list its models (spec §6)."""

import httpx
import pytest
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services import probe


@pytest.fixture
def client(settings_in_memory):
    settings_in_memory.rows["models.connections"] = [
        {"name": "Local", "server": "ollama", "endpoint": "http://ollama:11434", "key": None},
        {"name": "Cloud", "server": "hosted", "endpoint": "", "key": None},
    ]
    return TestClient(create_app())


def test_test_reports_a_listening_endpoint(client, monkeypatch):
    async def listening(base_url):
        return base_url == "http://ollama:11434"

    monkeypatch.setattr(probe, "answers", listening)
    body = client.post("/api/settings/models.connections/items/Local/test").json()
    assert body["ok"] is True and "answer" in body["says"]


def test_a_hosted_provider_is_not_probed(client):
    body = client.post("/api/settings/models.connections/items/Cloud/test").json()
    assert body["ok"] is None and "not probed" in body["says"]


def test_models_are_listed_with_the_prefix_their_server_needs(client, monkeypatch):
    def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "qwen2.5:7b"}, {"id": "gemma3:4b"}]})

    monkeypatch.setattr(probe, "TRANSPORT", httpx.MockTransport(handler))
    body = client.post("/api/settings/models.connections/items/Local/models").json()
    assert body["values"] == ["ollama_chat/gemma3:4b", "ollama_chat/qwen2.5:7b"]


def test_an_endpoint_that_hangs_answers_not_ok(client, monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    monkeypatch.setattr(probe, "TRANSPORT", httpx.MockTransport(handler))
    body = client.post("/api/settings/models.connections/items/Local/models").json()
    assert body["ok"] is False and body["values"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/api/settings/models.nothing/items/Local/test",
        "/api/settings/models.connections/items/Nowhere/test",
        "/api/settings/models.connections/items/Local/explode",
    ],
)
def test_unknown_setting_record_or_action_is_404(client, path):
    assert client.post(path).status_code == 404


def test_an_endpoint_written_with_v1_is_not_doubled_and_the_key_is_sent(monkeypatch):
    """Review M2, re-graded: vLLM and LM Studio endpoints are usually written with /v1."""
    seen = {}

    def handler(request):
        seen["path"], seen["auth"] = request.url.path, request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"id": "qwen"}]})

    monkeypatch.setattr(probe, "TRANSPORT", httpx.MockTransport(handler))
    listed = probe.listed("http://vllm:8000/v1/", "openai_compatible", "sk-v")
    body = __import__("asyncio").run(listed)
    assert body == ["openai/qwen"] and seen == {"path": "/v1/models", "auth": "Bearer sk-v"}
