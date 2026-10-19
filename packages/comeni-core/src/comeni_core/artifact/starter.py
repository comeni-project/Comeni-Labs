"""A file to start a build from: `pipeline.yml` version 7 with only `intent` and `facts`
(Part I.0 Plan B, spec §8.5). `mendel build <file>` resolves it and writes the whole file back,
so there is one format, and the no-AI path is writing its top half by hand."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from comeni_core.goal.asked import Facts, Goal, Intent


class Starter(BaseModel):
    """What is wanted and what is known; no steps, registry, `ai` or `emitted` yet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[7] = 7
    intent: Intent
    facts: Facts

    @property
    def goal(self) -> Goal:
        return Goal.of(self.intent, self.facts)
