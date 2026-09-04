"""Invariant 13 — self-hosted is not a degraded tier.

A local model behind an OpenAI-compatible endpoint and a hosted provider differ by **what is
in a `ModelAccess` and by nothing else**. A branch per lane is the design error invariant 13
names, and it is the kind of thing that arrives quietly: one `if access.base_url:` added to
handle a provider quirk, and the local lane is now a second code path nobody measures.

§1.9 of the Forge MVP plan restates it as an acceptance criterion — "Local Ollama and a hosted
API differ only by `ai-core` configuration" — so it gets a test rather than a paragraph.
"""

from comeni_ai.access import ModelAccess
from comeni_ai.client import Client
from pydantic import BaseModel

OLLAMA = {"COMENI_AI_MODEL": "ollama/llama3", "COMENI_AI_BASE_URL": "http://ollama:11434"}
HOSTED = {"COMENI_AI_MODEL": "anthropic/claude-sonnet-4-5", "COMENI_AI_API_KEY": "sk-x"}


class Answer(BaseModel):
    answer: str


def test_both_lanes_construct_the_same_type() -> None:
    ollama = ModelAccess.from_env(OLLAMA)
    hosted = ModelAccess.from_env(HOSTED)
    assert type(ollama) is type(hosted) is ModelAccess


def test_the_lanes_differ_only_in_configuration_fields() -> None:
    """Which fields differ is itself the assertion.

    If a lane ever needed a different timeout or temperature *to work*, that difference would
    show up here as a fourth field — and a lane that needs different settings to work is a
    lane that is being treated differently.
    """
    ollama = ModelAccess.from_env(OLLAMA)
    hosted = ModelAccess.from_env(HOSTED)
    differing = {
        field
        for field in ModelAccess.model_fields
        if getattr(ollama, field) != getattr(hosted, field)
    }
    assert differing == {"model", "base_url", "api_key"}, (
        f"the lanes differ in a field that is not configuration: {sorted(differing)}"
    )


def test_both_lanes_compose_the_same_prompt() -> None:
    """A `ModelAccess` is only half the claim — the fork could still be inside `Client`.

    Same question down both lanes; the transport must see one shape.
    """
    seen: list[str] = []

    class Spy:
        def send(self, access: ModelAccess, prompt: str) -> str:
            seen.append(prompt)
            return '{"answer": "ok"}'

    for env in (OLLAMA, HOSTED):
        access = ModelAccess.from_env(env)
        assert access is not None
        assert Client(access, Spy()).generate("q", Answer, ["E001"]) is not None

    assert len(seen) == 2
    assert seen[0] == seen[1], "the two lanes composed different prompts"


def test_a_local_lane_needs_no_credential() -> None:
    """Requiring a key would make the self-hosted lane the awkward one, which is the shape
    invariant 13 forbids."""
    access = ModelAccess.from_env(OLLAMA)
    assert access is not None
    assert access.api_key is None


def test_neither_lane_is_reachable_without_configuration() -> None:
    """`from_env` returns `None` rather than defaulting to a provider — an unconfigured
    install must not quietly reach one on somebody's first model-backed command."""
    assert ModelAccess.from_env({}) is None
