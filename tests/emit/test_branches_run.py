"""Each sample down its own branch, run under Nextflow's stub mode (#466, stage 4).

Read length differs between samples: the alignment rule sends 70 bases or more to STAR and
shorter reads to HISAT2. The run records each sample's tool, and an index no sample needs never
starts.
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


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("branches")
    starter = _starter(tmp / "starter.yml", {
        "have": [{"type_id": t} for t in INPUTS], "want": ["counts.matrix"],
        "constraints": {"varies": ["read_length"]}, "profile": {}})
    out = tmp / "built"
    subprocess.run(["uv", "run", "mendel", "build", str(starter), "--registry", "registry",
                    "--out", str(out)], cwd=ROOT, check=True, capture_output=True)
    return out


def _run(tmp_path, out, cells: list[str]) -> tuple[subprocess.CompletedProcess, dict, set]:
    data = tmp_path / "data"
    data.mkdir()
    for name in ("g.fa", "g.gtf"):
        (data / name).write_text("stub\n")
    rows = ["sample,reads_1,reads_2,read_length"]
    for n, cell in enumerate(cells, 1):
        for mate in (1, 2):
            (data / f"s{n}_{mate}.fq.gz").write_text("stub\n")
        rows.append(f"S{n},{data}/s{n}_1.fq.gz,{data}/s{n}_2.fq.gz,{cell}")
    sheet = tmp_path / "sheet.csv"
    sheet.write_text("\n".join(rows) + "\n")
    results = tmp_path / "results"
    done = subprocess.run(
        ["nextflow", "-q", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker",
         "--input", str(sheet), "--fasta", str(data / "g.fa"), "--gtf", str(data / "g.gtf"),
         "--outdir", str(results)],
        cwd=out, capture_output=True, text=True, timeout=900)
    routed = {}
    record = results / "decided/alignment.tool.tsv"
    if record.exists():
        for line in record.read_text().splitlines():
            sample, tool, *_ = line.split("\t")
            routed[sample] = tool
    # What ran, from the log's submissions: a trace needs `ps` in every container.
    log = (out / ".nextflow.log").read_text()
    ran = {line.split("Submitted process > ")[1].split(" ")[0].split(":")[-1]
           for line in log.splitlines() if "Submitted process > " in line}
    return done, routed, ran


def test_each_sample_takes_its_own_aligner(built, tmp_path):
    done, routed, ran = _run(tmp_path, built, ["150", "50"])
    assert done.returncode == 0, done.stdout + done.stderr
    assert routed == {"S1": "nf-core.star.align:2.7.11b", "S2": "nf-core.hisat2.align:2.2.2"}
    assert {"STAR_ALIGN", "HISAT2_ALIGN", "STAR_GENOMEGENERATE", "HISAT2_BUILD",
            "SAMTOOLS_SORT", "SUBREAD_FEATURECOUNTS"} <= ran


def test_an_index_no_sample_needs_never_starts(built, tmp_path):
    """Review Focus 4."""
    done, routed, ran = _run(tmp_path, built, ["150", "100"])
    assert done.returncode == 0, done.stdout + done.stderr
    assert set(routed.values()) == {"nf-core.star.align:2.7.11b"}
    assert "HISAT2_BUILD" not in ran and "HISAT2_ALIGN" not in ran
    assert "SUBREAD_FEATURECOUNTS" in ran


def test_a_sample_whose_length_is_undetermined_stops_the_run_naming_it(built, tmp_path):
    """Measured where blank; a stub measures nothing, so no row covers it (Review Focus 3).
    Nobody chose a tool for such a sample, so the run stops and names it: it never vanishes."""
    done, _, _ = _run(tmp_path, built, ["50", ""])
    assert done.returncode != 0
    said = done.stdout + done.stderr
    assert "sample S2: no row of implementation:alignment applies to its read_length" in said
