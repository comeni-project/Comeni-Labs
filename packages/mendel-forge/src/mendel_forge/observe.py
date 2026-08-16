"""What a source proved about a tool, and where each fact was read from.

Source-neutral by construction: an `Observation` names facts by string, so an adapter
for a source nobody has written yet does not need this file changed. It holds no
opinions about contracts — turning facts into a contract's fields is `scaffold.py`'s
job, and keeping the two apart is what lets a second source exist at all.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

_NO_EXTRAS = ConfigDict(extra="forbid")


class Excerpt(BaseModel):
    """A span of source text and a resolvable pointer to it.

    `locator` is a `file:line` or a URL — never a bare claim. The rule drafter's §3.2
    makes the same demand of a citation for the same reason: a reviewer approving
    something is approving that the quoted text supports it, and they cannot do that
    without the text.

    **A file locator is relative to the root it was read under, never absolute.** An
    absolute one carries the machine into every draft and every golden file, which is the
    defect issue #46 found in `digest_of_directory` — and it was a golden file that caught
    it here too, on the first one written.

    **`text` is weaker than this docstring asks for, today.** The nf-core source sets one
    excerpt per fact naming the process and the file rather than quoting the line the fact
    was read from, because `ModuleSpec` records no line numbers. That is enough to find the
    evidence and not enough to read it without opening the file — a real gap, and the right
    place to close it is `ModuleSpec`, so that conformance diagnostics gain line numbers at
    the same time.
    """

    model_config = _NO_EXTRAS

    locator: str
    text: str


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
