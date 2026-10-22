"""What the user has, what they want, and what the data actually looks like.

Invariant 15: Mendel does not receive patient data. A `Goal` describes a *shape* —
type ids, states, and declared measurements. "Paired, 150bp, reverse-stranded, twelve
samples" is true of thousands of studies and identifies nobody. There is no filename
field, no sample identifier field and no path, and `extra="forbid"` on every model
here is what stops one being added by accident: an unrecognised key is a loud error
rather than a quietly carried payload.

Sample identity enters at run time, in the laboratory's own environment, through the
`params.input` placeholder the emitted pipeline declares. It never reaches Mendel's
process. See the clinical data-protection spec, §3.

`DataProfile` and `Measured` are defined in `comeni_core.goal.profile` — a profile is made of
measurements and measurements are declared there — and re-exported here because a goal is
where most code meets one.
"""

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from comeni_core.goal.profile import DataProfile, Measured  # noqa: F401  (re-exported)
from comeni_core.spell.marks import (
    ChannelName,
    ContractId,
    HumanParamValue,
    PortName,
    RoleName,
    StateName,
    TypeId,
)

__all__ = [
    "Constraints",
    "DataProfile",
    "Goal",
    "GoalInput",
    "Measured",
    "ParamOverride",
    "ProducerPin",
    "Site",
]


class GoalInput(BaseModel):
    """One thing the laboratory already has, as a **shape**.

    **A goal names channels rather than types since Plan 5B phase 3**, and that is what lets a
    goal say *I have two annotations* — one for the reference and one per sample — where before
    it could only say *I have an annotation*. `materialise.goal_of` deduplicated by `type_id`
    in one line, and that line was the whole of why two `annotation.gtf` inputs were one hole.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_id: TypeId
    name: ChannelName | None = None
    """This input's channel. **`None` means "derive it"**, which is every goal file written by
    hand and every goal written before phase 3 — the derivation is the type id's last segment
    and is what one-channel-per-type has always produced.

    A goal naming two inputs of one type must name both, because the deduplication that made
    the second one vanish is gone and two unnamed inputs of a type would derive the same name.
    `MD0226` refuses the resulting pipeline rather than letting them merge quietly.

    **`None` rather than `""`.** `ChannelName` is an identifier and an empty one is not a name;
    saying *absent* with a value the type refuses would mean widening the type to carry a
    sentinel, which is how a validated alias stops validating.
    """
    states: frozenset[StateName] = frozenset()

    @field_serializer("states")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class ParamOverride(BaseModel):
    """A parameter the user pinned. Closed, so it cannot carry a path.

    Previously these lived as arbitrary keys in an open `dict[str, Any]`, which meant
    `constraints: {seq_platform: /data/patients/PT-4471023/S1_R1.fastq.gz}` validated,
    reached `main.nf`, was labelled tier 1 with review `none`, and *suppressed* the
    tier-4 flag it replaced. Invariant 15 says no input accepts a path; it did.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: PortName
    value: HumanParamValue
    """Guarded: this is what a person types into a goal file. Audit A3."""


class RequiredStates(BaseModel):
    """States a wanted output must carry.

    A record rather than a mapping key, because `tests/guards/test_egress.py` forbids mappings in
    anything reachable from a payload and `Goal` became reachable when the publication payload
    started carrying one. `dict[TypeId, list[StateName]]` type-checks perfectly while
    saying nothing about whether the key was ever declared.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_id: TypeId
    states: list[StateName] = Field(default_factory=list)


class Site(BaseModel):
    """Where the router chooses a tool: the type it must produce, with these states.

    One identity for a place a tool is chosen — a person's pin, the blueprint's candidates for a
    step, an amendment (§14.3 of the consultant build) — so the three cannot disagree about
    which place they mean.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_id: TypeId
    states: frozenset[StateName] = frozenset()

    @field_serializer("states")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class ProducerPin(BaseModel):
    """A person's tool at a site. Honoured by the router before any rule, and recorded as the
    person's at tier 4 when it differs from the engine's pick (invariant 6): the step is then no
    longer proven from the data, and a reader sees who decided."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    site: Site
    contract: ContractId


class RoleAbsence(BaseModel):
    """A role a person switched off: no step fills it (A1, the one-builder design). The same
    semantics as a rule's `presence: absent`, so the router drops every contract filling it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: RoleName


