"""Diagnostics for an empty registry submodule and minimal private overlays."""

import pathlib

import pytest
from comeni_core.declared.layered import _KIND_OF, DeclaredKind, declared_kind
from mendel_resolver import layers
from support.paths import ROOT

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Add the declaration marker implied by a fixture's containing directory."""
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/fastqc.contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body



def test_an_empty_layer_directory_names_the_submodule(tmp_path):
    empty = tmp_path / "registry"
    empty.mkdir()
    with pytest.raises(ValueError) as caught:
        layers.load(empty)
    message = str(caught.value)
    assert "submodule" in message
    assert "git submodule update --init" in message


def test_a_layer_with_one_kind_is_not_mistaken_for_an_empty_one(tmp_path):
    """An overlay carrying only contracts is the normal private-layer case, not a broken one.

    Written because the tempting spelling is `all(...)`, which would refuse every real
    overlay: a laboratory shipping three contracts over the public base has no `rules/`,
    no `vocabularies/` and no `measurements/`.
    """
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    (overlay / "contracts" / "a.yml").write_text(_declared(overlay / "contracts" / "a.yml", ""))
    # Loading it fully would need a real contract; the refusal is what is under test, and
    # it must not be what raises.
    with pytest.raises(Exception) as caught:  # noqa: B017 - any error but ours
        layers.load(overlay)
    assert "submodule" not in str(caught.value)


def test_the_real_registry_loads():
    """The check must not fire on the thing it guards."""
    loaded = layers.load(ROOT / "registry")
    assert loaded.registry.contracts


def test_the_message_counts_the_kinds_rather_than_asserting_a_number(tmp_path):
    """The missing-kind diagnostic derives its choices from the complete kind mapping."""
    where = tmp_path / "nothing.yml"
    where.write_text("id: something\n")
    with pytest.raises(ValueError) as caught:
        declared_kind(where)

    said = str(caught.value)
    assert "MD0010" in said
    # The singular spellings are explicit because `vocabularies` cannot be singularized safely.
    assert set(_KIND_OF.values()) == set(DeclaredKind), (
        "a declared kind has no singular spelling, so no file can ever declare it and "
        "MD0010 will not offer it"
    )
    for singular in _KIND_OF:
        assert singular in said, (
            f"{singular!r} is a kind a file may declare and the refusal does not offer it"
        )


def test_an_empty_layer_is_refused_by_name(tmp_path):
    """The other half of what the test above used to cover: the submodule case still fires."""
    empty = tmp_path / "registry"
    empty.mkdir()
    with pytest.raises(ValueError, match="submodule"):
        layers.load(empty)
