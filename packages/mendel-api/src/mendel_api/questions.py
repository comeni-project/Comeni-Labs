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

from enum import StrEnum

from comeni_core.review import Candidate, Excerpt
from mendel_forge.scaffold import Hole
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


def question_from_hole(hole: Hole, *, draft: str) -> OpenQuestion:
    return OpenQuestion(
        subject=hole.subject,
        what=hole.what,
        why_open=hole.why_open,
        band=band_for(hole.subject),
        asked_by=[draft],
        candidates=list(hole.candidates),
        closed=hole.closed,
        evidence=list(hole.evidence),
    )