class ProducerExclusion(BaseModel):
    """A tool a person excluded at a site (A1). The router takes the next candidate there; if
    none is left, the conflict is raised rather than resolved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    site: Site
    contract: ContractId


class SourcePin(BaseModel):
    """Which tool a person chose to feed a step's port (A1): the consumer's contract, its port,
    and the producer whose output feeds it. Recorded as the person's at tier 4."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    consumer: ContractId
    port: PortName
    producer: ContractId


class Constraints(BaseModel):
    """Everything a goal may pin. `extra="forbid"` is the whole point of the type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    required_states: list[RequiredStates] = Field(default_factory=list)
    params: list[ParamOverride] = Field(default_factory=list)
    producers: list[ProducerPin] = Field(
        default_factory=list, exclude_if=lambda producers: not producers
    )
    """Tools a person chose, each at its site. **Omitted from a dump when empty**, so a goal
    with none emits exactly the bytes it did before the field existed (invariant 10)."""
    absent_roles: list[RoleAbsence] = Field(
        default_factory=list, exclude_if=lambda absent: not absent
    )
    """Roles a person switched off. Omitted when empty, as `producers` is."""
    exclusions: list[ProducerExclusion] = Field(
        default_factory=list, exclude_if=lambda exclusions: not exclusions
    )
    """Tools a person excluded, each at its site. Omitted when empty."""
    sources: list[SourcePin] = Field(default_factory=list, exclude_if=lambda sources: not sources)
    """Ports whose source a person chose. Omitted when empty."""

    @model_validator(mode="before")
    @classmethod
    def _accept_mapping(cls, data: object) -> object:
        """`required_states: {counts.matrix: [gene_level]}` still works.

        A mapping is the natural way to *write* one in a goal file, and every existing
        goal and test does. The list is what the guard requires; this keeps the ergonomic
        form and the safe representation from being the same decision. Same pattern as
        `IRNode.params` and `DataProfile.measurements`.
        """
        if isinstance(data, dict) and isinstance(data.get("required_states"), dict):
            data = dict(data)
            data["required_states"] = [
                {"type_id": k, "states": v} for k, v in sorted(data["required_states"].items())
            ]
        return data

    def producer_at(self, site: Site) -> ProducerPin | None:
        """The pin at `site`: the last one, so a later amendment wins."""
        return next((p for p in reversed(self.producers) if p.site == site), None)

    def excluded_at(self, site: Site) -> frozenset[str]:
        """The tools a person excluded at `site`, and nowhere else."""
        return frozenset(e.contract for e in self.exclusions if e.site == site)

    def source_at(self, consumer: str, port: str) -> SourcePin | None:
        """The pin on `consumer`'s `port`: the last one, so a later amendment wins."""
        return next(
            (p for p in reversed(self.sources) if (p.consumer, p.port) == (consumer, port)), None
        )

    def roles_absent(self) -> frozenset[str]:
        return frozenset(absence.role for absence in self.absent_roles)

    def states_for(self, type_id: str) -> frozenset[StateName]:
        return frozenset(
            state
            for required in self.required_states
            if required.type_id == type_id
            for state in required.states
        )


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    have: list[GoalInput] = Field(default_factory=list)
    want: list[TypeId] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    profile: DataProfile = Field(default_factory=DataProfile)

    @property
    def intent(self) -> "Intent":
        return Intent(want=self.want, constraints=self.constraints)

    @property
    def facts(self) -> "Facts":
        return Facts(inputs=self.have, measurements=self.profile.measurements)

    @classmethod
    def of(cls, intent: "Intent", facts: "Facts") -> "Goal":
        """The resolver's input, projected from what is wanted and what is known."""
        return cls.model_validate({"have": facts.inputs, "want": intent.want,
                                   "constraints": intent.constraints,
                                   "profile": {"measurements": facts.measurements}})


class Intent(BaseModel):
    """What is wanted: the types to end with, and what the person pinned (spec §8.1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    want: list[TypeId] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)


class Facts(BaseModel):
    """What is known: the inputs held, and each measurement with its source (spec §8.1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    inputs: list[GoalInput] = Field(default_factory=list)
    measurements: list[Measured] = Field(default_factory=list)
