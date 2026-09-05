"""The context dossier: what one adaptation puts in front of a model, and what it left out.

§5.3 fixes the order of ten sections and the reduction policy when they do not fit. Both are
here, and both are pure — this module reads no clock, no environment and no registry of its
own. Its callers hand it values.

**Measured in characters, not tokens, and that is a choice rather than a shortcut.** A real
tokenizer means a provider's tokenizer, which would make the dossier's *content* depend on
which model is configured: the same source would compose different context on Ollama than on
Claude, and the golden file for a rendered prompt would be a golden file for one lane. A
character budget is an approximation of a token budget; it is also the same approximation on
every machine, which is what a stored review record needs more.

**A section that cannot be dropped and does not fit is a refusal, never a truncation.** That
is `MF0400`, and the argument is in its explanation: a model shown nine of eleven legal values
does not know it was shown nine.
"""

import hashlib
from collections.abc import Iterable, Sequence
from enum import IntEnum, StrEnum
from typing import Self

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, Field, model_validator

_FROZEN = ConfigDict(extra="forbid", frozen=True)

CHARS_PER_TOKEN = 4
"""The approximation, named so it can be cited rather than rediscovered.

Roughly right for English prose and for the JSON and Groovy this dossier is mostly made of.
It is deliberately not tuned per source: a budget that is 15% off in a stable direction costs
one dropped exemplar, and a budget that moves with the model costs reproducibility.
"""


class Section(StrEnum):
    """The ten sections of §5.3, in the order they are rendered.

    Declared as an enum rather than left to the composer's call order, because the order is a
    claim about how a model reads: identity and evidence before facts, the response schema
    second to last, and **the task instruction last**, where an instruction is least likely to
    be lost behind six pages of vocabulary.
    """

    IDENTITY = "identity"
    EVIDENCE = "evidence"
    FACTS = "facts"
    HOLES = "holes"
    REGISTRY_VERSION = "registry-version"
    VOCABULARY = "vocabulary"
    EXEMPLARS = "exemplars"
    EXISTING_RULES = "existing-rules"
    RESPONSE_SCHEMA = "response-schema"
    TASK = "task"


ORDER: tuple[Section, ...] = tuple(Section)
"""Rendering order, which is declaration order. `ORDER.index` is the sort key."""


class Drop(IntEnum):
    """How readily a segment may be given up, and in what order.

    §5.3 names two droppable classes and their order — *low-ranked similar contracts first,
    then redundant prose* — and four that may never go: schemas, legal values, holes, and
    validation diagnostics. This is that sentence as a total order, so the reduction is a sort
    rather than a series of `if` branches that each have to remember the rule.

    **`KEPT` is not a rank, it is a floor.** A reduction never considers it, so adding a new
    protected section is one enum value and no change to `fit`.
    """

    EXEMPLAR = 0
    """A similar landed contract. Helpful, and the only section whose absence costs nothing
    but quality — every claim it supports is also supported by the vocabulary."""
    PROSE = 1
    """Documentation excerpts beyond the first for a given fact. Redundant rather than
    optional: a fact keeps its own evidence, and this is the surrounding paragraph."""
    KEPT = 2
    """Never dropped. Not an ordering position — `fit` stops before reaching it."""


class Segment(BaseModel):
    """One addressable piece of the dossier.

    **`key` is what an omission names.** A manifest saying *three exemplars were dropped* is
    not reviewable; one saying `nf-core/samtools/sort@1.21` was dropped is. Every segment
    therefore carries an address inside its section, even the singletons, whose key is the
    section name repeated — a small redundancy that keeps `Omission` one shape.
    """

    model_config = _FROZEN

    section: Section
    key: str
    text: str
    drop: Drop = Drop.KEPT
    rank: int = 0
    """Within a `drop` class, higher goes first. The exemplar ranker's score, negated by its
    caller — this module does no scoring, because what makes a contract similar is Forge
    policy and belongs beside the thing that knows about ports."""

    @model_validator(mode="after")
    def _addressable(self) -> Self:
        if not self.key.strip() or self.key != self.key.strip():
            raise ValueError(
                f"a dossier segment's key must be usable as an address: {self.key!r}. "
                "It is stored in the manifest, cited in a review and matched when a prompt is "
                "regenerated; one with stray whitespace matches nothing."
            )
        return self

    def size(self) -> int:
        """Characters, including the heading and the blank line that will follow it.

        Counting the heading matters at the margin: forty segments carry forty headings, and a
        budget that ignores them is a budget that is wrong by a section.

        **Each segment is charged its own separator, so the sum is an upper bound** — by one
        separator, since the last segment is not followed by one. Erring high is the direction
        that cannot overflow, and the alternative is a size that depends on how many other
        segments happen to survive the reduction, which would make `size()` unusable as the
        sort key that decides which ones do.
        """
        return len(_heading(self)) + 1 + len(self.text) + 2


