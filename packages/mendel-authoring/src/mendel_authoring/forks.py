"""The builder's fork subjects and the snapshot they read. The engine's `Subject` and
`DEFAULT` live in `comeni_flow.forks`.

A fork delegates case selection to its subject, making setting-dependent paths part of the
validated protocol rather than hidden conditionals in shell handlers.
"""

from comeni_core.settings.declare import Kind, Setting
from comeni_flow.forks import Subject
from pydantic import BaseModel, ConfigDict, JsonValue


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Snapshot(_Frozen):
    """What the builder's forks may read, as plain data. A field per kind of subject."""

    settings: dict[str, JsonValue] = {}


NO_SNAPSHOT = Snapshot()
"""What a run reads when the shell passes nothing: every subject takes its declared default."""


class SettingSubject(Subject):
    """A setting, its cases read off its own declaration so they cannot drift from the menu."""

    key: str
    cases: frozenset[str] | None
    default: JsonValue = None

    @classmethod
    def of(cls, setting: Setting, title: str | None = None) -> "SettingSubject":
        if setting.kind is Kind.CHOICE:
            cases: frozenset[str] | None = frozenset(o.value for o in setting.options)
        elif setting.kind is Kind.TOGGLE:
            cases = frozenset({"on", "off"})
        else:
            cases = None
        return cls(
            key=setting.key,
            title=title or setting.label,
            cases=cases,
            default=setting.default,
        )

    def options(self) -> frozenset[str] | None:
        return self.cases

    def snapshot_key(self) -> str:
        return self.key

    def value(self, snapshot: Snapshot | None) -> str:
        # `None`: the shell passed nothing, so the declared default answers (as `NO_SNAPSHOT`).
        raw = (snapshot or NO_SNAPSHOT).settings.get(self.key, self.default)
        if isinstance(raw, bool):
            return "on" if raw else "off"
        if raw is None and self.cases == {"on", "off"}:
            return "off"
        return str(raw)
