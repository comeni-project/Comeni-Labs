"""Decision records: what was ambiguous, what was chosen, and why."""

from typing import Any

from pydantic import BaseModel, Field

from comeni_core.ir import Tier


class Ambiguity(BaseModel):
    """A question the deterministic ladder could not answer."""

    node_id: str
    subject: str
    candidates: list[Any] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    def key(self) -> str:
        return f"{self.node_id}.{self.subject}"


class Resolution(BaseModel):
    chosen: Any
    reason: str
    confidence: float = 0.0
    resolved_by: str = "flag-only"


class DecisionRecord(BaseModel):
    key: str
    subject: str
    candidates: list[Any] = Field(default_factory=list)
    chosen: Any
    reason: str
    confidence: float = 0.0
    resolved_by: str
    tier: Tier = Tier.AMBIGUOUS
    human_override: Any = None