class Omission(BaseModel):
    """One thing that did not go in, and why.

    §5.3: *record every omission*. Not a count — a count tells a reviewer that the model was
    working with less than the record shows and gives them no way to find out what.
    """

    model_config = _FROZEN

    section: Section
    key: str
    reason: str


class Manifest(BaseModel):
    """What the dossier is made of, as a value that can be stored beside the response.

    This is what makes a review answerable six months later. The rendered prompt says what the
    model saw; the manifest says what it was *not* shown, which is the half a reader cannot
    reconstruct from the text.
    """

    model_config = _FROZEN

    budget: int
    used: int
    omitted: tuple[Omission, ...] = ()
    prompt_digest: str = ""
    """Of the rendered text. Carried here so a repair can assert it is working from the same
    dossier as the attempt it repairs, rather than trusting that it was rebuilt the same way."""

    def fits(self) -> bool:
        return self.used <= self.budget


class Dossier(BaseModel):
    """The composed context for one invocation.

    Built once per adaptation attempt and reused across repairs unchanged — §5.7 says the
    repair prompt carries *the unchanged dossier*, and the only way to be sure of that is to
    hand it the same object rather than rebuild it and hope the inputs have not moved.
    """

    model_config = _FROZEN

    segments: tuple[Segment, ...] = ()
    manifest: Manifest

    def render(self) -> str:
        """The dossier as the text a prompt embeds.

        Sorted by section order and then by the caller's rank and key, so two runs over the
        same inputs produce the same bytes. Insertion order would be composition order, which
        moves under a refactor nobody asked for — the same argument `Observation._sorted`
        makes.
        """
        return render(self.segments)

    def evidence_ids(self) -> frozenset[str]:
        """Every id a response is permitted to cite.

        The legal set is exactly what went in, which is why this reads the segments rather
        than the source bundle: a citation of evidence that was *dropped* is as unfollowable
        for a reviewer as one that was invented, and `MF0401` should say so either way.
        """
        return frozenset(s.key for s in self.segments if s.section is Section.EVIDENCE)


def _heading(segment: Segment) -> str:
    return f"## {segment.section.value}: {segment.key}"


def _ordered(segments: Iterable[Segment]) -> list[Segment]:
    return sorted(segments, key=lambda s: (ORDER.index(s.section), -s.rank, s.key))


def render(segments: Iterable[Segment]) -> str:
    """`Dossier.render` as a free function, so `compose` can digest what it is about to store
    without constructing a dossier twice."""
    return "\n\n".join(f"{_heading(s)}\n{s.text}" for s in _ordered(segments))


def compose(segments: Sequence[Segment], *, budget: int) -> Dossier:
    """Fit the segments into the budget, recording what had to go.

    Drops whole segments and never parts of one. A half-included exemplar is a contract that
    reads as complete and is not, and there is nothing in the rendered text to tell a model
    otherwise — the same property that makes `MF0400` refuse rather than trim.
    """
    kept = list(segments)
    omitted: list[Omission] = []
    used = sum(s.size() for s in kept)

    while used > budget:
        giveable = [s for s in kept if s.drop is not Drop.KEPT]
        if not giveable:
            protected = sorted({s.section.value for s in kept})
            raise ValueError(
                coded("MF0400", f"the dossier needs {used} characters and has {budget}")
                + f"\n  everything left is protected: {', '.join(protected)}"
                + "\n  §5.3 forbids truncating schemas, legal values, holes or diagnostics"
            )
        loser = min(giveable, key=lambda s: (s.drop, s.rank, s.key))
        kept.remove(loser)
        used -= loser.size()
        omitted.append(
            Omission(
                section=loser.section,
                key=loser.key,
                reason=f"dropped to fit the context budget ({loser.size()} characters)",
            )
        )

    ordered = tuple(_ordered(kept))
    return Dossier(
        segments=ordered,
        manifest=Manifest(
            budget=budget,
            used=used,
            omitted=tuple(omitted),
            prompt_digest=digest_of(render(ordered)),
        ),
    )


def digest_of(text: str) -> str:
    """`sha256:`-prefixed, so a digest in a record says what produced it.

    A bare hex string beside a container digest and a registry digest is three things a reader
    has to tell apart by length.
    """
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


class Budget(BaseModel):
    """A token budget, expressed the way a provider states it and consumed as characters.

    Separate from `compose`'s `budget: int` so that the conversion lives in one place and the
    reduction stays a function over characters. A caller that has a real token count from a
    real tokenizer can bypass this and pass characters directly.
    """

    model_config = _FROZEN

    tokens: int = Field(gt=0)
    reserved_for_response: int = Field(default=4000, ge=0)
    """Held back, because a context window is shared between the prompt and the answer and a
    dossier sized to the whole window leaves no room to be answered in."""

    def characters(self) -> int:
        usable = self.tokens - self.reserved_for_response
        if usable <= 0:
            raise ValueError(
                f"a budget of {self.tokens} tokens reserves {self.reserved_for_response} for "
                "the response and leaves nothing for the dossier"
            )
        return usable * CHARS_PER_TOKEN
