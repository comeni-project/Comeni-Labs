"""The registry is a layer, and a layer is a directory that can live anywhere.

Federation §8 moves `contracts/`, `rules/`, `vocabularies/` and `measurements/` out of
`examples/` and into the `comeni-registry` repository. What is testable here is that the
move is a path change and nothing else.
"""

import pathlib
import shutil

import pytest
import yaml
from comeni_core.declared.layer import REGISTRY_FORMAT, LayerManifest
from comeni_core.declared.layered import _KIND_OF, DeclaredKind
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent


def test_the_layer_describes_itself():
    """A layer that moves to its own repository has to say what it is, since the
    directory name it happened to be checked out into stops being meaningful."""
    manifest = yaml.safe_load((ROOT / "registry" / "registry.yml").read_text())
    assert manifest["name"]
    assert manifest["licence"] == "CC-BY-4.0"


def test_the_manifest_places_every_kind_that_exists():
    """`layout:` is `mendel registry lint`'s argument, and a kind it does not mention is a kind
    the lint cannot place — so a correctly filed file of that kind would be refused.

    **This test used to pin `kinds:` against a hardcoded list**, and that was the whole problem:
    `kinds:` had no consumer, its own comment said so, and pinning a literal is what let it name
    four kinds for the whole of Plan 1.15 Task 0 — which shipped `roles/` beside it. A33 again.
    The list is derived from `DeclaredKind` here, so a seventh kind fails this rather than
    quietly not being linted.
    """
    manifest = LayerManifest.of(ROOT / "registry")
    assert manifest is not None
    placed = set(manifest.layout)
    expected = {_KIND_OF_SINGULAR[kind] for kind in DeclaredKind}
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


# ═══ THE VERSION FLOOR — Plan 5B §2.1, spec §1.3 ═══════════════════════════════════════════
#
# **It lands before the feature it protects, and that is the whole of why it is a phase of its
# own.** A compatibility check that arrives with the change it guards is a check every older
# install has already failed to run: the registry ships `params.{param}`, an older Mendel does
# no substitution, and the seven literal characters go into Groovy.


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
