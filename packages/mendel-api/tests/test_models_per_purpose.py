"""Each call uses its purpose's model (spec §6)."""

import pytest
from comeni_ai import access as ai_access
from comeni_core.settings import catalogue
from mendel_api.services import authoring_ai, installation
from mendel_api.services.models import PURPOSES, where_purposes
from mendel_api.settings import model_access
from mendel_forge.workflow import InvocationPurpose


@pytest.fixture
def clean_env(monkeypatch):
    for name in (*ai_access.DEPRECATED, *ai_access.DEPRECATED.values()):
        monkeypatch.delenv(name, raising=False)
    for setting in (catalogue.DEFAULT_MODEL, *catalogue.PURPOSE_SETTINGS):
        monkeypatch.delenv(setting.env, raising=False)


def _choose(store, **purposes):
    store.rows["models.connections"] = [
        {"name": "Local", "server": "ollama", "endpoint": "http://ollama:11434", "key": None}
    ]
    for name, model in purposes.items():
        store.rows[f"models.{name}"] = {"connection": "Local", "model": model}


def test_every_call_purpose_maps_to_a_menu_purpose():
    builder = {("builder", p.value) for p in authoring_ai.Purpose}
    forge = {("forge", p.value) for p in InvocationPurpose}
    assert builder and forge, "an enum is empty — this test is measuring nothing"
    assert builder | forge == set(PURPOSES), "a call purpose has no model in Settings"


def test_a_purpose_uses_its_own_model(clean_env, settings_in_memory):
    _choose(settings_in_memory, default="ollama_chat/gemma3:12b", talk="ollama_chat/gemma3:4b")
    assert model_access("builder", "ask").model == "ollama_chat/gemma3:4b"
    assert model_access("builder", "ask").base_url == "http://ollama:11434"
    assert model_access("builder", "goal").model == "ollama_chat/gemma3:12b"


def test_a_purpose_without_its_own_model_uses_the_default(clean_env, settings_in_memory):
    _choose(settings_in_memory, default="ollama_chat/qwen2.5:7b")
    assert model_access("forge", "analysis").model == "ollama_chat/qwen2.5:7b"


def test_a_purpose_with_no_default_still_counts_as_configured(clean_env, settings_in_memory):
    _choose(settings_in_memory, talk="ollama_chat/gemma3:4b")
    assert model_access() is not None
    assert model_access("builder", "goal") is None


def test_the_env_still_configures_the_default(clean_env, monkeypatch):
    monkeypatch.setenv("COMENI_AI_MODEL", "ollama_chat/gemma3:12b")
    monkeypatch.setenv("COMENI_AI_BASE_URL", "http://ollama:11434")
    got = model_access("builder", "readback")
    assert (got.model, got.base_url) == ("ollama_chat/gemma3:12b", "http://ollama:11434")


def test_a_deprecated_name_alone_still_works(clean_env, monkeypatch):
    monkeypatch.setenv("MENDEL_MODEL", "ollama_chat/gemma3:12b")
    assert model_access().model == "ollama_chat/gemma3:12b"


