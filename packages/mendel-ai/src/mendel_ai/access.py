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

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict


class NoModelError(ValueError):
    """Nothing was configured and something asked for a model. `MA0001`.

    **A `ValueError` because that is the refusal contract every caller already catches** —
    `mendel_forge.ops`' docstring states it, and both forge transports catch it in one place
    and turn it into an exit code or a 4xx.
    """


MODEL = "MENDEL_MODEL"
API_KEY = "MENDEL_API_KEY"
BASE_URL = "MENDEL_BASE_URL"
TIMEOUT = "MENDEL_TIMEOUT_SECONDS"
TEMPERATURE = "MENDEL_TEMPERATURE"


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
    temperature: float = 0.0
    """Sampling randomness. **Zero by default, and that default is the point.**

    Nothing set this until 2026-08-17, so every call sampled at the provider's default — which
    for Ollama is non-zero. Two drafts of the same tool could differ, and an accuracy figure
    measured across configurations was partly measuring the dice: a two-point difference
    between prompt designs is not distinguishable from sampling noise.

    The forge does not claim determinism — "same goal in, same pipeline out" is the resolver
    and compiler — but *unreproducible* is a different thing from *not guaranteed*. A person
    re-running `forge fill --model` on the same draft should get the same answer, and a
    measurement comparing two prompts should be comparing two prompts.
    """

    @classmethod
    def require_from_env(cls, env: Mapping[str, str]) -> "ModelAccess":
        """`from_env`, but a missing model is `MA0001` rather than `None`.

        **The raising form is the one a transport calls**, because "nothing is configured" is
        a refusal a user can act on and `None` is a value somebody forgets to check. The
        non-raising form stays for the question *is anything configured at all*.

        This raises here, in `mendel-ai`, rather than in whichever CLI resolves the
        configuration — `MA0001` is declared `emitted_by: ai`, and
        `tests/diagnostics/test_diagnostics_ownership.py` checks a code is raised by the package
        that owns it. Moving the raise would move the code.
        """
        access = cls.from_env(env)
        if access is None:
            raise NoModelError(
                coded("MA0001", "no model is configured")
                + f"\n  set {MODEL}, and {API_KEY} for a provider or {BASE_URL} for a local one"
                + "\n  or pass --model <id> explicitly"
            )
        return access

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
            temperature=float(env.get(TEMPERATURE, "").strip() or 0.0),
        )
