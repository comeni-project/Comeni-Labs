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
