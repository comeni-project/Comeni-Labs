"""A step that runs on parts of each sample says so on its card, with the switch (#466, stage 6)."""

from emit.fixtures.parts import layer
from mendel_api.services.build import step_views
from mendel_compiler import orchestrate
from mendel_resolver.goal import Goal
from support.paths import ROOT

GOAL = {"have": [{"type_id": "fastq.reads"}, {"type_id": "genome.fasta"}], "want": ["hits.tsv"]}


def _views(tmp_path, whole=()):
    goal = Goal.model_validate({**GOAL, "constraints": {"whole": list(whole)}})
    built = orchestrate.build(goal, registry_roots=[ROOT / "registry", layer(tmp_path)])
    return {v.id: v for v in step_views(built.pipeline, built.layers)}


def test_a_step_on_parts_says_how_it_is_split(tmp_path):
    views = _views(tmp_path)
    parts = views["search"].parts
    assert parts.on and parts.splitter == "lab/split_reads@1.0.0"
    assert parts.mergers == ["lab/merge_hits@1.0.0"]
    assert "can run on parts of fastq.reads" in parts.because
    assert views["split_search"].parts is None


def test_a_step_kept_whole_still_offers_the_switch(tmp_path):
    parts = _views(tmp_path, ["lab/search@1.0.0"])["search"].parts
    assert parts is not None and not parts.on
