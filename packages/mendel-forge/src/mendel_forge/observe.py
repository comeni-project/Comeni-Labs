"""What a source proved about a tool, and where each fact was read from.

Source-neutral by construction: an `Observation` names facts by string, so an adapter
for a source nobody has written yet does not need this file changed. It holds no
opinions about contracts — turning facts into a contract's fields is `scaffold.py`'s
job, and keeping the two apart is what lets a second source exist at all.
"""

from typing import Any

# `Excerpt` moved to comeni_core.review.question in Plan 2.5 — a build-path question
# that quotes its evidence needs the same type. Re-exported so call sites here do not move.
from comeni_core.review.question import Excerpt
from pydantic import BaseModel, ConfigDict, Field, field_serializer

_NO_EXTRAS = ConfigDict(extra="forbid")


class Fact(BaseModel):
    """One thing the source says, with the evidence for it.

    `value` is `Any` because a fact is a process name, an arity, a list of emits or a
    container URI. This is not an egress payload — invariant 14's ban on `Any` covers
    what crosses a door, and an `Observation` never does.
    """

    model_config = _NO_EXTRAS

    value: Any
    evidence: Excerpt


class Observation(BaseModel):
    model_config = _NO_EXTRAS

    source: str
    ref_id: str
    facts: dict[str, Fact] = Field(default_factory=dict)
    prose: list[Excerpt] = Field(default_factory=list)
    """Documentation. Unused in Phase 1 beyond display; it is what Phase 2's filler reads."""

    @field_serializer("facts")
    def _sorted(self, facts: dict[str, Fact]) -> dict[str, Fact]:
        """Byte-identical output is a hard requirement, and a dict serialises in insertion
        order — which is parse order, which is not stable across a refactor."""
        return {name: facts[name] for name in sorted(facts)}

    def fact(self, name: str) -> Any | None:
        found = self.facts.get(name)
        return None if found is None else found.value
