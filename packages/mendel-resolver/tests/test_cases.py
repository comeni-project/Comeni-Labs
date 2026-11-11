"""A rule's cases, with the measurement that could not decide among them (#466).

The cases are the ones `check_table` already tries, one per interval and boundary the rows tell
apart, plus *undetermined* for each fact: a measurement in the run can come back without a
value, and the build must know what such a sample gets before the run.
"""

import pytest
from mendel_resolver import layers
from mendel_resolver.cases import UNDETERMINED, cases, overlapping, uncovered
from mendel_resolver.rules.format import Decision
from support.paths import ROOT

LOADED = layers.load(ROOT / "registry")


def _decision(rows: list[dict], hit: str = "first") -> Decision:
    return Decision.model_validate({
        "decides": {"effect": "param", "of": "alignment", "name": "threads"},
        "hit": hit, "rows": rows})


def _row(when: dict, then: object) -> dict:
    return {"when": when, "then": then, "because": "a reason", "cite": "a source"}


def test_numeric_cases_straddle_each_threshold():
    decision = _decision([_row({"read_length": ">= 70"}, 8)])
    found = cases(["read_length"], decision.rows, LOADED.measurements, {})
    assert [c["read_length"] for c in found] == [69, 70, 71, UNDETERMINED]


def test_alignment_rows_leave_only_undetermined_uncovered():
    alignment = next(d for d in LOADED.rules.decisions
                     if d.key() == "implementation:alignment")
    assert uncovered(alignment, ["read_length"], {}, LOADED.measurements, {}) == [
        {"read_length": UNDETERMINED}]


def test_a_gap_between_rows_is_uncovered():
    decision = _decision([_row({"read_length": ">= 70"}, 8), _row({"read_length": "< 50"}, 2)])
    gaps = uncovered(decision, ["read_length"], {}, LOADED.measurements, {})
    assert {"read_length": 50} in gaps and {"read_length": UNDETERMINED} in gaps
    assert {"read_length": 70} not in gaps and {"read_length": 49} not in gaps


def test_overlapping_unique_rows_are_found():
    decision = _decision([_row({"read_length": ">= 70"}, 8), _row({"read_length": ">= 50"}, 4)],
                         hit="unique")
    overlaps = overlapping(decision, ["read_length"], {}, LOADED.measurements, {})
    assert (0, 1, {"read_length": 70}) in overlaps
    assert all(case["read_length"] is not UNDETERMINED for _, _, case in overlaps)


def test_two_facts_take_their_product():
    decision = _decision([_row({"strandedness": "reverse", "paired": True}, 1)])
    found = cases(["paired", "strandedness"], decision.rows, LOADED.measurements, {})
    assert len(found) == (2 + 1) * (3 + 1)


def test_a_known_fact_is_substituted_not_enumerated():
    decision = _decision([_row({"strandedness": "reverse", "paired": True}, 1)])

    class Known:
        value = True

    gaps = uncovered(decision, ["strandedness"], {"paired": Known()}, LOADED.measurements, {})
    assert {"strandedness": "forward"} in gaps and {"strandedness": "reverse"} not in gaps


def test_too_many_cases_is_refused():
    facts = ["paired", "strandedness", "quality_encoding"]
    decision = _decision([_row({f: v for f, v in zip(facts, (True, "reverse", "phred33"),
                                                     strict=True)}, 1)])
    from mendel_resolver import cases as module

    with pytest.raises(ValueError, match="MD0324"):
        module.cases(facts, decision.rows, LOADED.measurements, {}, bound=10)


def test_a_fact_that_cannot_be_enumerated_is_not_reported_clean():
    """No cases is not no gaps (Task 4 review): the caller must not decide at run time."""
    from comeni_core.declared.measurement import MeasurementKind

    decision = _decision([_row({"x": "a"}, 1)])
    derived = {"x": MeasurementKind.ENUM}
    assert uncovered(decision, ["x"], {}, LOADED.measurements, derived) is None
    assert overlapping(decision, ["x"], {}, LOADED.measurements, derived) is None


def test_cases_stay_within_the_declared_bounds():
    """`read_length` is at least 1, so 0 is no case a sample can be (Task 4 review)."""
    decision = _decision([_row({"read_length": ">= 1"}, 8)])
    assert uncovered(decision, ["read_length"], {}, LOADED.measurements, {}) == [
        {"read_length": UNDETERMINED}]


def test_an_integer_fact_gets_whole_points():
    decision = _decision([_row({"read_length": ">= 70"}, 8)])
    found = cases(["read_length"], decision.rows, LOADED.measurements, {})
    assert all(type(c["read_length"]) is int for c in found if c["read_length"] is not UNDETERMINED)


def test_a_fact_both_known_and_unknown_is_refused():
    decision = _decision([_row({"paired": True}, 1)])

    class Known:
        value = True

    with pytest.raises(ValueError, match="both"):
        uncovered(decision, ["paired"], {"paired": Known()}, LOADED.measurements, {})


def test_a_unique_rule_over_a_per_sample_fact_may_not_overlap():
    """Nobody can answer a tie per sample in the run, so the author fixes it (operator, 11-11)."""
    from mendel_resolver.rules.validate import check_table

    decision = _decision([_row({"read_length": ">= 70"}, 8), _row({"read_length": ">= 50"}, 4)],
                         hit="unique")
    findings = check_table(decision, measurements=LOADED.measurements, derived={})
    assert findings and findings[0].startswith("MD0333")
    assert "rows 1 and 2" in findings[0] and "read_length = 70" in findings[0]


def test_a_unique_rule_over_a_study_fact_may_still_tie():
    """A tie over the study's facts is the build's question, as rules v2 has it."""
    from mendel_resolver.rules.validate import check_table

    decision = _decision([_row({"genome_length": ">= 70"}, 8),
                          _row({"genome_length": ">= 50"}, 4)], hit="unique")
    assert check_table(decision, measurements=LOADED.measurements, derived={}) == []
