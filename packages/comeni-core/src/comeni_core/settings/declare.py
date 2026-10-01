"""One declaration per setting (spec §4).

**A setting is declared once, here or in a catalogue, and everything else is generic.** The
resolver, the API and the menu read these fields and know nothing about any one setting, so
adding one is three steps: declare it, place it in a section, read it where it is used.

**Kinds are factories** (`Setting.choice(...)`), so a declaration reads as what it is and the
validator below refuses a declaration that could not work — a default outside its options, a
secret with a default, a browser setting the server claims to pin.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator, model_validator

from comeni_core.settings.reasons import Reason

LOWER = frozenset("abcdefghijklmnopqrstuvwxyz")
DIGITS = frozenset("0123456789")


def _is_key(key: str) -> bool:
    """`section.name`, lower case: two or more dotted parts, each a lower-case letter followed by
    letters, digits or underscores. The key is a stored row's primary key and a URL segment.

    **Without `re`**, which is not on `comeni-core`'s import allowlist in
    `tests/guards/test_purity.py`; this is short enough not to be worth widening a guard for."""
    parts = key.split(".")
    return len(parts) >= 2 and all(
        part and part[0] in LOWER and set(part) <= LOWER | DIGITS | {"_"} for part in parts
    )

HELP_FLOOR = 20
"""Shorter than this is a label repeated, not an explanation."""

TRUE = frozenset({"1", "true", "yes", "on"})
FALSE = frozenset({"0", "false", "no", "off"})


class IllegalValue(ValueError):
    """A value this setting cannot hold. Uncoded here; the API that refuses it adds the code."""


class Kind(StrEnum):
    CHOICE = "choice"
    TEXT = "text"
    NUMBER = "number"
    TOGGLE = "toggle"
    SECRET = "secret"
    READONLY = "readonly"


class Where(StrEnum):
    """Where a value is kept. **`browser` is per browser and never reaches the server**: the
    theme is one. The server still declares it, so the menu draws it with everything else."""

    INSTALLATION = "installation"
    BROWSER = "browser"


class ChoiceOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str
    label: str


class Setting(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    help: str
    """What it is and what changes when it changes. The first half of the ⓘ (spec §5)."""
    kind: Kind
    default: JsonValue = None
    env: str | None = None
    """The variable that pins it. **Set means locked**: `.env` is the operator's last word."""
    options: tuple[ChoiceOption, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    unavailable: Reason | None = None
    """Declared greyed out, with its reason — `Designed` until something reads it."""
    where: Where = Where.INSTALLATION

    @field_validator("key")
    @classmethod
    def _key(cls, key: str) -> str:
        if not _is_key(key):
            raise ValueError(f"key {key!r} must be dotted and lower case, as `section.name`")
        return key

    @field_validator("help")
    @classmethod
    def _help(cls, text: str) -> str:
        if len(text.strip()) < HELP_FLOOR:
            raise ValueError(f"help must say what the setting is, in {HELP_FLOOR}+ characters")
        return text.strip()

    @model_validator(mode="after")
    def _coherent(self) -> "Setting":
        if self.kind is Kind.CHOICE:
            values = [o.value for o in self.options]
            if not values or len(set(values)) != len(values):
                raise ValueError("a choice needs options, each value once")
        elif self.options:
            raise ValueError("options belong to a choice only")
        if self.kind is Kind.SECRET and self.default is not None:
            raise ValueError("a secret has no default: a default secret is a published one")
        if self.where is Where.BROWSER and self.env is not None:
            raise ValueError("a browser setting cannot be pinned by the server's .env")
        if self.kind not in (Kind.SECRET, Kind.READONLY):
            try:
                self.check(self.default)
            except IllegalValue as refused:
                raise ValueError(f"default {self.default!r}: {refused}") from None
        return self

    def check(self, value: Any) -> Any:
        """The value, if this setting can hold it; `IllegalValue` otherwise."""
        match self.kind:
            case Kind.CHOICE:
                legal = [o.value for o in self.options]
                if value not in legal:
                    raise IllegalValue(f"{value!r} is not one of {', '.join(legal)}")
            case Kind.TEXT:
                if not isinstance(value, str):
                    raise IllegalValue("a text setting holds text")
            case Kind.NUMBER:
                if isinstance(value, bool) or not isinstance(value, int | float):
                    raise IllegalValue("a number setting holds a number")
                if self.minimum is not None and value < self.minimum:
                    raise IllegalValue(f"{value} is below the minimum, {self.minimum:g}")
                if self.maximum is not None and value > self.maximum:
                    raise IllegalValue(f"{value} is above the maximum, {self.maximum:g}")
            case Kind.TOGGLE:
                if not isinstance(value, bool):
                    raise IllegalValue("a toggle is on or off")
            case Kind.SECRET:
                if not isinstance(value, str) or not value.strip():
                    raise IllegalValue("a secret cannot be empty")
            case Kind.READONLY:
                raise IllegalValue("this setting is read-only here")
        return value

    def parse_env(self, raw: str) -> Any:
        """A value from `.env`'s text. Checked by the caller, which knows the variable's name."""
        if self.kind is Kind.TOGGLE:
            lowered = raw.lower()
            if lowered in TRUE:
                return True
            if lowered in FALSE:
                return False
            raise IllegalValue(f"{raw!r} is not on or off")
        if self.kind is Kind.NUMBER:
            try:
                number = float(raw)
            except ValueError:
                raise IllegalValue(f"{raw!r} is not a number") from None
            return int(number) if number.is_integer() else number
        return raw

    # ── factories ────────────────────────────────────────────────────────────────────────

    @classmethod
    def choice(cls, *, options: list[tuple[str, str]], **fields: Any) -> "Setting":
        return cls(
            kind=Kind.CHOICE,
            options=tuple(ChoiceOption(value=v, label=label) for v, label in options),
            **fields,
        )

    @classmethod
    def text(cls, **fields: Any) -> "Setting":
        return cls(kind=Kind.TEXT, **{"default": "", **fields})

    @classmethod
    def number(cls, **fields: Any) -> "Setting":
        return cls(kind=Kind.NUMBER, **fields)

    @classmethod
    def toggle(cls, **fields: Any) -> "Setting":
        return cls(kind=Kind.TOGGLE, **fields)

    @classmethod
    def secret(cls, **fields: Any) -> "Setting":
        return cls(kind=Kind.SECRET, **fields)

    @classmethod
    def readonly(cls, **fields: Any) -> "Setting":
        return cls(kind=Kind.READONLY, **fields)
