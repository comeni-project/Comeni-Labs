"""User-authored pipeline graph before validation, routing, or materialisation.

A draft records nodes, four-endpoint wires, optional channel groupings, labels, and typed values.
Resolver-derived types, states, tiers, and reasons belong to :mod:`comeni_core.plan.ir` instead.
"""

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.goal.profile import DataProfile
from comeni_core.plan.tiers import Tier
from comeni_core.review.answer import ValueSource
from comeni_core.spell.marks import (
    ContractId,
    DecisionKey,
    HumanParamValue,
    Line,
    NfIdentifier,
    NodeId,
    PortName,
    SocketKey,
)

__all__ = [
    "ChannelSettled",
    "DraftChannel",
    "DraftProvenance",
    "DraftEdge",
    "DraftGraph",
    "DraftLabel",
    "DraftNode",
    "NodeSettled",
    "ParamSettled",
    "Settled",
    "DraftParam",
]


class DraftParam(BaseModel):
    """A safe parameter value and optional reason entered in the builder.

    The client does not assign provenance or tier; materialisation derives those trusted fields.
    """

    model_config = ConfigDict(extra="forbid")

    name: NfIdentifier
    value: HumanParamValue = None
    why: Line = ""
    """User-supplied reason; an empty value means no reason was supplied."""


class DraftEdge(BaseModel):
    """One wire: where it starts, where it ends. Nothing derived."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_node: NodeId
    from_port: PortName
    to_node: NodeId
    to_port: PortName


class DraftLabel(BaseModel):
    """Private canvas label for one socket.

    Labels never rename channel keys, parameters, samplesheet columns, or Nextflow variables and
    do not reach the materialised IR or published artifact.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: SocketKey
    """Input channel name or `<node>.<port>` output socket shown by the canvas."""

    label: Line = ""


class DraftChannel(BaseModel):
    """Sockets explicitly grouped into one input channel.

    Unlisted ports retain the default one-channel-per-type behavior.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: str | None = None
    """Optional `run` or `sample` override; `None` keeps the type's declared default."""

    why: Line = ""
    """Reason for the scope override; ignored when no override is present."""

    ports: tuple[SocketKey, ...]
    """Frozen tuple of `<node>.<port>` sockets fed by this channel."""


class DraftNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    contract_id: ContractId
    params: list[DraftParam] = Field(default_factory=list)


class DraftGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[DraftNode] = Field(default_factory=list)
    edges: list[DraftEdge] = Field(default_factory=list)
    channels: list[DraftChannel] = Field(default_factory=list)
    """Explicit channel groups; empty means one channel per type."""
    labels: list[DraftLabel] = Field(default_factory=list)
    """Private canvas labels that do not affect materialisation."""
    profile: DataProfile = Field(default_factory=DataProfile)
    """Known measurements used when validating advisory rule premises."""


class Settled(BaseModel):
    """Trusted provenance retained for one decision while a draft is edited."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: ValueSource
    tier: Tier
    reason: Line = ""
    axis_reason: Line = ""
    by: Line = ""
    """Model ID when `source` is `MODEL`; empty for other sources."""


class NodeSettled(BaseModel):
    """Independent provenance for a node's presence and selected contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: NodeId
    selection: Settled | None = None
    presence: Settled | None = None


class ParamSettled(BaseModel):
    """Provenance for one setting, keyed as `<node>.<param>`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: DecisionKey
    settled: Settled


class ChannelSettled(BaseModel):
    """Provenance for a scope override, keyed by its stable input sockets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ports: tuple[SocketKey, ...]
    settled: Settled


class DraftProvenance(BaseModel):
    """Server-owned provenance sidecar for draft nodes, parameters, and channels.

    The browser-writable `DraftGraph` does not accept these trusted fields. Typed record lists
    provide validated keys and deterministic ordering; empty lists mean no provenance is recorded.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    nodes: list[NodeSettled] = Field(default_factory=list)
    params: list[ParamSettled] = Field(default_factory=list)
    channels: list[ChannelSettled] = Field(default_factory=list)

    def node(self, node_id: str) -> NodeSettled | None:
        return next((n for n in self.nodes if n.node == node_id), None)

    def param(self, key: str) -> Settled | None:
        return next((p.settled for p in self.params if p.key == key), None)

    def channel(self, ports: tuple[str, ...]) -> Settled | None:
        return next((c.settled for c in self.channels if tuple(c.ports) == tuple(ports)), None)

    def retaining(
        self, *, nodes: set[str], params: set[str], channels: set[tuple[str, ...]]
    ) -> "DraftProvenance":
        """Return a sidecar containing only subjects that remain in the edited graph."""
        return DraftProvenance(
            nodes=[n for n in self.nodes if n.node in nodes],
            params=[p for p in self.params if p.key in params],
            channels=[c for c in self.channels if tuple(c.ports) in channels],
        )
