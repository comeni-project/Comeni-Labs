"""Resolved pipeline representation shared by the resolver, artifacts, and compiler."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    model_validator,
)

from comeni_core.declared.layered import Displacement
from comeni_core.goal.asked import Site
from comeni_core.goal.premise import PremiseRecord
from comeni_core.goal.profile import DataProfile
from comeni_core.plan.decision import DecisionRecord
from comeni_core.plan.tiers import ReviewLevel, Tier, ValueSource, review_level_for
from comeni_core.spell.marks import (
    ChannelName,
    ContractId,
    LayerName,
    Line,
    NodeId,
    ParamValue,
    PortName,
    SocketKey,
    StateName,
    TypeId,
)


def _still_open(value: "ResolvedValue") -> bool:
    """Return whether a required-review value has not been answered by a human."""
    return (
        value.review_level is ReviewLevel.REQUIRED and value.source is not ValueSource.HUMAN
    )


class ResolvedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _drop_computed(cls, data: object) -> object:
        """Ignore serialized `review_level`; it is always derived from `tier`."""
        if isinstance(data, dict) and "review_level" in data:
            data = {k: v for k, v in data.items() if k != "review_level"}
        return data

    value: ParamValue
    tier: Tier
    source: ValueSource = ValueSource.RESOLVER
    reason: Line
    """Declared free-text explanation for the selected value."""

    premise: list[PremiseRecord] = Field(default_factory=list)
    """Facts consulted by the resolver when selecting this value."""

    axis_reason: Line = ""
    """Methodology for the decision axis; `reason` separately explains why this value won."""

    from_layer: LayerName | None = None
    """Registry layer that supplied the selected contract or rule; `None` for no layer."""

    displaced_layer: LayerName | None = None
    """Lower layer displaced by this value, when an overlay changed an existing route."""

    @computed_field
    @property
    def review_level(self) -> ReviewLevel:
        return review_level_for(self.tier)


class ParamBinding(BaseModel):
    """One resolved parameter represented as a typed record for safe egress."""

    model_config = ConfigDict(extra="forbid")

    name: PortName
    value: ResolvedValue


class IRNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    contract_id: ContractId
    site: Site | None = Field(default=None, exclude=True)
    """In-memory routing site used by authoring; excluded from serialization."""
    params: list[ParamBinding] = Field(default_factory=list)
    selection: ResolvedValue = Field(
        default_factory=lambda: ResolvedValue(
            value=None, tier=Tier.STRUCTURAL, reason="only one contract can produce this"
        )
    )
    """Selected contract value, resolution tier, provenance, and reason."""

    presence: ResolvedValue = Field(
        default_factory=lambda: ResolvedValue(
            value=None, tier=Tier.STRUCTURAL, reason="required by the pipeline"
        )
    )
    """Why the step exists, independently of which contract was selected for it."""

    @model_validator(mode="before")
    @classmethod
    def _accept_mapping(cls, data: object) -> object:
        """`params={"strandedness": ...}` still works; it is stored as bindings.

        The list is what the egress guard requires, but a mapping is the natural way to
        write one, so the ergonomic form survives the representation change.
        """
        if isinstance(data, dict) and isinstance(data.get("params"), dict):
            data = dict(data)
            data["params"] = [{"name": k, "value": v} for k, v in data["params"].items()]
        return data

    def param(self, name: str) -> ResolvedValue | None:
        return next((b.value for b in self.params if b.name == name), None)

    def set_param(self, name: str, value: ResolvedValue) -> None:
        self.params.append(ParamBinding(name=name, value=value))


class IREdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_node: NodeId
    from_port: PortName
    to_node: NodeId
    to_port: PortName
    type_id: TypeId
    states: frozenset[StateName] = frozenset()

    @field_serializer("states")
    def _sorted_states(self, states: frozenset[str]) -> list[StateName]:
        return sorted(states)


class IRChannel(BaseModel):
    """One channel and the sockets it feeds. The resolved form of a `DraftChannel`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: ChannelName
    type_id: TypeId

    scope: ResolvedValue | None = None
    """Resolved scope override, or `None` when the type's declared default applies."""

    ports: list[SocketKey] = Field(default_factory=list)
    """Sorted `<node>.<port>` sockets fed by this channel."""


class PipelineIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[IRNode] = Field(default_factory=list)
    edges: list[IREdge] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)

    channels: list[IRChannel] = Field(default_factory=list)
    """Resolved channel groups; empty means one channel per type."""

    profile: DataProfile = Field(default_factory=DataProfile)
    """Measurements used to resolve the pipeline and populate emitted metadata."""

    registry_layers: list[LayerName] = Field(default_factory=list)
    """Registry layers in stacking order; later layers have higher precedence."""

    displaced: list[Displacement] = Field(default_factory=list)
    """Declared data replaced or extended by higher registry layers."""

    unverified: list[ContractId] = Field(default_factory=list)
    """Contracts whose module source was unavailable for conformance checking."""

    def needs_review(self) -> list[str]:
        """Return unresolved parameter, module-selection, and decision keys requiring review."""
        flagged = [
            f"{node.id}.{binding.name}"
            for node in self.nodes
            for binding in node.params
            if _still_open(binding.value)
        ]
        # Module selections are shown by node even when a related decision record also exists.
        flagged += [
            f"{node.id} (module)" for node in self.nodes if _still_open(node.selection)
        ]
        answered = {key for key, _ in self._overrides()}
        flagged += [
            decision.key
            for decision in self.decisions
            if review_level_for(decision.tier) is ReviewLevel.REQUIRED
            and decision.key not in flagged
            and decision.key not in answered
        ]
        return flagged

    def overrides(self) -> list[str]:
        """Return human-answered tier-four values omitted from `needs_review`."""
        return [f"{key} = {value!r}" for key, value in self._overrides()]

    def _overrides(self) -> list[tuple[str, object]]:
        """Collect human answers using the same keys as `needs_review`."""
        found = [
            (f"{node.id}.{binding.name}", binding.value.value)
            for node in self.nodes
            for binding in node.params
            if binding.value.source is ValueSource.HUMAN
        ]
        found += [
            (f"{node.id} (module)", node.contract_id)
            for node in self.nodes
            if node.selection.source is ValueSource.HUMAN
        ]
        # Decision keys and reviewer-facing module keys differ; deduplicate only exact keys.
        seen = {key for key, _ in found}
        found += [
            (decision.key, decision.human_override)
            for decision in self.decisions
            if getattr(decision, "human_override", None) is not None
            and decision.key not in seen
        ]
        return found

    def overlay_reroutes(self) -> list[str]:
        """Describe module and parameter routes changed by higher registry layers."""
        lines = [
            f"{node.id} (module) = {node.contract_id}: from "
            f"{node.selection.from_layer!r}, displacing {node.selection.displaced_layer!r}"
            for node in self.nodes
            if node.selection.displaced_layer is not None
        ]
        lines += [
            f"{node.id}.{binding.name} = {binding.value.value!r}: from "
            f"{binding.value.from_layer!r}, displacing {binding.value.displaced_layer!r}"
            for node in self.nodes
            for binding in node.params
            if binding.value.displaced_layer is not None
        ]
        return lines
