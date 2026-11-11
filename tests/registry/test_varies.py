"""A person may say a per-sample fact differs between samples (#466): `constraints.varies`."""

import pytest
from comeni_core.goal.asked import Goal
from mendel_resolver import layers
from support.paths import ROOT

LOADED = layers.load(ROOT / "registry")


def _goal(profile: dict, varies: list[str]) -> Goal:
    return Goal.model_validate({
        "have": [{"type_id": "fastq.reads"}], "want": ["counts.matrix"],
        "constraints": {"varies": varies},
        "profile": LOADED.measurements.profile(profile).model_dump(mode="json")})


def test_varies_is_sorted_and_kept():
    assert _goal({}, ["strandedness", "paired"]).constraints.varies == ["paired", "strandedness"]


def test_a_fact_cannot_be_stated_and_vary():
    with pytest.raises(ValueError, match="MD0332.*strandedness"):
        LOADED.measurements.check_varies(_goal({"strandedness": "reverse"}, ["strandedness"]))


def test_a_study_fact_cannot_vary():
    with pytest.raises(ValueError, match="MD0332.*genome_length"):
        LOADED.measurements.check_varies(_goal({}, ["genome_length"]))


def test_a_sample_fact_that_varies_is_accepted():
    LOADED.measurements.check_varies(_goal({"read_length": 150}, ["strandedness"]))


def test_samples_that_disagree_on_a_meta_fact_must_say_it_varies():
    """`paired: [true, false]` would reach no module's `meta`, and single-end samples would run
    as paired (Task 2 review). Saying it varies is what carries it per sample."""
    with pytest.raises(ValueError, match="MD0332.*paired"):
        LOADED.measurements.check_varies(_goal({"paired": [True, False]}, []))
    LOADED.measurements.check_varies(_goal({"paired": [True, True]}, []))


def test_an_equality_test_on_a_list_is_refused():
    """A list is several samples; `== true` over it has no one answer (Task 2 review)."""
    from comeni_core.logic.when import PredicateError, matches

    class Seen:
        value = [True, False]

    for expected in (True, {"not": True}, {"in": [True]}):
        with pytest.raises(PredicateError, match="MD0312"):
            matches({"paired": expected}, {"paired": Seen()})


def test_describes_must_name_a_declared_type(tmp_path):
    """A typo in `describes` would silently make a reference's fact per sample."""
    import shutil

    layer = tmp_path / "layer"
    shutil.copytree(ROOT / "registry", layer, ignore=shutil.ignore_patterns(".git"))
    path = layer / "vocabulary" / "measurements" / "genome_length.yml"
    path.write_text(path.read_text().replace("describes: genome.fasta", "describes: genome.fasat"))
    with pytest.raises(ValueError, match="MD0334.*genome.fasat"):
        layers.load(layer)


def test_the_goals_required_states_keep_their_plain_meaning():
    """`required_states` is a list by shape, not several samples (Task 3 review): a rule
    reading it is not refused."""
    from comeni_core.logic.when import matches

    class States:
        value = ["gene_level"]

    assert matches({"required_states": "transcript_level"}, {"required_states": States()}) is False
