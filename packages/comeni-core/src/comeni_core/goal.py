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

`DataProfile` and `Measured` are defined in `comeni_core.profile` — a profile is made of
measurements and measurements are declared there — and re-exported here because a goal is
where most code meets one.
"""

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from comeni_core.marks import HumanParamValue, PortName, StateName, TypeId
from comeni_core.profile import DataProfile, Measured  # noqa: F401  (re-exported)

__all__ = ["Constraints", "DataProfile", "Goal", "GoalInput", "Measured", "ParamOverride"]


class GoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type_id: TypeId
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

    A record rather than a mapping key, because `tests/test_egress.py` forbids mappings in
    anything reachable from a payload and `Goal` became reachable when the publication payload
    started carrying one. `dict[TypeId, list[StateName]]` type-checks perfectly while
    saying nothing about whether the key was ever declared.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_id: TypeId
    states: list[StateName] = Field(default_factory=list)


class Constraints(BaseModel):
    """Everything a goal may pin. `extra="forbid"` is the whole point of the type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    required_states: list[RequiredStates] = Field(default_factory=list)
    params: list[ParamOverride] = Field(default_factory=list)

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
