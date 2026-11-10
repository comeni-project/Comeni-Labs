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


def test_an_all_optional_entry_may_be_an_all_or_none_group():
    contract = ModuleContract.model_validate(_gatk([
        {"kind": "all_or_none", "members": ["dbsnp", "dbsnp_tbi"],
         "because": "the tabix index is read with the VCF it indexes"}]))
    assert contract.groups[0].kind is GroupKind.ALL_OR_NONE


def test_a_slot_may_mix_required_and_optional_ports():
    """gatk passes optional intervals in the same tuple as its BAM (#464)."""
    data = _gatk([])
    data["consumes"].append({"name": "intervals", "type_id": "regions.bed", "required": False})
    data["nf_inputs"][0] = {"ports": ["input", "intervals"], "join": "broadcast"}
    data["groups"] = [{"kind": "all_or_none", "members": ["dbsnp", "dbsnp_tbi"],
                       "because": "the tabix index is read with the VCF it indexes"}]
    contract = ModuleContract.model_validate(data)
    assert contract.optional_ports() == ["dbsnp", "dbsnp_tbi", "intervals"]


def _spades(**changes: Any) -> dict:
    contract = {
        "id": "nf-core/spades@4.1.0", "nf_process": "SPADES",
        "nf_include": "modules/nf-core/spades/main", "roles": ["assembly"],
        "consumes": [
            {"name": "illumina", "type_id": "fastq.reads", "required": False},
            {"name": "pacbio", "type_id": "pacbio.reads", "required": False},
            {"name": "nanopore", "type_id": "nanopore.reads", "required": False},
        ],
        "nf_inputs": [{"ports": ["illumina", "pacbio", "nanopore"], "join": "by_sample",
                       "absent": 4}],
        "groups": [{"kind": "any_of", "members": ["illumina", "pacbio", "nanopore"],
                    "because": "SPAdes assembles from at least one kind of reads"}],
        "provenance": PROVENANCE,
    }
    contract.update(changes)
    return contract


def test_a_slot_may_hold_independent_optional_ports():
    """spades takes Illumina, PacBio and Nanopore reads in one tuple, any of them (#464)."""
    contract = ModuleContract.model_validate(_spades())
    assert contract.optional_ports() == ["illumina", "pacbio", "nanopore"]


def test_an_all_optional_slot_still_needs_absent():
    _refused("MD0601", _spades(nf_inputs=[{"ports": ["illumina", "pacbio", "nanopore"],
                                           "join": "by_sample"}]))


def test_absent_on_an_all_required_slot_is_still_refused():
    _refused("MD0601", _quast(nf_inputs=[{"ports": ["consensus"], "absent": 2},
                                         {"ports": ["fasta"], "absent": 2},
                                         {"ports": ["gff"], "absent": 2}]))


def test_a_group_names_real_ports_or_params():
    _refused("MD0602", _gatk([{"kind": "all_or_none", "members": ["dbsnp", "nope"],
                               "because": "names nothing"}]))


def test_a_misspelt_given_value_is_refused():
    """Final review: `presnt` made the row silently never apply."""
    _refused("MD0602", _quast(constraints=[{"when": {"given.gff": "presnt"},
                                            "requires": ["fasta"], "because": "typo"}]))


def _gatk_slot(join: Any, *, first_optional: bool = False) -> dict:
    """gatk's real input tuple: the BAM, its per-sample index, and run-wide intervals (#464)."""
    data = _gatk([{"kind": "all_or_none", "members": ["dbsnp", "dbsnp_tbi"],
                   "because": "the tabix index is read with the VCF it indexes"}])
    data["consumes"][0]["required"] = not first_optional
    data["consumes"] += [{"name": "input_index", "type_id": "alignment.bai"},
                         {"name": "intervals", "type_id": "regions.bed", "required": False}]
    data["nf_inputs"][0] = {"ports": ["input", "input_index", "intervals"], "join": join}
    if first_optional:
        data["consumes"][3]["required"] = False
        data["nf_inputs"][0]["absent"] = 4
    return data


