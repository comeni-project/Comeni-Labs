"""One sample's work runs in parallel parts and merges back per sample (#466, stage 6 part A).

A search step can run on parts of a sample's reads. The build splits each sample's reads before
it and merges its hits after it; each sample's parts merge as soon as they are all done.
"""

import shutil
import subprocess

import pytest
from comeni_core.artifact.pipeline import Pipeline
from mendel_compiler import orchestrate
from mendel_compiler.emit import emit, emit_config
from mendel_resolver.goal import Goal
from support.paths import ROOT

from emit.fixtures.parts import layer, modules

GOAL = {"have": [{"type_id": "fastq.reads"}, {"type_id": "genome.fasta"}], "want": ["hits.tsv"]}


def _built(tmp_path, constraints=None) -> Pipeline:
    goal = Goal.model_validate({**GOAL, "constraints": constraints or {}})
    roots = [ROOT / "registry", layer(tmp_path)]
    return orchestrate.build(goal, registry_roots=roots).pipeline


def _call(text: str, process: str) -> str:
    return next(line.strip() for line in text.splitlines()
                if line.strip().startswith(f"{process}("))


def test_the_saved_pipeline_records_the_parts(tmp_path):
    pipeline = _built(tmp_path)
    steps = {s.id: s for s in pipeline.steps}
    assert steps["search"].parts.on
    (reads,) = [i for i in steps["search"].inputs if i.port == "reads"]
    assert reads.parts.value == "spread" and reads.source == "split_search.reads"
    (hits,) = steps["merge_search_hits"].inputs
    assert hits.parts.value == "gather" and hits.source == "search.hits"
    assert Pipeline.model_validate(pipeline.model_dump(mode="json")) == pipeline


def test_the_split_spreads_into_parts(tmp_path):
    search = _call(emit(_built(tmp_path)), "SEARCH")
    assert search.startswith("SEARCH(SPLIT_READS.out.reads.flatMap {")
    assert "parts instanceof List ? parts : [parts]" in search
    assert "part: i, comeni_parts: list.size()" in search


def test_the_merge_gathers_one_samples_parts(tmp_path):
    merge = _call(emit(_built(tmp_path)), "MERGE_HITS")
    assert "groupKey(meta.id, meta.comeni_parts)" in merge
    assert ".groupTuple()" in merge and ".collect()" not in merge
    assert "it.key !in ['part', 'comeni_parts']" in merge


def test_each_part_publishes_under_its_own_name(tmp_path):
    config = emit_config(_built(tmp_path))
    assert 'withName: SEARCH { ext.prefix = { "${meta.id}.part${meta.part}" } }' in config


def test_a_step_kept_whole_has_no_parts_in_the_run(tmp_path):
    text = emit(_built(tmp_path, {"whole": ["lab/search@1.0.0"]}))
    assert "SPLIT_READS" not in text and "MERGE_HITS" not in text
    assert "comeni_parts" not in text


def test_a_sample_rule_still_reads_each_part(tmp_path):
    from comeni_core.plan.at_run import AtRunCondition, AtRunTest, SampleRule

    pipeline = _built(tmp_path)
    rule = SampleRule(when=[AtRunCondition(fact="read_length", test=AtRunTest.LT,
                                           operand=[50])], says="a fixture rule")
    steps = [s.model_copy(update={"sample_rules": [rule]}) if s.id == "search" else s
             for s in pipeline.steps]
    search = _call(emit(pipeline.model_copy(update={"steps": steps})), "SEARCH")
    assert search.index("flatMap") < search.index("a fixture rule")


@pytest.mark.slow
def test_each_sample_merges_its_own_parts(tmp_path):
    """Review Focus 1 and 2: one part for one sample, three for the other."""
    if shutil.which("nextflow") is None or shutil.which("docker") is None:
        pytest.skip("needs Nextflow and Docker")
    from support.pipeline import _starter

    starter = _starter(tmp_path / "starter.yml", GOAL)
    out = tmp_path / "built"
    done = subprocess.run(
        ["uv", "run", "mendel", "build", str(starter), "--registry", "registry",
         "--registry", str(layer(tmp_path)), "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    modules(out)
    data = tmp_path / "data"
    data.mkdir()
    for sample in ("S_one", "S_three"):
        for mate in (1, 2):
            (data / f"{sample}_R{mate}.fq.gz").write_text("stub\n")
    (data / "genome.fa").write_text(">c\nA\n")
    results = tmp_path / "results"
    done = subprocess.run(
        ["nextflow", "-q", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker",
         "--input", str(data / "*_R{1,2}.fq.gz"), "--fasta", str(data / "genome.fa"),
         "--outdir", str(results)],
        cwd=out, capture_output=True, text=True, timeout=900)
    assert done.returncode == 0, done.stdout + done.stderr
    merged = {p.name: sorted(p.read_text().split()) for p in (results / "merge_hits").iterdir()}
    assert merged == {"S_one.merged.tsv": ["S_one.1"],
                      "S_three.merged.tsv": ["S_three.1", "S_three.2", "S_three.3"]}
    published = sorted(p.name for p in (results / "search").iterdir())
    assert published == ["S_one.part0.tsv", "S_three.part0.tsv", "S_three.part1.tsv",
                         "S_three.part2.tsv"]
