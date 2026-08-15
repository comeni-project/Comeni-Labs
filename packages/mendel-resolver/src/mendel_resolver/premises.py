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

import math
from typing import Any

from comeni_core.declared.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal
from comeni_core.plan.tiers import PremiseOrigin, ValueSource
from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.predicates import matches
from mendel_resolver.rules import Derivation

__all__ = ["Premise", "PremiseError", "PremiseOrigin", "build_premises"]
"""`PremiseOrigin` is re-exported rather than declared here: the artifact carries it, so it
lives in `comeni_core.plan.tiers` beside `ValueSource`. Same move `Goal` and `DataProfile` made."""


class PremiseError(ValueError):
    """The premise set could not be built."""


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
            coded(
                "MD0303",
                f"a measurement is declared named {_RESERVED!r}, which is the goal's own "
                f"shape and cannot also be measured. Rename the measurement — a property of the "
            f"data that happens to concern states is a different fact from the states the "
            f"goal asked for, and a rule reading one must not silently get the other.")
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
        if derivation.aggregate is not None:
            _aggregate(premises, derivation)
            continue
        if derivation.transform:
            _transform(premises, derivation)
            continue
        for row in derivation.rows:
            if not matches(row.when, premises):
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


_REDUCERS = {
    "max": max,
    "min": min,
    "mean": lambda values: sum(values) / len(values),
}


_OPS = {
    "add": lambda value, by: value + by,
    "subtract": lambda value, by: value - by,
    "multiply": lambda value, by: value * by,
    "divide": lambda value, by: value / by,
    "log2": lambda value, by: math.log2(value),
    "at_most": lambda value, by: min(value, by),
    "at_least": lambda value, by: max(value, by),
}
"""The whole arithmetic this format has. Issue #39.

Closed and total over `Transform.op`, read with `[]`, so a new operation forces somebody to
implement it rather than defaulting into silence — A38's tripwire, in a fourth place.
"""


def _transform(premises: dict[str, Premise], derivation: Derivation) -> None:
    """Compute a fact by chaining named operations over another. Issue #39.

    Left to right, with no precedence to get wrong and no way to name a second fact. That is
    the constraint keeping this from being an expression language:
    `docs/design/rule-tables-and-port-logic.md` §13.2 asks for arithmetic *without*
    reintroducing a solver, and a chain of unary steps satisfies both halves.

    The result is coerced to the fact's declared `kind`, because `kind: integer` is a promise
    about the fact rather than a hint — a 15.79 reaching a flag that takes an integer is the
    same defect as a computed string reaching one, which is what A118 was.
    """
    source = premises.get(derivation.source)
    if source is None:
        return
    if isinstance(source.value, list):
        raise PremiseError(
            coded(
                "MD0314",
                f"derivation {derivation.fact!r} transforms {derivation.source!r}, which "
                f"is a cohort of {len(source.value)} values, and arithmetic takes one. Reduce it "
            f"first with an `aggregate:` derivation and transform the derived fact, so the "
            f"file says which sample the rule meant.")
        )
    value = source.value
    for step in derivation.transform:
        value = _OPS[step.op](value, step.by)
    premises[derivation.fact] = Premise(
        id=derivation.fact,
        value=int(value) if derivation.kind is MeasurementKind.INTEGER else value,
        origin=PremiseOrigin.DERIVED,
        because=derivation.because or "",
        cite=derivation.cite or "",
        derived_from=[derivation.source],
    )


def _aggregate(premises: dict[str, Premise], derivation: Derivation) -> None:
    """Reduce a per-sample premise to one value. Spec §3.2, R19.

    A scalar reduces to itself: a per-sample measurement written as one value is the claim
    that the cohort is uniform, so the max, min and mean of it are all that value. Writing
    it out is what stops `cohort_max_read_length` from existing for a three-sample profile
    and vanishing for a one-sample one — a fact that appears and disappears with the shape of
    the input is a fact no rule can be written against.

    An absent source leaves the fact absent rather than raising. The premise it would have
    reduced was optional, and a rule reading the aggregate can ask `absent` — which is the
    whole point of the origin vocabulary carrying `unmeasured`.
    """
    source = premises.get(derivation.aggregate.measurement)
    if source is None:
        return
    values = source.value if isinstance(source.value, list) else [source.value]
    if not values:
        return
    premises[derivation.fact] = Premise(
        id=derivation.fact,
        value=_REDUCERS[derivation.aggregate.using](values),
        origin=PremiseOrigin.DERIVED,
        because=derivation.because or "",
        cite=derivation.cite or "",
        derived_from=[derivation.aggregate.measurement],
    )
