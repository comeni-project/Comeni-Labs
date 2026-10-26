"""Resolve setting values from defaults, installation storage, and environment locks."""

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, JsonValue

from comeni_core.settings.declare import IllegalValue, Kind, Setting
from comeni_core.settings.reasons import Designed, Needs, Pinned, Reason

SETTINGS_KEY_ENV = "COMENI_SETTINGS_KEY"
"""Environment key used to seal stored secrets; absence disables secret editing."""


class Source(StrEnum):
    DEFAULT = "default"
    INSTALLATION = "installation"
    ENVIRONMENT = "environment"
    REPORTED = "reported"
    """Computed by the serving process on each read."""


class Resolved(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: JsonValue
    source: Source
    locked: bool
    reason: Reason | None = None


def resolve(
    setting: Setting,
    stored: Mapping[str, object],
    env: Mapping[str, str],
    *,
    secrets_available: bool = True,
    secrets_need: str | None = None,
) -> Resolved:
    """Return the current value, source, lock state, and optional lock reason.

    Designed settings remain unavailable even when pinned. A valid environment value has highest
    precedence and locks the result. Invalid environment input locks the default with a diagnostic;
    invalid stored input falls back to the current default so it can be replaced.
    """
    default = Resolved(value=setting.default, source=Source.DEFAULT, locked=False)
    if isinstance(setting.unavailable, Designed):
        return default.model_copy(update={"locked": True, "reason": setting.unavailable})

    raw = env.get(setting.env, "").strip() if setting.env else ""
    if raw:
        try:
            value = raw if setting.kind is Kind.READONLY else setting.check(setting.parse_env(raw))
        except IllegalValue as refused:
            return default.model_copy(
                update={
                    "locked": True,
                    "reason": Needs(what=f"{setting.env} in .env holds {raw!r}: {refused}"),
                }
            )
        return Resolved(
            value=value, source=Source.ENVIRONMENT, locked=True, reason=Pinned(env=setting.env)
        )

    if setting.unavailable is not None:
        return default.model_copy(update={"locked": True, "reason": setting.unavailable})

    if setting.kind is Kind.SECRET and not secrets_available:
        return default.model_copy(
            update={
                "locked": True,
                "reason": Needs(
                    what=secrets_need
                    or f"set {SETTINGS_KEY_ENV} in .env to store secrets here"
                    + (f", or set {setting.env} there directly" if setting.env else "")
                ),
            }
        )

    if setting.key in stored:
        value = stored[setting.key]
        try:
            # A stored secret is sealed text; only its being text can be checked here.
            checked = value if setting.kind is Kind.SECRET else setting.check(value)
        except IllegalValue:
            return default
        return Resolved(value=checked, source=Source.INSTALLATION, locked=False)
    return default
