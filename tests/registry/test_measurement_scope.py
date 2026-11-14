"""A measurement's scope is the grain of the type it describes (#466): `per_sample` is gone.

Read length describes reads, which arrive per sample, so it may differ between samples. Genome
length describes the reference, one for the study, so it cannot. Declaring the two separately
would be a second statement of one fact, free to disagree with the first.
"""

import pytest
from comeni_core.declared.measurement import Measurement
from comeni_core.plan.tiers import Grain
from mendel_resolver import layers
from support.paths import ROOT


@pytest.fixture(scope="module")
def measurements():
    return layers.load(ROOT / "registry").measurements


def test_read_length_is_per_sample(measurements):
    assert measurements.scope_of("read_length") is Grain.SAMPLE


def test_genome_length_is_study(measurements):
    assert measurements.scope_of("genome_length") is Grain.STUDY


def test_organism_is_study(measurements):
    assert measurements.measurements["organism"].describes is None
    assert measurements.scope_of("organism") is Grain.STUDY


def test_a_list_for_a_study_fact_is_refused(measurements):
    with pytest.raises(ValueError, match="genome_length"):
        measurements.profile({"genome_length": [1000, 2000]})


def test_a_list_for_a_sample_fact_is_kept(measurements):
    assert measurements.profile({"read_length": [150, 100]}).get("read_length") == [150, 100]


def test_per_sample_is_gone():
    with pytest.raises(ValueError, match="per_sample"):
        Measurement.model_validate({"id": "read_length", "kind": "integer", "per_sample": True})


def test_a_uniform_list_reaches_meta_as_one_value(measurements):
    profile = measurements.profile({"strandedness": ["reverse", "reverse"]})
    sourced = measurements.meta_sources_by_type({"fastq.reads"}, profile)
    assert sourced["fastq.reads"]["strandedness"][1] == "reverse"


def test_a_varying_list_is_never_one_constant_in_meta(measurements):
    """Two samples, two strandednesses: one value in every sample's `meta` would be wrong for
    one of them. It travels per sample instead, from the samplesheet."""
    profile = measurements.profile({"strandedness": ["forward", "reverse"]})
    sourced = measurements.meta_sources_by_type({"fastq.reads"}, profile)
    assert "strandedness" not in sourced.get("fastq.reads", {})
