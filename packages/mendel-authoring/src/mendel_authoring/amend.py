"""Frozen amendments that update a goal before the pipeline is resolved again.

Tool choices become producer pins and facts replace the validated profile. Keeping decisions in
the goal makes the next blueprint a deterministic result of the amended goal and registry.
"""

from comeni_core.goal.asked import Goal, ProducerPin
from comeni_core.goal.profile import DataProfile
from comeni_core.spell.marks import ParamValue
from pydantic import BaseModel, ConfigDict


class ChooseTool(BaseModel):
    """Use this tool at its site: adds the pin, or replaces the one already there."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pin: ProducerPin

    def apply(self, goal: Goal) -> Goal:
        kept = [p for p in goal.constraints.producers if p.site != self.pin.site]
        constraints = goal.constraints.model_copy(update={"producers": [*kept, self.pin]})
        return goal.model_copy(update={"constraints": constraints})

    def says(self) -> str:
        return f"use {self.pin.contract} to make {self.pin.site.type_id}"


class SetFact(BaseModel):
    """A fact a rule lacked. **`profile` is built by the shell**, through the measurement
    registry, before the amendment exists — nothing else may construct a `DataProfile`
    (invariant 15) — so `apply` only swaps it in, and stays pure like every other `apply`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: str
    value: ParamValue
    profile: DataProfile

    def apply(self, goal: Goal) -> Goal:
        return goal.model_copy(update={"profile": self.profile})

    def says(self) -> str:
        return f"{self.measurement} is {self.value}"


Amendment = ChooseTool | SetFact
