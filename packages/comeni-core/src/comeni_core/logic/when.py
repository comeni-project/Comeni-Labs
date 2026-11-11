"""Evaluate rule predicates consistently at validation and resolution time.

Predicates support equality, ordered comparisons, membership, negation, and explicit presence or
absence. Rules (a resolver `Premise`) and contracts (#460) both call it: a fact is anything with
a `value`, so the evaluator depends on neither.
"""

import operator
from collections.abc import Mapping
from typing import Any, Protocol

from comeni_core.diagnostics import coded
from comeni_core.plan.tiers import Tier


class Fact(Protocol):
    """One fact a condition reads. Only its value matters here; provenance is the caller's."""

    @property
    def value(self) -> Any: ...

_OPS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}

_MAPPING_PREDICATES = ("not", "in")

ABSENT = "absent"
PRESENT = "present"

GOAL_SHAPED = frozenset({"required_states"})
"""Premises that are lists by shape, the goal's own (`required_states`), not several samples'
values: a test on one keeps its plain meaning rather than MD0312's refusal."""


class PredicateError(ValueError):
    """A `when` clause could not be evaluated. Always a defect in the rule, never in the data."""


def tier_of_row(when: dict[str, Any]) -> Tier:
    """Return the tier implied by the row's declared conditions.

    A row earns tier 3 only by testing a premise *positively*. `when: {}` is a catch-all and
    `when: {x: absent}` is a convention about what to assume in a gap — both produce
    `value + citation`, which is tier 2's shape and not tier 3's.

    `present` and `absent` look like a pair and are not one. `present` is a test on the data —
    something measured this — so a row conditioned on it did tier-3 work. `absent` is a test on
    the *absence* of data, which is exactly the case with no measurement behind it.

    Static on purpose: an author sees each branch's tier while writing it, and a reviewer can
    predict a build's review load from the rules rather than from a run.
    """
    positive = [key for key, expected in when.items() if expected != ABSENT]
    return Tier.DATA_PROFILED if positive else Tier.CONVENTION


def matches(when: dict[str, Any], facts: Mapping[str, Fact]) -> bool:
    return all(_one(key, expected, facts.get(key)) for key, expected in when.items())


def _one(fact: str, expected: Any, premise: Fact | None) -> bool:
    if expected == ABSENT:
        return premise is None
    if expected == PRESENT:
        return premise is not None
    if premise is None:
        return False
    actual = premise.value
    if isinstance(actual, list) and fact not in GOAL_SHAPED:
        # Several samples' values: no test on one value has a single answer over them, so the
        # rule must say how to reduce them first (Task 2 review: equality, `not` and `in` too).
        raise PredicateError(
            coded(
                "MD0312",
                f"{fact!r} is a cohort of {len(actual)} values and {expected!r} tests one. "
                f"Reduce it first with a `derives:` aggregate and test the derived fact, so the "
                f"file says which sample the rule meant.")
        )

    if isinstance(expected, dict):
        if "not" in expected:
            return actual != expected["not"]
        if "in" in expected:
            return actual in expected["in"]
        raise PredicateError(
            coded(
                "MD0305",
                f"{fact!r} is tested with {sorted(expected)}, which is not a predicate. "
                f"The mapping predicates are {', '.join(_MAPPING_PREDICATES)} — write "
            f"`{{not: <value>}}` or `{{in: [<value>, …]}}`.")
        )

    if isinstance(expected, str):
        symbol, _, literal = expected.partition(" ")
        if symbol in _OPS:
            return _OPS[symbol](*_comparable(fact, actual, literal, expected))
    return actual == expected


def _comparable(fact: str, actual: Any, literal: str, expected: str) -> tuple[Any, Any]:
    """The two operands of a comparison, or a refusal naming why there are not two.

    A cohort is refused rather than compared because a rule must explicitly declare how to reduce
    per-sample values before applying a scalar comparison.

    The numeric conversion is attempted and fallen back on rather than decided by the
    measurement's `kind`, because `matches` deliberately does not take a registry: it is called
    from load-time validation over rules whose facts may be derived and have no declaration to
    consult. `"< beta"` comparing two strings is legitimate and rare; `"< 70"` is the case.
    """
    if isinstance(actual, list) and fact not in GOAL_SHAPED:
        raise PredicateError(
            coded(
                "MD0312",
                f"{fact!r} is a cohort of {len(actual)} values and {expected!r} compares "
                f"one. Reduce it first with a `derives:` aggregate — "
            f"`aggregate: {{measurement: {fact}, over: cohort, using: max}}` — and test the "
            f"derived fact, so the file says which sample the rule meant.")
        )
    try:
        return actual, type(actual)(literal) if isinstance(actual, int | float) else literal
    except (TypeError, ValueError):
        return actual, literal
