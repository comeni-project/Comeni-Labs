"""One evaluator, shared by load-time validation and runtime matching.

Two copies of a predicate is how a rule passes validation and then fails to fire, which is why
`_comparison` was one function in the old format and why this is one here. The old pair was not
hypothetical: A121 is a matcher that ran every literal through `float()`, so `!= unstranded` was
refused as a malformed number — a diagnostic instructing the author to make a categorical
comparison numeric.

Imports `Premise` only for type checking. `premises.build_premises` calls `matches`, so a
runtime import in the other direction is a cycle; nothing here reads a `Premise` beyond whether
it exists and what its `value` is.
"""

import operator
from typing import TYPE_CHECKING, Any

from comeni_core.diagnostics import coded
from comeni_core.plan.tiers import Tier

if TYPE_CHECKING:
    from mendel_resolver.premises import Premise

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


class PredicateError(ValueError):
    """A `when` clause could not be evaluated. Always a defect in the rule, never in the data."""


def tier_of_row(when: dict[str, Any]) -> Tier:
    """The tier this row exits at, determined by the rule **text** rather than by the data.

    A row earns tier 3 only by testing a premise *positively*. `when: {}` is a catch-all and
    `when: {x: absent}` is a convention about what to assume in a gap — both produce
    `value + citation`, which is tier 2's shape and not tier 3's. Labelling them tier 3 is
    what made the tier stop meaning anything: `CLAUDE.md` says tier 3 is *"the machinery
    worked, check the premise"*, and a catch-all offers no premise to check.

    `present` and `absent` look like a pair and are not one. `present` is a test on the data —
    something measured this — so a row conditioned on it did tier-3 work. `absent` is a test on
    the *absence* of data, which is exactly the case with no measurement behind it.

    Static on purpose: an author sees each branch's tier while writing it, and a reviewer can
    predict a build's review load from the rules rather than from a run.
    """
    positive = [key for key, expected in when.items() if expected != ABSENT]
    return Tier.DATA_PROFILED if positive else Tier.CONVENTION


def matches(when: dict[str, Any], premises: "dict[str, Premise]") -> bool:
    return all(_one(key, expected, premises.get(key)) for key, expected in when.items())


def _one(fact: str, expected: Any, premise: "Premise | None") -> bool:
    if expected == ABSENT:
        return premise is None
    if expected == PRESENT:
        return premise is not None
    if premise is None:
        return False
    actual = premise.value

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

    A cohort is refused rather than compared. `read_length` is `per_sample`, so a profile may
    carry `[150, 100, 150]`, and `[150, 100, 150] >= 70` is a `TypeError` raised from inside
    the resolver with no rule named in it. Aggregating first is what `derives:` is for, and the
    diagnostic says so — a refusal names the offending thing *and* what would have been right.

    The numeric conversion is attempted and fallen back on rather than decided by the
    measurement's `kind`, because `matches` deliberately does not take a registry: it is called
    from load-time validation over rules whose facts may be derived and have no declaration to
    consult. `"< beta"` comparing two strings is legitimate and rare; `"< 70"` is the case.
    """
    if isinstance(actual, list):
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
