"""Optional inputs, conditional outputs, constraint rows and groups in a contract (#460).

QUAST is the case that found the gap: its reference (`fasta`) and `gff` are optional, and three
of its reports exist only with a reference. GATK's `dbsnp` and its index go together or not at
all. These tests build contracts inline, so each states the one thing it is about.
"""

from typing import Any

import pytest
from comeni_core.declared.contract import GroupKind, ModuleContract

PROVENANCE = {"source": "test", "drafted_by": "test", "approved_by": "test",
              "approved_at": "2026-11-06"}


def _quast(**changes: Any) -> dict:
    contract = {
        "id": "nf-core/quast@5.3.0", "nf_process": "QUAST",
        "nf_include": "modules/nf-core/quast/main", "roles": ["qc_per_sample"],
        "consumes": [
            {"name": "consensus", "type_id": "assembly.fasta"},
            {"name": "fasta", "type_id": "genome.fasta", "required": False},
            {"name": "gff", "type_id": "annotation.gff", "required": False},
        ],
        "produces": [
            {"name": "results", "type_id": "qc.report", "format": ["folder"]},
            {"name": "misassemblies", "type_id": "qc.report", "format": ["tsv"],
             "produced_when": {"given.fasta": "present"}},
        ],
        "nf_inputs": [{"ports": ["consensus"]}, {"ports": ["fasta"], "absent": 2},
                      {"ports": ["gff"], "absent": 2}],
        "constraints": [{"when": {"given.gff": "present"}, "requires": ["fasta"],
                         "because": "QUAST reads --features only against a reference (-r)"}],
        "provenance": PROVENANCE,
    }
    contract.update(changes)
    return contract


def _refused(code: str, data: dict) -> None:
    with pytest.raises(ValueError, match=code):
        ModuleContract.model_validate(data)


def test_quast_loads_with_optional_inputs_and_a_conditional_output():
    contract = ModuleContract.model_validate(_quast())
    ports = {p.name: p for p in contract.consumes}
    assert ports["consensus"].required is True
    assert ports["fasta"].required is False and ports["gff"].required is False
    outputs = {p.name: p for p in contract.produces}
    assert outputs["results"].produced_when is None
    assert outputs["misassemblies"].produced_when == {"given.fasta": "present"}
    assert contract.optional_ports() == ["fasta", "gff"]
    assert contract.constraints[0].requires == ["fasta"]


def test_a_row_naming_an_unknown_port_is_refused():
    row = {"when": {"given.gff": "present"}, "requires": ["FASTA"], "because": "case matters"}
    _refused("MD0602", _quast(constraints=[row]))


def test_a_when_with_a_measurement_key_is_refused_in_phase_1():
    row = {"when": {"paired": True}, "requires": ["fasta"], "because": "per sample: #466"}
    _refused("MD0602", _quast(constraints=[row]))


def test_given_must_name_a_port_and_param_a_param():
    for when in ({"given.nope": "present"}, {"param.nope": True}):
        _refused("MD0602", _quast(constraints=[
            {"when": when, "requires": ["fasta"], "because": "names nothing"}]))
    _refused("MD0602", _quast(produces=[
        {"name": "results", "type_id": "qc.report", "produced_when": {"given.nope": "present"}}]))


def test_a_row_must_require_or_forbid_something():
    with pytest.raises(ValueError):
        ModuleContract.model_validate(_quast(constraints=[
            {"when": {"given.gff": "present"}, "because": "says nothing"}]))


def test_an_all_optional_entry_needs_absent_and_a_required_one_forbids_it():
    _refused("MD0601", _quast(nf_inputs=[{"ports": ["consensus"]}, {"ports": ["fasta"]},
                                         {"ports": ["gff"], "absent": 2}]))
    _refused("MD0601", _quast(nf_inputs=[{"ports": ["consensus"], "absent": 2},
                                         {"ports": ["fasta"], "absent": 2},
                                         {"ports": ["gff"], "absent": 2}]))


def _gatk(groups: list[dict]) -> dict:
    return {
        "id": "nf-core/gatk4/haplotypecaller@4.6.1", "nf_process": "GATK4_HAPLOTYPECALLER",
        "nf_include": "modules/nf-core/gatk4/haplotypecaller/main", "roles": ["calling"],
        "consumes": [
            {"name": "input", "type_id": "alignment.bam"},
            {"name": "dbsnp", "type_id": "variants.vcf", "required": False},
            {"name": "dbsnp_tbi", "type_id": "variants.tbi", "required": False},
        ],
        "nf_inputs": [{"ports": ["input"]},
                      {"ports": ["dbsnp", "dbsnp_tbi"], "absent": 3, "join": "broadcast"}],
        "groups": groups,
        "provenance": PROVENANCE,
    }


def test_a_multi_port_entry_is_all_required_or_one_all_or_none_group():
    _refused("MD0601", _gatk([]))
    contract = ModuleContract.model_validate(_gatk([
        {"kind": "all_or_none", "members": ["dbsnp", "dbsnp_tbi"],
         "because": "the tabix index is read with the VCF it indexes"}]))
    assert contract.groups[0].kind is GroupKind.ALL_OR_NONE


def test_a_group_names_real_ports_or_params():
    _refused("MD0602", _gatk([{"kind": "all_or_none", "members": ["dbsnp", "nope"],
                               "because": "names nothing"}]))
