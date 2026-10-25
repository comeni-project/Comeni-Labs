"""Payload-to-arrow binding and source-subject serialization contracts."""

import pytest
from mendel_authoring.payloads import (
    EMPTY,
    Empty,
    SampleAnswered,
    check,
    source_of,
    source_subject,
)


def test_source_subject_round_trips_the_consumer_and_port():
    subject = source_subject("nf-core/subread/featurecounts@2.0.6", "bam")

    assert subject == "nf-core/subread/featurecounts@2.0.6|bam"
    assert source_of(subject) == ("nf-core/subread/featurecounts@2.0.6", "bam")


def test_payload_check_accepts_only_the_type_bound_to_the_arrow():
    payload = SampleAnswered(answered=True)

    assert check("upload_sample", payload) is payload
    with pytest.raises(ValueError, match="upload_sample: payload must be SampleAnswered"):
        check("upload_sample", Empty())


def test_an_untyped_arrow_accepts_only_the_shared_empty_payload():
    assert check(None, EMPTY) is EMPTY
    with pytest.raises(ValueError, match="None: payload must be Empty"):
        check(None, SampleAnswered(answered=False))
