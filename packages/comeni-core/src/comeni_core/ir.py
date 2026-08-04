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
from comeni_core.profile import DataProfile
from comeni_core.tiers import ReviewLevel, Tier, ValueSource, review_level_for


class ResolvedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _drop_computed(cls, data: object) -> object:
        """Ignore `review_level` on the way in. It is derived, not stored.

        `computed_field` serialises it on dump, and `extra="forbid"` then refuses it on
        load — so the IR did not round-trip at all: `PipelineIR.model_validate_json(
        ir.model_dump_json())` raised. Nothing noticed, because nothing read an IR back
        until now.

        That matters beyond this file. `mendel upgrade` reads a `PublishBundle` off disk
        (Plan 2.5) and the repair loop reads back an IR it sent (Plan 2); both would have
        failed on a field this class computes for itself. Dropping it is right rather than
        merely convenient — the stored value would be a duplicate of `review_level_for(tier)`
        and could disagree with it.
        """
        if isinstance(data, dict) and "review_level" in data:
            data = {k: v for k, v in data.items() if k != "review_level"}
        return data

    value: ParamValue
    tier: Tier
    source: ValueSource = ValueSource.RESOLVER
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
    selection: ResolvedValue = Field(
        default_factory=lambda: ResolvedValue(
            value=None, tier=Tier.STRUCTURAL, reason="only one contract can produce this"
        )
    )
    """How this module was chosen, at which tier, and why.

    Spec §6.1 has always said every module choice exits at exactly one tier; until this
    field existed only parameters were tiered, so a module selected because it was the sole
    producer was indistinguishable from one selected by priority.
    """

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
    profile: DataProfile = Field(default_factory=DataProfile)
    """What was measured about the data this pipeline was built for.

    On the IR rather than passed to the emitter separately, because it is part of what the
    pipeline was built *from* — the same reason Plan 2.5 puts `registry_layers` here. The
    emitter needs it to populate the `meta` map, and a reviewer reading `pipeline.ir.json`
    needs it to know which measurement a tier-3 decision rested on.
    """

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
        # A module choice carries a tier too, since `selection` landed. A tied producer
        # also emits a DecisionRecord, so this would mostly be a duplicate — except the
        # record is keyed on the ambiguity and this is keyed on the node, and a reviewer
        # reading "which modules need looking at" should not have to join the two.
        flagged += [
            f"{node.id} (module)"
            for node in self.nodes
            if node.selection.review_level is ReviewLevel.REQUIRED
        ]
        flagged += [
            decision.key
            for decision in self.decisions
            if review_level_for(decision.tier) is ReviewLevel.REQUIRED
            and decision.key not in flagged
        ]
        return flagged
