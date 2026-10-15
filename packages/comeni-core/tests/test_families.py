"""Families: the first level of the type choice (#194).

A model choosing a type is shown the families first, then every type of the families it chose,
whole. Families are closed like every other vocabulary (invariant 7) and stack like every other
kind (invariant 11).
"""

import pytest
from comeni_core.declared.families import (
    Family,
    FamilyVocabulary,
    UnknownFamilyError,
    family_of,
)
from comeni_core.declared.layered import DeclaredKind


def _vocab(*ids):
    return FamilyVocabulary(families={i: Family(id=i, description=f"{i} things") for i in ids})


def _write(directory, family_id, description):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{family_id}.yml").write_text(
        f"declares: family\nid: {family_id}\ndescription: {description}\n"
    )


def test_a_type_belongs_to_the_family_before_its_first_dot():
    assert family_of("genome.index.star") == "genome"
    assert family_of("profile.yml") == "profile"


def test_a_type_whose_family_is_undeclared_is_refused_naming_both():
    with pytest.raises(UnknownFamilyError, match=r"MD0316.*variants\.vcf.*variants"):
        _vocab("fastq").check(["fastq.reads", "variants.vcf"])


def test_declared_families_pass():
    _vocab("fastq", "genome").check(["fastq.reads", "genome.index.star"])


def test_types_of_is_each_family_whole_and_sorted():
    types = ["genome.fasta", "fastq.reads", "genome.index.star", "counts.matrix"]
    assert _vocab("genome").types_of(["genome"], types) == ["genome.fasta", "genome.index.star"]


def test_families_are_a_declared_kind():
    assert DeclaredKind.FAMILIES.value == "families"


def test_a_family_file_loads(tmp_path):
    _write(tmp_path, "alignment", "Reads placed on a reference")
    loaded = FamilyVocabulary.load(tmp_path)
    assert loaded.families["alignment"].description == "Reads placed on a reference"


def test_an_overlay_replaces_a_familys_description_and_adds_its_own(tmp_path):
    base, lab = tmp_path / "base", tmp_path / "lab"
    _write(base, "alignment", "Reads placed on a reference")
    _write(lab, "alignment", "Reads on our lab's assemblies")
    _write(lab, "variants", "Differences from a reference")
    loaded = FamilyVocabulary.load([base, lab])
    assert loaded.families["alignment"].description == "Reads on our lab's assemblies"
    assert set(loaded.families) == {"alignment", "variants"}


def test_a_family_needs_a_description():
    with pytest.raises(ValueError):
        Family(id="alignment", description="")
