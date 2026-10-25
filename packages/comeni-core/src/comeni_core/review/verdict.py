"""Represent validation findings without deciding whether a workflow should proceed.

Review reports all findings in one pass. Callers own refusal and gate policy. The module depends
only on diagnostics and spell-level identifiers so :mod:`comeni_core.plan` can depend on review
without creating a cycle.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from comeni_core.diagnostics import REGISTRY
from comeni_core.spell.marks import EdgeRef, NodeId, PortName

__all__ = ["Finding", "Level", "Verdict"]


class Level(StrEnum):
    """Severity and workflow meaning of a review finding."""

    ILLEGAL = "illegal"
    """The graph violates a rule and cannot be emitted."""

    UNMET = "unmet"
    """A requirement is incomplete but the draft itself remains legal."""

    ADVISORY = "advisory"
    """The graph is legal but differs from a convention or preferred choice."""


class Finding(BaseModel):
    """One declared diagnostic with optional node, port, and edge-endpoint context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    level: Level
    message: str

    node: NodeId | None = None
    port: PortName | None = None

    source: EdgeRef | None = None
    """Upstream endpoint in ``<node>.<port>`` form."""

    target: EdgeRef | None = None
    """Consuming endpoint in ``<node>.<port>`` form."""

    @field_validator("code")
    @classmethod
    def _declared(cls, code: str) -> str:
        """Reject diagnostic codes absent from the package registry."""
        if code not in REGISTRY:
            raise ValueError(
                f"{code} is not a declared diagnostic. Declare it in comeni_core/"
                f"diagnostics.yml, or fix the code."
            )
        return code


class Verdict(BaseModel):
    """A complete collection of validation findings."""

    model_config = ConfigDict(extra="forbid")

    findings: list[Finding] = []

    @property
    def illegal(self) -> list[Finding]:
        """Return only findings that make the graph illegal."""
        return [f for f in self.findings if f.level is Level.ILLEGAL]

    @property
    def emittable(self) -> bool:
        """Return whether the verdict contains no illegal findings.

        This does not mean the draft is complete: callers separately handle ``UNMET`` findings.
        """
        return not self.illegal
