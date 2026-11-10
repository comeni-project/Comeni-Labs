"""A run-time setting reaches the saved pipeline: its lookup and its input's join (#217)."""

from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from support.at_run import ROOT, STAR_ID


def test_the_saved_pipeline_carries_the_lookup_and_the_join(tmp_path):
    from mendel_compiler import orchestrate
    from support.at_run import overlay as _overlay

    roots = [ROOT / "registry", _overlay(tmp_path)]
    stack = layers.load(roots)
    goal = Goal(have=[GoalInput(type_id="genome.fasta"), GoalInput(type_id="annotation.gtf")],
                want=["genome.index.star"], profile=stack.measurements.profile({}))
    pipeline = orchestrate.build(goal, registry_roots=roots).pipeline
    star = next(s for s in pipeline.steps if s.module.contract_id == STAR_ID)
    setting = next(s for s in star.settings if s.name == "sa_index_nbases")
    assert setting.at_run is not None and setting.at_run.fact == "genome_length"
    (genome,) = [c for c in pipeline.channels if c.type_id == "genome.fasta"]
    assert [m.measurement for m in genome.meta_at_run] == ["genome_length"]
    assert pipeline.intent.want == ["genome.index.star"]
