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
    HumanParamValue,
    PortName,
    StateName,
    TypeId,
)

__all__ = ["Constraints", "DataProfile", "Goal", "GoalInput", "Measured", "ParamOverride"]


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
