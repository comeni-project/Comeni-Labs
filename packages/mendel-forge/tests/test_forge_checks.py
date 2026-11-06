"""The engine's findings on type questions (#452): advice for the person, never a decision."""

from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.checks import arrival, channel_formats, findings, type_format
from mendel_forge.model import Channel

QUAST = ModuleSpec.of("""
process QUAST {
    input:
    tuple val(meta) , path(consensus)
    tuple val(meta2), path(fasta)
    tuple val(meta3), path(gff)

    output:
    tuple val(meta), path("${prefix}.tsv"), emit: results

    script:
    ""
}
""")
SCOPES = {"genome.fasta": "run", "annotation.gtf": "run"}


def _asked(**suggested: str) -> dict[str, dict]:
    return {f"questions:input_type:{name}": {"asks": "?", "suggested": type_id,
                                             "options": [{"id": type_id}]}
            for name, type_id in suggested.items()}


def test_the_meta_name_says_how_an_input_arrives():
    assert arrival(QUAST, "consensus") == "sample"
    assert arrival(QUAST, "fasta") == arrival(QUAST, "gff") == "run"
    assert arrival(ModuleSpec.of("process P {\n    input:\n    path(x)\n\n    output:\n"
                                 "    path('y'), emit: y\n\n    script:\n    ''\n}"), "x") is None


def test_quasts_walk_suggestions_are_each_flagged():
    """The GPU walk (#412): genome.fasta for both, annotation.gtf for a gff input."""
    asked = _asked(consensus="genome.fasta", fasta="genome.fasta", gff="annotation.gtf")
    found = findings({}, SCOPES, QUAST, {}, asked)
    codes = {key.rsplit(":", 1)[1]: sorted(f.code for f in fs) for key, fs in found.items()}
    assert codes == {"consensus": ["MF0520", "MF0521"], "fasta": ["MF0521"], "gff": ["MF0522"]}
    assert "one per sample" in found["questions:input_type:consensus"][0].says


def test_the_right_answers_draw_no_finding():
    asked = _asked(consensus="assembly.fasta", fasta="genome.fasta", gff="annotation.gff")
    assert findings({}, SCOPES, QUAST, {}, asked) == {}


def test_an_answer_counts_over_the_suggestion():
    asked = _asked(consensus="genome.fasta", fasta="genome.fasta")
    items = {"questions:input_type:consensus": {"choice": "assembly.fasta"}}
    assert findings(items, SCOPES, QUAST, {}, asked) == {}


def test_a_pattern_names_the_format_before_the_name_does():
    assert channel_formats(Channel(name="gff", pattern="*.{gtf,gtf.gz}"), "gff") == {"gtf"}
    assert channel_formats(None, "gff") == {"gff"}
    assert channel_formats(None, "consensus") == set()
    assert type_format("fastq.reads") == "fastq" and type_format("qc.report") is None


# ── contract findings and items (#460) ──────────────────────────────────────────────────────

from comeni_core import yaml_strict  # noqa: E402
from comeni_core.declared.contract import ModuleContract, Provenance  # noqa: E402
from mendel_compiler.modulespec import ModuleSpec  # noqa: E402
from mendel_forge.forging.checks import contract_findings  # noqa: E402
from mendel_forge.forging.values import contract_of, items_of  # noqa: E402
from support.paths import ROOT  # noqa: E402

QUAST_YML = ROOT / "packages/comeni-core/tests/fixtures/constraints/quast.yml"
QUAST_NF = ROOT / "packages/mendel-compiler/tests/fixtures/quast/main.nf"


def _quast_items() -> dict:
    return items_of(ModuleContract.model_validate(yaml_strict.load(QUAST_YML)))


def _codes(items: dict) -> dict[str, list[str]]:
    found = contract_findings(items, ModuleSpec.parse(QUAST_NF), QUAST_NF.read_text())
    return {key: [f.code for f in fs] for key, fs in found.items()}


def test_quast_items_round_trip_through_contract_of():
    items = _quast_items()
    assert "contract:constraint:0" in items
    contract = contract_of(items, "nf-core/quast@5.3.0", Provenance(
        source="t", drafted_by="t", approved_by="t", approved_at="2026-11-06"))
    assert contract.constraints[0].requires == ["fasta"]
    assert contract.optional_ports() == ["fasta", "gff"]


def test_the_quast_items_have_no_contract_findings():
    assert _codes(_quast_items()) == {}


def test_an_optional_emit_without_produced_when_is_mf0530():
    items = _quast_items()
    items["contract:output:unaligned"] = {**items["contract:output:unaligned"]}
    items["contract:output:unaligned"].pop("produced_when")
    assert _codes(items) == {"contract:output:unaligned": ["MF0530"]}


def test_an_input_used_only_under_a_ternary_marked_required_is_mf0531():
    items = _quast_items()
    items["contract:input:gff"] = {**items["contract:input:gff"]}
    items["contract:input:gff"].pop("required")
    items["contract:nf_inputs"] = [e if e.get("ports") != ["gff"] else {"ports": ["gff"]}
                                   for e in items["contract:nf_inputs"]]
    items.pop("contract:constraint:0")
    assert _codes(items) == {"contract:input:gff": ["MF0531"]}


def test_an_all_optional_entry_without_absent_is_mf0532():
    items = _quast_items()
    items["contract:nf_inputs"] = [{k: v for k, v in e.items() if k != "absent"}
                                   for e in items["contract:nf_inputs"]]
    assert _codes(items) == {"contract:nf_inputs": ["MF0532", "MF0532"]}, "fasta and gff"
