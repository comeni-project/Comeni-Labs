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

from typing import Any

from comeni_core.declared.layered import DeclaredKind
from comeni_core.diagnostics import coded
from comeni_core.review import Answer, Candidate, Excerpt, Question, ValueSource
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from mendel_forge.observe import Observation

__all__ = [
    "Candidate",
    "Excerpt",
    "FilledValue",
    "Hole",
    "Proposal",
    "Scaffold",
]
"""`Candidate` and `Excerpt` are re-exports, not uses.

They moved to `comeni_core.review` in Plan 2.5 and are named here so that the forge's own
call sites — and its tests — keep importing them from the module that used to define them.
Without this `__all__`, `ruff --fix` deletes them as unused imports and sixteen test modules
fail to collect, which is exactly what happened while writing this.
"""

_NO_EXTRAS = ConfigDict(extra="forbid")


class FilledValue(Answer):
    """A settled hole. Adds nothing to `Answer` — see the spec's §4.2, where that is read
    as a signal the base is drawn at about the right place.

    `by` is `nf-core` for a derived fact, a username for a hand fill, a model id for a
    model one. `land` copies it verbatim into `Provenance.drafted_by`.
    """


class Hole(Question):
    """An unanswered question about a contract being drafted.

    **The blocking lives in `Scaffold`, not here.** `Scaffold.is_complete()` gates
    `contract_from`, so the forge cannot emit an invalid declared file. Putting that on
    this class — as a field or as a method — would trade a structural guarantee for a
    runtime check on a value, which is the mistake `CLAUDE.md` records about invariant 1.
    """

    after: str | None = None
    """A field that must be answered first, because this hole's candidates depend on it.

    **Holes were independent, and they never were.** A port's name comes from its type, so
    asking both from the same evidence produced a model that answered `gtf` for
    `consumes[1].name` and `genome.index.hisat2` for `consumes[1].type_id` — the same port,
    contradicted between two calls that could not see each other.
    """

    channels: tuple[str, ...] = ()
    """What the module calls this port, kept so candidates can be recomputed once `after`
    lands without re-reading the source."""


class Proposal(BaseModel):
    """What a hole needs that the vocabulary cannot express yet.

    **Not a fill.** A hole with a proposal stays open: `is_complete()` is still false and
    `contract_from` still refuses, because a contract whose port cites an undeclared type is
    the load-time refusal invariant 7 already makes. What a proposal changes is that the hole
    now says *why* it is open — "nothing declared fits, and here is what would" — rather than
    looking like a field nobody has reached.

    **Not a vocabulary file either.** It lives in the workspace draft. Nothing writes
    `vocabularies/`; a person moves it, which is invariant 2's approval step and the whole of
    what bounds a model inventing an id and a sentence.

    See `notes/specs/2026-08-17-vocabulary-proposals.md`.
    """

    model_config = _NO_EXTRAS

    id: str
    description: str
    why: str
    by: str
    """The model id that proposed it. `Provenance.drafted_by`'s argument, one document over."""


class Scaffold(BaseModel):
    model_config = _NO_EXTRAS

    kind: DeclaredKind
    target: str
    observation: Observation
    filled: dict[str, FilledValue] = Field(default_factory=dict)
    holes: list[Hole] = Field(default_factory=list)
    proposed: dict[str, Proposal] = Field(default_factory=dict)
    """Field -> what it needs declared. Keyed by field, because two ports may need the same
    new type and a reviewer should see both places it was wanted."""

    @field_serializer("filled")
    def _sorted_filled(self, filled: dict[str, FilledValue]) -> dict[str, FilledValue]:
        return {name: filled[name] for name in sorted(filled)}

    @field_serializer("proposed")
    def _sorted_proposed(self, proposed: dict[str, Proposal]) -> dict[str, Proposal]:
        return {name: proposed[name] for name in sorted(proposed)}

    def replacing(self, hole: Hole) -> "Scaffold":
        """This scaffold with one hole swapped for an updated version of itself.

        A dependent hole's candidates are recomputed once what it depends on is filled, and
        the recomputed hole has to *be* the scaffold's hole — otherwise `fill` validates the
        answer against the stale candidate list and refuses a value the model was correctly
        offered.
        """
        return self.model_copy(
            update={"holes": [hole if h.subject == hole.subject else h for h in self.holes]}
        )

    def propose(self, field: str, proposal: Proposal) -> "Scaffold":
        """Record that nothing declared fits this field. **The hole stays open.**"""
        if self.hole(field) is None:
            raise ValueError(coded("MF0002", f"{field} is not a hole in this scaffold"))
        return self.model_copy(update={"proposed": {**self.proposed, field: proposal}})

    @field_serializer("holes")
    def _sorted_holes(self, holes: list[Hole]) -> list[dict[str, Any]]:
        """Determinism: ingestion order is parse order, and parse order moves under a
        refactor that changes nothing anybody asked to change."""
        return [hole.model_dump() for hole in sorted(holes, key=lambda h: h.subject)]

    def is_complete(self) -> bool:
        return not self.holes

    def hole(self, field: str) -> Hole | None:
        return next((h for h in self.holes if h.subject == field), None)

    def fill(
        self, field: str, value: Any, how: ValueSource, *, by: str, why: str
    ) -> "Scaffold":
        """Returns a new scaffold. A scaffold is a value; mutating one would make the
        workspace's saved copy disagree with the one in hand."""
        found = self.hole(field)
        if found is None:
            open_fields = ", ".join(h.subject for h in sorted(self.holes, key=lambda h: h.subject))
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
                    field: FilledValue(value=value, by=by, how=how, why=why),
                },
                "holes": [h for h in self.holes if h.subject != field],
            }
        )
