"""Profile evidence, provenance validation, and reviewer-facing premise prose."""

import pytest
from comeni_core.goal.profile import DataProfile, Evidence, Measured
from comeni_core.plan.tiers import PremiseOrigin, ValueSource
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


@pytest.mark.parametrize(
    "bad",
    # A piece reference has a bounded, lowercase identifier and a semantic version.
    ["fastq", "fastq@1", "Fastq@1.0.0", "fastq@1.0.0\nx", "a/b@1.0.0", "a" * 65 + "@1.0.0",
     "fastq@1.0." + "9" * 40],
)
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
    """Absent pieces and evidence stay out of the serialized measurement."""
    m = Measured(measurement="strandedness", value="reverse")
    assert m.model_dump(mode="json") == {
        "measurement": "strandedness",
        "value": "reverse",
        "source": "said",
        "by": None,
    }


def test_a_share_above_one_is_refused():
    with pytest.raises(ValidationError):
        Evidence(share=1.2)


def test_evidence_writes_only_the_counts_it_has():
    """Unknown evidence counts stay out of serialized output instead of becoming nulls."""
    assert Evidence(records=8412, share=0.97).model_dump(mode="json") == {
        "records": 8412,
        "share": 0.97,
    }


def test_evidence_that_says_nothing_is_refused():
    with pytest.raises(ValidationError, match="no count"):
        Evidence()


@pytest.mark.parametrize("field", ["records", "rows"])
def test_evidence_counts_cannot_be_negative(field):
    with pytest.raises(ValidationError):
        Evidence(**{field: -1})


@pytest.mark.parametrize("source", [ValueSource.SAID, ValueSource.HUMAN])
def test_pieces_or_evidence_on_a_value_nobody_measured_are_refused(source):
    """Its reason would say *asserted* while its entry names what measured it."""
    with pytest.raises(ValidationError, match="measured"):
        Measured(measurement="read_length", value=151, source=source, pieces=PIECES)
    with pytest.raises(ValidationError, match="measured"):
        Measured(
            measurement="read_length", value=151, source=source, evidence=Evidence(records=9)
        )


def test_a_profile_rejects_repeated_measurements():
    with pytest.raises(ValidationError, match="repeated: read_length"):
        DataProfile(
            measurements=[
                Measured(measurement="read_length", value=101),
                Measured(measurement="read_length", value=151),
            ]
        )


# A decision names the profiler or inspector pieces that measured its premise.

from comeni_core.goal.premise import PremiseRecord  # noqa: E402


def test_a_premise_an_inspector_measured_names_its_pieces():
    record = PremiseRecord(id="read_length", value=101, origin=PremiseOrigin.MEASURED,
                           pieces=PIECES)
    assert record.prose() == "read_length is 101, measured by fastq@1.0.0 + read_length@1.0.0"


def test_a_premise_a_profiler_measured_names_its_contract():
    record = PremiseRecord(id="read_length", value=151, origin=PremiseOrigin.MEASURED,
                           by="comeni/profile/fastqc@0.12.1")
    assert record.prose() == "read_length is 151, measured by comeni/profile/fastqc@0.12.1"


def test_a_premise_with_no_measurer_reads_as_before_and_dumps_as_before():
    record = PremiseRecord(id="read_length", value=150, origin=PremiseOrigin.MEASURED)
    assert record.prose() == "read_length is 150, measured"
    assert record.model_dump(mode="json") == {
        "id": "read_length", "value": 150, "origin": "measured",
    }


@pytest.mark.parametrize(
    ("origin", "description"),
    [
        (PremiseOrigin.MODEL_READ, "read by AI"),
        (PremiseOrigin.ASSERTED, "asserted, not measured"),
        (PremiseOrigin.GOAL, "declared in the goal"),
        (PremiseOrigin.DERIVED, "inferred — nothing measured it"),
        (PremiseOrigin.UNMEASURED, "not measured"),
    ],
)
def test_each_non_measured_premise_origin_has_its_public_description(origin, description):
    record = PremiseRecord(id="read_length", value=150, origin=origin)
    assert record.prose() == f"read_length is 150, {description}"
