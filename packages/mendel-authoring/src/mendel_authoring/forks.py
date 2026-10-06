"""What a fork switches on (spec §12): a **subject**, its **cases**, and a **snapshot** to read.

A fork is a node whose outgoing edges are the cases of a subject; the interpreter asks the
subject which case the snapshot is in and takes that edge, so a path that depends on a setting is
drawn in the diagram rather than decided by an `if` in a handler. **The subject is the strategy**:
a setting today; a parameter, a fact or a property of the plan later, each one more subclass and
no change to the interpreter. Pure: the snapshot is plain data the shell builds.
"""

from comeni_core.settings.declare import Kind, Setting
from pydantic import BaseModel, ConfigDict, JsonValue

DEFAULT = "*"
"""The case an open subject's fallback edge names. No option can be `*`."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Snapshot(_Frozen):
    """What a fork may read, as plain data. A field per kind of subject, as they arrive."""

    settings: dict[str, JsonValue] = {}


class Subject(_Frozen):
    """What a fork switches on. Subclass it; the interpreter only calls these two methods."""

    title: str
    """What the diamond says."""

    def options(self) -> frozenset[str] | None:
        """The closed set of cases, or `None` for an open domain (which then needs `DEFAULT`)."""
        raise NotImplementedError

    def value(self, snapshot: Snapshot) -> str:
        """The case `snapshot` is in."""
        raise NotImplementedError


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

    def value(self, snapshot: Snapshot) -> str:
        raw = snapshot.settings.get(self.key, self.default)
        if isinstance(raw, bool):
            return "on" if raw else "off"
        if raw is None and self.cases == {"on", "off"}:
            return "off"
        return str(raw)
