import pathlib

import pytest
from comeni_core.declared.measurement import BadMeasurementValueError, MeasurementRegistry
from comeni_core.plan.tiers import ValueSource
from mendel_resolver.goal import DataProfile, Goal
from pydantic import ValidationError

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `contracts/nf-core/fastqc.yml` sits two levels down from the directory that names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


@pytest.fixture
def measurements(tmp_path):
    d = tmp_path / "measurements"
    d.mkdir()
    (d / "read_length.yml").write_text(
        _declared(
            d / "read_length.yml",
            "kind: integer\nminimum: 1\n"))
    (d / "strandedness.yml").write_text(
        _declared(
            d / "strandedness.yml",
            "kind: enum\nvalues: [forward, reverse, unstranded]\n"))
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