def test_a_slot_may_join_each_port_its_own_way():
    from comeni_core.spell.routes import Join

    contract = ModuleContract.model_validate(
        _gatk_slot({"input_index": "by_sample", "intervals": "broadcast"}))
    slot = contract.nf_inputs[0]
    assert slot.join_for("input_index") is Join.BY_SAMPLE
    assert slot.join_for("intervals") is Join.BROADCAST


def test_a_scalar_join_applies_to_every_later_port():
    from comeni_core.spell.routes import Join

    slot = ModuleContract.model_validate(_gatk_slot("by_sample")).nf_inputs[0]
    assert slot.join_for("input_index") is Join.BY_SAMPLE
    assert slot.join_for("intervals") is Join.BY_SAMPLE


@pytest.mark.parametrize("join", [
    {"input_index": "by_sample"},                                        # misses intervals
    {"input": "by_sample", "input_index": "by_sample", "intervals": "broadcast"},  # the head
    {"input_index": "by_sample", "intervals": "broadcast", "nope": "broadcast"},   # unknown
])
def test_a_join_map_names_every_later_port_and_nothing_else(join):
    with pytest.raises(ValueError, match="join map"):
        ModuleContract.model_validate(_gatk_slot(join))


def test_an_optional_first_port_with_mixed_joins_is_refused():
    """The first port that is on takes the head's place, which is sound only if every later
    port joins the same way."""
    _refused("MD0601.*join the same way",
             _gatk_slot({"input_index": "by_sample", "intervals": "broadcast"},
                        first_optional=True))


def test_a_join_map_digests_the_same_in_any_order():
    from comeni_core.artifact.digest import digest_of

    one = ModuleContract.model_validate(
        _gatk_slot({"input_index": "by_sample", "intervals": "broadcast"}))
    other = ModuleContract.model_validate(
        _gatk_slot({"intervals": "broadcast", "input_index": "by_sample"}))
    assert digest_of(one) == digest_of(other)


def test_absent_on_a_mixed_slot_is_refused():
    """A slot with a required port is never left out whole, so its `absent` would be dead."""
    data = _gatk_slot("broadcast")
    data["nf_inputs"][0]["absent"] = 4
    _refused("MD0601.*never left out whole", data)


def _typed(when: dict) -> dict:
    data = _quast()
    data["consumes"][0].pop("type_id")
    data["consumes"][0]["accepts"] = [{"type_id": "assembly.fasta"},
                                      {"type_id": "assembly.fastg"}]
    data["constraints"] = [{"when": when, "requires": ["fasta"], "because": "a typed row"}]
    return data


def test_a_condition_may_test_the_connected_type():
    contract = ModuleContract.model_validate(_typed({"type.consensus": "assembly.fastg"}))
    assert contract.constraints[0].when == {"type.consensus": "assembly.fastg"}
    ModuleContract.model_validate(_typed({"type.consensus": {"in": ["assembly.fasta",
                                                                    "assembly.fastg"]}}))
    ModuleContract.model_validate(_typed({"type.consensus": {"not": "assembly.fasta"}}))


def test_a_type_the_port_does_not_accept_is_refused():
    """A forge draft naming a type the port cannot take (#464 review focus 4)."""
    _refused("MD0602.*alignment.cram", _typed({"type.consensus": "alignment.cram"}))
    _refused("MD0602", _typed({"type.consensus": {"in": ["assembly.fasta", "alignment.cram"]}}))
    _refused("MD0602", _typed({"type.consensus": "present"}))


def test_type_of_an_unknown_port_is_refused():
    _refused("MD0602", _typed({"type.nope": "assembly.fasta"}))


def test_join_for_names_only_a_port_after_the_first():
    for join in ("broadcast", {"input_index": "by_sample", "intervals": "broadcast"}):
        slot = ModuleContract.model_validate(_gatk_slot(join)).nf_inputs[0]
        with pytest.raises(ValueError, match="after the first"):
            slot.join_for("input")
