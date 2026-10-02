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
    MODEL = "model"
    """`None` — the default model — or `{"connection": name, "model": id}`."""
    COLLECTION = "collection"
    """A list of records, each keyed by field name. Connections are one."""


class Where(StrEnum):
    """Where a value is kept. **`browser` is per browser and never reaches the server**: the
    theme is one. The server still declares it, so the menu draws it with everything else."""

    INSTALLATION = "installation"
    BROWSER = "browser"


class ChoiceOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str
    label: str
    designed: str | None = None
    """Why this option cannot be chosen yet, when it is designed and not built. The menu draws
    it greyed with this line, so the menu says what is coming without offering it (#134)."""


FROM_ENV = "From .env"
"""The name of the record `.env` supplies. Locked: it is changed in `.env`, never in the menu."""


class EnvItem(BaseModel):
    """A record built from the environment, shown first and locked (spec §6).

    `fields` maps a record field to the variable that fills it; the record exists when
    `present_when` is set. Declared, so the facade needs no code that knows about models.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    present_when: tuple[str, ...]
    """The record exists when **any** of these is set: a purpose pinned in `.env` without a
    default still needs the endpoint and key `.env` gives it (review I3)."""
    fields: dict[str, str]

    @field_validator("present_when", mode="before")
    @classmethod
    def _one_or_many(cls, value: Any) -> Any:
        return (value,) if isinstance(value, str) else value


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
    fields: tuple["Setting", ...] = ()
    """A collection's record fields. Each is a declaration; its key's last segment is the name."""
    item_name: str = "name"
    from_env: EnvItem | None = None
    actions: tuple[str, ...] = ()
    """What a record can be asked to do — `test`, `models`. Served by the API, drawn as buttons."""
    of: str | None = None
    """For a model: the key of the collection whose records it picks from."""

    @property
    def field_name(self) -> str:
        return self.key.rsplit(".", 1)[1]

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
            if any(o.value == self.default and o.designed for o in self.options):
                raise ValueError("a default must be built: a designed option cannot be one")
        elif self.options:
            raise ValueError("options belong to a choice only")
        if self.kind is Kind.SECRET and self.default is not None:
            raise ValueError("a secret has no default: a default secret is a published one")
        if self.where is Where.BROWSER and self.env is not None:
            raise ValueError("a browser setting cannot be pinned by the server's .env")
        if self.kind is Kind.COLLECTION:
            names = [f.field_name for f in self.fields]
            if self.item_name not in names:
                raise ValueError(f"a collection's records need a {self.item_name!r} field")
            if self.from_env and set(self.from_env.fields) - set(names):
                raise ValueError(
                    f"from_env names fields the records do not have: "
                    f"{sorted(set(self.from_env.fields) - set(names))}"
                )
        elif self.fields or self.from_env or self.actions:
            raise ValueError("fields, from_env and actions belong to a collection only")
        if self.kind is Kind.MODEL and not self.of:
            raise ValueError("a model setting says which collection it picks from, as `of`")
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
            case Kind.MODEL:
                if value is not None and (
                    not isinstance(value, dict)
                    or set(value) != {"connection", "model"}
                    or not all(isinstance(v, str) and v.strip() for v in value.values())
                ):
                    raise IllegalValue("a model is a connection and a model id, or the default")
            case Kind.COLLECTION:
                return self._records(value)
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
        if self.kind is Kind.MODEL:
            return {"connection": FROM_ENV, "model": raw}
        return raw

    def _records(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not all(isinstance(r, dict) for r in value):
            raise IllegalValue("a list of records")
        by_name = {f.field_name: f for f in self.fields}
        records, seen = [], set()
        for record in value:
            unknown = set(record) - set(by_name)
            if unknown:
                raise IllegalValue(f"no field called {', '.join(sorted(unknown))}")
            name = record.get(self.item_name)
            if not isinstance(name, str) or not name.strip():
                raise IllegalValue(f"every record needs a {self.item_name}")
            if name in seen:
                raise IllegalValue(f"{name!r} is named twice")
            seen.add(name)
            clean = {}
            for field_name, field in by_name.items():
                raw = record.get(field_name, field.default)
                if field.kind is Kind.SECRET:
                    if raw is not None and not isinstance(raw, str):
                        raise IllegalValue(f"{field_name} is text")
                    clean[field_name] = raw
                else:
                    clean[field_name] = field.check(raw)
            records.append(clean)
        return records

    # ── factories ────────────────────────────────────────────────────────────────────────

    @classmethod
    def choice(
        cls,
        *,
        options: list[tuple[str, str]],
        designed: dict[str, str] | None = None,
        **fields: Any,
    ) -> "Setting":
        """`designed` maps an option's value to why it is not built yet."""
        designed = designed or {}
        unknown = set(designed) - {v for v, _ in options}
        if unknown:
            raise ValueError(f"designed names options that do not exist: {sorted(unknown)}")
        return cls(
            kind=Kind.CHOICE,
            options=tuple(
                ChoiceOption(value=v, label=label, designed=designed.get(v)) for v, label in options
            ),
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

    @classmethod
    def model(cls, **fields: Any) -> "Setting":
        return cls(kind=Kind.MODEL, **fields)

    @classmethod
    def collection(cls, **fields: Any) -> "Setting":
        return cls(kind=Kind.COLLECTION, **{"default": [], **fields})
