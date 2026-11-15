"""Declare the payload model and flow for each outbound boundary.

This registry describes allowed payload shapes; it does not send data or
intercept transport. Publication uses the saved Pipeline model itself.

Registry projections and filtering take O(b) time and memory for b boundaries.
The registry holds one entry per door; there are no nested scans.
"""

from enum import StrEnum
from typing import NamedTuple

from pydantic import BaseModel

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.egress.agent import AgentRequest
from comeni_core.egress.characterisation import CharacteriseRequest
from comeni_core.egress.forge import ForgeRequest
from comeni_core.egress.repair import RepairRequest
from comeni_core.egress.rules import RuleProposalRequest


class BoundaryFlow(StrEnum):
    """Workflow served by a boundary: pipeline operations, or the forge's."""

    PIPELINE = "pipeline"
    FORGE = "forge"


class Boundary(NamedTuple):
    """Payload model and workflow declared for one outbound boundary."""

    payload: type[BaseModel]
    flow: BoundaryFlow


BOUNDARIES: dict[str, Boundary] = {
    "compiler_repair": Boundary(RepairRequest, BoundaryFlow.PIPELINE),
    "publication": Boundary(Pipeline, BoundaryFlow.PIPELINE),
    # Forge MVP 3 (#364): public module files and registry ids in, drafted items out.
    "forge_drafting": Boundary(ForgeRequest, BoundaryFlow.FORGE),
    "characterisation": Boundary(CharacteriseRequest, BoundaryFlow.PIPELINE),
    # #463: the builder agent's conversation and what its tools return to its model. At level 0
    # a result may carry a sample's name; `tests/fixtures/guard-ledger.md` records why.
    "builder_agent": Boundary(AgentRequest, BoundaryFlow.PIPELINE),
    # #462: people's past answers and the study facts they rested on, a rule row out.
    "rule_proposal": Boundary(RuleProposalRequest, BoundaryFlow.FORGE),
}
"""Single declaration of all outbound boundaries and their payload models."""

PAYLOADS: dict[str, type[BaseModel]] = {
    name: boundary.payload for name, boundary in BOUNDARIES.items()
}
"""Boundary name to payload model, derived from BOUNDARIES."""

FLOWS: dict[str, BoundaryFlow] = {name: boundary.flow for name, boundary in BOUNDARIES.items()}
"""Boundary name to workflow, derived from BOUNDARIES."""


def payloads_for(flow: BoundaryFlow) -> dict[str, type[BaseModel]]:
    """Return payload models for boundaries serving the requested workflow."""
    return {
        name: boundary.payload for name, boundary in BOUNDARIES.items() if boundary.flow is flow
    }
