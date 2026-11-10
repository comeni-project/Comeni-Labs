"""What a run measured, read back as Wiener's own events and compared with the build (#465)."""

import pytest
from wiener_core.events import EventKind, admit, measured
from wiener_core.measured import (
    DecidedValue,
    Estimate,
    MeasuredFact,
    collect,
    compare,
)
from wiener_core.state import replay


def _fact(sample, value, measurement="read_length", **kw):
    return MeasuredFact(measurement=measurement, sample=sample, value=value, coverage="all",
                        by=["fastq@1.1.0", "read_length@1.0.0"], **kw)


def test_nextflow_cannot_author_a_measured_event():
    with pytest.raises(ValueError, match="MW0002"):
        admit({"event": "measured", "utcTime": "2026-11-10T10:00:00Z"}, run_id="r", seq=0)


def test_facts_are_collected_once_each_in_a_stable_order():
    events = [measured("r", 1, 2, fact=_fact("b", 100)),
              measured("r", 1, 3, fact=_fact("a", 150)),
              measured("r", 1, 4, fact=_fact("a", 150)),
              measured("r", 1, 5, decided=DecidedValue(step="star", setting="n", sample="a",
                                                       value="6"))]
    got = collect(events)
    assert [(f.sample, f.value) for f in got.facts] == [("a", 150), ("b", 100)]
    assert [d.value for d in got.decided] == ["6"]
    assert replay(events).last_seq == 5


def test_an_estimate_the_run_bears_out_is_confirmed_and_one_it_does_not_disagrees():
    got = collect([measured("r", 1, 1, fact=_fact("a", 150)),
                   measured("r", 1, 2, fact=_fact("b", 100))])
    views = {v.sample: v for v in compare(got, [Estimate(measurement="read_length",
                                                         estimate=150,
                                                         used_by=["selection:align"])])}
    assert views["a"].status == "confirmed"
    assert views["b"].status == "disagrees" and views["b"].used_by == ["selection:align"]
    assert views["b"].estimate == 150


def test_a_fact_nothing_estimated_is_measured_and_one_without_a_value_undetermined():
    got = collect([measured("r", 1, 1, fact=_fact("g", 29903, measurement="genome_length")),
                   measured("r", 1, 2, fact=_fact("h", None, measurement="genome_length",
                                                  undetermined="no sequences"))])
    assert [v.status for v in compare(got, [])] == ["measured", "undetermined"]


def test_numbers_agree_across_int_and_float():
    got = collect([measured("r", 1, 1, fact=_fact("a", 150.0))])
    (view,) = compare(got, [Estimate(measurement="read_length", estimate=150, used_by=[])])
    assert view.status == "confirmed"


def test_the_kind_is_wieners_own():
    assert measured("r", 1, 1, fact=_fact("a", 1)).kind is EventKind.MEASURED
    with pytest.raises(ValueError):
        measured("r", 1, 1)


def test_collect_reads_a_generator_whole():
    """The route hands it a generator; both facts and decided values come out (Task 9)."""
    events = [measured("r", 1, 1, fact=_fact("a", 150)),
              measured("r", 1, 2, decided=DecidedValue(step="s", setting="n", sample="a",
                                                       value="6"))]
    got = collect(e for e in events)
    assert len(got.facts) == 1 and len(got.decided) == 1
