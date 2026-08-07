import pytest
from comeni_core.measurement import BadMeasurementValueError, MeasurementRegistry
from comeni_core.tiers import ValueSource
from mendel_resolver.goal import DataProfile, Goal
from pydantic import ValidationError


@pytest.fixture
def measurements(tmp_path):
    d = tmp_path / "measurements"
    d.mkdir()
    (d / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
    (d / "strandedness.yml").write_text("kind: enum\nvalues: [forward, reverse, unstranded]\n")
    return MeasurementRegistry.load(tmp_path)


def test_the_mapping_form_still_works():
    """Every existing call site and every goal file writes it this way."""
    profile = DataProfile(read_length=150, strandedness="reverse")
    assert profile.get("read_length") == 150
    assert profile.get("strandedness") == "reverse"


def test_an_unmeasured_value_is_none():
    assert DataProfile(read_length=150).get("paired") is None


def test_a_bare_scalar_is_an_assertion():
    """A human typed it, so it is asserted. The syntax matches the meaning."""
    profile = DataProfile(read_length=150)
    assert profile.measurements[0].source is ValueSource.GOAL


def test_a_registry_built_profile_validates(measurements):
    profile = measurements.profile({"read_length": 150, "strandedness": "reverse"})
    assert profile.get("read_length") == 150


def test_a_registry_built_profile_rejects_an_undeclared_measurement(measurements):
    with pytest.raises(Exception, match="organism"):
        measurements.profile({"organism": "homo_sapiens"})


def test_a_registry_built_profile_rejects_a_bad_value(measurements):
    with pytest.raises(BadMeasurementValueError, match="sideways"):
        measurements.profile({"strandedness": "sideways"})


def test_a_goal_still_carries_a_profile():
    goal = Goal(want=["counts.matrix"], profile={"read_length": 150})
    assert goal.profile.get("read_length") == 150


def test_the_profile_forbids_unknown_shapes():
    with pytest.raises(ValidationError):
        DataProfile(measurements="not a list")


def test_a_generated_profile_records_the_tool_that_measured_it(measurements):
    """Provenance is per measurement, because a profile can mix the two."""
    profile = measurements.profile({"read_length": 150}, source=ValueSource.MEASURED)
    assert profile.measurements[0].source is ValueSource.MEASURED
