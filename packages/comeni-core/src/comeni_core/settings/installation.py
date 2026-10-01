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

from collections.abc import Callable, Mapping
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue, SecretStr

from comeni_core.settings.declare import IllegalValue, Kind, Setting, Where
from comeni_core.settings.reasons import Needs, ReadOnlyHere, Reason
from comeni_core.settings.resolve import SETTINGS_KEY_ENV, Resolved, Source, resolve
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

UNREADABLE = Needs(
    what=f"the stored value was sealed under another {SETTINGS_KEY_ENV}; enter it again"
)
"""A secret the codec cannot open — the key was rotated. Not set, and said so (review I2)."""

LAST4_FLOOR = 12
"""Shorter than this, the last four characters are most of the secret, so none are shown."""


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
    lede: str = ""
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
        *,
        server: Literal["mendel", "wiener"] = "mendel",
        secrets_need: str | None = None,
        reporters: Mapping[str, Callable[[], object]] | None = None,
    ):
        """`server` is who is serving this menu: a setting another server reports is never
        written here. `secrets_need` is the precise reason secrets cannot be stored when the
        caller knows it — a malformed key rather than a missing one. `reporters` compute the
        read-only values a server reports, by setting key (spec §6, §7)."""
        self.catalogue = catalogue
        self.store = store
        self.env = env
        self.codec = codec
        self.server = server
        self.secrets_need = secrets_need
        self.reporters = dict(reporters or {})

    # ── reading ──────────────────────────────────────────────────────────────────────────

    def resolved(self, setting: Setting) -> Resolved:
        if setting.kind is Kind.READONLY and setting.key in self.reporters:
            try:
                value = self.reporters[setting.key]()
            except Exception as failed:  # a report must never take the menu down
                # The type, never the message: a message can carry a host, a path or a DSN.
                value = f"could not be read ({type(failed).__name__})"
            return Resolved(
                value=value,
                source=Source.REPORTED,
                locked=True,
                reason=setting.unavailable or ReadOnlyHere(why="worked out by the server"),
            )
        got = resolve(
            setting,
            self.store.values(),
            self.env,
            secrets_available=self.codec is not None,
            secrets_need=self.secrets_need,
        )
        if setting.kind is Kind.COLLECTION:
            own = self._env_record(setting)
            return got.model_copy(update={"value": ([own] if own else []) + list(got.value or [])})
        if setting.kind is Kind.MODEL and isinstance(got.value, dict):
            names = {r["name"] for r in self._records_of(setting)}
            if got.value["connection"] not in names:
                gone = got.value["connection"]
                return Resolved(
                    value=None,
                    source=Source.DEFAULT,
                    locked=False,
                    reason=Needs(what=f"the connection {gone!r} is gone; choose another"),
                )
        return got

    def _env_record(self, setting: Setting) -> dict | None:
        """The record `.env` supplies, first and locked. Its secrets are the variables' text."""
        spec = setting.from_env
        if spec is None or not any(self.env.get(v, "").strip() for v in spec.present_when):
            return None
        record = {f.field_name: f.default for f in setting.fields}
        record[setting.item_name] = spec.name
        for field_name, variable in spec.fields.items():
            record[field_name] = self.env.get(variable, "").strip() or None
        return {**record, "locked": True}

    def _records_of(self, model: Setting) -> list[dict]:
        assert model.of is not None
        return list(self.resolved(self.catalogue.setting(model.of)).value or [])

    def _secret_fields(self, setting: Setting) -> list[str]:
        return [f.field_name for f in setting.fields if f.kind is Kind.SECRET]

    def record(self, setting: Setting, name: str) -> dict | None:
        """One record, with its secrets opened and handed over as `SecretStr` (spec §8). A
        secret this codec cannot open — a rotated key — is `None`: the record reads as having
        no key, which the provider then refuses, rather than as an error that takes the menu
        down."""
        for record in self.resolved(setting).value or []:
            if record[setting.item_name] != name:
                continue
            opened = {k: v for k, v in record.items() if k != "locked"}
            for field in self._secret_fields(setting):
                raw = opened.get(field)
                if not raw:
                    opened[field] = None
                elif record.get("locked"):
                    opened[field] = SecretStr(raw)
                elif self.codec is None:
                    # Stored while a key was set, and the key has gone: unreadable, not a crash
                    # (review C2). The menu shows it as not set.
                    opened[field] = None
                else:
                    try:
                        opened[field] = SecretStr(self.codec.open(raw)) or None
                    except ValueError:
                        opened[field] = None
            return opened
        return None

    def get(self, setting: Setting) -> object:
        """The value for the code that uses it. **The only place a secret is opened**, and it
        is handed over as a `SecretStr`, which prints as hidden (spec §8). A codec that cannot
        open it raises; `shown` turns that into *not set*, and a caller learns it cannot read
        the key rather than receiving an empty one."""
        if setting.kind is Kind.COLLECTION:
            return [
                self.record(setting, r[setting.item_name])
                for r in self.resolved(setting).value or []
            ]
        got = self.resolved(setting)
        if setting.kind is not Kind.SECRET or got.value is None:
            return got.value
        if got.source is Source.INSTALLATION:
            assert self.codec is not None  # resolve() locks secrets when there is no codec
            return SecretStr(self.codec.open(str(got.value)))
        return SecretStr(str(got.value))

    def shown(self, setting: Setting) -> Shown:
        got = self.resolved(setting)
        if setting.kind is Kind.COLLECTION:
            return Shown(
                value=[self._masked(setting, r) for r in got.value or []],
                source=got.source,
                locked=got.locked,
                reason=got.reason,
            )
        if setting.kind is not Kind.SECRET:
            # Field by field, not `**got.model_dump()`: a dump carries each reason's computed
            # `says`, and a reason forbids extra fields on the way back in.
            return Shown(
                value=got.value, source=got.source, locked=got.locked, reason=got.reason
            )
        try:
            secret = self.get(setting)
        except ValueError:
            return Shown(value=None, source=got.source, locked=False, reason=UNREADABLE, set=False)
        plain = secret.get_secret_value() if isinstance(secret, SecretStr) else None
        return Shown(
            value=None,
            source=got.source,
            locked=got.locked,
            reason=got.reason,
            set=bool(plain),
            last4=_last4(plain),
        )

    def _masked(self, setting: Setting, record: dict) -> dict:
        """A record as a server may show it: each secret field is `{set, last4}`."""
        opened = self.record(setting, record[setting.item_name]) or {}
        view = dict(record)
        for field in self._secret_fields(setting):
            secret = opened.get(field)
            plain = secret.get_secret_value() if isinstance(secret, SecretStr) else None
            view[field] = {"set": bool(plain), "last4": _last4(plain)}
        return view

    # ── writing ──────────────────────────────────────────────────────────────────────────

    def put(self, key: str, value: object, by: str) -> Shown:
        setting = self.catalogue.setting(key)
        if setting.where is Where.BROWSER:
            raise SettingLocked(setting, BROWSER_ONLY)
        served_by = self.catalogue.section_of(key).served_by
        if served_by != self.server:
            raise SettingLocked(
                setting, ReadOnlyHere(why=f"{served_by} reports this from its own .env")
            )
        got = self.resolved(setting)
        if got.locked:
            assert got.reason is not None  # resolve() never locks without a reason
            raise SettingLocked(setting, got.reason)
        if setting.kind is Kind.COLLECTION:
            checked = self._sealed_records(setting, value)
        else:
            checked = setting.check(value)
        if setting.kind is Kind.MODEL and checked is not None:
            names = {r["name"] for r in self._records_of(setting)}
            if checked["connection"] not in names:
                raise IllegalValue(f"no connection called {checked['connection']!r}")
        if setting.kind is Kind.SECRET:
            assert self.codec is not None
            checked = self.codec.seal(checked)
        self.store.put(key, checked, by)
        return self.shown(setting)

    def _sealed_records(self, setting: Setting, value: object) -> list[dict]:
        """Records as stored. **A secret field sent as `None` keeps what is stored**, so a
        person saves the list without retyping every key; `""` clears it; text is sealed. The
        record `.env` supplies is never stored."""
        own = setting.from_env.name if setting.from_env else None
        incoming = [
            r for r in (value if isinstance(value, list) else [value])
            if not (isinstance(r, dict) and r.get(setting.item_name) == own)
        ]
        records = setting.check(incoming)
        stored = {
            r[setting.item_name]: r
            for r in self.store.values().get(setting.key, []) or []
            if isinstance(r, dict)
        }
        for record in records:
            for field in self._secret_fields(setting):
                given = record[field]
                if given is None:
                    record[field] = stored.get(record[setting.item_name], {}).get(field)
                elif given == "":
                    record[field] = None
                elif self.codec is None:
                    raise SettingLocked(
                        setting,
                        Needs(
                            what=self.secrets_need
                            or f"set {SETTINGS_KEY_ENV} in .env to store keys here"
                        ),
                    )
                else:
                    record[field] = self.codec.seal(given)
        return records

    def menu(self, server: Literal["mendel", "wiener"] = "mendel") -> Menu:
        return Menu(
            sections=[
                MenuSection(
                    key=section.key,
                    title=section.title,
                    lede=section.lede,
                    order=section.order,
                    served_by=section.served_by,
                    entries=[Entry(setting=s, shown=self.shown(s)) for s in section.settings],
                )
                for section in self.catalogue.served_by(server)
            ]
        )


def _last4(plain: str | None) -> str | None:
    return plain[-4:] if plain and len(plain) >= LAST4_FLOOR else None
