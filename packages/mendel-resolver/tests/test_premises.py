"""The facts a rule may read, and where each one came from.

Tier 3 is defined as producing `value + rule + measurement` and produced only the first two:
a measured build and an asserted one had a byte-identical `steps:` block (A108). The premise
is the missing third, and it has to carry its own provenance or `sealed` cannot refuse a
decision resting on an assertion (issue #2).

`ValueSource` answers *who settled this*. `PremiseOrigin` answers *how good is it as a
premise*, and the two are not the same question — which is why there are two enums and a
mapping between them rather than one enum used twice.
"""

import pathlib

import pytest
from comeni_core.tiers import ValueSource
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.premises import PremiseOrigin, build_premises

ROOT = pathlib.Path(__file__).parents[3]
LOADED = layers.load(ROOT / "registry")


def _goal(source: ValueSource = ValueSource.MEASURED, **measured) -> Goal:
    """A goal whose profile carries `measured`, through the one validated constructor.

    `MeasurementRegistry.profile()` rather than `DataProfile(...)`: the construction guard
    scans `packages/*/src` and not `tests/`, so building one directly here would pass — and
    it would skip the validation that makes an undeclared measurement impossible, which is
    the whole reason that constructor exists.
    """
    return Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["counts.matrix"],
        profile=LOADED.measurements.profile(measured, source=source),
    )


def test_a_measured_fact_says_it_was_measured():
    premises = build_premises(
        goal=_goal(read_length=150), derivations=[], measurements=LOADED.measurements
    )
    assert premises["read_length"].value == 150
    assert premises["read_length"].origin is PremiseOrigin.MEASURED


def test_an_asserted_fact_is_not_a_measured_one():
    """The distinction `sealed` exists to act on (issue #2).

    `Measured.source` is per entry, so one profile can carry a measured `read_length` beside
    an asserted `strandedness`, and the premise layer must not flatten them into one claim.
    """
    premises = build_premises(
        goal=_goal(ValueSource.GOAL, strandedness="reverse"),
        derivations=[],
        measurements=LOADED.measurements,
    )
    assert premises["strandedness"].origin is PremiseOrigin.ASSERTED


def test_a_human_override_is_evidence_of_the_same_quality_as_a_goal_assertion():
    """Different authors, identical evidence: in neither case did anything look at the data.

    Collapsing them here rather than at each point of use is what keeps `sealed` a single
    check instead of a list somebody has to keep complete.
    """
    premises = build_premises(
        goal=_goal(ValueSource.HUMAN, strandedness="forward"),
        derivations=[],
        measurements=LOADED.measurements,
    )
    assert premises["strandedness"].origin is PremiseOrigin.ASSERTED


def test_a_goal_declared_purpose_is_a_premise():
    """Spec §4.6 — `purpose` is a declared measurement, so it needs no field on `Goal`.

    Adding one would widen a door-1 *and* door-4 payload and pull in the egress guard and
    invariant 14's literal list. `Measured.source` already distinguishes a goal assertion
    from a measurement, so the existing machinery answers A120 for the price of one YAML
    file. `n_samples` is the precedent: a measurement describing the study, not a read.
    """
    premises = build_premises(
        goal=_goal(ValueSource.GOAL, purpose="variant_calling"),
        derivations=[],
        measurements=LOADED.measurements,
    )
    assert premises["purpose"].value == "variant_calling"
    assert premises["purpose"].origin is PremiseOrigin.ASSERTED


def test_required_states_reach_the_premise_set():
    """A120's cheaper half: the router already consults these and `when` could not see them.

    R11 — Salmon for transcript-level, featureCounts for gene-level — dies on exactly this.
    """
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
    )
    premises = build_premises(
        goal=goal, derivations=[], measurements=LOADED.measurements
    )
    assert "gene_level" in premises["required_states"].value
    assert premises["required_states"].origin is PremiseOrigin.GOAL


def test_required_states_is_present_and_empty_rather_than_absent():
    """So `when: {required_states: absent}` means "the goal asked for no states" and not
    "this build predates the field". A premise that vanishes when empty cannot be tested."""
    premises = build_premises(
        goal=_goal(read_length=150), derivations=[], measurements=LOADED.measurements
    )
    assert premises["required_states"].value == []


def test_nothing_may_declare_a_measurement_named_required_states():
    """It is the goal's own shape. A measurement of that name would silently shadow it, and
    the shadowing would depend on which the loader reached first."""
    from mendel_resolver.premises import PremiseError

    class _Shadowing:
        def ids(self):
            return ["required_states"]

    with pytest.raises(PremiseError, match="MD0303"):
        build_premises(
            goal=Goal(have=[GoalInput(type_id="fastq.reads")], want=["counts.matrix"]),
            derivations=[],
            measurements=_Shadowing(),
        )
