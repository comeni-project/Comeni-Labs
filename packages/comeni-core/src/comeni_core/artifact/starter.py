"""The minimal version-8 pipeline document accepted as build input.

A starter contains only intent and facts. ``mendel build`` resolves it into the complete pipeline
artifact, keeping person-authored and generated inputs on one serialized format.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from comeni_core.goal.asked import Facts, Goal, Intent


class Starter(BaseModel):
    """What is wanted and what is known; no steps, registry, `ai` or `emitted` yet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[8] = 8
    intent: Intent
    facts: Facts

    @property
    def goal(self) -> Goal:
        return Goal.of(self.intent, self.facts)
