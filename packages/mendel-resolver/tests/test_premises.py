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
from mendel_resolver.premises import PremiseError, PremiseOrigin, build_premises
from mendel_resolver.rules import Derivation

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


_INFER_STRANDEDNESS = {
    "fact": "strandedness",
    "kind": "enum",
    "rows": [
        {
            "when": {"strandedness": "absent"},
            "then": "reverse",
            "because": "dUTP protocols dominate current library prep, so reverse is the "
            "safer default where nothing measured it — and this records that nothing did",
            "cite": "Wang et al. 2012, doi:10.1093/bib/bbs046",
        }
    ],
}
"""R15, which the shipped format loads dead: a row conditioned on an absent measurement
validated clean and could never fire, because `when` could only read a measurement that was
there. Audit A122."""


def test_a_derivation_fills_a_gap():
    derivation = Derivation.model_validate(_INFER_STRANDEDNESS)
    premises = build_premises(
        goal=_goal(), derivations=[derivation], measurements=LOADED.measurements
    )
    assert premises["strandedness"].value == "reverse"
    assert premises["strandedness"].origin is PremiseOrigin.DERIVED
    assert premises["strandedness"].derived_from == ["strandedness"]


def test_a_derivation_never_overwrites_a_measurement():
    """The half that makes the other half safe. A fallback that can overwrite is not a
    fallback, and the failure is silent: the pipeline would resolve against a default while
    the profile beside it named the measured value."""
    derivation = Derivation.model_validate(_INFER_STRANDEDNESS)
    premises = build_premises(
        goal=_goal(strandedness="forward"),
        derivations=[derivation],
        measurements=LOADED.measurements,
    )
    assert premises["strandedness"].value == "forward"
    assert premises["strandedness"].origin is PremiseOrigin.MEASURED


def test_a_derivation_carries_the_row_justification_it_fired_on():
    """§4.7 and MD0301: a premise a reader cannot check is what tier 3 being *advisory*
    was supposed to prevent. A derived fact is the case with no measurement behind it at
    all, so it is the one that most needs to say why."""
    derivation = Derivation.model_validate(_INFER_STRANDEDNESS)
    premises = build_premises(
        goal=_goal(), derivations=[derivation], measurements=LOADED.measurements
    )
    assert "dUTP" in premises["strandedness"].because
    assert premises["strandedness"].cite.startswith("Wang et al. 2012")


def test_a_derivation_with_no_rows_is_refused():
    """A derivation that cannot fire is A122's own shape, one layer down: it loads clean,
    contributes nothing, and reads to a reviewer as a fact the registry supplies. Spec §5 —
    everything is refused at load."""
    with pytest.raises(ValueError, match="MD0304"):
        Derivation.model_validate({"fact": "strandedness", "kind": "enum", "rows": []})


def test_a_derivation_row_that_matches_nothing_leaves_the_fact_unmeasured():
    """`absent` is the whole point of R15, so the case where a row simply does not fire has
    to be distinguishable from the case where the derivation was not there. A gap is
    evidence; it is evidence of a gap."""
    derivation = Derivation.model_validate(
        {
            "fact": "strandedness",
            "kind": "enum",
            "rows": [{"when": {"read_length": 999}, "then": "reverse", "because": "never"}],
        }
    )
    premises = build_premises(
        goal=_goal(read_length=150), derivations=[derivation], measurements=LOADED.measurements
    )
    assert "strandedness" not in premises


def test_a_derivation_whose_row_would_match_still_never_overwrites():
    """The guard `test_a_derivation_never_overwrites_a_measurement` was too weak to be.

    That test conditions on `strandedness: absent`, so with a measured strandedness the row
    fails its own predicate and the never-overwrite rule is never consulted — deleting the
    rule left all twelve tests green. This one conditions on a *different* fact, so the row
    matches and only the rule stands between a measurement and a default.

    Found by reverting, in code written the same hour. The plan's Step 5 predicted the weak
    test would fail and it does not, for exactly this reason.
    """
    derivation = Derivation.model_validate(
        {
            "fact": "strandedness",
            "kind": "enum",
            "rows": [
                {
                    "when": {"read_length": 150},
                    "then": "reverse",
                    "because": "a row that matches on a fact other than the one it derives",
                }
            ],
        }
    )
    premises = build_premises(
        goal=_goal(read_length=150, strandedness="forward"),
        derivations=[derivation],
        measurements=LOADED.measurements,
    )
    assert premises["strandedness"].value == "forward"
    assert premises["strandedness"].origin is PremiseOrigin.MEASURED


