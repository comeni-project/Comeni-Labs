"""The three lanes, and the invariants they carry.

Invariant 13 — self-hosted is not a degraded tier — means the lanes differ by configuration
and not by code path. Invariant 12 — no subscription OAuth — is enforced by there being
nowhere to put a subscription token.
"""

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
    """Ollama and vLLM behind an OpenAI-compatible endpoint. Invariant 13: identical path."""
    access = ModelAccess.from_env(
        {"COMENI_AI_MODEL": "ollama/llama3", "COMENI_AI_BASE_URL": "http://localhost:11434"}
    )
    assert access is not None
    assert access.api_key is None
    assert access.base_url == "http://localhost:11434"


def test_there_is_nowhere_to_put_a_subscription_token() -> None:
    """Invariant 12. Enforced by shape: a field that does not exist cannot be filled."""
    assert "oauth" not in ModelAccess.model_fields
    assert "token" not in ModelAccess.model_fields
    with pytest.raises(ValidationError):
        ModelAccess(model="m", oauth_token="whatever")


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
    """**Nothing set this until 2026-08-17**, so every call sampled at the provider's default
    and two runs of the same draft could differ. An accuracy figure compared across prompt
    designs was partly measuring the dice."""
    assert ModelAccess(model="m").temperature == 0.0
    assert ModelAccess.from_env({"COMENI_AI_MODEL": "m"}).temperature == 0.0


def test_it_can_be_raised_deliberately() -> None:
    access = ModelAccess.from_env({"COMENI_AI_MODEL": "m", "COMENI_AI_TEMPERATURE": "0.7"})
    assert access.temperature == 0.7


def test_the_deprecated_mendel_names_are_still_read() -> None:
    """The compatibility window. A deployment that has not edited its `.env` still works."""
    access = ModelAccess.from_env({"MENDEL_MODEL": "ollama/llama3", "MENDEL_API_KEY": "k"})
    assert access is not None
    assert access.model == "ollama/llama3"
    assert access.api_key == "k"


def test_the_new_name_wins_when_both_are_set() -> None:
    """The only safe direction. A half-migrated `.env` that kept the old line must not
    silently un-migrate somebody who added the new one."""
    access = ModelAccess.from_env(
        {"COMENI_AI_MODEL": "anthropic/new", "MENDEL_MODEL": "anthropic/old"}
    )
    assert access is not None
    assert access.model == "anthropic/new"


def test_an_empty_new_name_falls_through_rather_than_shadowing() -> None:
    """`COMENI_AI_API_KEY=` exported and empty is the half-migration that reads as complete.

    An empty string is not a value anywhere else in this module, and it must not become one
    here — shadowing the old name with a blank would make the credential vanish.
    """
    access = ModelAccess.from_env(
        {
            "COMENI_AI_MODEL": "",
            "MENDEL_MODEL": "m",
            "COMENI_AI_API_KEY": "",
            "MENDEL_API_KEY": "k",
        }
    )
    assert access is not None
    assert access.model == "m"
    assert access.api_key == "k"


def test_every_new_name_has_a_deprecated_partner() -> None:
    """The map is what makes the window closable: one place lists what may still be read."""
    from comeni_ai import access as module

    assert set(module.DEPRECATED) == {
        module.MODEL,
        module.API_KEY,
        module.BASE_URL,
        module.TIMEOUT,
        module.TEMPERATURE,
    }
    assert all(old.startswith("MENDEL_") for old in module.DEPRECATED.values())
    assert all(new.startswith("COMENI_AI_") for new in module.DEPRECATED)


def test_the_refusal_names_the_current_spelling() -> None:
    """A refusal telling somebody to set a variable this package no longer reads first is a
    refusal that costs them a debugging session."""
    with pytest.raises(NoModelError) as raised:
        ModelAccess.require_from_env({})
    assert "COMENI_AI_MODEL" in str(raised.value)
    assert "MENDEL_MODEL" not in str(raised.value)
