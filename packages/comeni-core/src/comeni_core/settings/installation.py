"""The installation's settings: read, write, and serve (spec §4, §8).

**The store and the codec are `Protocol`s**, so this module never touches a database or a
cipher (invariant 1). `mendel-api` supplies a Postgres store and a Fernet codec; a test supplies a
dictionary. **Read on every use, never cached**, for the reason `model_access()` reads the
environment at call time: the AI worker is another process, and a change made in the menu must
reach its next call.

**A secret never leaves through here.** `shown()` is what a server serialises, and it carries
`set` and the last four characters; the plaintext comes back only from `get()`, which is what the
code that uses a key calls.
"""

from collections.abc import Mapping
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

from comeni_core.settings.declare import Kind, Setting, Where
from comeni_core.settings.reasons import ReadOnlyHere, Reason
from comeni_core.settings.resolve import Resolved, Source, resolve
from comeni_core.settings.sections import Catalogue


class SettingsStore(Protocol):
    def values(self) -> Mapping[str, object]: ...

    def put(self, key: str, value: object, by: str) -> None: ...


class SecretCodec(Protocol):
    def seal(self, plain: str) -> str: ...

    def open(self, sealed: str) -> str: ...


class SettingLocked(Exception):
    """A put on a setting that is locked. Uncoded here; the API adds the code and the 409."""

    def __init__(self, setting: Setting, reason: Reason):
        super().__init__(f"{setting.key} is locked: {reason.says}")
        self.setting = setting
        self.reason = reason


BROWSER_ONLY = ReadOnlyHere(why="this one is kept by your browser, not the server")


class Shown(BaseModel):
    """What a server may say about a value. For a secret, `value` is always `None`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: JsonValue
    source: Source
    locked: bool
    reason: Reason | None = None
    set: bool | None = None
    last4: str | None = None


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    setting: Setting
    shown: Shown


class MenuSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    title: str
    order: int
    served_by: Literal["mendel", "wiener"]
    entries: list[Entry]


class Menu(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sections: list[MenuSection]


class Installation:
    def __init__(
        self,
        catalogue: Catalogue,
        store: SettingsStore,
        env: Mapping[str, str],
        codec: SecretCodec | None = None,
    ):
        self.catalogue = catalogue
        self.store = store
        self.env = env
        self.codec = codec

    def resolved(self, setting: Setting) -> Resolved:
        return resolve(
            setting, self.store.values(), self.env, secrets_available=self.codec is not None
        )

    def get(self, setting: Setting) -> object:
        """The value for the code that uses it. **The only place a secret is opened.**"""
        got = self.resolved(setting)
        if setting.kind is Kind.SECRET and got.source is Source.INSTALLATION:
            assert self.codec is not None  # resolve() locks secrets when there is no codec
            return self.codec.open(str(got.value))
        return got.value

    def shown(self, setting: Setting) -> Shown:
        got = self.resolved(setting)
        if setting.kind is not Kind.SECRET:
            # Field by field, not `**got.model_dump()`: a dump carries each reason's computed
            # `says`, and a reason forbids extra fields on the way back in.
            return Shown(
                value=got.value, source=got.source, locked=got.locked, reason=got.reason
            )
        plain = self.get(setting) or None  # "" is a secret the codec could not open: not set
        return Shown(
            value=None,
            source=got.source,
            locked=got.locked,
            reason=got.reason,
            set=plain is not None,
            last4=str(plain)[-4:] if plain is not None else None,
        )

    def put(self, key: str, value: object, by: str) -> Shown:
        setting = self.catalogue.setting(key)
        if setting.where is Where.BROWSER:
            raise SettingLocked(setting, BROWSER_ONLY)
        got = self.resolved(setting)
        if got.locked:
            assert got.reason is not None  # resolve() never locks without a reason
            raise SettingLocked(setting, got.reason)
        checked = setting.check(value)
        if setting.kind is Kind.SECRET:
            assert self.codec is not None
            checked = self.codec.seal(checked)
        self.store.put(key, checked, by)
        return self.shown(setting)

    def menu(self, server: Literal["mendel", "wiener"] = "mendel") -> Menu:
        return Menu(
            sections=[
                MenuSection(
                    key=section.key,
                    title=section.title,
                    order=section.order,
                    served_by=section.served_by,
                    entries=[Entry(setting=s, shown=self.shown(s)) for s in section.settings],
                )
                for section in self.catalogue.served_by(server)
            ]
        )
