"""salmon quant built end to end from BAM and from FASTQ reads (#464).

The curated registry plus an overlay: salmon's contract (the comeni-core fixture) and the
families and types the registry does not declare. Which inputs the step takes depends on the
type routing connected to `reads`.
"""

from pathlib import Path

from comeni_core.artifact.pipeline import Pipeline
from mendel_compiler import orchestrate
from mendel_resolver.goal import Goal, GoalInput

ROOT = Path(__file__).resolve().parents[3]
SALMON = (ROOT / "packages/comeni-core/tests/fixtures/constraints/salmon_quant.yml").read_text()
SALMON_ID = "nf-core/salmon/quant@1.10.3"

OVERLAY = {
    "salmon.family.yml": "declares: family\nid: salmon\n"
                         "description: Salmon's index and its per-sample quantifications\n",
    "transcripts.family.yml": "declares: family\nid: transcripts\n"
                              "description: Transcript sequences of a genome\n",
    "salmon.index.yml": "declares: vocabulary\nid: salmon.index\nstates: []\nscope: run\n",
    "salmon.quant.yml": "declares: vocabulary\nid: salmon.quant\nstates: []\nscope: sample\n",
    "transcripts.fasta.yml": "declares: vocabulary\nid: transcripts.fasta\nstates: []\n"
                             "scope: run\n",
    "salmon.contract.yml": "declares: contract\n" + SALMON,
}


def _build(tmp_path: Path, have: list[str]) -> Pipeline:
    layer = tmp_path / "overlay"
    layer.mkdir()
    for name, body in OVERLAY.items():
        (layer / name).write_text(body)
    goal = Goal(have=[GoalInput(type_id=t) for t in have], want=["salmon.quant"])
    return orchestrate.build(goal, registry_roots=[ROOT / "registry", layer]).pipeline


def _salmon(pipeline: Pipeline):
    return next(s for s in pipeline.steps if s.module.contract_id == SALMON_ID)


def _channel_type(pipeline: Pipeline, name: str) -> str:
    return next(c.type_id for c in pipeline.channels if c.name == name)


def test_bam_reads_reach_an_accepts_port_from_the_goal(tmp_path):
    """Review focus 1: the port's own type is empty when it declares `accepts`, so the
    materialiser must find the channel by the type that matched."""
    pipeline = _build(tmp_path, ["alignment.bam", "transcripts.fasta"])
    inputs = {i.port: i for i in _salmon(pipeline).inputs}
    assert sorted(inputs) == ["reads", "transcript_fasta"]
    assert _channel_type(pipeline, inputs["reads"].channel) == "alignment.bam"


def test_fastq_reads_take_the_index_instead(tmp_path):
    pipeline = _build(tmp_path, ["fastq.reads", "salmon.index"])
    inputs = {i.port: i for i in _salmon(pipeline).inputs}
    assert sorted(inputs) == ["index", "reads"]
    assert _channel_type(pipeline, inputs["reads"].channel) == "fastq.reads"


def test_an_optional_accepts_port_from_outside_gets_a_channel(tmp_path):
    """Task 5 review: switched on, fed by nothing in the pipeline and not in the goal, the port
    still had no type to choose its channel by."""
    from comeni_core.goal.asked import Constraints, InputChoice, InputState

    layer = tmp_path / "overlay"
    layer.mkdir()
    salmon = SALMON.replace("  - {name: gtf, type_id: annotation.gtf, required: false}",
                            "  - name: gtf\n    required: false\n    accepts: "
                            "[{type_id: annotation.gtf}, {type_id: annotation.gff}]")
    assert salmon != SALMON
    extra = {"salmon.contract.yml": "declares: contract\n" + salmon,
             "annotation.gff.yml": "declares: vocabulary\nid: annotation.gff\nstates: []\n"
                                   "scope: run\n"}
    for name, body in {**OVERLAY, **extra}.items():
        (layer / name).write_text(body)
    goal = Goal(have=[GoalInput(type_id="alignment.bam"), GoalInput(type_id="transcripts.fasta")],
                want=["salmon.quant"],
                constraints=Constraints(inputs=[InputChoice(contract=SALMON_ID, port="gtf",
                                                            state=InputState.OPTIONAL)]))
    pipeline = orchestrate.build(goal, registry_roots=[ROOT / "registry", layer]).pipeline
    inputs = {i.port: i for i in _salmon(pipeline).inputs}
    assert _channel_type(pipeline, inputs["gtf"].channel) == "annotation.gtf"
