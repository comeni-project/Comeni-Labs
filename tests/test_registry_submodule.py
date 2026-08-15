"""An unchecked-out submodule says so, rather than failing thirty-three times about contracts.

`registry/` is a git submodule since issue #46. `git clone` without `--recurse-submodules`
leaves it as an **empty directory that exists** — so every "does the path exist" check passes,
the loader finds no contracts, and the failure surfaces as `cannot route this goal` or as a
contract count of zero. None of those names the cause, and the cause is one command away.

This is the repository's least-tested class of state, because it only ever occurs on somebody
else's machine. Producing it here is the only way the message is ever read.
"""

import pathlib

import pytest
from comeni_core.declared.layered import DeclaredKind
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent


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
    (overlay / "contracts" / "a.yml").write_text("")
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
    """`len(DeclaredKind)` rather than a literal — invariant 11's stated reason.

    The count said "four" in prose for six plans and was wrong the day `roles/` arrived.
    """
    empty = tmp_path / "registry"
    empty.mkdir()
    with pytest.raises(ValueError) as caught:
        layers.load(empty)
    assert str(len(DeclaredKind)) in str(caught.value)
