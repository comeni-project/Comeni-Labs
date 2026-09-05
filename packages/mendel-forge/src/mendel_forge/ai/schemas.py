"""What a model is allowed to say back, and what is checked before anybody reads it.

**A response answers holes by id.** It does not describe a contract, and it does not hand back
a document to be merged — it answers the typed, addressable questions the scaffold already
opened, which is the property `CLAUDE.md` names as the contribution: *a model answers only
those, addressed by id, and cannot produce a value outside the candidate set.* Inventing a
second shape here would have made that claim true of the build path and false of the forge.

Three consequences follow, and each is a check in `admit()`:

- an answer to a hole that is not in the scaffold is refused, so a response cannot widen the
  question it was asked;
- an answer to an `exhaustive` hole must be one of that hole's `legal_values`;
- every citation must be an evidence id that survived into the dossier — `MF0401`, and
  `Dossier.evidence_ids()` is the legal set rather than the source bundle, because evidence
  dropped by the budget is as unfollowable for a reviewer as evidence that was invented.

**No field here is ever used as a path.** §5.6: a response never chooses a destination. The
path comes from `bundle.joined(adaptation_id, Area.CANDIDATE, ...)`, which is derived from the
adaptation id and a fixed name; `test_ai_schemas.py` holds that literally, the way the egress
guard holds its payload allowlist.
"""

from collections.abc import Iterable, Sequence
from typing import Self

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, Field, model_validator

from mendel_forge.hole_manifest import ScaffoldHole

_FROZEN = ConfigDict(extra="forbid", frozen=True)

CONFIDENCE = "confidence"
"""Named so the scan below can say what it forbids.

§5.5's last line: *confidence never turns missing evidence into a fact*. A score on an answer
invites exactly that trade — a reviewer reads 0.9 and stops reading the evidence — so the
shape has no room for one, and `extra="forbid"` makes offering one a validation error rather
than a silently ignored field.
"""


class Answer(BaseModel):
    """One hole, closed.

    `value` is a string because every hole's vocabulary is strings — a type id, a state, a
    role, a route, a process name. Typing it per `HoleKind` would put the vocabulary in two
    places, and the hole already carries the legal set.
    """

    model_config = _FROZEN

    hole_id: str
    value: str
    evidence_ids: tuple[str, ...] = ()
    """May be empty **only** for a hole whose answer is a naming choice rather than a claim
    about the tool — a process name is invented, not read. `admit()` enforces which."""
    reason: str = ""
    """Why this value, in the model's words. Free text, and it stays inside the forge: it is
    written into a candidate file a human reads before approving, and the forge is not on the
    prompt-taint path (invariant 14, and `notes/specs/2026-08-17-forge-phase-2.md` §1)."""


class Unresolved(BaseModel):
    """A hole the evidence does not close, and what would close it.

    §5.5: *each unresolved item carries `needed_evidence`, so review tells a person what would
    close it.* That is the difference between this and a hole that was simply skipped — one
    tells a curator where to look, the other tells them only that they have work.

    **This is the answer the shared invariant block asks for when evidence runs out**, and it
    has to be as easy to return as a guess or it will not be returned. So it carries no
    apology, no confidence, and nothing that reads as failure.
    """

    model_config = _FROZEN

    hole_id: str
    needed_evidence: str = Field(min_length=1)


class Analysis(BaseModel):
    """The response to `forge.analysis.v1`: every hole either answered or explicitly left open.

    **Both lists are required to be disjoint and to cover nothing they were not asked.** A hole
    appearing in neither is not an error here — it is reported by `owed()`, because the caller
    decides whether an incomplete analysis is a repair or a review.
    """

    model_config = _FROZEN

    answers: tuple[Answer, ...] = ()
    unresolved: tuple[Unresolved, ...] = ()

    @model_validator(mode="after")
    def _a_hole_is_answered_or_open_and_not_both(self) -> Self:
        both = {a.hole_id for a in self.answers} & {u.hole_id for u in self.unresolved}
        if both:
            raise ValueError(
                f"these holes are both answered and reported unresolved: {sorted(both)}. "
                "A reviewer reading the candidate would see a settled value and a request for "
                "more evidence about the same field, with nothing to say which is current."
            )
        return self

    def addressed(self) -> frozenset[str]:
        return frozenset({a.hole_id for a in self.answers} | {u.hole_id for u in self.unresolved})

    def cited(self) -> frozenset[str]:
        return frozenset(e for a in self.answers for e in a.evidence_ids)


