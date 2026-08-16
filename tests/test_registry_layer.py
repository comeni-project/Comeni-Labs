"""The registry is a layer, and a layer is a directory that can live anywhere.

Federation §8 moves `contracts/`, `rules/`, `vocabularies/` and `measurements/` out of
`examples/` and into the `comeni-registry` repository. What is testable here is that the
move is a path change and nothing else.
"""

import pathlib

import yaml
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent


def test_the_layer_describes_itself():
    """A layer that moves to its own repository has to say what it is, since the
    directory name it happened to be checked out into stops being meaningful."""
    manifest = yaml.safe_load((ROOT / "registry" / "registry.yml").read_text())
    assert manifest["name"]
    assert manifest["licence"] == "CC-BY-4.0"
    assert manifest["kinds"] == ["contracts", "measurements", "roles", "rules", "vocabularies"]


def test_the_layer_loads_from_its_new_home():
    loaded = layers.load(ROOT / "registry")
    assert len(loaded.registry.all()) >= 12
    assert loaded.measurements.ids() == [
        "adapter_content",
        "duplicate_rate",
        "genome_length",
        "library_prep",
        "n_samples",
        "node_memory_gb",
        "organism",
        "paired",
        "purpose",
        "read_length",
        "rrna_fraction",
        "strandedness",
    ]


def test_the_layer_loads_from_anywhere(tmp_path):
    """The move to comeni-registry is a path change and nothing else. Prove it by loading
    the layer from a directory with a different name."""
    import shutil

    elsewhere = tmp_path / "comeni-registry"
    shutil.copytree(ROOT / "registry", elsewhere)
    assert len(layers.load(elsewhere).registry.all()) >= 12


def test_the_goal_file_stayed_behind():
    """`Registry.load` globs `*.yml` recursively, so a goal file inside a layer would be
    read as a contract. It lives one level up for that reason."""
    assert (ROOT / "examples" / "rnaseq-goal.yml").exists()
    assert not list((ROOT / "registry").glob("*-goal.yml"))


def test_the_manifest_is_not_read_as_a_contract():
    """`registry.yml` sits at the layer root beside `contracts/`, never inside it, so the
    recursive glob that finds contracts never sees it. If it moved one level down, every
    build would fail trying to validate a manifest as a `ModuleContract`."""
    assert (ROOT / "registry" / "registry.yml").exists()
    # `registry.yml` sits at the layer root and nowhere else. It used to be phrased as
    # "not inside contracts/", which stopped meaning anything when the layer was
    # arranged by tool (comeni-registry#1) and `contracts/` ceased to exist.
    assert [p.relative_to(ROOT / "registry") for p in (ROOT
        / "registry").rglob("registry.yml")] == [
        pathlib.Path("registry.yml")
    ]
    assert layers.load(ROOT / "registry").registry.all()
