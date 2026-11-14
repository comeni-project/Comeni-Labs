"""Each sample's own strandedness, from its samplesheet row (#466). A real run: Nextflow, Docker,
nf-core's test reads, two samples that differ only in what their row says."""

import shutil
import subprocess

import pytest
from support.paths import ROOT

pytestmark = pytest.mark.slow

STARTER = """version: 9
intent:
  want: [counts.matrix]
  constraints: {varies: [strandedness]}
facts:
  inputs:
    - {type_id: fastq.reads}
    - {type_id: genome.fasta}
    - {type_id: annotation.gtf}
  measurements:
    - {measurement: read_length, value: 150}
"""


def test_each_sample_gets_its_strandedness(tmp_path):
    if shutil.which("nextflow") is None or shutil.which("docker") is None:
        pytest.skip("needs Nextflow and Docker")
    starter = tmp_path / "starter.yml"
    starter.write_text(STARTER)
    out = tmp_path / "p"
    subprocess.run(["uv", "run", "mendel", "build", str(starter), "--registry", "registry",
                    "--out", str(out)], cwd=ROOT, check=True, capture_output=True)
    import yaml
    from comeni_core.artifact.pipeline import Pipeline
    from mendel_compiler.emit import test_samplesheet

    pipeline = Pipeline.model_validate(yaml.safe_load((out / "pipeline.yml").read_text()))
    header, row, _ = test_samplesheet(pipeline).split("\n")
    cells = dict(zip(header.split(","), row.split(","), strict=True))
    lines = [header]
    for sample, strand in (("S1", "forward"), ("S2", "reverse")):
        lines.append(",".join({**cells, "sample": sample, "strandedness": strand}[c]
                              for c in header.split(",")))
    sheet = tmp_path / "sheet.csv"
    sheet.write_text("\n".join(lines) + "\n")
    done = subprocess.run(["nextflow", "run", "main.nf", "-profile", "test,docker", "--input",
                           str(sheet), "--outdir", str(tmp_path / "results")],
                          cwd=out, capture_output=True, text=True, timeout=3000)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    counted = {}
    for script in (out / "work").rglob(".command.sh"):
        text = script.read_text()
        if "featureCounts" in text:
            log = (script.parent / ".command.log").read_text() if (
                script.parent / ".command.log").exists() else ""
            sample = "S1" if "S1" in text + log else "S2"
            counted[sample] = text
    assert set(counted) == {"S1", "S2"}
    assert "-s 1" in counted["S1"] and "-s 2" in counted["S2"]
