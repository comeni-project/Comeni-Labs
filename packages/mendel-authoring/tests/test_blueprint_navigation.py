"""Package-owned navigation contracts for stored resolver blueprints."""

import pytest


def test_blueprint_navigation_follows_declared_reveal_order(rnaseq):
    blueprint = rnaseq(read_length=150)

    assert blueprint.after(None) == "fastqc"
    assert blueprint.after("fastqc") == "star_align"
    assert blueprint.after("multiqc") is None


def test_blueprint_lookup_refuses_unknown_steps(rnaseq):
    blueprint = rnaseq(read_length=150)

    with pytest.raises(KeyError, match="missing"):
        blueprint.step("missing")
    with pytest.raises(ValueError, match="missing"):
        blueprint.after("missing")
