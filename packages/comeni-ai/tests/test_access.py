"""Model access configuration for hosted, self-hosted, and unconfigured deployments."""

import pytest
from comeni_ai.access import ModelAccess, NoModelError
from pydantic import ValidationError


def test_no_model_configured_is_none_rather_than_a_default() -> None:
    """A default model would make an unconfigured install quietly reach a provider."""
    assert ModelAccess.from_env({}) is None


def test_the_byo_key_lane() -> None:
    access = ModelAccess.from_env(
        {"COMENI_AI_MODEL": "anthropic/claude-x", "COMENI_AI_API_KEY": "k"}
    )
    assert access is not None
    assert access.model == "anthropic/claude-x"
    assert access.api_key == "k"
    assert access.base_url is None


def test_the_local_lane_needs_no_key() -> None:
    """Ollama and vLLM use the same access shape without requiring a credential."""
    access = ModelAccess.from_env(
        {"COMENI_AI_MODEL": "ollama/llama3", "COMENI_AI_BASE_URL": "http://localhost:11434"}
    )
    assert access is not None
    assert access.api_key is None
    assert access.base_url == "http://localhost:11434"


def test_it_is_frozen() -> None:
    """What was configured is what is used — the same argument EgressPayload makes."""
    access = ModelAccess(model="m")
    with pytest.raises(ValidationError):
        access.model = "other"


def test_a_blank_model_is_not_a_model() -> None:
    assert ModelAccess.from_env({"COMENI_AI_MODEL": "   "}) is None


def test_a_blank_key_is_no_key_rather_than_an_empty_one() -> None:
    """An empty credential looks like a credential to a provider that wanted none, which is
    the local lane's most likely misconfiguration."""
    access = ModelAccess.from_env({"COMENI_AI_MODEL": "ollama/llama3", "COMENI_AI_API_KEY": ""})
    assert access is not None
    assert access.api_key is None


def test_the_timeout_is_configurable_and_has_a_default() -> None:
    assert ModelAccess.from_env({"COMENI_AI_MODEL": "m"}).timeout_seconds == 60.0
    assert (
        ModelAccess.from_env(
            {"COMENI_AI_MODEL": "m", "COMENI_AI_TIMEOUT_SECONDS": "180"}
        ).timeout_seconds
        == 180.0
    )


def test_from_env_reads_the_mapping_it_is_given_and_not_the_process() -> None:
    """Takes a mapping so a test cannot leak the developer's own configuration into an
    assertion, and needs no monkeypatching to be honest."""
    import os

    os.environ["COMENI_AI_MODEL"] = "leaked/model"
    try:
        assert ModelAccess.from_env({}) is None
    finally:
        del os.environ["COMENI_AI_MODEL"]


def test_require_from_env_refuses_with_a_code() -> None:
    """`MA0001` must be reachable. It was declared, emitted, and unreachable for a day —
    `Client.for_env` raised it and nothing but a test ever called `Client.for_env`."""
    with pytest.raises(NoModelError) as raised:
        ModelAccess.require_from_env({})
    assert "MA0001" in str(raised.value)


def test_the_refusal_names_the_variables_to_set() -> None:
    with pytest.raises(NoModelError) as raised:
        ModelAccess.require_from_env({})
    message = str(raised.value)
    assert "COMENI_AI_MODEL" in message
    assert "COMENI_AI_API_KEY" in message
    assert "--model" in message


def test_require_from_env_returns_the_access_when_configured() -> None:
    assert ModelAccess.require_from_env({"COMENI_AI_MODEL": "m"}).model == "m"


def test_sampling_is_deterministic_by_default() -> None:
    """The package default avoids provider-specific sampling defaults."""
    assert ModelAccess(model="m").temperature == 0.0
    assert ModelAccess.from_env({"COMENI_AI_MODEL": "m"}).temperature == 0.0


def test_it_can_be_raised_deliberately() -> None:
    access = ModelAccess.from_env({"COMENI_AI_MODEL": "m", "COMENI_AI_TEMPERATURE": "0.7"})
    assert access.temperature == 0.7


def test_the_old_mendel_names_are_not_read() -> None:
    """The compatibility window closed before any release (#298): `COMENI_AI_*` only."""
    assert ModelAccess.from_env({"MENDEL_MODEL": "ollama/llama3", "MENDEL_API_KEY": "k"}) is None
    access = ModelAccess.from_env({"COMENI_AI_MODEL": "m", "MENDEL_API_KEY": "k"})
    assert access is not None and access.api_key is None


def test_a_blank_name_is_unset() -> None:
    assert ModelAccess.from_env({"COMENI_AI_MODEL": "  "}) is None


def test_the_refusal_names_the_current_spelling() -> None:
    """A refusal telling somebody to set a variable this package no longer reads first is a
    refusal that costs them a debugging session."""
    with pytest.raises(NoModelError) as raised:
        ModelAccess.require_from_env({})
    assert "COMENI_AI_MODEL" in str(raised.value)
    assert "MENDEL_MODEL" not in str(raised.value)
