"""Samplesheet cells checked by the run itself, before any sample is processed (#466).

Mendel never reads a samplesheet (invariant 15), so a cell outside its declared values can only
be refused by the pipeline. These run the emitted workflow under Nextflow's stub mode on a
two-row sheet, and read what it says.
"""

import shutil
import subprocess

import pytest
from support.paths import ROOT
from support.pipeline import _starter

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("nextflow") is None, reason="needs Nextflow"),
    pytest.mark.skipif(shutil.which("docker") is None, reason="nf-core stubs need Docker"),
]

INPUTS = ("fastq.reads", "genome.fasta", "annotation.gtf")


def _pipeline(tmp_path, varies: list[str]):
    starter = _starter(tmp_path / "starter.yml", {
        "have": [{"type_id": t} for t in INPUTS], "want": ["counts.matrix"],
        "constraints": {"varies": varies}, "profile": {"read_length": 150}})
    out = tmp_path / "built"
    subprocess.run(["uv", "run", "mendel", "build", str(starter), "--registry", "registry",
                    "--out", str(out)], cwd=ROOT, check=True, capture_output=True)
    return out


def _run(tmp_path, out, rows: list[str]) -> subprocess.CompletedProcess:
    data = tmp_path / "data"
    data.mkdir()
    for name in ("a_1.fq.gz", "a_2.fq.gz", "b_1.fq.gz", "b_2.fq.gz", "g.fa", "g.gtf"):
        (data / name).write_text("stub\n")
    sheet = tmp_path / "sheet.csv"
    header = rows[0]
    sheet.write_text("\n".join([header, *(r.format(d=data) for r in rows[1:])]) + "\n")
    return subprocess.run(
        # The stub gate's profiles: Docker, and the limits a stub run fits in. Parameters given
        # here win over the profile's.
        ["nextflow", "-q", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker",
         "--input", str(sheet),
         "--fasta", str(data / "g.fa"), "--gtf", str(data / "g.gtf"),
         "--outdir", str(tmp_path / "results")],
        cwd=out, capture_output=True, text=True, timeout=900)


def test_a_bad_cell_stops_the_run(tmp_path):
    out = _pipeline(tmp_path, ["strandedness"])
    done = _run(tmp_path, out, [
        "sample,reads_1,reads_2,strandedness",
        "S1,{d}/a_1.fq.gz,{d}/a_2.fq.gz,reverse",
        "S2,{d}/b_1.fq.gz,{d}/b_2.fq.gz,Forward",
    ])
    assert done.returncode != 0
    assert ("samplesheet row 2 (sample S2), column strandedness: 'Forward' is not one of "
            "forward, reverse, unstranded") in done.stdout + done.stderr


def test_a_blank_required_cell_stops_the_run(tmp_path):
    out = _pipeline(tmp_path, ["strandedness"])
    done = _run(tmp_path, out, [
        "sample,reads_1,reads_2,strandedness",
        "S1,{d}/a_1.fq.gz,{d}/a_2.fq.gz,",
    ])
    assert done.returncode != 0
    assert "samplesheet row 1 (sample S1), column strandedness is required" in (
        done.stdout + done.stderr)


def test_each_sample_carries_its_own_cell(tmp_path):
    """Two samples, two strandednesses, and featureCounts reads each sample's own."""
    out = _pipeline(tmp_path, ["strandedness"])
    done = _run(tmp_path, out, [
        "sample,reads_1,reads_2,strandedness",
        "S1,{d}/a_1.fq.gz,{d}/a_2.fq.gz,forward",
        "S2,{d}/b_1.fq.gz,{d}/b_2.fq.gz,reverse",
    ])
    assert done.returncode == 0, done.stdout + done.stderr


def test_a_single_end_sample_runs_beside_a_paired_one(tmp_path):
    """Pairing that varies is read off each row: a blank second file is single-end (#466)."""
    out = _pipeline(tmp_path, ["paired"])
    done = _run(tmp_path, out, [
        "sample,reads_1,reads_2",
        "S1,{d}/a_1.fq.gz,{d}/a_2.fq.gz",
        "S2,{d}/b_1.fq.gz,",
    ])
    assert done.returncode == 0, done.stdout + done.stderr
