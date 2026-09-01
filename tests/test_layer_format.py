"""A layer says which Mendel it needs, and an older one refuses instead of guessing.

Plan 5B phase 2.1, and **it has to land before any registry ships a template or it cannot land
at all.** Phase 2.2 makes `entry_channel` a `params.{param}` template; a registry shipping one,
read by an engine that does no substitution, writes the literal string `params.{param}` into
Groovy. That is a broken pipeline produced silently by a build that reported success, and an
older engine cannot detect it — it can only be *told*.
"""

import pathlib

import pytest
from comeni_core.declared.layer import LAYER_FORMAT, LayerManifest, LayerTooNewError
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent


def _layer(tmp_path: pathlib.Path, manifest: str) -> pathlib.Path:
    where = tmp_path / "lab"
    where.mkdir()
    (where / "registry.yml").write_text(manifest)
    (where / "read_length.yml").write_text(
        "declares: measurement\nid: read_length\nkind: integer\n"
        "why: because\ncite: nowhere\n"
    )
    return where


def test_a_layer_from_the_future_is_refused_by_name(tmp_path):
    """**The whole point.** The alternative is reading it as far as it parses and emitting
    something wrong, which is what a floor exists to replace."""
    where = _layer(tmp_path, f"name: lab\nrequires: {LAYER_FORMAT + 1}\n")

    with pytest.raises(LayerTooNewError) as caught:
        LayerManifest.of(where)

    said = str(caught.value)
    assert "MD0020" in said
    assert str(LAYER_FORMAT + 1) in said and str(LAYER_FORMAT) in said
    assert "Upgrade Mendel" in said


def test_the_refusal_reaches_the_loader(tmp_path):
    """Checked in `LayerManifest.of` rather than in `layers.load`, because that is the one
    function every reader of a manifest goes through — the loader, `layer_name`, and the lint.
    A floor checked in one caller is a floor the other callers walk past.
    """
    where = _layer(tmp_path, f"name: lab\nrequires: {LAYER_FORMAT + 1}\n")
    with pytest.raises(LayerTooNewError, match="MD0020"):
        layers.load(where)


def test_a_layer_at_this_format_loads(tmp_path):
    """The check must not fire on the thing it guards."""
    assert LayerManifest.of(_layer(tmp_path, f"name: lab\nrequires: {LAYER_FORMAT}\n")) is not None


def test_a_layer_that_declares_nothing_is_format_one(tmp_path):
    """Every layer written before the floor existed implicitly is, and there are laboratories
    holding those. A default that refused them would make the floor's first act a regression."""
    manifest = LayerManifest.of(_layer(tmp_path, "name: lab\n"))
    assert manifest is not None and manifest.requires == 1


def test_a_layer_with_no_manifest_at_all_is_still_legal(tmp_path):
    """A private overlay a lab assembled by hand is the common case, and requiring a manifest
    to load one would make the guard more annoying than the bug it closes."""
    where = tmp_path / "bare"
    where.mkdir()
    (where / "x.yml").write_text("declares: role\nroles: [trimming]\n")
    assert LayerManifest.of(where) is None


def test_the_shipped_registry_declares_a_floor_this_engine_meets():
    """It has to, or `make check` is testing an engine nothing can be built with."""
    manifest = LayerManifest.of(ROOT / "registry")
    assert manifest is not None
    assert manifest.requires <= LAYER_FORMAT