def test_an_env_purpose_pin_uses_the_env_connection(clean_env, monkeypatch):
    monkeypatch.setenv("COMENI_AI_MODEL", "ollama_chat/gemma3:12b")
    monkeypatch.setenv("COMENI_AI_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("COMENI_AI_MODEL_TALK", "ollama_chat/gemma3:4b")
    got = model_access("builder", "chat")
    assert (got.model, got.base_url) == ("ollama_chat/gemma3:4b", "http://ollama:11434")


def test_a_purpose_naming_a_gone_connection_falls_back(clean_env, settings_in_memory):
    _choose(settings_in_memory, default="ollama_chat/qwen2.5:7b", talk="ollama_chat/gemma3:4b")
    settings_in_memory.rows["models.talk"] = {"connection": "Gone", "model": "x"}
    assert model_access("builder", "ask").model == "ollama_chat/qwen2.5:7b"


def test_the_builder_client_is_built_for_its_purpose(clean_env, settings_in_memory):
    from mendel_api.services import authoring_jobs

    _choose(settings_in_memory, default="ollama_chat/gemma3:12b", readback="ollama_chat/gemma3:4b")
    client = authoring_jobs._client(authoring_ai.Purpose.READBACK)
    assert client.access.model == "ollama_chat/gemma3:4b"


def test_where_each_purpose_goes(clean_env, settings_in_memory):
    _choose(settings_in_memory, default="ollama_chat/gemma3:12b")
    settings_in_memory.rows["models.connections"].append(
        {"name": "Anthropic", "server": "hosted", "endpoint": "", "key": None}
    )
    settings_in_memory.rows["models.tier4"] = {
        "connection": "Anthropic", "model": "anthropic/claude-sonnet-4-5",
    }
    rows = {r["purpose"]: r for r in where_purposes(installation.installation())}
    assert rows["Talking with you"]["goes"] == "stays on this machine or your network"
    assert rows["Choosing where the rules cannot"]["goes"] == "goes to anthropic"


def test_a_hosted_provider_from_env_is_said_to_leave(clean_env, monkeypatch):
    """Review C1: a provider configured in .env (no base URL) goes to that provider."""
    monkeypatch.setenv("COMENI_AI_MODEL", "anthropic/claude-sonnet-4-5")
    monkeypatch.setenv("COMENI_AI_API_KEY", "sk-ant-guard-0000-1111")
    rows = where_purposes(installation.installation())
    assert rows and all(r["goes"] == "goes to anthropic" for r in rows)


def test_a_connection_with_no_endpoint_is_said_to_leave(clean_env, settings_in_memory):
    """Review C1: Server left at its default, no endpoint — still a provider."""
    settings_in_memory.rows["models.connections"] = [
        {"name": "Cloud", "server": "ollama", "endpoint": "", "key": None}
    ]
    settings_in_memory.rows["models.default"] = {"connection": "Cloud", "model": "openai/gpt-x"}
    rows = where_purposes(installation.installation())
    assert all(r["goes"] == "goes to openai" for r in rows)


def test_old_names_alone_are_reported_where_they_go(clean_env, monkeypatch):
    """Review M5, re-graded: calls reach the model, so Privacy must not say nothing is sent."""
    monkeypatch.setenv("MENDEL_MODEL", "anthropic/claude-sonnet-4-5")
    rows = where_purposes(installation.installation())
    assert all(r["goes"] == "goes to anthropic" for r in rows)


def test_a_purpose_pinned_in_env_works_without_a_default(clean_env, monkeypatch):
    """Review I3: COMENI_AI_MODEL_WANT alone is honoured, not reported as a gone connection."""
    monkeypatch.setenv("COMENI_AI_MODEL_WANT", "ollama_chat/gemma3:12b")
    monkeypatch.setenv("COMENI_AI_BASE_URL", "http://ollama:11434")
    got = model_access("builder", "goal")
    assert (got.model, got.base_url) == ("ollama_chat/gemma3:12b", "http://ollama:11434")


def test_stored_keys_with_no_codec_do_not_take_the_menu_down(clean_env, settings_in_memory):
    """Review C2: keys stored, then COMENI_SETTINGS_KEY removed — no 500, no failed call."""
    settings_in_memory.rows["models.connections"] = [
        {"name": "Cloud", "server": "hosted", "endpoint": "", "key": "gAAAA-sealed"}
    ]
    settings_in_memory.rows["models.default"] = {"connection": "Cloud", "model": "openai/gpt-x"}
    inst = installation.installation()
    assert inst.codec is None
    shown = inst.shown(catalogue.CONNECTIONS).value
    assert shown[0]["key"] == {"set": False, "last4": None}
    assert model_access("builder", "goal").api_key is None


def test_a_purpose_can_go_back_to_the_default(clean_env, settings_in_memory):
    """Found executing plan 7: *Same as the default* sends null, which a model setting holds."""
    from fastapi.testclient import TestClient

    from mendel_api.main import create_app

    _choose(settings_in_memory, default="ollama_chat/qwen2.5:7b", talk="ollama_chat/gemma3:4b")
    client = TestClient(create_app())
    answer = client.put("/api/settings/models.talk", json={"value": None})
    assert answer.status_code == 200, answer.text
    assert answer.json()["value"] is None
    assert model_access("builder", "ask").model == "ollama_chat/qwen2.5:7b"