def test_a_derivation_never_overwrites_an_earlier_derivation_either():
    """First wins, rather than last. Two derivations of the same fact is a registry defect
    and Task 11 should refuse it at load, but until then the resolution must not depend on
    which file `stack()` reached first — that is invariant 10, and it is the same
    first-record-wins convention `ReplayResolver` already uses for duplicate keys."""
    rows = [{"when": {"read_length": 150}, "then": "reverse", "because": "first"}]
    second = [{"when": {"read_length": 150}, "then": "forward", "because": "second"}]
    premises = build_premises(
        goal=_goal(read_length=150),
        derivations=[
            Derivation.model_validate({"fact": "strandedness", "kind": "enum", "rows": rows}),
            Derivation.model_validate({"fact": "strandedness", "kind": "enum", "rows": second}),
        ],
        measurements=LOADED.measurements,
    )
    assert premises["strandedness"].value == "reverse"


_COHORT_MAX = {
    "fact": "cohort_max_read_length",
    "kind": "integer",
    "aggregate": {"measurement": "read_length", "over": "cohort", "using": "max"},
    "because": "the index is built once per run, so it must suit the longest read in it",
    "cite": "STAR manual 2.7, --sjdbOverhang",
}
"""R19, which the shipped format cannot express at all — and §12's cohort-versus-sample
question, which it could not even ask."""


def test_an_aggregate_reduces_the_cohort():
    premises = build_premises(
        goal=_goal(read_length=[150, 100, 150]),
        derivations=[Derivation.model_validate(_COHORT_MAX)],
        measurements=LOADED.measurements,
    )
    assert premises["cohort_max_read_length"].value == 150
    assert premises["cohort_max_read_length"].origin is PremiseOrigin.DERIVED
    assert premises["cohort_max_read_length"].derived_from == ["read_length"]


def test_an_aggregate_over_a_scalar_reduces_to_that_scalar():
    """A per-sample measurement written as one value is the claim that the cohort is
    uniform, so its max is that value. Without this the fact would exist for a three-sample
    profile and vanish for a one-sample one, and no rule can be written against a fact that
    appears and disappears with the shape of the input."""
    premises = build_premises(
        goal=_goal(read_length=150),
        derivations=[Derivation.model_validate(_COHORT_MAX)],
        measurements=LOADED.measurements,
    )
    assert premises["cohort_max_read_length"].value == 150


def test_an_aggregate_over_an_absent_measurement_leaves_the_fact_absent():
    """Rather than raising. The premise it would have reduced was optional, and a rule
    reading the aggregate can ask `absent`."""
    premises = build_premises(
        goal=_goal(),
        derivations=[Derivation.model_validate(_COHORT_MAX)],
        measurements=LOADED.measurements,
    )
    assert "cohort_max_read_length" not in premises


def test_a_derivation_declaring_both_rows_and_an_aggregate_is_refused():
    """Ordering them would be a precedence no reader of the file could see — invariant 8's
    argument, one layer down."""
    with pytest.raises(ValueError, match="MD0304"):
        Derivation.model_validate({**_COHORT_MAX, "rows": [{"when": {}, "then": 1}]})


def test_a_list_is_refused_where_the_measurement_is_not_per_sample():
    """`check` is what stands between a goal file and routing. A list reaching a comparison
    predicate raises TypeError at resolution rather than a diagnostic at load."""
    with pytest.raises(ValueError, match="per_sample"):
        LOADED.measurements.profile({"n_samples": [1, 2, 3]})


# --- Issue #39: a computed fact, without an expression language ---------------------------


