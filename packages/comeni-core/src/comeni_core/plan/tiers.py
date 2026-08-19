"""The four resolution tiers and the review level each implies.

Separate from `ir.py` so `decision.py` can name a tier without importing the IR, which
is what lets `PipelineIR.decisions` be typed `list[DecisionRecord]` instead of
`list[Any]`. The mapping is a function rather than stored data so the table in the spec
cannot drift from the table in the code.
"""

from enum import IntEnum, StrEnum
from typing import NamedTuple

# `ValueSource` lives in `review/answer.py` so that `review/` need not import `plan/` —
# `plan/decision.py` imports `Question` from there, and the reverse edge would be a cycle.
# Re-exported because 25 call sites and the package's public surface name it here.
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
    """What a tier is called where a person reads it, and what it means.

    **Declared here rather than typed into an interface**, which is where it was: the four
    names lived in a React file and in `docs/design/dashboard.html`, two copies of a vocabulary
    with nothing holding them together. That is the drift `diagnostics.yml` exists to prevent —
    one declaration, generated consumers — and a tier is at least as load-bearing as a
    diagnostic code.

    `name` is the noun a **band** carries and `group` the heading a **settings card** puts over
    it; they differ because one is read in a legend and the other over a list, and forcing them
    to be the same word made one of the two read wrong. `colour` is a token name, never a hex:
    the palette is `tokens.css`'s job and a value here would be a second palette.
    """

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
"""**Every tier, once.** A consumer that hardcodes one of these four strings has made a second
copy of a vocabulary, which is how the interface came to say *Standard practice* with nothing
in the repository agreeing that it should."""


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
