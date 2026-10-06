"""What a person — or, in part 4, a model — can change about a pipeline in the walk.

Each amendment is a frozen value applied to the goal, so **the goal holds every decision** and
the blueprint is a function of it (§14.3 of the consultant build): same goal in, same pipeline
out, with the person's choices included. A card offers amendments by id, and nothing outside
what it offered can be sent.
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
