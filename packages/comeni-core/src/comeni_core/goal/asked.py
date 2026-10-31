"""Validated models for what a build has, wants, and may constrain.

A goal carries data shape rather than patient data: declared type identifiers, states,
measurements, and routing choices. Every model rejects unknown fields so filenames, sample
identifiers, paths, and other undeclared payloads cannot pass through silently.

`DataProfile` and `Measured` live in :mod:`comeni_core.goal.profile` and are re-exported here
for callers that construct complete goals.
"""

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from comeni_core.declared.signature import states_in_type
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
