import pytest
from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.layered import DeclaredKind
from mendel_forge.assemble import contract_from, to_yaml
from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.scaffold import FilledValue, Filler, Hole, Scaffold


def _complete() -> Scaffold:
    def derived(value):
        return FilledValue(value=value, filler=Filler.DERIVED, by="nf-core", why="main.nf")

    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="tools/nf-core/fastqc/fastqc.contract.yml",
        observation=Observation(
            source="nf-core",
            ref_id="nf-core:fastqc",
            facts={"process": Fact(value="FASTQC", evidence=Excerpt(locator="m:1", text="t"))},
        ),
        filled={
            "id": derived("nf-core/fastqc@0.12.1"),
            "nf_process": derived("FASTQC"),
            "nf_include": derived("modules/nf-core/fastqc/main"),
            "container": derived("quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0"),
            "produces[0].name": derived("zip"),
            "produces[0].type_id": FilledValue(
                value="qc.report", filler=Filler.HAND, by="rafael", why="it is a report"
            ),
            "roles": FilledValue(
                value=["qc_per_sample"], filler=Filler.HAND, by="rafael", why="it QCs a sample"
            ),
            "priority_because": FilledValue(
                value="the only QC tool", filler=Filler.HAND, by="rafael", why="no alternative"
            ),
            "provenance.source": derived("nf-core"),
        },
        holes=[],
    )


def test_a_complete_scaffold_becomes_a_real_contract():
    contract = contract_from(_complete(), approved_by="rafael", approved_at="2026-08-20")
    assert isinstance(contract, ModuleContract)
    assert contract.nf_process == "FASTQC"
    assert contract.produces[0].type_id == "qc.report"
    assert contract.roles == ["qc_per_sample"]


def test_provenance_carries_the_filler_forward():
    """`drafted_by` is where Phase 2's model id lands, and the field already exists."""
    contract = contract_from(_complete(), approved_by="rafael", approved_at="2026-08-20")
    assert contract.provenance.source == "nf-core"
    assert contract.provenance.approved_by == "rafael"
    assert contract.provenance.drafted_by == "hand", "no model was involved, so say so"


def test_a_scaffold_with_a_hole_refuses_rather_than_defaulting():
    """The property everything rests on. A default here would be the forge inventing a
    value with a straight face, which is what a hole exists to prevent."""
    incomplete = _complete().model_copy(
        update={"holes": [Hole(field="roles", what="w", why_open="o")]}
    )
    with pytest.raises(ValueError, match="MF0004") as caught:
        contract_from(incomplete, approved_by="r", approved_at="2026-08-20")
    assert "roles" in str(caught.value)


def test_the_yaml_declares_its_own_kind():
    text = to_yaml(_complete(), approved_by="rafael", approved_at="2026-08-20")
    assert text.startswith("declares: contract\n")


def test_the_yaml_round_trips_through_the_real_loader(tmp_path):
    """The strongest assertion available: what the forge writes is what the registry reads."""
    from pathlib import Path

    from mendel_resolver import layers

    root = Path(__file__).resolve().parents[3]
    stack = layers.load(root / "registry")
    path = tmp_path / "fastqc.contract.yml"
    path.write_text(to_yaml(_complete(), approved_by="rafael", approved_at="2026-08-20"))
    assert ModuleContract.load(path, stack.vocabulary).id == "nf-core/fastqc@0.12.1"
