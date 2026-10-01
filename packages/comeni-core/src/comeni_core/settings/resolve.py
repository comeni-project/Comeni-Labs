"""Where a value comes from (spec §3): default → installation → [lab, person later], with the
environment above all of them as a lock.

**Every resolved value carries its source**, the way every value in a pipeline says which tier
settled it. And **a locked value always carries its reason**: the only ways to be locked are
listed below, and each one returns a `Reason` from the closed list.
"""

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, JsonValue

from comeni_core.settings.declare import IllegalValue, Kind, Setting
from comeni_core.settings.reasons import Designed, Needs, Pinned, Reason

SETTINGS_KEY_ENV = "COMENI_SETTINGS_KEY"
"""The key that seals secrets stored from the menu. Its absence greys every secret field."""


class Source(StrEnum):
    DEFAULT = "default"
    INSTALLATION = "installation"
    ENVIRONMENT = "environment"


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
    """The value a setting has right now, and why.

    **`Designed` is asked first**: a setting nothing reads must not say *pinned by .env*, or the
    menu claims a control works. **An illegal env value locks the default** rather than raising,
    because a typo in `.env` must not take the menu down; the reason names the variable. **An
    illegal stored value falls through to the default**: it is a value an older declaration
    allowed, and the person can choose again.
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
