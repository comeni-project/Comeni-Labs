"""A role is the job a contract does, and a rule targets one.

Audit A119 and A123 are one defect: a rule's target named a *type*, so two unrelated
decisions about `alignment.bam` shared a key and REPLACE stacking deleted one of them.
Reproduced 2026-08-15 — a lab's duplicate-handling rule swapped the aligner on 50bp reads
and both builds passed `gate lint` at exit 0.

Roles are closed like every other vocabulary (invariant 7), and they stack like every other
kind (invariant 11), which is why they live in `roles/` rather than in a file at the layer
root: `stack()` reads `layer.path / kind.which.value`, a directory.
"""

import pathlib

import pytest
from comeni_core.roles import RoleVocabulary, UnknownRoleError
from pydantic import ValidationError

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
    (overlay / "roles" / "extra.yml").write_text("roles: [ribo_depletion]\n")
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
    """The validator `RoleName` carries. Watched failing 2026-08-15: removing the
    `AfterValidator` broke nothing, so this is the test that makes it mean something."""
    from comeni_core.contract import ModuleContract

    for bad in ("Alignment", "ribo-depletion", "2pass", "_hidden", "trailing_"):
        with pytest.raises(ValidationError, match="is not a role name"):
            ModuleContract.model_validate({**_MINIMAL, "roles": [bad]})
    assert ModuleContract.model_validate({**_MINIMAL, "roles": ["ribo_depletion"]}).roles


def test_a_vocabulary_cannot_declare_a_role_no_contract_could_name(tmp_path):
    """Otherwise `roles.yml` declares `Ribo-Depletion`, it loads, and every contract naming
    it is refused by `RoleName` — a declaration nothing can use. Same defect as A122."""
    overlay = tmp_path / "lab"
    (overlay / "roles").mkdir(parents=True)
    (overlay / "roles" / "bad.yml").write_text("roles: [Ribo-Depletion]\n")
    with pytest.raises(ValueError, match="is not a role name"):
        RoleVocabulary.load([REGISTRY, overlay])
