"""Closed planning vocabularies for resolution tier, evidence, grain, and input form."""

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


class Coverage(StrEnum):
    """How much of the data a measured fact was read from (#465)."""

    HEAD = "head"
    """Part of it: an upload's first 4 MB, a file cut short, or reading stopped early. An
    estimate."""
    ALL = "all"
    """All of it, every file read to its end."""


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


class Grain(StrEnum):
    """How many items a channel carries relative to the analysis, and what a fact is about
    (#466): one for the whole study, one per sample, or a part of one sample's item between a
    splitter and its merger. Groups and lanes are declared on ports and channels instead (`by`,
    `Channel.units`)."""

    STUDY = "study"
    """One item for the analysis, such as a reference genome or annotation, emitted as a value
    channel and reused by every sample."""

    SAMPLE = "sample"
    """One queued item per sample."""

    PART = "part"
    """A piece of one sample's item, split to run in parallel and merged back per sample
    (stage 6). Only a splitter's output fans out to it; no type and no fact has it."""


class InputForm(StrEnum):
    """How a laboratory supplies per-sample pipeline inputs."""

    DIRECT = "direct"
    """`params.input` is a glob consumed by one sample-scoped channel."""

    SAMPLESHEET = "samplesheet"
    """`params.input` is a CSV projected into multiple sample-scoped channels."""
