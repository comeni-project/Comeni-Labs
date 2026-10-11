"""Selected answers compose a goal; observations and attribution stay outside its shape.

Pure values only. The API owns revisions and evidence records; the measurement registry
validates the profile through its existing constructor, including heterogeneous origins.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol, Self

from comeni_core.declared.measurement import MeasuredEntry
from comeni_core.goal.asked import (
    Constraints,
    Goal,
    GoalInput,
    ParamOverride,
    ProducerPin,
    RequiredStates,
    Site,
)
from comeni_core.goal.profile import DataProfile, Evidence
from comeni_core.plan.tiers import ValueSource
from comeni_core.spell.marks import (
    ContractId,
    MeasurementId,
    ParamValue,
    PieceRef,
    PortName,
    TypeId,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActorKind(StrEnum):
    PERSON = "person"
    MODEL = "model"
    RESOLVER = "resolver"
    UNKNOWN = "unknown"


class FactOrigin(StrEnum):
    PERSON_SAID = "person_said"
    MEASURED = "measured"
    MODEL_READ = "model_read"
    OPEN = "open"


class _Value(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Attribution(_Value):
    kind: ActorKind
    who: str = Field(default="", max_length=200)
    legacy: bool = False

    @model_validator(mode="after")
    def _unknown_is_legacy(self) -> Self:
        if self.kind is ActorKind.UNKNOWN and not self.legacy:
            raise ValueError("unknown attribution is only available for legacy records")
        return self


class InputDecision(_Value):
    key: str
    type_id: TypeId
    name: str | None = None
    states: list[str] = Field(default_factory=list)
    present: bool = True
    origin: FactOrigin = FactOrigin.PERSON_SAID


class WantDecision(_Value):
    type_id: TypeId
    states: list[str] = Field(default_factory=list)
    present: bool = True


class FactDecision(_Value):
    subject: MeasurementId
    value: ParamValue | list[ParamValue] | None = None
    origin: FactOrigin = FactOrigin.PERSON_SAID
    by: ContractId | None = None
    pieces: list[PieceRef] = Field(default_factory=list)
    evidence: Evidence | None = None

    @model_validator(mode="after")
    def _unknown_has_no_value(self) -> Self:
        if self.origin is FactOrigin.OPEN and self.value is not None:
            raise ValueError("an unknown fact cannot carry a value")
        if self.origin is not FactOrigin.OPEN and self.value is None:
            raise ValueError("a known fact needs a value; select unknown to retract it")
        return self


class ProducerChoice(_Value):
    site: Site
    contract: ContractId | None = None


class ParameterChoice(_Value):
    name: PortName
    value: ParamValue | None = None


class Profiles(Protocol):
    def profile_of(self, entries: Sequence[MeasuredEntry]) -> DataProfile: ...


_SOURCE = {
    FactOrigin.PERSON_SAID: ValueSource.GOAL,
    FactOrigin.MEASURED: ValueSource.MEASURED,
    FactOrigin.MODEL_READ: ValueSource.MODEL,
}
_ORIGIN = {source: origin for origin, source in _SOURCE.items()}


class Decisions(_Value):
    inputs: list[InputDecision] = Field(default_factory=list)
    wants: list[WantDecision] = Field(default_factory=list)
    facts: list[FactDecision] = Field(default_factory=list)
    producers: list[ProducerChoice] = Field(default_factory=list)
    parameters: list[ParameterChoice] = Field(default_factory=list)

    def goal(self, measurements: Profiles) -> Goal:
        """The active goal. Only a declaration-validating registry constructs its profile."""
        return Goal(
            have=[GoalInput(type_id=i.type_id, name=i.name, states=frozenset(i.states))
                  for i in self.inputs if i.present],
            want=[w.type_id for w in self.wants if w.present],
            constraints=Constraints(
                required_states=[RequiredStates(type_id=w.type_id, states=w.states)
                                 for w in self.wants if w.present and w.states],
                params=[ParamOverride(name=p.name, value=p.value)
                        for p in self.parameters if p.value is not None],
                producers=[ProducerPin(site=p.site, contract=p.contract)
                           for p in self.producers if p.contract is not None],
            ),
            profile=measurements.profile_of([
                MeasuredEntry(f.subject, f.value, _SOURCE[f.origin], f.by,
                              tuple(f.pieces), f.evidence)
                for f in self.facts if f.origin is not FactOrigin.OPEN
            ]),
        )

    @classmethod
    def from_goal(cls, goal: Goal) -> Self:
        """Import a confirmed goal without treating its evidence as a fresh observation."""
        return cls(
            inputs=[InputDecision(key=i.name or i.type_id, type_id=i.type_id,
                                  name=i.name, states=sorted(i.states))
                    for i in goal.have],
            wants=[WantDecision(type_id=w, states=sorted(goal.constraints.states_for(w)))
                   for w in goal.want],
            facts=[FactDecision(subject=f.measurement, value=f.value,
                                origin=(_ORIGIN[f.source] if f.value is not None
                                        else FactOrigin.OPEN),
                                by=f.by, pieces=f.pieces, evidence=f.evidence)
                   for f in goal.profile.measurements],
            producers=[ProducerChoice(site=p.site, contract=p.contract)
                       for p in goal.constraints.producers],
            parameters=[ParameterChoice(name=p.name, value=p.value)
                        for p in goal.constraints.params],
        )
