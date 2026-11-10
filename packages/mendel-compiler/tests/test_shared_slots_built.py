"""Shared slots built and emitted (#464): an optional file inside a tuple with other files.

gatk4/haplotypecaller passes its BAM, the BAM's per-sample index, run-wide intervals and a
per-sample DRAGstr model in one tuple; spades passes Illumina, PacBio and Nanopore reads in
one, any of them. A file that is off gets `[]` in its own position, so the tuple's order still
matches the module's input block.
"""

import re
from pathlib import Path

import pytest
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.goal.asked import Constraints, InputChoice, InputState
from mendel_compiler import orchestrate
from mendel_compiler.emit import emit
from mendel_resolver.goal import Goal, GoalInput

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "packages/comeni-core/tests/fixtures/constraints"
GATK_ID = "nf-core/gatk4/haplotypecaller@4.6.1"
SPADES_ID = "nf-core/spades@4.1.0"


def _family(name: str, says: str) -> str:
    return f"declares: family\nid: {name}\ndescription: {says}\n"


def _type(type_id: str, scope: str) -> str:
    return f"declares: vocabulary\nid: {type_id}\nstates: []\nscope: {scope}\n"


OVERLAY = {
    "regions.family.yml": _family("regions", "Genomic intervals to restrict analysis to"),
    "dragstr.family.yml": _family("dragstr", "DRAGstr models of short tandem repeats"),
    "variants.family.yml": _family("variants", "Called variants and their indexes"),
    "pacbio.family.yml": _family("pacbio", "PacBio long reads"),
    "nanopore.family.yml": _family("nanopore", "Nanopore long reads"),
    "assembly.family.yml": _family("assembly", "Genomes assembled from reads"),
    "regions.bed.yml": _type("regions.bed", "run"),
    "dragstr.model.yml": _type("dragstr.model", "sample"),
    "variants.vcf.yml": _type("variants.vcf", "sample"),
    "variants.tbi.yml": _type("variants.tbi", "run"),
    "pacbio.reads.yml": _type("pacbio.reads", "sample"),
    "nanopore.reads.yml": _type("nanopore.reads", "sample"),
    "assembly.fasta.yml": _type("assembly.fasta", "sample"),
    "roles.yml": "declares: role\nroles:\n"
                 "  - {id: calling, explain: Calls variants from aligned reads.}\n"
                 "  - {id: assembly, explain: Assembles reads into contigs.}\n",
    "gatk.contract.yml": "declares: contract\n"
                         + (FIXTURES / "gatk4_haplotypecaller.yml").read_text(),
    "spades.contract.yml": "declares: contract\n" + (FIXTURES / "spades.yml").read_text(),
}


def _build(tmp_path: Path, have: list[str], want: str, contract: str,
           *choices: tuple[str, InputState]) -> Pipeline:
    layer = tmp_path / "overlay"
    layer.mkdir()
    for name, body in OVERLAY.items():
        (layer / name).write_text(body)
    goal = Goal(have=[GoalInput(type_id=t) for t in have], want=[want],
                constraints=Constraints(inputs=[InputChoice(contract=contract, port=p, state=s)
                                                for p, s in choices]))
    return orchestrate.build(goal, registry_roots=[ROOT / "registry", layer]).pipeline


def _call(text: str, process: str) -> str:
    return next(line for line in text.splitlines() if line.strip().startswith(f"{process}("))


def _first_argument(call: str) -> str:
    """The call's first argument: everything up to the first top-level comma."""
    inside = call.strip()[call.strip().index("(") + 1:]
    depth = 0
    for n, char in enumerate(inside):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            return inside[:n]
    return inside.rstrip(")")


GATK_HAVE = ["alignment.bam", "alignment.bai", "regions.bed", "dragstr.model"]


def test_gatk_with_intervals_off_passes_an_empty_slot_in_place(tmp_path):
    """Review focus 3: `[]` lands in intervals' position, between the index and DRAGstr."""
    pipeline = _build(tmp_path, GATK_HAVE, "variants.vcf", GATK_ID,
                      ("dragstr_model", InputState.REQUIRED))
    argument = _first_argument(_call(emit(pipeline), "GATK4_HAPLOTYPECALLER"))
    assert re.search(r"\.map \{ (\w+), (\w+), (\w+), (\w+) -> \[ \1, \2, \3, \[\], \4 \] \}$",
                     argument), argument


def test_a_per_sample_index_joins_and_a_run_file_combines(tmp_path):
    """Review focus 2: the index pairs with its own BAM; the intervals go to every sample."""
    pipeline = _build(tmp_path, GATK_HAVE, "variants.vcf", GATK_ID,
                      ("intervals", InputState.REQUIRED), ("dragstr_model", InputState.REQUIRED))
    argument = _first_argument(_call(emit(pipeline), "GATK4_HAPLOTYPECALLER"))
    assert argument.count(".join(") == 2, argument  # index and DRAGstr, per sample
    assert argument.count(".combine(") == 1, argument  # intervals, once per run
    assert ".map {" not in argument.split(".combine(")[-1].split(")")[-1], "nothing is off"


def test_spades_with_only_illumina_passes_two_empty_slots(tmp_path):
    pipeline = _build(tmp_path, ["fastq.reads"], "assembly.fasta", SPADES_ID,
                      ("illumina", InputState.REQUIRED))
    argument = _first_argument(_call(emit(pipeline), "SPADES"))
    assert re.search(r"\.map \{ (\w+), (\w+) -> \[ \1, \2, \[\], \[\] \] \}$", argument), argument


def test_spades_with_only_nanopore_starts_from_nanopore(tmp_path):
    pipeline = _build(tmp_path, ["nanopore.reads"], "assembly.fasta", SPADES_ID,
                      ("nanopore", InputState.REQUIRED))
    argument = _first_argument(_call(emit(pipeline), "SPADES"))
    channel = next(c.name for c in pipeline.channels if c.type_id == "nanopore.reads")
    assert channel in argument.split(".map")[0]
    assert re.search(r"\.map \{ (\w+), (\w+) -> \[ \1, \[\], \[\], \2 \] \}$", argument), argument


def test_an_optional_at_run_port_in_a_slot_is_an_empty_pair_when_left_empty(tmp_path):
    """Task 1 review: inside a shared slot the port's own channel is `[meta, file]`, so its
    empty form is the per-port pair, not the slot's width."""
    pipeline = _build(tmp_path, GATK_HAVE, "variants.vcf", GATK_ID,
                      ("intervals", InputState.OPTIONAL))
    intervals = next(c for c in pipeline.channels if c.type_id == "regions.bed")
    assert intervals.optional and intervals.absent_width == 2
    text = emit(pipeline)
    assert f"params.{intervals.param} ? (" in text
    argument = _first_argument(_call(text, "GATK4_HAPLOTYPECALLER"))
    assert ".combine(" in argument


def test_an_optional_at_run_port_joined_per_sample_is_refused(tmp_path):
    """A per-sample file a run may leave blank needs per-row placeholders: part 5 (#466)."""
    pipeline = _build(tmp_path, GATK_HAVE, "variants.vcf", GATK_ID,
                      ("dragstr_model", InputState.OPTIONAL))
    with pytest.raises(ValueError, match="466"):
        emit(pipeline)
