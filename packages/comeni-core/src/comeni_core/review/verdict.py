"""What a check reports. **It reports; it does not refuse.**

The precedent is the forge's `verify` ladder. Three problems visible in one pass through the
screen beats three refusals, and the person drawing the graph is mid-gesture rather than at a
gate. Refusal stays where it already lives: `keep` and the emission gates.

`review/` is the right home rather than `plan/` — this is the stage where something is *open*,
and a `Verdict` is the forge's and the resolver's shared answer to "what is still wrong".

**Which is exactly why nothing here may import `plan/`.** `plan/decision.py` imports `Question`
from this package and `plan/tiers.py` imports `ValueSource`; an edge back would be a cycle, and
`tiers.py`'s own comment says so. A finding names each end of a wire with an `EdgeRef` — a
`spell/` alias, below both — and never with a `DraftEdge`.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from comeni_core.diagnostics import REGISTRY
from comeni_core.spell.marks import EdgeRef, NodeId, PortName

__all__ = ["Finding", "Level", "Verdict"]


class Level(StrEnum):
    ILLEGAL = "illegal"
    """The graph cannot be emitted."""

    UNMET = "unmet"
    """Something required has nothing behind it. Not illegal — incomplete."""

    ADVISORY = "advisory"
    """Legal, and not what convention or a rule would have chosen."""


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    level: Level
    message: str

    node: NodeId | None = None
    port: PortName | None = None

    source: EdgeRef | None = None
    """The upstream output this finding is about, as `<node>.<port>`."""

    target: EdgeRef | None = None
    """The consuming input. **Two `EdgeRef`s, not one `DraftEdge` and not one wire string.**

    A `Finding` carrying a `DraftEdge` would make `review/` import `plan/`, and `plan/` already
    imports `review/` — a cycle that fails at import. `plan/tiers.py` says so in as many words.

    One `EdgeRef` spelled `a:bam->b:bam` was the first repair and is also wrong: `_edge_ref`
    validates `<node>.<port>`, **one endpoint**, and refuses that outright. A wire is two of
    them. Two fields, both validated by an alias that already exists, and no new spelling
    invented for something the system already knows how to write down.
    """

    @field_validator("code")
    @classmethod
    def _declared(cls, code: str) -> str:
        """Same guarantee `coded()` gives, at the other end.

        `coded()` checks the code when a *message* is built. A `Finding` is data that may be
        constructed without one, so the check has to exist here too or an undeclared code
        reaches a client through the field rather than through the sentence.
        """
        if code not in REGISTRY:
            raise ValueError(
                f"{code} is not a declared diagnostic. Declare it in comeni_core/"
                f"diagnostics.yml, or fix the code."
            )
        return code


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[Finding] = []

    @property
    def illegal(self) -> list[Finding]:
        return [f for f in self.findings if f.level is Level.ILLEGAL]

    @property
    def emittable(self) -> bool:
        """**Not "is it finished".** An `UNMET` port is legal to hold in a draft and illegal to
        emit; that is `keep`'s judgement, made against `illegal` plus `unmet`. This property
        answers only whether anything is outright wrong."""
        return not self.illegal
