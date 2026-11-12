"""Each sample goes down its own branch (#466, stage 4).

A person says read length differs between samples. The alignment rule picks STAR for 70 bases
or more and HISAT2 below, so the pipeline holds both: each aligner, with its index, takes only
the samples the rule sends it, and the two rejoin at sorting.
"""

import pytest
from comeni_core.artifact.pipeline import Pipeline
from mendel_compiler import orchestrate
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from support.paths import ROOT

STACK = layers.load(ROOT / "registry")
INPUTS = ("fastq.reads", "genome.fasta", "annotation.gtf")
STAR = "nf-core/star/align@2.7.11b"
HISAT2 = "nf-core/hisat2/align@2.2.2"


def _built(varies: list[str], profile: dict | None = None) -> Pipeline:
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in INPUTS], "want": ["counts.matrix"],
        "constraints": {"varies": varies},
        "profile": STACK.measurements.profile(profile or {}).model_dump(mode="json")})
    return orchestrate.build(goal, registry_roots=[ROOT / "registry"]).pipeline


@pytest.fixture(scope="module")
def branched() -> Pipeline:
    return _built(["read_length"])


def test_the_saved_pipeline_keeps_each_steps_guard(branched):
    steps = {s.id: s for s in branched.steps}
    assert steps["star_align"].guard.takes == [STAR]
    assert steps["hisat2_build"].guard.takes == [HISAT2]
    assert steps["samtools_sort"].guard is None
    (bam,) = [i for i in steps["samtools_sort"].inputs if i.port == "bam"]
    assert {bam.source, *bam.mixed} == {"star_align.bam", "hisat2_align.bam"}
    (fact,) = branched.sheet_facts
    assert (fact.measurement, fact.auto, fact.required) == ("read_length", True, False)
    again = Pipeline.model_validate(branched.model_dump(mode="json"))
    assert again == branched
