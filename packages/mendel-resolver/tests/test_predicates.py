"""One evaluator, and a row's tier read off its own text.

Two copies of a predicate is how a rule passes validation and then fails to fire — which is
what `_comparison`'s docstring already said about the last pair, and what A121 was: the old
matcher ran every literal through `float()`, so `!= unstranded` was refused as a malformed
number rather than evaluated as a negation.
"""

import pytest
from comeni_core.plan.tiers import Tier
from mendel_resolver.predicates import PredicateError, matches, tier_of_row
from mendel_resolver.premises import Premise, PremiseOrigin


def P(**facts) -> dict[str, Premise]:
    return {
        key: Premise(id=key, value=value, origin=PremiseOrigin.MEASURED)
        for key, value in facts.items()
    }


def test_equality_and_comparison_still_work():
    """The two the shipped format had. Everything below is what it could not express."""
    assert matches({"strandedness": "reverse"}, P(strandedness="reverse"))
    assert not matches({"strandedness": "reverse"}, P(strandedness="forward"))
    assert matches({"read_length": ">= 70"}, P(read_length=150))
    assert not matches({"read_length": ">= 70"}, P(read_length=50))


def test_negation_over_an_enum_is_not_a_malformed_number():
    """A121: `_comparison` ran every literal through `float()`, so `!= unstranded` was
    reported as *'unstranded is not a number. Write it as "!= 70"'* — a diagnostic telling
    the author to make a categorical comparison numeric."""
    assert matches({"strandedness": {"not": "unstranded"}}, P(strandedness="reverse"))
    assert not matches({"strandedness": {"not": "unstranded"}}, P(strandedness="unstranded"))


def test_membership_over_an_enum():
    stranded = {"strandedness": {"in": ["forward", "reverse"]}}
    assert matches(stranded, P(strandedness="reverse"))
    assert not matches(stranded, P(strandedness="unstranded"))


def test_absence_is_a_predicate():
    """A122's whole cause: `when` could only read a measurement that was there, so R15's
    'infer strandedness where nothing measured it' validated and could never fire."""
    assert matches({"strandedness": "absent"}, {})
    assert not matches({"strandedness": "absent"}, P(strandedness="reverse"))


def test_presence_is_a_predicate_and_is_not_the_negation_of_absent_over_a_value():
    """`present` asks whether anything settled the fact at all, which is a different
    question from what it settled to — and the only way to write "we know the strandedness,
    whatever it is" without enumerating the enum."""
    assert matches({"strandedness": "present"}, P(strandedness="unstranded"))
    assert not matches({"strandedness": "present"}, {})


def test_an_unknown_predicate_is_refused_rather_than_ignored():
    """A mapping with a key nothing implements would otherwise evaluate to *some* answer.
    Silently false is the dangerous one: the row never fires and reads as if it could."""
    with pytest.raises(PredicateError, match="MD0305"):
        matches({"read_length": {"betwixt": [70, 150]}}, P(read_length=100))


def test_a_comparison_against_a_cohort_is_refused_rather_than_raising_TypeError():
    """`read_length` is `per_sample`, so a profile may carry `[150, 100, 150]`. Comparing
    that to 70 has no defined meaning, and Python's answer is `TypeError` from inside the
    resolver. The rule author is told to aggregate first, which is what `derives:` is for."""
    with pytest.raises(PredicateError, match="MD0312"):
        matches({"read_length": ">= 70"}, P(read_length=[150, 100, 150]))


def test_a_row_testing_no_premise_positively_is_tier_2():
    """§4.4. A catch-all is a documented default; it did not do tier-3 work, and calling it
    tier 3 is what made the tier label stop meaning anything."""
    assert tier_of_row({}) is Tier.CONVENTION
    assert tier_of_row({"strandedness": "absent"}) is Tier.CONVENTION
    assert tier_of_row({"read_length": ">= 70"}) is Tier.DATA_PROFILED
    assert tier_of_row({"read_length": ">= 70", "paired": "absent"}) is Tier.DATA_PROFILED


def test_present_earns_tier_3_and_absent_does_not():
    """They look like a pair and are not one. `present` is a test *on the data* — something
    measured it — so a row conditioned on it did tier-3 work. `absent` is a convention about
    what to assume in a gap, which is tier 2's shape: value plus citation, no measurement."""
    assert tier_of_row({"strandedness": "present"}) is Tier.DATA_PROFILED
    assert tier_of_row({"strandedness": "absent"}) is Tier.CONVENTION
