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
