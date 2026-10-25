"""Behavioral checks for role spelling, closure, and layer composition."""

import pathlib

import pytest
from comeni_core.declared.roles import RoleVocabulary, UnknownRoleError
from pydantic import ValidationError

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

ROOT = pathlib.Path(__file__).parents[3]
REGISTRY = ROOT / "registry"

_MINIMAL = {
    "id": "nf-core/star/align@1.11.0",
    "nf_process": "STAR_ALIGN",
    "nf_include": "modules/nf-core/star/align/main",
    "provenance": {"source": "t", "drafted_by": "t", "approved_by": "t", "approved_at": "t"},
}


def test_the_shipped_registry_declares_the_roles_its_contracts_fill():
    names = RoleVocabulary.load(REGISTRY).names
    assert {"alignment", "trimming", "quantification"} <= names


def test_an_overlay_adds_a_role_the_base_does_not_have(tmp_path):
    """A lab vendoring a step type we do not ship must be able to name it."""
    overlay = tmp_path / "lab"
    (overlay / "roles").mkdir(parents=True)
    (overlay / "roles" / "extra.yml").write_text(
        _declared(overlay / "roles" / "extra.yml", "roles: [ribo_depletion]\n")
    )
    names = RoleVocabulary.load([REGISTRY, overlay]).names
    assert "ribo_depletion" in names
    assert "alignment" in names, "an overlay adds; it does not replace the base"


def test_an_undeclared_role_is_refused_and_the_message_names_what_exists(tmp_path):
    vocabulary = RoleVocabulary(names=frozenset({"alignment", "trimming"}))
    with pytest.raises(UnknownRoleError) as exc:
        vocabulary.check("nf-core/star/align@1.11.0", ["alignmnet"])
    message = str(exc.value)
    assert "alignmnet" in message
    assert "alignment" in message, "naming what does exist is half the message"
    assert "MD0302" in message


def test_a_contract_may_fill_no_role_and_still_load(tmp_path):
    """Empty is legal, so the field is addable without rewriting every layer that day.
    Task 4's `test_every_contract_declares_a_role` is what stops it staying empty here."""
    vocabulary = RoleVocabulary(names=frozenset({"alignment"}))
    vocabulary.check("some/contract@1.0.0", [])


def test_a_role_name_is_snake_case_on_a_contract():
    """Contract role references use the same snake-case names as the vocabulary."""
    from comeni_core.declared.contract import ModuleContract

    for bad in ("Alignment", "ribo-depletion", "2pass", "_hidden", "trailing_"):
        with pytest.raises(ValidationError, match="is not a role name"):
            ModuleContract.model_validate({**_MINIMAL, "roles": [bad]})
    assert ModuleContract.model_validate({**_MINIMAL, "roles": ["ribo_depletion"]}).roles


def test_a_vocabulary_cannot_declare_a_role_no_contract_could_name(tmp_path):
    """Reject declarations that no contract could reference legally."""
    overlay = tmp_path / "lab"
    (overlay / "roles").mkdir(parents=True)
    (overlay / "roles" / "bad.yml").write_text(
        _declared(overlay / "roles" / "bad.yml", "roles: [Ribo-Depletion]\n")
    )
    with pytest.raises(ValueError, match="is not a role name"):
        RoleVocabulary.load([REGISTRY, overlay])
