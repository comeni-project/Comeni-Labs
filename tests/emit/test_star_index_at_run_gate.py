"""STAR's index sized during the run from the genome it is given, measured by samtools faidx
(#217, #465). A real run: Nextflow, Docker, nf-core's pinned test genome."""

import json
import math
import shutil

import pytest
from mendel_compiler.cli import main
from support.paths import ROOT

pytestmark = pytest.mark.slow

STARTER = """version: 10
intent:
  want: [genome.index.star]
facts:
  inputs:
    - {type_id: genome.fasta}
    - {type_id: annotation.gtf}
  measurements: []
"""


def test_star_runs_with_the_index_size_its_genome_measures_to(tmp_path):
    if shutil.which("nextflow") is None or shutil.which("docker") is None:
        pytest.skip("needs Nextflow and Docker")
    starter = tmp_path / "starter.yml"
    starter.write_text(STARTER)
    out = tmp_path / "p"
    assert main(["build", str(starter), "--out", str(out), "--root", str(ROOT),
                 "--gate", "test"]) == 0

    (report,) = (out / "results" / "measure_genome_length_fai").glob("*.measured.json")
    fact = json.loads(report.read_text())["facts"]["genome_length"]
    assert fact["coverage"] == "all" and fact["value"] > 0
    expected = round(min(14, math.log2(fact["value"]) / 2 - 1))

    star = [p for p in (out / "work").rglob(".command.sh") if "genomeGenerate" in p.read_text()]
    assert len(star) == 1
    assert f"--genomeSAindexNbases {expected}" in star[0].read_text()

    decided = out / "results" / "decided" / "star_genomegenerate.sa_index_nbases.tsv"
    sample, value, read = decided.read_text().split()
    assert (sample, value) == (report.name.removesuffix(".measured.json"), str(expected))
    assert read == f"genome_length={fact['value']}:measured"

    # Its memory, ruled from the same length rather than the label's 72 GB clamped to the smoke
    # cap (#509): STAR is told the task's memory less 100 MB, so the request is in the script.
    gigabytes = max(2, round(fact["value"] * 1e-8 + 1))
    assert f"--limitGenomeGenerateRAM {gigabytes * 1024**3 - 100_000_000}" in star[0].read_text()
    decided = out / "results" / "decided" / "star_genomegenerate.memory.tsv"
    assert decided.read_text().split()[1] == str(gigabytes)
