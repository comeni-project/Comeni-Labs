"""A step's ports on the canvas when an input takes several types or shares a slot (#464)."""

from pathlib import Path

from comeni_core.goal.asked import Constraints, InputChoice, InputState
from mendel_api.services.build import step_views
from mendel_compiler import orchestrate
from mendel_resolver.goal import Goal, GoalInput
from support.paths import ROOT

FIXTURES = ROOT / "packages/comeni-core/tests/fixtures/constraints"


def _family(name: str) -> str:
    return f"declares: family\nid: {name}\ndescription: {name}\n"


def _type(type_id: str, grain: str = "study") -> str:
    return f"declares: vocabulary\nid: {type_id}\nstates: []\ngrain: {grain}\n"


OVERLAY = {
    **{f"{f}.family.yml": _family(f) for f in ("salmon", "transcripts", "regions", "dragstr",
                                               "variants")},
    "salmon.index.yml": _type("salmon.index"),
    "salmon.quant.yml": _type("salmon.quant", "sample"),
    "transcripts.fasta.yml": _type("transcripts.fasta"),
    "regions.bed.yml": _type("regions.bed"),
    "dragstr.model.yml": _type("dragstr.model", "sample"),
    "variants.vcf.yml": _type("variants.vcf", "sample"),
    "variants.tbi.yml": _type("variants.tbi"),
    "roles.yml": "declares: role\nroles:\n  - {id: calling, explain: Calls variants.}\n",
    "salmon.contract.yml": "declares: contract\n" + (FIXTURES / "salmon_quant.yml").read_text(),
    "gatk.contract.yml": "declares: contract\n"
                         + (FIXTURES / "gatk4_haplotypecaller.yml").read_text(),
}


def _ports(tmp_path: Path, have: list[str], want: str, contract: str,
           *choices: tuple[str, InputState]) -> dict:
    layer = tmp_path / "overlay"
    layer.mkdir()
    for name, body in OVERLAY.items():
        (layer / name).write_text(body)
    goal = Goal(have=[GoalInput(type_id=t) for t in have], want=[want],
                constraints=Constraints(inputs=[InputChoice(contract=contract, port=p, state=s)
                                                for p, s in choices]))
    built = orchestrate.build(goal, registry_roots=[ROOT / "registry", layer])
    [view] = [v for v in step_views(built.pipeline, built.layers) if v.contract_id == contract]
    return {(p.side, p.name): p for p in view.ports}


SALMON_ID = "nf-core/salmon/quant@1.10.3"
GATK_ID = "nf-core/gatk4/haplotypecaller@4.6.1"


def test_an_optional_port_in_a_shared_slot_is_reported_like_any_other(tmp_path):
    ports = _ports(tmp_path, ["alignment.bam", "alignment.bai", "regions.bed", "dragstr.model"],
                   "variants.vcf", GATK_ID, ("dragstr_model", InputState.REQUIRED))
    intervals = ports[("in", "intervals")]
    assert (intervals.optional, intervals.state) == (True, "off")
    assert ports[("in", "dragstr_model")].state == "required"


def test_a_type_row_gives_its_sentence(tmp_path):
    ports = _ports(tmp_path, ["alignment.bam", "transcripts.fasta"], "salmon.quant", SALMON_ID)
    reason = ports[("in", "transcript_fasta")].reason
    assert "alignment mode quantifies BAM reads against the transcripts" in reason
    assert "`reads` as alignment.bam" in reason


def test_an_input_of_several_types_shows_the_one_connected_and_is_met(tmp_path):
    """The port has no type of its own: the canvas shows what was connected, fed from the goal."""
    reads = _ports(tmp_path, ["alignment.bam", "transcripts.fasta"], "salmon.quant",
                   SALMON_ID)[("in", "reads")]
    assert reads.type_id == "alignment.bam"
    assert reads.met is True


def test_a_condition_on_a_type_reads_in_words():
    from mendel_api.services.build import _only_with

    assert _only_with({"type.reads": "alignment.cram"}) == "only with reads as alignment.cram"
    assert _only_with({"type.reads": {"in": ["alignment.bam", "alignment.cram"]}}) == (
        "only with reads as one of alignment.bam, alignment.cram")
    assert _only_with({"type.reads": {"not": "alignment.bam"}}) == (
        "only with reads not as alignment.bam")
    assert _only_with({"given.fasta": "present"}) == "only with fasta"
