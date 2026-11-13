"""Validated models for what a build has, wants, and may constrain.

A goal carries data shape rather than patient data: declared type identifiers, states,
measurements, and routing choices. Every model rejects unknown fields so filenames, sample
identifiers, paths, and other undeclared payloads cannot pass through silently.

`DataProfile` and `Measured` live in :mod:`comeni_core.goal.profile` and are re-exported here
for callers that construct complete goals.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from comeni_core.declared.signature import states_in_type
from comeni_core.goal.profile import DataProfile, Measured  # noqa: F401  (re-exported)
from comeni_core.spell.marks import (
    ChannelName,
    ContractId,
    HumanParamValue,
    MeasurementId,
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
    """One available input, described by type, optional channel name, and states."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_id: TypeId
    name: ChannelName | None = None
    """The input channel, or ``None`` for a name derived from the type identifier.

    Multiple inputs of one type must be named explicitly; downstream materialisation rejects
    derived channel-name collisions.
    """
    states: frozenset[StateName] = frozenset()

    @field_serializer("states")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class ParamOverride(BaseModel):
    """A validated human parameter override.

    The closed value type prevents arbitrary path-bearing values from entering a goal.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: PortName
    value: HumanParamValue
    """A value accepted from a person-authored goal file."""


class RequiredStates(BaseModel):
    """A wanted output type and the states it must carry.

    The record form keeps payload keys declared and validated. ``Constraints`` still accepts a
    mapping shorthand when reading person-authored goal files.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_id: TypeId
    states: list[StateName] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _carried(cls, data: object) -> object:
        return states_in_type(data, "states")


class Site(BaseModel):
    """A routing location identified by output type and required states."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_id: TypeId
    states: frozenset[StateName] = frozenset()

    @field_serializer("states")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class ProducerPin(BaseModel):
    """A person's producer choice at a routing site.

    The router applies it before rules and records a differing choice as a human override.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    site: Site
    contract: ContractId


class RoleAbsence(BaseModel):
    """A role disabled by a person, excluding every contract that fills it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: RoleName


class ProducerExclusion(BaseModel):
    """A producer excluded at one site.

    The router uses another candidate or reports a conflict when none remains.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    site: Site
    contract: ContractId


class SourcePin(BaseModel):
    """A person's choice of producer for one consumer port."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    consumer: ContractId
    port: PortName
    producer: ContractId


class InputState(StrEnum):
    """Whether a tool's optional input is part of the pipeline (#460).

    `off` leaves it out. `optional` makes it a pipeline input each run may supply or leave
    empty. `required` makes every run supply it, or wires it from another step."""

    OFF = "off"
    OPTIONAL = "optional"
    REQUIRED = "required"


class InputChoice(BaseModel):
    """A person's choice for one optional input of one tool. Like `SourcePin`, it is the
    person's by being in the goal's constraints, so it carries no `by`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract: ContractId
    port: PortName
    state: InputState


class Constraints(BaseModel):
    """The complete closed set of routing and parameter choices in a goal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    required_states: list[RequiredStates] = Field(default_factory=list)
    params: list[ParamOverride] = Field(default_factory=list)
    producers: list[ProducerPin] = Field(
        default_factory=list, exclude_if=lambda producers: not producers
    )
    """Chosen producers, omitted from serialized output when empty."""
    absent_roles: list[RoleAbsence] = Field(
        default_factory=list, exclude_if=lambda absent: not absent
    )
    """Disabled roles, omitted from serialized output when empty."""
    exclusions: list[ProducerExclusion] = Field(
        default_factory=list, exclude_if=lambda exclusions: not exclusions
    )
    """Excluded producers, omitted from serialized output when empty."""
    sources: list[SourcePin] = Field(default_factory=list, exclude_if=lambda sources: not sources)
    """Pinned port sources, omitted from serialized output when empty."""
    inputs: list[InputChoice] = Field(default_factory=list, exclude_if=lambda inputs: not inputs)
    """Optional inputs a person switched on or off, omitted from serialized output when empty."""
    varies: list[MeasurementId] = Field(default_factory=list, exclude_if=lambda varies: not varies)
    """Per-sample facts a person said differ between samples (#466): each sample's value comes
    from its samplesheet cell or a measurement in the run, never one value for all. Sorted."""

    units: list[TypeId] = Field(default_factory=list, exclude_if=lambda units: not units)
    """Inputs whose rows may repeat a sample, such as a sample sequenced over several lanes
    (#466): the build merges each sample's rows before anything reads them. Sorted."""

    whole: list[ContractId] = Field(default_factory=list, exclude_if=lambda whole: not whole)
    """Tools a person keeps whole (#466): a step that could run on parts of a sample is not
    split. Sorted."""

    @model_validator(mode="after")
    def _varies_sorted(self) -> "Constraints":
        object.__setattr__(self, "varies", sorted(set(self.varies)))
        object.__setattr__(self, "units", sorted(set(self.units)))
        object.__setattr__(self, "whole", sorted(set(self.whole)))
        return self

    @model_validator(mode="before")
    @classmethod
    def _accept_mapping(cls, data: object) -> object:
        """Convert the concise goal-file mapping to the declared record representation."""
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

    def input_at(self, contract: str, port: str) -> InputChoice | None:
        """The person's choice for `contract`'s optional `port`: the last one wins."""
        return next(
            (c for c in reversed(self.inputs) if (c.contract, c.port) == (contract, port)), None
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
    """The resolver input, combining desired outputs with known input facts."""

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
    """Desired output types and the person's explicit constraints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    want: list[TypeId] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)


class Facts(BaseModel):
    """Available inputs and measurements, including measurement provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    inputs: list[GoalInput] = Field(default_factory=list)
    measurements: list[Measured] = Field(default_factory=list)
