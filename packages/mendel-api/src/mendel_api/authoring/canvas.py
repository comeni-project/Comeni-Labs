"""The canvas as one coherent frame: the steps, their wires and where each sits."""

from comeni_core.plan.draft import DraftGraph
from pydantic import BaseModel, ConfigDict, Field, model_validator

from mendel_api.services.build import ChannelView, StepView


class OfferContext(BaseModel):
    """What the frame was drawn against, so a stale frame is recognisable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draft_revision: int = Field(ge=0)
    decision_revision: int = Field(ge=0)
    session_version: int = Field(ge=0)
    registry: str


class CanvasFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: OfferContext
    current: bool
    graph: DraftGraph
    steps: list[StepView]
    channels: list[ChannelView]
    placement: dict[str, dict[str, int]]

    @model_validator(mode="after")
    def _coherent(self):
        nodes = {n.id: n.contract_id for n in self.graph.nodes}
        steps = {s.id: s.contract_id for s in self.steps}
        if len(nodes) != len(self.graph.nodes) or len(steps) != len(self.steps) or nodes != steps:
            raise ValueError("frame nodes and step metadata must agree uniquely")
        if set(self.placement) != set(nodes):
            raise ValueError("every visible node needs a position")
        keys = [(e.from_node, e.from_port, e.to_node, e.to_port) for e in self.graph.edges]
        if len(keys) != len(set(keys)) or any(
            e.from_node not in nodes or e.to_node not in nodes for e in self.graph.edges
        ):
            raise ValueError("frame wires must be unique and visible")
        ports = {f"{s.id}.{p.name}" for s in self.steps for p in s.ports if p.side == "in"}
        if any(not c.ports or not set(c.ports) <= ports for c in self.channels):
            raise ValueError("channels must feed visible input ports")
        return self
