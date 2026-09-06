"""What a scaffold could not settle, addressed by something that will not move.

**An index is not an identity, and that is the whole reason this module exists.** The old
scaffold named its holes `consumes[0].type_id`. Add a channel upstream and every hole after it
is renamed: a stored answer, a review citing it, and a repair pass pointing at it all now
describe a different port. The plan's word for the fix is *stable semantic hole ids and current
pointers*, and those are two fields rather than one because they answer two questions — **which
port is this** and **where is it in today's document**.

The id is built from the port's own channel name, which is what upstream calls the thing and is
the most stable handle a source offers. The pointer is a JSON pointer into the contract being
drafted and is expected to move.

**A hole carries no answer and no candidate ranking.** `comeni_core.review.Question` and
`mendel_forge.candidates` already own that, and duplicating either here would give the forge two
ideas of what a legal value is. What this adds is the addressing and the `prompt_hint_id` — a
pointer to a *committed* instruction fragment, never a paragraph generated into each draft, so
two drafts of two tools ask the same question in the same words.
"""

import re
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_SEGMENT = re.compile(r"[^a-z0-9]+")


class HoleKind(StrEnum):
    """What sort of thing is missing. The plan's list, closed.

    It is coarse on purpose: it decides which committed instruction fragment a hole is asked
    with and how a page groups them, not what the answer may be. A finer vocabulary would be a
    second, weaker copy of the candidate machinery.
    """

    TYPE = "type"
    STATE = "state"
    ROLE = "role"
    PARAM = "param"
    RULE = "rule"
    NEXTFLOW = "nextflow"
    VERSION = "version"
    CITATION = "citation"


HINTS: dict[HoleKind, str] = {
    HoleKind.TYPE: "ports.semantic-type.v1",
    HoleKind.STATE: "ports.state.v1",
    HoleKind.ROLE: "contract.roles.v1",
    HoleKind.PARAM: "contract.param.v1",
    HoleKind.RULE: "rules.candidate.v1",
    HoleKind.NEXTFLOW: "module.nextflow.v1",
    HoleKind.VERSION: "container.version.v1",
    HoleKind.CITATION: "contract.citation.v1",
}
"""Kind -> the committed instruction fragment that explains how to answer it.

**Every kind has one, and `test_every_kind_has_a_hint` is why that stays true.** A hole with no
hint falls back to whatever the surrounding prompt happens to say, which is how one question
comes to be asked two different ways in two drafts — and the difference then reads as a model
being inconsistent rather than as a prompt being missing.

The files these name are Task 6's. Naming them here rather than there is deliberate: the hole
declares what it needs explained, and the prompt pack answers; the reverse — a prompt pack that
decides which holes exist — is how a prompt starts steering the scaffold.
"""


def slug(text: str) -> str:
    """A path segment safe to put in an id: lowercase, non-alphanumerics collapsed to `-`.

    Applied to a channel name, so `bam_unsorted` becomes `bam-unsorted` and `[meta]` becomes
    `meta`. It is not reversible and does not need to be — the pointer is what addresses the
    document, and this only has to be stable and readable.
    """
    return _SEGMENT.sub("-", text.strip().lower()).strip("-")


class ScaffoldHole(BaseModel):
    """One question the deterministic half could not answer.

    `required` is the field that decides whether a candidate can be approved with this still
    open. It is **not** derived from the kind: a missing semantic type blocks, and a missing
    citation on an optional parameter does not, and both are `TYPE`-ish in flavour. Deriving it
    would make a judgement look like a classification.
    """

    model_config = _FROZEN

    id: str
    """Stable and semantic — `consumes.reads.type_id`, never `consumes[0].type_id`."""
    pointer: str
    """A JSON pointer into the contract being drafted — `/consumes/0/type_id`. Expected to move
    between revisions, which is exactly why it is not the id."""
    kind: HoleKind
    question: str
    why_open: str
    required: bool = True
    legal_values: tuple[str, ...] = ()
    """Empty means *not a closed choice*, which is a different statement from *no legal value
    exists*. A hole with an empty list and `required` set is one only a person can close."""
    exhaustive: bool = True
    """Whether `legal_values` is the whole set. False for a hole where the vocabulary is open
    and the list is a ranking — the distinction `Question` already draws, kept here rather than
    inferred from emptiness, because *we listed everything* and *we listed what we found* are
    the two answers a reviewer most needs told apart."""
    suggested: str | None = None
    evidence_ids: tuple[str, ...] = ()
    prompt_hint_id: str = ""
    multiple: bool = False
    """Whether the field holds several values rather than one.

    **A question nobody could answer was being asked.** `roles` is `list[RoleName]` on the
    contract and every landed one reads `roles: [qc_per_sample]`, but the answer shape handed
    to a model was a single string — so *these two roles* had no expressible form and a model
    given that hole could only decline. Measured on 2026-09-06 driving `seqkit/fq2fa`: every
    closed-choice hole with one value was answered and this one was skipped, three times.

    **Derived from the contract schema, never listed here.** `list[X]` on the field is the fact;
    a second list of *which fields are multi-valued* is a second place to be wrong, and it goes
    stale the first time a field changes arity. `legal_values` still says what each element may
    be — cardinality and vocabulary are separate questions and only one of them changed."""

    @model_validator(mode="after")
    def _the_addressing_holds(self) -> Self:
        if not self.id or self.id != self.id.strip():
            raise ValueError(f"{self.id!r} is not a usable hole id")
        if not self.pointer.startswith("/"):
            raise ValueError(f"{self.pointer!r} is not a JSON pointer")
        if self.suggested is not None and self.legal_values and self.suggested not in (
            self.legal_values
        ):
            raise ValueError(
                f"{self.id}: suggested {self.suggested!r} is not among its legal values"
            )
        if self.exhaustive and not self.legal_values and self.kind is not HoleKind.NEXTFLOW:
            # An exhaustive list of nothing would say *no answer is legal*, which is never what
            # is meant — it is what an empty candidate set looks like when nobody set the flag.
            raise ValueError(
                f"{self.id}: claims an exhaustive list of legal values and offers none"
            )
        return self

    @property
    def hint(self) -> str:
        """The committed fragment, falling back to the kind's default."""
        return self.prompt_hint_id or HINTS[self.kind]


def port_hole_id(group: str, channel: str, field: str) -> str:
    """`consumes` + `bam_unsorted` + `type_id` -> `consumes.bam-unsorted.type_id`.

    **When a source names no channel**, the caller passes the index — which is the one case
    where an id is positional, and it is positional because there is nothing else to be. A
    source that names none of its ports offers no stable handle, and inventing one from
    ordering would be a stable-looking id that is not stable.
    """
    return f"{group}.{slug(channel)}.{field}"


def pointer_for(group: str, index: int, field: str) -> str:
    return f"/{group}/{index}/{field}"


def unresolved(holes: tuple[ScaffoldHole, ...], answered: frozenset[str]) -> tuple[str, ...]:
    """The required hole ids nobody has closed — approval's precondition, in one place.

    Counting them at the call site is how the number on the page and the number the service
    refuses on come to disagree, and the disagreement always favours the page.
    """
    return tuple(hole.id for hole in holes if hole.required and hole.id not in answered)
