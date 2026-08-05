"""One test per finding in the 2026-08-06 audit, named for it.

Kept in one file rather than scattered into the suites they belong to, because the
question a reader has is "is A9 still closed?" and the answer should not require knowing
which module A9 was about. Each test carries the finding's one-line summary.

The audit is `docs/internal/audits/2026-08-06-plan-1-to-1.7-audit.md`; every finding
there records how it was reproduced, which is what these tests are the standing version of.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

CONTRACT = {
    "id": "audit/x@1.0.0",
    "nf_process": "X",
    "nf_include": "./modules/x/main",
    "provenance": {
        "source": "audit",
        "drafted_by": "audit",
        "approved_by": "audit",
        "approved_at": "2026-08-06",
    },
}


def test_a13_a_profile_rejects_a_duplicate_measurement():
    """A13 — `get` was first-wins, so list order changed the pipeline."""
    from comeni_core.profile import DataProfile

    with pytest.raises(ValidationError, match="strandedness"):
        DataProfile.model_validate(
            {
                "measurements": [
                    {"measurement": "strandedness", "value": "reverse"},
                    {"measurement": "strandedness", "value": "unstranded"},
                ]
            }
        )


def test_a13_a_profile_sorts_so_the_same_facts_are_the_same_profile():
    """Order must not survive validation, or two equal profiles compare unequal."""
    from comeni_core.profile import DataProfile

    forward = DataProfile.model_validate(
        {"measurements": [{"measurement": "a", "value": 1}, {"measurement": "b", "value": 2}]}
    )
    backward = DataProfile.model_validate(
        {"measurements": [{"measurement": "b", "value": 2}, {"measurement": "a", "value": 1}]}
    )
    assert forward.model_dump_json() == backward.model_dump_json()


def test_a11_a_contract_rejects_a_duplicate_param_name():
    """A11 — two bindings of one name reached `sorted` and compared two ResolvedValues."""
    from comeni_core.contract import ModuleContract

    with pytest.raises(ValidationError, match="threads"):
        ModuleContract.model_validate(
            {
                **CONTRACT,
                "params": [{"name": "threads", "default": 4}, {"name": "threads", "default": 8}],
            }
        )


def test_a10_an_unknown_contract_key_is_refused():
    """A10 — dropped keys meant two different files pinned to one digest."""
    from comeni_core.contract import ModuleContract

    with pytest.raises(ValidationError, match="clinical_use"):
        ModuleContract.model_validate({**CONTRACT, "clinical_use": "approved"})
    with pytest.raises(ValidationError, match="ext_arg"):
        ModuleContract.model_validate({**CONTRACT, "ext_arg": "--misspelled"})


def test_a10_every_model_a_contract_is_built_from_forbids_extras():
    """The nested models too: a smuggled key on a Param is as invisible as one on the top."""
    from comeni_core import contract as contract_module

    for name in ("ModuleContract", "InputPort", "OutputPort", "Param", "NfInput", "Provenance"):
        model = getattr(contract_module, name)
        assert model.model_config.get("extra") == "forbid", (
            f"{name} ignores unknown keys, so `digest_of` pins what survived parsing "
            "rather than the file it came from (audit A10)"
        )


def test_a10_two_contract_files_cannot_share_a_digest():
    """The property the lockfile actually sells: 'built against exactly this contract'."""
    from comeni_core.contract import ModuleContract
    from comeni_core.digest import digest_of

    plain = ModuleContract.model_validate(CONTRACT)
    with pytest.raises(ValidationError):
        ModuleContract.model_validate({**CONTRACT, "validated_by": "Dr Nobody, 2019"})
    assert digest_of(plain).startswith("sha256:")


def test_a9_a_symlinked_contract_is_refused_by_the_digest(tmp_path):
    """A9 — the registry read through it; the digest hashed its target path."""
    from comeni_core.digest import digest_of_directory

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.yml").write_text("id: alpha\n")
    contracts = tmp_path / "layer" / "contracts"
    contracts.mkdir(parents=True)
    (contracts / "c.yml").symlink_to(outside / "real.yml")

    with pytest.raises(ValueError, match="symlink"):
        digest_of_directory(tmp_path / "layer")


def test_a9_a_symlinked_layer_is_refused_at_load(tmp_path):
    """The message must arrive at load, not at publish.

    A digest that raises is a publish-time error, and publication is the door with no
    undo — by then the reroute has already happened and been emitted.
    """
    import shutil

    from mendel_resolver import layers as layers_mod

    layer = tmp_path / "lab"
    shutil.copytree("registry", layer)
    victim = next((layer / "contracts").rglob("*.yml"))
    (tmp_path / "elsewhere.yml").write_text(victim.read_text())
    victim.unlink()
    victim.symlink_to(tmp_path / "elsewhere.yml")

    with pytest.raises(ValueError, match="symlink"):
        layers_mod.load(layer)


def test_a9_an_ordinary_layer_still_digests(tmp_path):
    """The refusal must not cost the normal case."""
    import shutil

    from comeni_core.digest import digest_of_directory

    layer = tmp_path / "plain"
    shutil.copytree("registry", layer)
    assert digest_of_directory(layer) == digest_of_directory(Path("registry"))


def test_a11_the_emitter_never_compares_two_resolved_values():
    """Belt and braces: the sort key is the name, so a tie cannot reach the value.

    Task 1 makes a tie unreachable by rejecting it at the contract. This asserts the
    emitter would survive one anyway, because the next unorderable field on
    `ResolvedValue` must not resurrect a crash that is already fixed.
    """
    from comeni_core.ir import IRNode, PipelineIR, ResolvedValue, Tier
    from mendel_compiler.emit import emit
    from mendel_resolver import layers as layers_mod

    loaded = layers_mod.load("registry")
    contract = next(c for c in loaded.registry.all() if c.params)
    node = IRNode(
        id=contract.nf_process.lower(),
        contract_id=contract.id,
        selection=ResolvedValue(value=contract.id, tier=Tier.STRUCTURAL, reason="r"),
    )
    name = contract.params[0].name
    node.set_param(name, ResolvedValue(value=1, tier=Tier.CONVENTION, reason="a"))
    node.set_param(name, ResolvedValue(value=2, tier=Tier.CONVENTION, reason="b"))

    # An IR is deserialised from a bundle, so a duplicate binding stays *representable*
    # even once a contract cannot declare one. It must not reach an unorderable compare.
    emit(PipelineIR(nodes=[node]), loaded.registry, loaded.vocabulary, loaded.measurements)
