"""The four resolution tiers and the review level each implies.

Separate from `ir.py` so `decision.py` can name a tier without importing the IR, which
is what lets `PipelineIR.decisions` be typed `list[DecisionRecord]` instead of
`list[Any]`. The mapping is a function rather than stored data so the table in the spec
cannot drift from the table in the code.
"""

from enum import IntEnum, StrEnum

# `ValueSource` lives in `review/answer.py` so that `review/` need not import `plan/` —
# `plan/decision.py` imports `Question` from there, and the reverse edge would be a cycle.
# Re-exported because 25 call sites and the package's public surface name it here.
from comeni_core.review.answer import ValueSource

__all__ = ["PremiseOrigin", "ReviewLevel", "Tier", "ValueSource", "review_level_for"]


class Tier(IntEnum):
    STRUCTURAL = 1
    CONVENTION = 2
    DATA_PROFILED = 3
    AMBIGUOUS = 4



class PremiseOrigin(StrEnum):
    """How good a fact is as a premise, which is not the same question as who settled it.

    Lives here rather than in `mendel_resolver.premises`, where it was declared, because the
    artifact carries it: `Why.premise` reaches `pipeline.yml` and `comeni-core` must not
    depend on `mendel-resolver`. Same move `DataProfile` and `Goal` both made, for the same
    reason, and `premises.py` re-exports it so every existing import still resolves.

    `ValueSource` answers *who settled this*; this answers *how good is it as evidence*. A
    goal assertion and a human override are different authors and identical evidence — in
    neither case did anything look at the data — so both are `ASSERTED`. Collapsing them at
    the point they are built rather than at each point of use is what keeps the `sealed`
    profile's check a single one (issue #2).
    """

    MEASURED = "measured"
    ASSERTED = "asserted"
    GOAL = "goal"
    DERIVED = "derived"
    UNMEASURED = "unmeasured"
    """Read by a row testing `absent`. A gap is evidence; it is evidence of a gap."""


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
