"""`profile_of` over entries that say what measured them, against the shipped registry (#134)."""

import pytest
from comeni_core.declared.measurement import MeasuredEntry
from comeni_core.goal.profile import Evidence
from comeni_core.plan.tiers import ValueSource
from mendel_resolver import layers
from support.paths import ROOT

PIECES = ("fastq@1.0.0", "read_length@1.0.0")


def _measurements():
    return layers.load(ROOT / "registry").measurements


def test_profile_of_carries_pieces_and_evidence():
    profile = _measurements().profile_of(
        [
            MeasuredEntry(
                "read_length",
                151,
                ValueSource.MEASURED,
                pieces=PIECES,
                evidence=Evidence(records=8412, share=0.97),
            ),
            MeasuredEntry("strandedness", "reverse", ValueSource.GOAL),
        ]
    )
    measured = {m.measurement: m for m in profile.measurements}
    assert measured["read_length"].pieces == list(PIECES)
    assert measured["read_length"].evidence.records == 8412
    assert measured["strandedness"].source is ValueSource.GOAL


def test_profile_of_still_checks_every_value():
    """Review focus 4: a person's `"yes"` for `paired` is refused, as before."""
    with pytest.raises(ValueError, match="paired"):
        _measurements().profile_of([MeasuredEntry("paired", "yes", ValueSource.GOAL)])


def test_an_inspected_meta_value_says_which_pieces_measured_it_and_on_how_much():
    from comeni_core.artifact.materialise import _meta_entry

    measurements = _measurements()
    profile = measurements.profile_of(
        [
            MeasuredEntry(
                "read_length",
                151,
                ValueSource.MEASURED,
                pieces=PIECES,
                evidence=Evidence(records=8412),
            ),
        ]
    )
    entry = _meta_entry("read_length", measurements.get("read_length"), 151, profile)
    assert entry.why.reason.startswith(
        "measured by fastq@1.0.0 + read_length@1.0.0, on 8,412 reads"
    )


def test_a_profiled_meta_value_still_names_its_contract():
    from comeni_core.artifact.materialise import _meta_entry

    measurements = _measurements()
    profile = measurements.profile_of(
        [MeasuredEntry("read_length", 151, ValueSource.MEASURED, by="comeni/profile/fastqc@0.12.1")]
    )
    entry = _meta_entry("read_length", measurements.get("read_length"), 151, profile)
    assert entry.why.reason.startswith("measured by comeni/profile/fastqc@0.12.1")


def _reason(entry_evidence, measurement="read_length", value=151):
    from comeni_core.artifact.materialise import _meta_entry

    measurements = _measurements()
    profile = measurements.profile_of(
        [MeasuredEntry(measurement, value, ValueSource.MEASURED, pieces=PIECES,
                       evidence=entry_evidence)]
    )
    return _meta_entry(measurement, measurements.get(measurement), value, profile).why.reason


def test_paireds_rows_are_cited_when_it_counted_no_records():
    """Issue 225: `paired` counts rows, not records, and its count never showed."""
    assert ", on 50,000 rows of reads" in _reason(Evidence(rows=50000), "paired", True)


def test_a_count_of_zero_is_cited_not_dropped():
    assert ", on 0 reads" in _reason(Evidence(records=0))


def test_pieces_given_as_one_string_are_refused_by_name():
    """Issue 225: `"fastq@1.0.0"` was read letter by letter: `'f' is not a piece ref`."""
    with pytest.raises(ValueError, match="pieces .* a tuple of piece refs, not one string"):
        _measurements().profile_of(
            [MeasuredEntry("read_length", 151, ValueSource.MEASURED, pieces="fastq@1.0.0")]
        )
