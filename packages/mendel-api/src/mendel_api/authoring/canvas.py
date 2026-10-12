"""A coherent visible frame and a saved, unapplied alternative."""

from comeni_core.plan.draft import DraftGraph
from pydantic import BaseModel, ConfigDict, model_validator

from mendel_api.authoring.envelopes import OfferContext
from mendel_api.services.build import ChannelView, StepView


class CanvasFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: OfferContext
    proposal_id: str | None
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


class AlternativePreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str
    contract: str
    frame: CanvasFrame
    observed_context: OfferContext

    @model_validator(mode="after")
    def _contract_present(self):
        if self.contract not in {s.contract_id for s in self.frame.steps}:
            raise ValueError("alternative contract must occur in its saved view")
        return self


def checked_previews(values: dict, payload: dict, proposal_id: str) -> dict:
    """Bind typed snapshots to the exact immutable offer that produced them."""
    from mendel_api.authoring.envelopes import StepOffer

    offer = StepOffer.model_validate(payload)
    parsed = {key: AlternativePreview.model_validate(value) for key, value in values.items()}
    if set(parsed) != set(offer.preview_options):
        raise ValueError("snapshot keys must match announced previews")
    for key, value in parsed.items():
        if (value.option_id != key or value.contract != offer.options.get(key)
                or value.frame.context != offer.context
                or value.frame.proposal_id != proposal_id):
            raise ValueError("snapshot must match its fixed offer")
    return {key: value.model_dump(mode="json") for key, value in parsed.items()}
