"""How a laboratory reaches a model. Three lanes, one code path.

**Invariant 13 — self-hosted is not a degraded tier.** BYO key, a local model behind an
OpenAI-compatible endpoint (Ollama and vLLM both qualify), and the hosted lane differ by what
is in this object and by nothing else. A branch per lane would be the design error that
invariant names.

**Invariant 12 — no subscription OAuth.** Claude Pro/Max tokens in third-party tools violate
Anthropic's Consumer ToS. There is no field here to put one in, and `extra="forbid"` refuses
an attempt. A ban enforced by having nowhere to write the value is worth more than one
enforced by a check somebody can forget to call.

**`from_env` returns `None` rather than a default.** A default model would make an
unconfigured install quietly reach a provider on somebody's first `forge fill --model`, which
is the opposite of what `--no-ai`-by-default means.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

MODEL = "MENDEL_MODEL"
API_KEY = "MENDEL_API_KEY"
BASE_URL = "MENDEL_BASE_URL"
TIMEOUT = "MENDEL_TIMEOUT_SECONDS"


class ModelAccess(BaseModel):
    """What is needed to reach one model. Frozen: what was configured is what is used."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    api_key: str | None = None
    """`None` is legal — a local endpoint needs no key, and requiring one would make the
    self-hosted lane the awkward one."""
    base_url: str | None = None
    """Set for a local or self-hosted OpenAI-compatible endpoint; `None` for a provider."""
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "ModelAccess | None":
        """`None` when no model is configured.

        Takes a mapping rather than reading `os.environ` so a test needs no monkeypatching and
        cannot leak the developer's own configuration into an assertion.

        **An empty string is not a value.** `MENDEL_API_KEY=` exported and empty is the local
        lane's most likely misconfiguration, and an empty credential looks like a credential to
        a provider that wanted none.
        """
        model = env.get(MODEL, "").strip()
        if not model:
            return None
        timeout = env.get(TIMEOUT, "").strip()
        return cls(
            model=model,
            api_key=env.get(API_KEY) or None,
            base_url=env.get(BASE_URL) or None,
            timeout_seconds=float(timeout) if timeout else 60.0,
        )