class ModuleProposal(BaseModel):
    """The response to `forge.implementation.v1`, for a source that ships no Nextflow.

    **Sections, not a file.** A model returning whole module text could rewrite the container
    line, the process name settled from the catalogue, or the parts `modulegen` already
    derived — and the diff a reviewer reads would be against nothing. So it fills the three
    blocks `modulegen.OPEN_SECTIONS` marks open and nothing else; `render.py` puts them back
    where the markers are.

    For an nf-core source this shape is never requested: §5.6 says the prompt may bind a
    contract to the existing process and must not emit replacement Nextflow, and the scaffold
    for such a source carries no open sections to fill.
    """

    model_config = _FROZEN

    input_block: str = ""
    output_block: str = ""
    script: str = ""
    versions_command: str = ""
    """The command whose output is captured as the tool's version, or empty.

    §5.6 asks for *a versions output based on a real evidenced command, or an unresolved
    item*. Empty is the unresolved case and is legitimate: most container-only tools print no
    version, and inventing `--version` for one that does not support it produces a module that
    fails at run time with a message about an unknown flag.
    """
    evidence_ids: tuple[str, ...] = ()

    def filled(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, text in (
                ("input_block", self.input_block),
                ("output_block", self.output_block),
                ("script", self.script),
            )
            if text.strip()
        )


class Proposal(BaseModel):
    """One attempt at one adaptation: the analysis, and the module if one was needed."""

    model_config = _FROZEN

    analysis: Analysis
    module: ModuleProposal | None = None


def admit(
    proposal: Proposal,
    *,
    holes: Sequence[ScaffoldHole],
    evidence_ids: Iterable[str],
) -> Proposal:
    """The gate between a validated shape and anything that reads it.

    Pydantic proves the response is the right *shape*. This proves it is about the *question
    that was asked* — which is a different claim, and the one that a schema can never make,
    because `hole_id: str` is satisfied by any string at all.

    Returns the proposal so a caller cannot use it without passing through here; that is the
    same construction `MeasurementRegistry.profile()` uses for `DataProfile` (invariant 15),
    and for the same reason — a validating constructor nobody is obliged to call is a
    convention rather than a guard.
    """
    by_id = {hole.id: hole for hole in holes}
    legal_evidence = frozenset(evidence_ids)

    unknown = sorted(proposal.analysis.addressed() - set(by_id))
    if unknown:
        raise ValueError(
            coded("MF0402", f"the response answers holes that were not asked: {unknown}")
            + f"\n  the scaffold opened: {sorted(by_id)}"
        )

    invented = sorted(proposal.analysis.cited() - legal_evidence)
    if invented:
        raise ValueError(
            coded("MF0401", f"the response cites evidence that is not in its dossier: {invented}")
            + f"\n  it was given: {sorted(legal_evidence) or 'no evidence at all'}"
        )

    if proposal.module is not None:
        stray = sorted(frozenset(proposal.module.evidence_ids) - legal_evidence)
        if stray:
            raise ValueError(
                coded("MF0401", f"the module proposal cites evidence not in its dossier: {stray}")
            )

    outside = sorted(
        f"{a.hole_id}={a.value!r}"
        for a in proposal.analysis.answers
        if (hole := by_id[a.hole_id]).exhaustive
        and hole.legal_values
        and a.value not in hole.legal_values
    )
    if outside:
        raise ValueError(
            coded("MF0403", f"the response answers outside the candidate set: {outside}")
            + "\n  an exhaustive hole's legal values are the whole vocabulary for that field"
        )

    return proposal


def owed(proposal: Proposal, holes: Sequence[ScaffoldHole]) -> tuple[str, ...]:
    """Required holes the response neither answered nor reported unresolved.

    Distinct from `hole_manifest.unresolved`, which counts what is *still open* after a
    curator has answered some. This counts what the model failed to address at all, and it is
    what decides whether an attempt goes to repair — a model that answered six of nine holes
    has not declined the other three, it has forgotten them, and §5.7's repair prompt is
    exactly the place to say so.
    """
    addressed = proposal.analysis.addressed()
    return tuple(sorted(h.id for h in holes if h.required and h.id not in addressed))