_SJDB_OVERHANG = {
    "fact": "sjdb_overhang",
    "kind": "integer",
    "source": "read_length",
    "transform": [{"op": "subtract", "by": 1}],
    "because": "the splice-junction overhang should be one less than the read length",
    "cite": "STAR manual 2.2.2",
}
"""R02, which the format could not express at all: `then: "read_length-1"` reached STAR as
that literal string, at tier 3, cited to a real paper. `MD0300` made the refusal honest in
Plan 1.13 and the rule stayed unwritable — issue #39."""


def test_a_transform_computes_a_fact_from_a_measurement():
    derivation = Derivation.model_validate(_SJDB_OVERHANG)
    premises = build_premises(
        goal=_goal(read_length=150), derivations=[derivation], measurements=LOADED.measurements
    )
    assert premises["sjdb_overhang"].value == 149
    assert premises["sjdb_overhang"].origin is PremiseOrigin.DERIVED
    assert premises["sjdb_overhang"].derived_from == ["read_length"]


def test_a_transform_chains_left_to_right():
    """R03: `min(14, log2(genome_length)/2 - 1)`. Four named steps, no expression parser and
    nothing to precedence-order — which is the whole point. A chain of named unary operations
    is readable in YAML, checkable at load, and cannot grow into a solver."""
    derivation = Derivation.model_validate(
        {
            "fact": "genome_sa_index_nbases",
            "kind": "integer",
            "source": "genome_length",
            "transform": [
                {"op": "log2"},
                {"op": "divide", "by": 2},
                {"op": "subtract", "by": 1},
                {"op": "at_most", "by": 14},
            ],
            "because": "the suffix-array index size must scale with the genome",
            "cite": "STAR manual 2.2.5",
        }
    )
    premises = build_premises(
        goal=_goal(genome_length=3_100_000_000),
        derivations=[derivation],
        measurements=LOADED.measurements,
    )
    # log2(3.1e9) ~ 31.5, /2 ~ 15.8, -1 ~ 14.8, capped at 14.
    assert premises["genome_sa_index_nbases"].value == 14


def test_a_transform_rounds_to_its_declared_kind():
    """`kind: integer` is a promise about the fact, not a hint. A `then` that arrives as
    15.79 where an integer was declared is the same defect as a computed string reaching the
    tool: the tool receives something its flag does not accept."""
    derivation = Derivation.model_validate(
        {
            "fact": "sjdb_overhang",
            "kind": "integer",
            "source": "read_length",
            "transform": [{"op": "divide", "by": 4}],
            "cite": "a fixture",
        }
    )
    premises = build_premises(
        goal=_goal(read_length=150), derivations=[derivation], measurements=LOADED.measurements
    )
    assert premises["sjdb_overhang"].value == 37
    assert isinstance(premises["sjdb_overhang"].value, int)


def test_a_transform_over_an_absent_measurement_leaves_the_fact_absent():
    derivation = Derivation.model_validate(_SJDB_OVERHANG)
    premises = build_premises(
        goal=_goal(), derivations=[derivation], measurements=LOADED.measurements
    )
    assert "sjdb_overhang" not in premises


def test_a_transform_over_a_cohort_reduces_it_first():
    """A per-sample measurement has no single value to transform, and picking one silently is
    the cohort-versus-sample question answered by a coin flip. `MD0312` refused a *comparison*
    against a cohort for the same reason; this is the other operator."""
    derivation = Derivation.model_validate(_SJDB_OVERHANG)
    with pytest.raises(PremiseError, match="MD0314"):
        build_premises(
            goal=_goal(read_length=[150, 100]),
            derivations=[derivation],
            measurements=LOADED.measurements,
        )


def test_a_derivation_declaring_a_transform_and_rows_is_refused():
    with pytest.raises(ValueError, match="MD0304"):
        Derivation.model_validate(
            {**_SJDB_OVERHANG, "rows": [{"when": {}, "then": 1, "cite": "a"}]}
        )


def test_a_transform_without_a_source_is_refused():
    """A chain with nothing to chain from is A122's shape again: it loads and computes
    nothing."""
    with pytest.raises(ValueError, match="MD0304"):
        Derivation.model_validate(
            {k: v for k, v in _SJDB_OVERHANG.items() if k != "source"}
        )
