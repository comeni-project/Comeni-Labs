"""The family check, through the real loader (#194).

`packages/comeni-core/tests/test_families.py` proves `FamilyVocabulary.check` works; only a load
of a real stack proves `layers.load()` calls it — the lesson `test_roles_through_the_loader.py`
was written for. Every test here copies the shipped registry and breaks one thing.
"""

import pathlib
import shutil

import pytest
from comeni_core.declared.families import UnknownFamilyError
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parents[3]
REGISTRY = ROOT / "registry"


def _registry_copy(tmp_path: pathlib.Path) -> pathlib.Path:
    layer = tmp_path / "layer"
    shutil.copytree(REGISTRY, layer, ignore=shutil.ignore_patterns(".git"))
    return layer


def test_the_shipped_registry_loads_with_its_families():
    loaded = layers.load(REGISTRY)
    assert {"alignment", "fastq", "genome", "measurement"} <= set(loaded.families.families)


def test_a_type_whose_family_is_removed_fails_the_load(tmp_path):
    layer = _registry_copy(tmp_path)
    (layer / "families" / "fastq.yml").unlink()
    with pytest.raises(UnknownFamilyError, match=r"MD0316.*fastq\.reads"):
        layers.load(layer)


def test_a_tool_directorys_own_type_is_held_to_a_family_too(tmp_path):
    """`genome.index.star` is declared under `tools/nf-core/star`, not `types/`."""
    layer = _registry_copy(tmp_path)
    (layer / "families" / "genome.yml").unlink()
    with pytest.raises(UnknownFamilyError, match=r"MD0316.*genome\."):
        layers.load(layer)


def test_derived_measurement_types_need_the_measurement_family(tmp_path):
    """They exist only after `with_measurements`, so the check must run after it."""
    layer = _registry_copy(tmp_path)
    (layer / "families" / "measurement.yml").unlink()
    with pytest.raises(UnknownFamilyError, match=r"MD0316.*measurement\."):
        layers.load(layer)


def test_an_overlay_brings_a_type_and_its_family(tmp_path):
    lab = tmp_path / "lab"
    lab.mkdir()
    (lab / "variants.vcf.yml").write_text("declares: vocabulary\nid: variants.vcf\nstates: []\n")
    with pytest.raises(UnknownFamilyError, match="variants"):
        layers.load([REGISTRY, lab])
    (lab / "variants.yml").write_text(
        "declares: family\nid: variants\ndescription: Differences from a reference\n"
    )
    loaded = layers.load([REGISTRY, lab])
    assert "variants" in loaded.families.families
