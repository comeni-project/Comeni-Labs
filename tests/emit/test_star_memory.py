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
