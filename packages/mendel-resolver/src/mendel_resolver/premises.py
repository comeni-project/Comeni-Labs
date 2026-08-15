"""The facts a rule may read, and where each one came from.

Tier 3 is defined as producing `value + rule + measurement` and produced only the first two:
a measured build and an asserted one had a byte-identical `steps:` block (A108). The premise
is the missing third, and it has to carry its own provenance or `sealed` cannot refuse a
decision resting on an assertion (issue #2).

`when` could previously see measurements and nothing else, so a rule could not ask what the
goal required — which is A120, and why R11 (Salmon for transcript-level counts, featureCounts
for gene-level) cannot be written in the shipped format. A premise set is one namespace over
measurements, goal facts and derived facts, so a rule author has one thing to learn.
"""

from enum import StrEnum
from typing import Any

from comeni_core.goal import Goal
from comeni_core.measurement import MeasurementRegistry
from comeni_core.tiers import ValueSource
from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.rules import Derivation


class PremiseError(ValueError):
    """The premise set could not be built."""


class PremiseOrigin(StrEnum):
    """How good a fact is as a premise, which is not the same question as who settled it."""

    MEASURED = "measured"
    ASSERTED = "asserted"
    GOAL = "goal"
    DERIVED = "derived"
    UNMEASURED = "unmeasured"
    """Read by a row testing `absent`. A gap is evidence; it is evidence of a gap."""


class Premise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    value: Any
    origin: PremiseOrigin
    because: str = ""
    cite: str = ""
    derived_from: list[str] = Field(default_factory=list)


_BY_SOURCE = {
    ValueSource.MEASURED: PremiseOrigin.MEASURED,
    ValueSource.GOAL: PremiseOrigin.ASSERTED,
    ValueSource.HUMAN: PremiseOrigin.ASSERTED,
    ValueSource.RESOLVER: PremiseOrigin.ASSERTED,
}
"""`ValueSource` answers *who settled this*; `PremiseOrigin` answers *how good is it as a
premise*, and the two are not the same question. A goal assertion and a human override are
different authors and identical evidence: nobody looked at the data. Collapsing them here
rather than at the point of use is what keeps `sealed` a single check.

Total over `ValueSource`, and read with `[]` rather than `.get(…, ASSERTED)`, so a fifth
member forces somebody to answer this question rather than defaulting into the safest-sounding
answer. That is A38's `Via` tripwire, which earned itself two plans after it was built.
`RESOLVER` cannot currently reach a profile — nothing constructs a `Measured` with it — and it
is mapped rather than refused because a resolver default is an assertion by the registry in
exactly the sense that matters here: no tool looked at the data.
"""

_RESERVED = "required_states"


def build_premises(
    *,
    goal: Goal,
    derivations: list[Derivation],
    measurements: MeasurementRegistry,
) -> dict[str, Premise]:
    """Measured, then asserted, then goal, then derived. One pass, no fixpoint.

    Ordered rather than iterated to a fixpoint because a fixpoint makes the premise set a
    function of evaluation order, and two rules could then disagree about the same fact
    depending on which loaded first. One pass is what keeps `same goal in -> same pipeline
    out` a property of the data rather than of the loader.

    Takes the `Goal` rather than a goal and a profile: the profile is `goal.profile`, and a
    signature that accepts both invites a caller to pass two that disagree.

    Derivations run **last** and may only fill gaps — see `_derive`.
    """
    premises: dict[str, Premise] = {}
    for entry in goal.profile.measurements:
        premises[entry.measurement] = Premise(
            id=entry.measurement,
            value=entry.value,
            origin=_BY_SOURCE[entry.source],
        )
    # `required_states` is the goal's own shape rather than a measurement, so it cannot
    # collide with one: `MeasurementRegistry.profile()` would have refused an undeclared key,
    # and nothing may declare a measurement by this name.
    if _RESERVED in measurements.ids():
        raise PremiseError(
            f"MD0303: a measurement is declared named {_RESERVED!r}, which is the goal's own "
            f"shape and cannot also be measured. Rename the measurement — a property of the "
            f"data that happens to concern states is a different fact from the states the "
            f"goal asked for, and a rule reading one must not silently get the other."
        )
    premises[_RESERVED] = Premise(
        id=_RESERVED,
        value=sorted(
            state for required in goal.constraints.required_states for state in required.states
        ),
        origin=PremiseOrigin.GOAL,
    )
    _derive(premises, derivations)
    return premises


def _derive(premises: dict[str, Premise], derivations: list[Derivation]) -> None:
    """Fill gaps, last, and never overwrite. Spec §3.1.

    Last because a derivation may read any earlier fact and nothing may read a derived one —
    that is what "one pass, no fixpoint" buys, and it is what keeps two derivations from
    resolving differently depending on which file loaded first.

    Never overwrite because a fallback that can win against a measurement is not a fallback.
    The failure would be silent in the worst way available: the pipeline resolves against a
    default while `pipeline.yml` prints the measured value beside it.
    """
    for derivation in derivations:
        if derivation.fact in premises:
            continue
        for row in derivation.rows:
            if not _matches(row.when, premises):
                continue
            premises[derivation.fact] = Premise(
                id=derivation.fact,
                value=row.then,
                origin=PremiseOrigin.DERIVED,
                because=row.because or derivation.because or "",
                cite=row.cite or derivation.cite or "",
                derived_from=sorted(row.when),
            )
            break


def _matches(when: dict[str, Any], premises: dict[str, Premise]) -> bool:
    """Equality and `absent`, and nothing else until Task 3.

    Deliberately not a second copy of `DecisionRow.matches`: that one reads a `DataProfile`
    and cannot express `absent` at all, which is A122. Task 3 replaces this with the one
    evaluator both layers share — two predicates that must agree is how a rule comes to pass
    validation and then fail to fire, which is what `_comparison`'s docstring already says
    about the last pair.
    """
    for fact, expected in when.items():
        premise = premises.get(fact)
        if expected == "absent":
            if premise is not None:
                return False
            continue
        if premise is None or premise.value != expected:
            return False
    return True
