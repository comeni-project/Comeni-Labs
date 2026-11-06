"""Constraints checked by trying every setup (#460): contradictions, dead and fake-optional
inputs, outputs never produced, and the bound on how many setups are tried."""

import pytest
from comeni_core import yaml_strict
from comeni_core.declared.constraints import check_constraints
from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.vocabulary import Vocabulary
from support.paths import ROOT

FIXTURES = ROOT / "packages/comeni-core/tests/fixtures/constraints"
PROVENANCE = {"source": "t", "drafted_by": "t", "approved_by": "t", "approved_at": "2026-11-06"}


def _tool(consumes: list[dict], **more) -> ModuleContract:
    optional = [p["name"] for p in consumes if p.get("required") is False]
    return ModuleContract.model_validate({
        "id": "test/tool@1.0", "nf_process": "TOOL", "nf_include": "modules/test/tool/main",
        "consumes": consumes,
        "nf_inputs": [{"ports": [p["name"]], **({"absent": 2} if p["name"] in optional else {})}
                      for p in consumes],
        "provenance": PROVENANCE, **more})


def _codes(contract: ModuleContract) -> list[str]:
    return [finding.split(":")[0] for finding in check_constraints(contract)]


A = {"name": "a", "type_id": "fastq.reads"}
B = {"name": "b", "type_id": "genome.fasta", "required": False}
C = {"name": "c", "type_id": "annotation.gtf", "required": False}


def test_a_required_input_that_is_forbidden_is_a_contradiction():
    contract = _tool([A, B], constraints=[
        {"when": {}, "forbids": ["a"], "because": "contradicts itself"}])
    assert _codes(contract) == ["MD0603"]


def test_an_optional_input_no_valid_setup_connects_is_dead():
    contract = _tool([A, B], constraints=[
        {"when": {"given.b": "present"}, "forbids": ["a"], "because": "b rules out a"}])
    assert _codes(contract) == ["MD0604"]


def test_an_optional_input_every_valid_setup_connects_is_fake():
    contract = _tool([A, B], constraints=[
        {"when": {}, "requires": ["b"], "because": "always needed"}])
    assert _codes(contract) == ["MD0605"]


def test_an_output_whose_condition_never_holds_is_never_produced():
    contract = _tool([A, B, C], produces=[
        {"name": "x", "type_id": "qc.report", "produced_when": {"given.b": "present"}}],
        constraints=[{"when": {"given.b": "present"}, "forbids": ["b"],
                      "because": "b cannot be used"}])
    assert "MD0606" in _codes(contract)


def test_too_many_setups_is_refused_rather_than_skipped():
    many = [A, *({"name": f"o{n}", "type_id": "genome.fasta", "required": False}
                 for n in range(13))]
    assert _codes(_tool(many)) == ["MD0607"]


def test_the_quast_kraken2_and_gatk_fixtures_are_clean():
    for name in ("quast", "kraken2", "gatk4_haplotypecaller"):
        contract = ModuleContract.model_validate(yaml_strict.load(FIXTURES / f"{name}.yml"))
        assert check_constraints(contract) == [], name


def test_load_refuses_a_contract_with_a_finding(tmp_path):
    path = tmp_path / "contract.yml"
    path.write_text(
        "declares: contract\nid: test/tool@1.0\nnf_process: TOOL\n"
        "nf_include: modules/test/tool/main\n"
        "consumes: [{name: a, type_id: fastq.reads}]\n"
        "constraints: [{when: {}, forbids: [a], because: contradicts itself}]\n"
        "provenance: {source: t, drafted_by: t, approved_by: t, approved_at: '2026-11-06'}\n")
    vocab = Vocabulary(types={"fastq.reads": frozenset()})
    with pytest.raises(ValueError, match="MD0603"):
        ModuleContract.load(path, vocab)


def test_a_param_named_only_in_requires_is_enumerated():
    """Final review I3: a param in `requires` but in no `when` was absent from every setup."""
    contract = _tool([A, B], params=[{"name": "k", "via": "positional", "default": 21,
                                      "because": "the tool's default"}],
                     constraints=[{"when": {"given.b": "present"}, "requires": ["k"],
                                   "because": "b needs k"}])
    contract = contract.model_copy(update={"nf_inputs": [*contract.nf_inputs,
                                                         contract.nf_inputs[0].model_copy(
                                                             update={"ports": [], "param": "k"})]})
    assert check_constraints(contract) == []


def test_a_param_with_a_default_that_a_row_forbids_kills_the_input():
    contract = _tool([A, B], params=[{"name": "k", "via": "positional", "default": 21,
                                      "because": "the tool's default"}],
                     constraints=[{"when": {"given.b": "present"}, "forbids": ["k"],
                                   "because": "b cannot run with k"}])
    assert _codes(contract) == ["MD0604"]
