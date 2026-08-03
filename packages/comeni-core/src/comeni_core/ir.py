"""The pipeline IR: resolver output, compiler input, and what tests assert on."""

from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_serializer


class Tier(IntEnum):
    STRUCTURAL = 1
    CONVENTION = 2
    DATA_PROFILED = 3
    AMBIGUOUS = 4


class ReviewLevel(StrEnum):
    NONE = "none"
    ADVISORY = "advisory"
    REQUIRED = "required"


_REVIEW_BY_TIER = {
    Tier.STRUCTURAL: ReviewLevel.NONE,
    Tier.CONVENTION: ReviewLevel.NONE,
    Tier.DATA_PROFILED: ReviewLevel.ADVISORY,
    Tier.AMBIGUOUS: ReviewLevel.REQUIRED,
}


def review_level_for(tier: Tier) -> ReviewLevel:
    return _REVIEW_BY_TIER[tier]


class ResolvedValue(BaseModel):
    value: Any
    tier: Tier
    reason: str

    @computed_field
    @property
    def review_level(self) -> ReviewLevel:
        return review_level_for(self.tier)


class IRNode(BaseModel):
    id: str
    contract_id: str
    params: dict[str, ResolvedValue] = Field(default_factory=dict)


class IREdge(BaseModel):
    from_node: str
    from_port: str
    to_node: str
    to_port: str
    type_id: str
    states: frozenset[str] = frozenset()

    @field_serializer("states")
    def _sorted_states(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class PipelineIR(BaseModel):
    nodes: list[IRNode] = Field(default_factory=list)
    edges: list[IREdge] = Field(default_factory=list)
    decisions: list[Any] = Field(default_factory=list)

    def needs_review(self) -> list[str]:
        """Everything a human must look at before this pipeline runs.

        Covers decisions as well as parameters. A routing tie emits a DecisionRecord
        at tier 4 — invariant 8 demotes it, invariant 6 says tier 4 is always flagged
        — but for a while this method scanned only node params, so the CLI reported
        "0 requiring review" while an aligner had been chosen alphabetically. A record
        nobody is shown is not a flag.
        """
        flagged = [
            f"{node.id}.{name}"
            for node in self.nodes
            for name, value in node.params.items()
            if value.review_level is ReviewLevel.REQUIRED
        ]
        flagged += [
            decision.key
            for decision in self.decisions
            if review_level_for(decision.tier) is ReviewLevel.REQUIRED
            and decision.key not in flagged
        ]
        return flagged
