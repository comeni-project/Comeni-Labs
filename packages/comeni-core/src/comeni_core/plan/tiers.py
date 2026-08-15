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
    MODEL = "model"
    """A model answered an ambiguity the deterministic ladder could not settle.

    Distinct from `HUMAN` for the reason `HUMAN` is distinct from `GOAL`: *who* settled a
    thing is what a reviewer needs, and the three answers oblige different amounts of trust.

    **Nothing writes this until Plan 2.** It is declared now rather than then so that a model
    adapter has somewhere truthful to write on the day it exists, instead of the enum arriving
    alongside the first thing that needs it — which is the moment a shortcut gets taken.

    **It is a claim, not a proof.** A resolver sets its own `source`, and an adapter that
    writes `resolver` here is indistinguishable from the deterministic ladder. Same standing as
    `confidence` and `reason`, and recorded as such in round three's inheritance notes. What
    *is* provable is the negative, and that lives on `Pipeline.ai` — see `AiProvenance`. A130.
    """
    MEASURED = "measured"
    """A tool produced this value by looking at the data, and named itself.

    The distinction that matters clinically: a measured 150bp read length is a fact a
    profiling run established, while an asserted one is a claim by whoever typed the goal
    file. Both are legitimate; only one is checkable. The `sealed` protection profile is
    meant to refuse a tier-3 decision resting on an assertion — issue #2, once Plan 2
    builds `ProfilePolicy`. Recording provenance here is what makes that check possible.
    """


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
