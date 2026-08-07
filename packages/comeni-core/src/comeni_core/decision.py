"""Decision records: what was ambiguous, what was chosen, and why."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.marks import (
    DecisionKey,
    HumanParamValue,
    Line,
    NodeId,
    ParamValue,
    ResolverId,
    Subject,
)
from comeni_core.tiers import Tier


class Ambiguity(BaseModel):
    """A question the deterministic ladder could not answer."""

    node_id: NodeId
    subject: Subject
    candidates: list[Any] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    def key(self) -> str:
        return f"{self.node_id}.{self.subject}"


class Resolution(BaseModel):
    chosen: ParamValue
    reason: Line
    confidence: float = 0.0
    resolved_by: str = "flag-only"


class DecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: DecisionKey
    subject: Subject
    candidates: list[ParamValue] = Field(default_factory=list)
    chosen: ParamValue
    reason: Line
    """Model- or resolver-written prose. Declared free text; see `ResolvedValue.reason`."""
    confidence: float = 0.0
    resolved_by: ResolverId
    tier: Tier = Tier.AMBIGUOUS
    human_override: HumanParamValue = None
    """A reviewer's answer, so it is guarded against path-shaped values. Audit A3."""
