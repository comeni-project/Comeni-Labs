"""A fact folded over the study in the run (#466, stage 5).

Read length differs between samples; a rule reads `agree(read_length)`. Each sample's length is
its cell, or measured where blank; the run folds them once every sample has one, and the value
joins every sample's `meta`, so the lookup reads it the way it reads any fact.
"""

import pytest
from comeni_core.artifact.pipeline import Pipeline
from mendel_compiler import orchestrate
from mendel_compiler.emit import emit
from mendel_resolver.goal import Goal
from support.paths import ROOT

INPUTS = ("fastq.reads", "genome.fasta", "annotation.gtf")
RULE = """declares: rule
version: 1
derives:
  - fact: study_read_length
    kind: integer
    aggregate: {measurement: read_length, over: study, using: agree}
    because: a fixture
decisions:
  - decides: {effect: param, of: quantification, name: min_mqs}
    rows:
      - {when: {study_read_length: ">= 100"}, then: 10, because: a fixture}
      - {when: {study_read_length: "< 100"}, then: 7, because: a fixture}
"""


def build(tmp_path, varies=("read_length",), profile=None) -> Pipeline:
    layer = tmp_path / "fold"
    (layer / "rules").mkdir(parents=True, exist_ok=True)
    (layer / "rules/fold.yml").write_text(RULE)
    from mendel_resolver import layers

    stack = layers.load([ROOT / "registry", layer])
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in INPUTS], "want": ["counts.matrix"],
        "constraints": {"varies": list(varies)},
        "profile": stack.measurements.profile(profile or {}).model_dump(mode="json")})
    return orchestrate.build(goal, registry_roots=[ROOT / "registry", layer]).pipeline


@pytest.fixture
def folded(tmp_path) -> Pipeline:
    return build(tmp_path)


def test_the_fold_joins_every_samples_meta(folded):
    text = emit(folded)
    assert ".toList().map { vs ->" in text
    assert "study_read_length:" in text
    assert "ch_reads_folded" in text


def test_the_fold_reaches_steps_after_the_measuring_branch(folded):
    text = emit(folded)
    star = next(line for line in text.splitlines() if line.strip().startswith("STAR_ALIGN("))
    assert "'study_read_length'" in star


def test_agree_is_undetermined_when_samples_differ_or_one_is_missing(folded):
    text = emit(folded)
    assert "known.size() == vs.size() && known.toSet().size() == 1 ? known[0] : null" in text


def test_a_known_fold_is_decided_at_build_time(tmp_path):
    pipeline = build(tmp_path, varies=(), profile={"read_length": 150})
    counts = next(s for s in pipeline.steps if s.id == "subread_featurecounts")
    (setting,) = [s for s in counts.settings if s.name == "min_mqs"]
    assert setting.value == 10 and setting.at_run is None
    assert ".toList().map { vs ->" not in emit(pipeline)


@pytest.mark.slow
def test_a_folded_fact_is_read_in_the_run(tmp_path):
    """Two samples agreeing at 150 give the setting 10; disagreeing, the fallback (Focus 3)."""
    import shutil
    import subprocess

    from support.pipeline import _starter

    if shutil.which("nextflow") is None or shutil.which("docker") is None:
        pytest.skip("needs Nextflow and Docker")
    layer = tmp_path / "fold"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules/fold.yml").write_text(RULE)
    starter = _starter(tmp_path / "starter.yml", {
        "have": [{"type_id": t} for t in INPUTS], "want": ["counts.matrix"],
        "constraints": {"varies": ["read_length"]}, "profile": {}})
    out = tmp_path / "built"
    subprocess.run(["uv", "run", "mendel", "build", str(starter), "--registry", "registry",
                    "--registry", str(layer), "--out", str(out)],
                   cwd=ROOT, check=True, capture_output=True)
    results = {}
    for name, cells in (("agree", ["150", "150"]), ("differ", ["150", "75"])):
        data = tmp_path / name
        data.mkdir()
        for f in ("g.fa", "g.gtf", "a_1.fq.gz", "a_2.fq.gz", "b_1.fq.gz", "b_2.fq.gz"):
            (data / f).write_text("stub\n")
        (data / "sheet.csv").write_text(
            "sample,reads_1,reads_2,read_length\n"
            f"S1,{data}/a_1.fq.gz,{data}/a_2.fq.gz,{cells[0]}\n"
            f"S2,{data}/b_1.fq.gz,{data}/b_2.fq.gz,{cells[1]}\n")
        done = subprocess.run(
            ["nextflow", "-q", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker",
             "--input", str(data / "sheet.csv"), "--fasta", str(data / "g.fa"),
             "--gtf", str(data / "g.gtf"), "--outdir", str(data / "results")],
            cwd=out, capture_output=True, text=True, timeout=900)
        assert done.returncode == 0, done.stdout + done.stderr
        record = (data / "results/decided/subread_featurecounts.min_mqs.tsv").read_text()
        results[name] = {line.split("\t")[0]: line.split("\t")[1]
                         for line in record.splitlines()}
    assert results["agree"] == {"S1": "10", "S2": "10"}
    assert set(results["differ"].values()) != {"10"} and set(results["differ"].values()) != {"7"}
