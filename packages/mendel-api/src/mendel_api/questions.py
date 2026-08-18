"""One schema for a question, whoever is asking and whoever answers.

**Two consumers, not two endpoints.** React renders an `OpenQuestion` as a card; an agent
GETs the same route and POSTs an answer back. That is what makes "the agent drives Mendel
via the API" cost nothing extra — spec §4.2.

**This is a DTO, not a door payload.** Plan 2.5 §5's egress rules govern `comeni-core`;
they do not reach here. It may carry prose freely.

**Slice 1 projects `Hole` only.** `Ambiguity` projects into this same shape when the Mendel
slice lands — it is the other subclass of the same `comeni_core.review.Question`, which is
why the projection is small. Nothing here is named for the forge.
"""

from datetime import datetime
from enum import StrEnum

from comeni_core.review import Candidate, Excerpt
from mendel_forge.scaffold import Hole, Proposal
from pydantic import BaseModel, ConfigDict


class Band(StrEnum):
    """How much a wrong answer costs, which is not the same as how likely one is.

    Graded by consequence rather than hit rate — the operator's call on 2026-08-17, after
    the forge measured a model at 97% on the fields that change which pipeline gets built
    and ~60% on port labels. A flat accuracy number averages those two and hides the only
    one worth knowing.
    """

    ROUTING = "routing"
    """Types and roles. A wrong answer routes, silently, and builds a different pipeline."""
    COSMETIC = "cosmetic"
    """Port labels. Routing is by `type_id`; a reviewer renames one in seconds."""
    PROSE = "prose"
    """Free text with no candidates. A model is never asked (issue #70)."""

    @property
    def rank(self) -> int:
        """Consequence order — lower is worse to get wrong. `docs/design/forge-review.md` §4.

        **Declared rather than derived from the member order or the value.** `Band` is a
        `StrEnum`, so `sorted()` compares the strings and produces cosmetic, prose, routing —
        alphabetical order that reads as a priority. That shipped, and the queue put port
        labels above the fields that decide which pipeline gets built.

        Drift (1) and blocked proposals (2) are the design's first two rungs and have no
        member yet: drift is phase 5, proposals are phase 3. The numbers are left free so
        they arrive in the right place rather than at the end.
        """
        return {Band.ROUTING: 3, Band.PROSE: 4, Band.COSMETIC: 5}[self]


_COSMETIC_SUFFIXES = (".name",)
_PROSE_SUBJECTS = frozenset({"priority_because"})


def band_for(subject: str) -> Band:
    """Derived from the subject, never stored on the hole.

    A stored band would be a second place that decides what a field costs, and it would go
    stale the first time a field is added. This reads the one authority: the field itself.
    """
    if subject in _PROSE_SUBJECTS:
        return Band.PROSE
    if subject.endswith(_COSMETIC_SUFFIXES):
        return Band.COSMETIC
    return Band.ROUTING


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    what: str
    why_open: str
    band: Band
    asked_by: list[str]
    """Which drafts ask it. A list because the same question recurs across modules, and
    answering once settles all of them — the throughput move the design rests on."""
    candidates: list[Candidate]
    closed: bool
    evidence: list[Excerpt]
    suggested: str | None = None
    """What a model answered, when one did. `None` means nobody has."""
    proposed: Proposal | None = None
    """Set when somebody declined this question — nothing declared fits, and here is what
    would. The hole is still open; this is why."""
    changed_at: datetime | None = None
    """When the newest draft asking this last moved. `None` where it is not known.

    On an aggregated row it is the MAXIMUM across the drafts asking, because the question a
    reviewer wants to see is one that moved *at all*, not one where everything moved."""


def question_from_hole(
    hole: Hole,
    *,
    draft: str,
    changed_at: datetime | None = None,
    proposed: Proposal | None = None,
) -> OpenQuestion:
    return OpenQuestion(
        subject=hole.subject,
        what=hole.what,
        why_open=hole.why_open,
        band=band_for(hole.subject),
        asked_by=[draft],
        candidates=list(hole.candidates),
        closed=hole.closed,
        evidence=list(hole.evidence),
        changed_at=changed_at,
        proposed=proposed,
    )


def aggregate(questions: list[OpenQuestion]) -> list[OpenQuestion]:
    """Collapse identical work into one row, keyed by `(subject, suggested)`.

    **Not by subject alone.** Two drafts asked the same question and a model answered them
    differently is precisely the disagreement a reviewer is scanning for, and merging those
    rows would hide it — the `samtools/faidx` case in the design's confirmable screen.

    `asked_by` is sorted because workspace order is directory order, and directory order
    moves under a refactor nobody asked for; the same argument as `Scaffold._sorted_holes`.

    The input is never mutated: a projection that edits its argument is one you cannot call
    twice, and the route calls it on a list it did not build.
    """
    merged: dict[tuple[str, str | None], OpenQuestion] = {}
    for q in questions:
        key = (q.subject, q.suggested)
        found = merged.get(key)
        if found is None:
            merged[key] = q.model_copy(update={"asked_by": list(q.asked_by)})
        else:
            found.asked_by.extend(q.asked_by)
            if q.changed_at and (found.changed_at is None or q.changed_at > found.changed_at):
                found.changed_at = q.changed_at
            # A merged row keeps the first proposal it saw: one draft declining is enough to
            # say the question was declined, and the row is the question rather than a draft.
            if found.proposed is None and q.proposed is not None:
                found.proposed = q.proposed
    for q in merged.values():
        q.asked_by.sort()
    # Ask before Confirm — design §4. `suggested is None` sorts False < True, so an
    # unanswered question comes first within a band.
    return sorted(
        merged.values(),
        key=lambda q: (q.band.rank, q.suggested is not None, q.subject, q.suggested or ""),
    )
