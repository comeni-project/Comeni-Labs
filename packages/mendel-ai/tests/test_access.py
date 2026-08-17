"""The three lanes, and the invariants they carry.

Invariant 13 — self-hosted is not a degraded tier — means the lanes differ by configuration
and not by code path. Invariant 12 — no subscription OAuth — is enforced by there being
nowhere to put a subscription token.
"""

import pytest
from mendel_ai.access import ModelAccess
from pydantic import ValidationError


def test_no_model_configured_is_none_rather_than_a_default() -> None:
    """A default model would make an unconfigured install quietly reach a provider."""
    assert ModelAccess.from_env({}) is None


def test_the_byo_key_lane() -> None:
    access = ModelAccess.from_env({"MENDEL_MODEL": "anthropic/claude-x", "MENDEL_API_KEY": "k"})
    assert access is not None
    assert access.model == "anthropic/claude-x"
    assert access.api_key == "k"
    assert access.base_url is None


def test_the_local_lane_needs_no_key() -> None:
    """Ollama and vLLM behind an OpenAI-compatible endpoint. Invariant 13: identical path."""
    access = ModelAccess.from_env(
        {"MENDEL_MODEL": "ollama/llama3", "MENDEL_BASE_URL": "http://localhost:11434"}
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
    assert ModelAccess.from_env({"MENDEL_MODEL": "   "}) is None


def test_a_blank_key_is_no_key_rather_than_an_empty_one() -> None:
    """An empty credential looks like a credential to a provider that wanted none, which is
    the local lane's most likely misconfiguration."""
    access = ModelAccess.from_env({"MENDEL_MODEL": "ollama/llama3", "MENDEL_API_KEY": ""})
    assert access is not None
    assert access.api_key is None


def test_the_timeout_is_configurable_and_has_a_default() -> None:
    assert ModelAccess.from_env({"MENDEL_MODEL": "m"}).timeout_seconds == 60.0
    assert (
        ModelAccess.from_env({"MENDEL_MODEL": "m", "MENDEL_TIMEOUT_SECONDS": "180"}).timeout_seconds
        == 180.0
    )


def test_from_env_reads_the_mapping_it_is_given_and_not_the_process() -> None:
    """Takes a mapping so a test cannot leak the developer's own configuration into an
    assertion, and needs no monkeypatching to be honest."""
    import os

    os.environ["MENDEL_MODEL"] = "leaked/model"
    try:
        assert ModelAccess.from_env({}) is None
    finally:
        del os.environ["MENDEL_MODEL"]
