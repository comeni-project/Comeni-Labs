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


def _call(text: str, process: str) -> str:
    return next(line.strip() for line in text.splitlines()
                if line.strip().startswith(f"{process}("))


def test_each_aligner_takes_only_its_samples(branched):
    from mendel_compiler.emit import emit

    text = emit(branched)
    star = _call(text, "STAR_ALIGN")
    assert ".filter {" in star and "in ['nf-core.star.align:2.7.11b']" in star
    assert "(meta.read_length as double) >= 70.0" in star
    hisat2 = _call(text, "HISAT2_ALIGN")
    assert "in ['nf-core.hisat2.align:2.2.2']" in hisat2


def test_the_branches_rejoin_by_mixing(branched):
    from mendel_compiler.emit import emit

    sort = _call(emit(branched), "SAMTOOLS_SORT")
    assert "HISAT2_ALIGN.out.bam.mix(STAR_ALIGN.out.bam)" in sort \
        or "STAR_ALIGN.out.bam.mix(HISAT2_ALIGN.out.bam)" in sort


def test_an_index_waits_for_a_sample_of_its_own(branched):
    """An index no sample needs never starts (Review Focus 4)."""
    from mendel_compiler.emit import emit

    text = emit(branched)
    for process in ("STAR_GENOMEGENERATE", "HISAT2_BUILD"):
        call = _call(text, process)
        assert ".combine(" in call and ".first().map { true }" in call
    lines = [line.strip() for line in text.splitlines()]
    trim = next(n for n, line in enumerate(lines) if line.startswith("TRIMGALORE("))
    index = next(n for n, line in enumerate(lines) if line.startswith("STAR_GENOMEGENERATE("))
    assert trim < index


def test_a_sample_no_row_covers_takes_the_fallback(branched):
    """It never vanishes: a tool's branch, or the run stops naming it (Review Focus 3)."""
    from mendel_compiler.emit import emit

    star = _call(emit(branched), "STAR_ALIGN")
    fallback = branched.steps[0].guard or next(s.guard for s in branched.steps if s.guard)
    if fallback.lookup.fallback_is.value == "stop":
        assert "throw new IllegalStateException" in star
    else:
        assert star.count("'nf-core.") >= 3


def test_the_run_records_each_samples_tool(branched):
    from mendel_compiler.emit import emit

    text = emit(branched)
    assert "name: 'alignment.tool.tsv'" in text
    assert 'storeDir: "${params.outdir}/decided"' in text


def test_a_pipeline_without_branches_emits_as_before():
    from mendel_compiler.emit import emit

    text = emit(_built([], {"read_length": 150}))
    assert ".mix(" not in text and "alignment.tool.tsv" not in text and ".map { true }" not in text
