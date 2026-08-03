"""The pipeline IR: resolver output, compiler input, and what tests assert on."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    model_validator,
)

from comeni_core.decision import DecisionRecord
from comeni_core.marks import (
    ContractId,
    NodeId,
    ParamValue,
    PortName,
    StateName,
    Text,
    TypeId,
)
from comeni_core.tiers import ReviewLevel, Tier, review_level_for


class ResolvedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: ParamValue
    tier: Tier
    reason: Text
    """Why this value was chosen. Prose, and declared as such — it reaches an egress
    payload through `RepairRequest.ir`, so `tests/test_egress.py` names it explicitly
    rather than letting it ride along unexamined."""

    @computed_field
    @property
    def review_level(self) -> ReviewLevel:
        return review_level_for(self.tier)


class ParamBinding(BaseModel):
    """One resolved parameter. A list rather than a dict on purpose.

    `tests/test_egress.py` forbids mappings in anything reachable from a payload, because
    a typed key does not prove a *declared* key — `{"patient_id": ...}` type-checks
    perfectly against `dict[str, ResolvedValue]`. A list of records carries the same
    information and can be inspected field by field.
    """

    model_config = ConfigDict(extra="forbid")

    name: PortName
    value: ResolvedValue


class IRNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    contract_id: ContractId
    params: list[ParamBinding] = Field(default_factory=list)

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


class PipelineIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[IRNode] = Field(default_factory=list)
    edges: list[IREdge] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)

    def needs_review(self) -> list[str]:
        """Everything a human must look at before this pipeline runs.

        Covers decisions as well as parameters. A routing tie emits a DecisionRecord
        at tier 4 — invariant 8 demotes it, invariant 6 says tier 4 is always flagged
        — but for a while this method scanned only node params, so the CLI reported
        "0 requiring review" while an aligner had been chosen alphabetically. A record
        nobody is shown is not a flag.
        """
        flagged = [
            f"{node.id}.{binding.name}"
            for node in self.nodes
            for binding in node.params
            if binding.value.review_level is ReviewLevel.REQUIRED
        ]
        flagged += [
            decision.key
            for decision in self.decisions
            if review_level_for(decision.tier) is ReviewLevel.REQUIRED
            and decision.key not in flagged
        ]
        return flagged
