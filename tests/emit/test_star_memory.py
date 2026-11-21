"""STAR's memory, ruled from the genome's length (#509): a directive decided at build when the
length is stated, and in the run from the measured length when it is not."""

import re

import pytest
from mendel_compiler.cli import main
from support.paths import ROOT

STARTER = """version: 10
intent:
  want: [genome.index.star]
facts:
  inputs:
    - {{type_id: genome.fasta}}
    - {{type_id: annotation.gtf}}
  measurements: [{measurements}]
"""


def _config(tmp_path, measurements: str = "") -> str:
    starter = tmp_path / "starter.yml"
    starter.write_text(STARTER.format(measurements=measurements))
    out = tmp_path / "p"
    assert main(["build", str(starter), "--out", str(out), "--root", str(ROOT)]) == 0
    return (out / "nextflow.config").read_text()


def _memory(config: str) -> str:
    (line,) = [x for x in config.splitlines()
               if "withName: STAR_GENOMEGENERATE" in x and "memory" in x]
    return line


def test_a_stated_genome_asks_for_what_the_rule_gives(tmp_path):
    line = _memory(_config(tmp_path, STATED))
    assert "MemoryUnit.of('2 GB') * task.attempt" in line


def test_a_measured_genome_is_sized_in_the_run(tmp_path):
    line = _memory(_config(tmp_path))
    assert "meta.genome_length" in line and "MemoryUnit.of(" in line
    assert "* task.attempt" in line


def test_without_a_measurement_the_label_still_asks(tmp_path):
    """The fallback reads the label table this config already emits, by the task's label."""
    config = _config(tmp_path)
    line = _memory(config)
    table = re.search(r"\[(process_single: \d+.*?)\]", line)
    assert table is not None and "process_high: 72" in table.group(1)
    assert "task.label" in line
    assert "withLabel: process_high {" in config


STATED = "{measurement: genome_length, value: 29903, source: said}"


@pytest.mark.parametrize("measurements", ["", STATED])
def test_the_ruled_memory_is_one_withName_line(tmp_path, measurements):
    config = _config(tmp_path, measurements)
    assert config.count("withName: STAR_GENOMEGENERATE { memory") == 1


ALIGNING = """version: 10
intent:
  want: [counts.matrix]
facts:
  inputs:
    - {type_id: fastq.reads}
    - {type_id: annotation.gtf}
    - {type_id: genome.fasta}
  measurements:
    - {measurement: n_samples, value: 2, source: said}
    - {measurement: paired, value: true, source: said}
    - {measurement: read_length, value: 150, source: said}
    - {measurement: strandedness, value: reverse, source: said}
"""


def _built(tmp_path):
    starter = tmp_path / "starter.yml"
    starter.write_text(ALIGNING)
    out = tmp_path / "p"
    assert main(["build", str(starter), "--out", str(out), "--root", str(ROOT)]) == 0
    return (out / "nextflow.config").read_text(), (out / "main.nf").read_text()


def test_the_aligner_is_sized_from_the_genome_on_its_index(tmp_path):
    """#601: STAR_ALIGN reads the genome's length from the index's `meta2`, not the reads'."""
    config, workflow = _built(tmp_path)
    (line,) = [x for x in config.splitlines() if "withName: STAR_ALIGN { memory" in x]
    assert "meta2.genome_length" in line and "meta.genome_length" not in line
    assert "star_align.memory.tsv" in workflow and "meta2.id" in workflow


@pytest.mark.slow
def test_a_real_alignment_asks_for_what_its_genome_needs(tmp_path):
    """#601, on Nextflow and Docker with nf-core's test genome (230,218 bp): both STAR steps ask
    for the ruled 2 GB instead of the label's 72 GB, and the run records the aligner's value."""
    import shutil
    import subprocess

    if shutil.which("nextflow") is None or shutil.which("docker") is None:
        pytest.skip("needs Nextflow and Docker")
    starter = tmp_path / "starter.yml"
    starter.write_text(ALIGNING)
    out = tmp_path / "p"
    assert main(["build", str(starter), "--out", str(out), "--root", str(ROOT),
                 "--gate", "test"]) == 0
    reference, value, read = (out / "results/decided/star_align.memory.tsv").read_text().split()
    assert value == "2" and read.startswith("genome_length=") and read.endswith(":measured")
    run = subprocess.run(["nextflow", "log", "-q"], cwd=out, capture_output=True, text=True)
    asked = subprocess.run(["nextflow", "log", "-f", "name,memory", run.stdout.split()[-1]],
                           cwd=out, capture_output=True, text=True).stdout
    star = [line for line in asked.splitlines() if line.startswith("STAR_")]
    assert len(star) == 2 and all(line.endswith("2 GB") for line in star), asked
