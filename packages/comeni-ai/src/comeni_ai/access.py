"""Provider access configuration shared by local, self-hosted, and hosted models.

All deployment lanes use the same :class:`ModelAccess` shape and transport path. Subscription
OAuth credentials are intentionally unsupported. Environment loading returns ``None`` when no
model is configured so an unconfigured installation cannot contact a provider implicitly.
"""

from collections.abc import Mapping

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict


class NoModelError(ValueError):
    """Raised with ``MA0001`` when a caller requires missing model configuration."""


MODEL = "COMENI_AI_MODEL"
API_KEY = "COMENI_AI_API_KEY"
BASE_URL = "COMENI_AI_BASE_URL"
TIMEOUT = "COMENI_AI_TIMEOUT_SECONDS"
TEMPERATURE = "COMENI_AI_TEMPERATURE"
MAX_CONCURRENT_JOBS = "COMENI_AI_MAX_CONCURRENT_JOBS"
"""Shared worker-concurrency setting; application workers, not this package, consume it."""

DEPRECATED: dict[str, str] = {
    MODEL: "MENDEL_MODEL",
    API_KEY: "MENDEL_API_KEY",
    BASE_URL: "MENDEL_BASE_URL",
    TIMEOUT: "MENDEL_TIMEOUT_SECONDS",
    TEMPERATURE: "MENDEL_TEMPERATURE",
}
"""Deprecated ``MENDEL_*`` names read only when the corresponding current value is blank.

The mapping is a temporary compatibility surface. Current ``COMENI_AI_*`` values always take
precedence when both spellings are present.
"""


def _read(env: Mapping[str, str], name: str) -> str:
    """Return the current value, its deprecated fallback, or an empty string.

    Blank current values do not shadow a non-blank deprecated value.
    """
    current = env.get(name, "").strip()
    if current:
        return current
    return env.get(DEPRECATED.get(name, ""), "").strip()


class ModelAccess(BaseModel):
    """Immutable configuration required to reach one model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    api_key: str | None = None
    """`None` is legal — a local endpoint needs no key, and requiring one would make the
    self-hosted lane the awkward one."""
    base_url: str | None = None
    """Set for a local or self-hosted OpenAI-compatible endpoint; `None` for a provider."""
    timeout_seconds: float = 60.0
    temperature: float = 0.0
    """Sampling randomness, defaulting to zero for reproducible comparisons."""

    @classmethod
    def require_from_env(cls, env: Mapping[str, str]) -> "ModelAccess":
        """Load configuration or raise the package-owned ``MA0001`` diagnostic."""
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
        """Load from ``env``, returning ``None`` when no model is configured.

        A supplied mapping keeps process environment access under the caller's control. Blank
        strings are treated as absent values.
        """
        model = _read(env, MODEL)
        if not model:
            return None
        timeout = _read(env, TIMEOUT)
        return cls(
            model=model,
            api_key=_read(env, API_KEY) or None,
            base_url=_read(env, BASE_URL) or None,
            timeout_seconds=float(timeout) if timeout else 60.0,
            temperature=float(_read(env, TEMPERATURE) or 0.0),
        )
