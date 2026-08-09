"""The four resolution tiers and the review level each implies.

Separate from `ir.py` so `decision.py` can name a tier without importing the IR, which
is what lets `PipelineIR.decisions` be typed `list[DecisionRecord]` instead of
`list[Any]`. The mapping is a function rather than stored data so the table in the spec
cannot drift from the table in the code.
"""

from enum import IntEnum, StrEnum


class Tier(IntEnum):
    STRUCTURAL = 1
    CONVENTION = 2
    DATA_PROFILED = 3
    AMBIGUOUS = 4


class ValueSource(StrEnum):
    """Who decided a value, recorded separately from how well it was decided.

    A tier says *how* something was settled; it should not also have to say *who*. A user
    who pins a parameter has legitimately removed the ambiguity, so the tier is still
    structural — but a reviewer needs to see that Mendel did not derive it. Same shape as
    measured-versus-asserted in the profiling spec, and for the same reason.
    """

    RESOLVER = "resolver"
    GOAL = "goal"
    HUMAN = "human"
    """A person answered an ambiguity **after** resolution had faced it and flagged it.

    Deliberately not the same as `GOAL`, and the tier is what makes the difference visible.
    A goal pin is tier 1: the user removed the ambiguity before anything looked at it, so no
    choice existed to be made. An override is tier 4 that stayed tier 4 — resolution met a
    real ambiguity, could not settle it, and a human settled it in the artifact.

    Collapsing the two would erase that the pipeline contains a question somebody had to
    answer, and it would erase it precisely on the pipelines most worth reviewing. So the
    tier is kept and the *review* is what clears: see `PipelineIR.overrides()`.
    """
    MEASURED = "measured"
    """A tool produced this value by looking at the data, and named itself.

    The distinction that matters clinically: a measured 150bp read length is a fact a
    profiling run established, while an asserted one is a claim by whoever typed the goal
    file. Both are legitimate; only one is checkable. The `sealed` protection profile is
    meant to refuse a tier-3 decision resting on an assertion — issue #2, once Plan 2
    builds `ProfilePolicy`. Recording provenance here is what makes that check possible.
    """


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
