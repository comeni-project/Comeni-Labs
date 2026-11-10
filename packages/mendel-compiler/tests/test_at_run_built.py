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


def _star(tmp_path):
    from mendel_compiler import orchestrate
    from support.at_run import overlay as _overlay

    roots = [ROOT / "registry", _overlay(tmp_path)]
    stack = layers.load(roots)
    goal = Goal(have=[GoalInput(type_id="genome.fasta"), GoalInput(type_id="annotation.gtf")],
                want=["genome.index.star"], profile=stack.measurements.profile({}))
    return orchestrate.build(goal, registry_roots=roots).pipeline


def test_the_emitted_pipeline_measures_then_joins_then_builds_the_index(tmp_path):
    from mendel_compiler.emit import emit, emit_config

    pipeline = _star(tmp_path)
    main = emit(pipeline)
    faidx = main.index("SAMTOOLS_FAIDX(ch_fasta)")
    measure = main.index("MEASURE_GENOME_LENGTH_FAI(SAMTOOLS_FAIDX.out.fai)")
    joined = main.index("ch_fasta_measured = ")
    star = main.index("STAR_GENOMEGENERATE(ch_fasta_measured")
    assert faidx < measure < joined < star
    assert ".facts?.get('genome_length')?.value" in main
    assert "meta + [genome_length: v0]" in main
    assert "collectFile(name: 'STAR_GENOMEGENERATE.sa_index_nbases.tsv'" in main
    config = emit_config(pipeline)
    line = next(x for x in config.splitlines() if "STAR_GENOMEGENERATE" in x and "ext.args" in x)
    assert "--genomeSAindexNbases" in line and "meta.genome_length == null" in line
    assert line.strip().startswith("withName: STAR_GENOMEGENERATE { ext.args = {")


def test_the_join_is_by_meta_never_combine(tmp_path):
    """A per-sample channel joined by `combine` would pair one sample with another's fact
    (Review Focus 4)."""
    from mendel_compiler.emit import emit

    main = emit(_star(tmp_path))
    line = next(x for x in main.splitlines() if "ch_fasta_measured = " in x)
    assert ".join(MEASURE_GENOME_LENGTH_FAI.out.genome_length" in line and "combine" not in line
