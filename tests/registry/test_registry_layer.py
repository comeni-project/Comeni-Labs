"""Integration checks for registry manifests, relocatable layers, and format compatibility."""

import pathlib
import shutil

import pytest
import yaml
from comeni_core.declared.layer import REGISTRY_FORMAT, LayerManifest
from comeni_core.declared.layered import _KIND_OF, DeclaredKind
from mendel_resolver import layers
from support.paths import ROOT


def test_the_layer_describes_itself():
    """A layer that moves to its own repository has to say what it is, since the
    directory name it happened to be checked out into stops being meaningful."""
    manifest = yaml.safe_load((ROOT / "registry" / "registry.yml").read_text())
    assert manifest["name"]
    assert manifest["licence"] == "CC-BY-4.0"


AHEAD_OF_THE_REGISTRY = {"test"}
"""Kinds this engine knows and the pinned submodule's `layout:` does not place yet. `test` lands in
comeni-registry with forge MVP 5 (#366), with `ENGINE_REF`: remove it from here then."""


def test_the_manifest_places_every_kind_that_exists():
    """Every declared kind has a manifest layout entry that registry lint can enforce."""
    manifest = LayerManifest.of(ROOT / "registry")
    assert manifest is not None
    placed = set(manifest.layout)
    expected = {_KIND_OF_SINGULAR[kind] for kind in DeclaredKind} - (AHEAD_OF_THE_REGISTRY - placed)
    assert placed == expected, (
        "every declared kind needs a place in `layout:` or the lint cannot check it:\n"
        f"  declared and unplaced: {sorted(expected - placed)}\n"
        f"  placed and not a kind: {sorted(placed - expected)}"
    )


_KIND_OF_SINGULAR = {kind: singular for singular, kind in _KIND_OF.items()}
"""`DeclaredKind.CONTRACTS` -> `"contract"`, inverted from the map a file's `declares:` line
reads. Inverted rather than written out, because two spellings of one mapping is how they come
to disagree — and `vocabularies` is not `vocabularys`."""


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
        "quality_encoding",
        "read_length",
        "rrna_fraction",
        "strandedness",
    ]


def test_the_layer_loads_from_anywhere(tmp_path):
    """Loading uses layer contents and manifest identity, not checkout location."""
    import shutil

    elsewhere = tmp_path / "comeni-registry"
    shutil.copytree(ROOT / "registry", elsewhere)
    assert len(layers.load(elsewhere).registry.all()) >= 12


def test_the_goal_file_stayed_behind():
    """`Registry.load` globs `*.yml` recursively, so a goal file inside a layer would be
    read as a contract. It lives one level up for that reason."""
    assert (ROOT / "examples" / "rnaseq.yml").exists()
    assert not list((ROOT / "registry").glob("*-goal.yml"))


def test_the_manifest_is_not_read_as_a_contract():
    """`registry.yml` sits at the layer root beside `contracts/`, never inside it, so the
    recursive glob that finds contracts never sees it. If it moved one level down, every
    build would fail trying to validate a manifest as a `ModuleContract`."""
    assert (ROOT / "registry" / "registry.yml").exists()
    # The manifest sits at the layer root and nowhere inside declared content.
    assert [p.relative_to(ROOT / "registry") for p in (ROOT
        / "registry").rglob("registry.yml")] == [
        pathlib.Path("registry.yml")
    ]
    assert layers.load(ROOT / "registry").registry.all()


# Registry format compatibility


def test_a_layer_from_the_future_is_refused_by_name():
    """MD0020. The message has to name the cause, because the alternative is a Nextflow syntax
    error on a machine that has no idea a registry was involved."""
    with pytest.raises(ValueError) as raised:
        LayerManifest(name="from-the-future", requires_format=REGISTRY_FORMAT + 1)
    assert "MD0020" in str(raised.value)
    assert "needs a newer Mendel" in str(raised.value)


def test_every_manifest_that_exists_today_loads_without_declaring_anything():
    """**The default is what makes this free.** `requires_format` is 1, which is every layer
    written before it existed — so no manifest has to be edited to keep working, and a private
    overlay that never uses a new feature never declares one."""
    assert LayerManifest(name="a-lab-overlay").requires_format == 1
    manifest = LayerManifest.of(ROOT / "registry")
    assert manifest is not None
    assert manifest.requires_format <= REGISTRY_FORMAT


def test_the_shipped_registry_still_loads():
    """The floor must not refuse the layer it ships beside. Stated as its own test because a
    floor set one too high is indistinguishable from a broken loader at every call site."""
    assert layers.load(ROOT / "registry").registry.all()


def test_the_check_is_on_the_MODEL_so_every_reader_gets_it(tmp_path):
    """`layer_name`, `mendel lint`, `Lockfile.of` and the loader all read the manifest through
    `LayerManifest.of`, and a check in one of them is a check the other three do not have.

    Written against the *loader*, which is the reader that would otherwise emit the broken
    `.nf` — so this fails if the validator is ever moved onto one call site.
    """
    layer = tmp_path / "layer"
    shutil.copytree(ROOT / "registry", layer)
    manifest = yaml.safe_load((layer / "registry.yml").read_text())
    manifest["requires_format"] = REGISTRY_FORMAT + 1
    (layer / "registry.yml").write_text(yaml.safe_dump(manifest))

    with pytest.raises(ValueError) as raised:
        layers.load(layer)
    assert "MD0020" in str(raised.value)


def test_an_equal_format_is_fine_and_only_greater_is_refused():
    """Off-by-one, and it is the one that matters: refusing `==` would make every layer
    unreadable the moment `REGISTRY_FORMAT` was bumped, which is the opposite of the point."""
    assert LayerManifest(name="exactly-current", requires_format=REGISTRY_FORMAT)
