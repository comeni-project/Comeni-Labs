"""Closed planning vocabularies for resolution tier, evidence, scope, and input form."""

from enum import IntEnum, StrEnum
from typing import NamedTuple

# Re-export the review-owned enum here to preserve the established planning API without
# introducing a dependency cycle from review back to plan.
from comeni_core.review.answer import ValueSource

__all__ = [
    "TIER_VOCABULARY",
    "PremiseOrigin",
    "ReviewLevel",
    "Tier",
    "TierWords",
    "ValueSource",
    "review_level_for",
]


class Tier(IntEnum):
    STRUCTURAL = 1
    CONVENTION = 2
    DATA_PROFILED = 3
    AMBIGUOUS = 4


class TierWords(NamedTuple):
    """User-facing label, group heading, explanation, and colour token for one tier."""

    name: str
    group: str
    what: str
    colour: str


TIER_VOCABULARY: dict[Tier, TierWords] = {
    Tier.STRUCTURAL: TierWords(
        name="Forced",
        group="Forced by inputs",
        what="no choice existed — the inputs settle it",
        colour="pea",
    ),
    Tier.CONVENTION: TierWords(
        name="Convention",
        group="Standard practice",
        what="a documented default, so nobody had to judge",
        colour="pea-soft",
    ),
    Tier.DATA_PROFILED: TierWords(
        name="Measured",
        group="Check the premise",
        what="a rule matched measured data — the machinery worked, check what it read",
        colour="measured",
    ),
    Tier.AMBIGUOUS: TierWords(
        name="Undecided",
        group="Needs your decision",
        what="no rule covered it, and nobody has judged it yet",
        colour="undecided",
    ),
}
"""Canonical user-facing vocabulary for every resolution tier."""


class PremiseOrigin(StrEnum):
    """Quality of a fact as evidence, independent of who supplied it."""

    MEASURED = "measured"
    MODEL_READ = "model_read"
    """A model inferred the value from a bounded sample excerpt."""
    ASSERTED = "asserted"
    GOAL = "goal"
    DERIVED = "derived"
    UNMEASURED = "unmeasured"
    """The measurement is known to be absent."""


class ReviewLevel(StrEnum):
    NONE = "none"
    ADVISORY = "advisory"
    REQUIRED = "required"


_REVIEW_BY_TIER = {
    Tier.STRUCTURAL: ReviewLevel.NONE,
    Tier.CONVENTION: ReviewLevel.NONE,
    Tier.DATA_PROFILED: ReviewLevel.ADVISORY,
    Tier.AMBIGUOUS: ReviewLevel.REQUIRED,
}


def review_level_for(tier: Tier) -> ReviewLevel:
    return _REVIEW_BY_TIER[tier]


class Scope(StrEnum):
    """Channel delivery cardinality relative to one pipeline run."""

    RUN = "run"
    """One reusable value for the run, such as a reference genome or annotation."""

    SAMPLE = "sample"
    """One queued value per sample."""


class InputForm(StrEnum):
    """How a laboratory supplies per-sample pipeline inputs."""

    DIRECT = "direct"
    """`params.input` is a glob consumed by one sample-scoped channel."""

    SAMPLESHEET = "samplesheet"
    """`params.input` is a CSV projected into multiple sample-scoped channels."""
