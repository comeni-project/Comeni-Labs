"""A measured fact names what measured it: a contract (a profiler) or inspector pieces (#134)."""

import pytest
from comeni_core.goal.profile import Evidence, Measured
from comeni_core.plan.tiers import ValueSource
from pydantic import ValidationError

PIECES = ["fastq@1.0.0", "read_length@1.0.0"]


def test_a_measured_fact_names_its_pieces_and_evidence():
    m = Measured(
        measurement="read_length",
        value=151,
        source=ValueSource.MEASURED,
        pieces=PIECES,
        evidence=Evidence(records=8412, share=0.97),
    )
    assert m.pieces == PIECES and m.evidence.records == 8412


@pytest.mark.parametrize("bad", ["fastq", "fastq@1", "Fastq@1.0.0", "fastq@1.0.0\nx", "a/b@1.0.0"])
def test_a_piece_ref_that_is_not_one_is_refused(bad):
    with pytest.raises(ValidationError):
        Measured(measurement="read_length", value=151, source=ValueSource.MEASURED, pieces=[bad])


def test_a_contract_and_pieces_together_are_refused():
    with pytest.raises(ValidationError, match="one measurer"):
        Measured(
            measurement="read_length",
            value=151,
            source=ValueSource.MEASURED,
            by="comeni/profile/fastqc@0.12.1",
            pieces=PIECES,
        )


def test_an_empty_measured_serialises_exactly_as_before():
    """Every pipeline.yml written so far must stay byte-identical."""
    m = Measured(measurement="strandedness", value="reverse")
    assert m.model_dump(mode="json") == {
        "measurement": "strandedness",
        "value": "reverse",
        "source": "goal",
        "by": None,
    }


def test_a_share_above_one_is_refused():
    with pytest.raises(ValidationError):
        Evidence(share=1.2)


def test_evidence_writes_only_the_counts_it_has():
    """Review of #134: unset counts were written as `null` in every pipeline.yml."""
    assert Evidence(records=8412, share=0.97).model_dump(mode="json") == {
        "records": 8412,
        "share": 0.97,
    }


def test_evidence_that_says_nothing_is_refused():
    with pytest.raises(ValidationError, match="no count"):
        Evidence()


@pytest.mark.parametrize("source", [ValueSource.GOAL, ValueSource.HUMAN])
def test_pieces_or_evidence_on_a_value_nobody_measured_are_refused(source):
    """Its reason would say *asserted* while its entry names what measured it."""
    with pytest.raises(ValidationError, match="measured"):
        Measured(measurement="read_length", value=151, source=source, pieces=PIECES)
    with pytest.raises(ValidationError, match="measured"):
        Measured(
            measurement="read_length", value=151, source=source, evidence=Evidence(records=9)
        )
