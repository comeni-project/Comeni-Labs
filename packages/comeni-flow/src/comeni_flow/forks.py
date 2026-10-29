"""What a fork switches on. The flow defines its subjects and the snapshot they read.

A fork delegates case selection to its subject, so a condition is part of the validated
protocol rather than a hidden branch in a handler. The engine never looks inside a snapshot.
"""

from pydantic import BaseModel, ConfigDict

DEFAULT = "*"
"""The case an open subject's fallback edge names. No option can be `*`."""


class Subject(BaseModel):
    """What a fork switches on. Subclass it; the interpreter only calls these two methods."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    """What the diamond says."""

    @property
    def key(self) -> str | None:
        """The snapshot key the shell must resolve for this subject, if any."""
        return None

    def options(self) -> frozenset[str] | None:
        """The closed set of cases, or `None` for an open domain (which then needs `DEFAULT`)."""
        raise NotImplementedError

    def value(self, snapshot) -> str:
        """The case `snapshot` is in. The snapshot's type is the flow's."""
        raise NotImplementedError
