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

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `contracts/nf-core/fastqc.yml` sits two levels down from the directory that names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body

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
    """`len(DeclaredKind)` rather than a literal — invariant 11's stated reason.

    The count said "four" in prose for six plans and was wrong the day `roles/` arrived.
    """
    empty = tmp_path / "registry"
    empty.mkdir()
    with pytest.raises(ValueError) as caught:
        layers.load(empty)
    assert str(len(DeclaredKind)) in str(caught.value)
