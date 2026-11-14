"""A step only some samples take says which, on its card (#466, stage 4)."""

from mendel_api.services.build import step_views
from mendel_compiler import orchestrate
from mendel_resolver.goal import Goal
from support.paths import ROOT


def _views(varies, profile):
    from mendel_resolver import layers

    stack = layers.load(ROOT / "registry")
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in ("fastq.reads", "genome.fasta", "annotation.gtf")],
        "want": ["counts.matrix"], "constraints": {"varies": varies},
        "profile": stack.measurements.profile(profile).model_dump(mode="json")})
    built = orchestrate.build(goal, registry_roots=[ROOT / "registry"])
    return {v.id: v for v in step_views(built.pipeline, built.layers)}


def test_a_branch_step_says_which_samples_it_takes():
    views = _views(["read_length"], {})
    star = views["star_align"].takes_samples
    assert star.tools == ["nf-core/star/align@2.7.11b"]
    assert star.samples.startswith("samples where read_length >= 70")
    assert star.lookup.rule == "implementation:alignment"
    assert star.lookup.rows[0] == "read_length >= 70 → nf-core/star/align@2.7.11b"
    assert views["hisat2_build"].takes_samples.samples == "samples where read_length < 70"
    assert views["samtools_sort"].takes_samples is None


def test_the_fallback_tool_takes_the_samples_no_row_covers_too():
    star = _views(["read_length"], {})["star_align"].takes_samples
    if star.lookup.fallback == "nf-core/star/align@2.7.11b":
        assert star.samples.endswith(", and any sample no row covers")


def test_without_branches_no_step_says_so():
    views = _views([], {"read_length": 150})
    assert all(v.takes_samples is None for v in views.values())
