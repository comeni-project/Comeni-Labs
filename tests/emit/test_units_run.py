"""A sample's lanes merged in a stub run (#466, stage 5; Review Focus 1 and 2)."""

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


def _built(tmp, varies):
    starter = _starter(tmp / "starter.yml", {
        "have": [{"type_id": t} for t in INPUTS], "want": ["counts.matrix"],
        "constraints": {"units": ["fastq.reads"], "varies": varies},
        "profile": {"read_length": 150}})
    out = tmp / "built"
    subprocess.run(["uv", "run", "mendel", "build", str(starter), "--registry", "registry",
                    "--out", str(out)], cwd=ROOT, check=True, capture_output=True)
    return out


def _run(tmp, out, rows):
    data = tmp / "data"
    data.mkdir()
    for name in ("g.fa", "g.gtf"):
        (data / name).write_text("stub\n")
    lines = ["sample,reads_1,reads_2,unit"]
    for sample, unit, mates in rows:
        names = [f"{sample}_L{unit}_{m}.fq.gz" for m in range(1, mates + 1)]
        for name in names:
            (data / name).write_text("stub\n")
        second = f"{data}/{names[1]}" if mates == 2 else ""
        lines.append(f"{sample},{data}/{names[0]},{second},{unit}")
    sheet = tmp / "sheet.csv"
    sheet.write_text("\n".join(lines) + "\n")
    done = subprocess.run(
        ["nextflow", "-q", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker",
         "--input", str(sheet), "--fasta", str(data / "g.fa"), "--gtf", str(data / "g.gtf"),
         "--outdir", str(tmp / "results")],
        cwd=out, capture_output=True, text=True, timeout=900)
    log = (out / ".nextflow.log").read_text() if (out / ".nextflow.log").exists() else ""
    ran = [line.split("Submitted process > ")[1].split(" ")[0].split(":")[-1]
           for line in log.splitlines() if "Submitted process > " in line]
    return done, ran


def test_three_lanes_merge_and_one_lane_passes_straight_on(tmp_path):
    out = _built(tmp_path, [])
    done, ran = _run(tmp_path, out, [("S1", 1, 2), ("S1", 2, 2), ("S1", 3, 2), ("S2", 1, 2)])
    assert done.returncode == 0, done.stdout + done.stderr
    assert ran.count("CAT_FASTQ") == 1
    assert ran.count("TRIMGALORE") == 2
    assert "SUBREAD_FEATURECOUNTS" in ran


def test_lanes_that_disagree_stop_the_run_naming_the_sample(tmp_path):
    out = _built(tmp_path, ["paired"])
    done, _ = _run(tmp_path, out, [("S1", 1, 2), ("S1", 2, 1)])
    assert done.returncode != 0
    said = done.stdout + done.stderr
    assert "samplesheet sample S1: its rows disagree on" in said
