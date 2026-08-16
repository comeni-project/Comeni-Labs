"""A partial artifact with typed holes.

**A scaffold is not a half-built contract.** `ModuleContract` has validators and forbids
extras, so a half-contract is unrepresentable — and it must stay that way, because the
moment a partially-valid contract is constructible somebody will persist one. The forge
therefore holds an `Observation` plus a list of `Hole`s and constructs the real model only
when the last hole is filled (`assemble.py`).

The consequence is the property the whole design rests on: **the forge cannot emit an
invalid declared file.** It emits either a valid one, or something that is honestly not one
yet and says which fields it is missing and why.
"""

from enum import StrEnum
from typing import Any

from comeni_core.declared.layered import DeclaredKind
from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from mendel_forge.observe import Excerpt, Observation

_NO_EXTRAS = ConfigDict(extra="forbid")


class Filler(StrEnum):
    """Who settled a value. `MODEL` exists before anything writes it, deliberately —
    the same argument as `ValueSource.MODEL`, which shipped a plan before its adapter."""

    DERIVED = "derived"
    HAND = "hand"
    MODEL = "model"


class FilledValue(BaseModel):
    model_config = _NO_EXTRAS

    value: Any
    filler: Filler
    by: str
    """`nf-core` for a derived fact, a username for a hand fill, a model id for a model one.
    Copied verbatim into `Provenance.drafted_by` at land time."""
    why: str


class Candidate(BaseModel):
    model_config = _NO_EXTRAS

    value: str
    note: str = ""
    """Where this candidate is declared, so a reviewer can check it without a second lookup."""


class Hole(BaseModel):
    model_config = _NO_EXTRAS

    field: str
    what: str
    why_open: str
    candidates: list[Candidate] = Field(default_factory=list)
    """Empty means free text. Non-empty means a closed choice, enforced by `fill`."""
    evidence: list[Excerpt] = Field(default_factory=list)

    def legal(self, value: Any) -> bool:
        return not self.candidates or any(c.value == value for c in self.candidates)


class Scaffold(BaseModel):
    model_config = _NO_EXTRAS

    kind: DeclaredKind
    target: str
    observation: Observation
    filled: dict[str, FilledValue] = Field(default_factory=dict)
    holes: list[Hole] = Field(default_factory=list)

    @field_serializer("filled")
    def _sorted_filled(self, filled: dict[str, FilledValue]) -> dict[str, FilledValue]:
        return {name: filled[name] for name in sorted(filled)}

    @field_serializer("holes")
    def _sorted_holes(self, holes: list[Hole]) -> list[dict[str, Any]]:
        """Determinism: ingestion order is parse order, and parse order moves under a
        refactor that changes nothing anybody asked to change."""
        return [hole.model_dump() for hole in sorted(holes, key=lambda h: h.field)]

    def is_complete(self) -> bool:
        return not self.holes

    def hole(self, field: str) -> Hole | None:
        return next((h for h in self.holes if h.field == field), None)

    def fill(self, field: str, value: Any, filler: Filler, *, by: str, why: str) -> "Scaffold":
        """Returns a new scaffold. A scaffold is a value; mutating one would make the
        workspace's saved copy disagree with the one in hand."""
        found = self.hole(field)
        if found is None:
            open_fields = ", ".join(h.field for h in sorted(self.holes, key=lambda h: h.field))
            raise ValueError(
                coded("MF0002", f"{field} is not a hole in {self.target}")
                + f"\n  open: {open_fields}"
            )
        if not found.legal(value):
            legal = ", ".join(c.value for c in found.candidates)
            raise ValueError(
                coded("MF0003", f"{value!r} is not legal for {field}") + f"\n  candidates: {legal}"
            )
        return self.model_copy(
            update={
                "filled": {
                    **self.filled,
                    field: FilledValue(value=value, filler=filler, by=by, why=why),
                },
                "holes": [h for h in self.holes if h.field != field],
            }
        )
