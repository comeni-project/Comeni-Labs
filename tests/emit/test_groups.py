"""Samples sharing a key run together as a group (#466, stage 5 part B).

A co-assembler reads every sample of one `group` in one call. The samplesheet has a `group`
column; each row's group size rides on its `meta`, so a group moves on as soon as its own samples
are done, never waiting for the study.
"""

import shutil
import subprocess

import pytest
from comeni_core.artifact.pipeline import Pipeline
from mendel_compiler import orchestrate
from mendel_compiler.emit import emit
from mendel_resolver.goal import Goal
from support.paths import ROOT

from emit.fixtures.relations import COASSEMBLE, MEASUREMENT, layer, module


def _goal() -> Goal:
    return Goal.model_validate({"have": [{"type_id": "fastq.reads"}],
                                "want": ["assembly.fasta"]})


def _built(tmp_path, extra=None) -> Pipeline:
    roots = [ROOT / "registry", layer(tmp_path, extra)]
    return orchestrate.build(_goal(), registry_roots=roots).pipeline


def test_a_key_a_port_groups_by_is_a_required_column(tmp_path):
    pipeline = _built(tmp_path)
    (fact,) = pipeline.sheet_facts
    assert (fact.measurement, fact.column, fact.kind.value, fact.required) == (
        "group", "group", "key", True)
    (reads,) = [i for s in pipeline.steps if s.id == "coassemble"
                for i in s.inputs if i.port == "reads"]
    assert reads.gather and reads.by == "group"


def test_a_group_gathers_with_its_size_from_the_sheet(tmp_path):
    text = emit(_built(tmp_path))
    assert "groupKey(it[0].group, it[0].comeni_groups['group'])" in text
    assert "comeni_groups:" in text
    assert "COASSEMBLE(" in text


def test_a_key_cell_is_an_identifier(tmp_path):
    text = emit(_built(tmp_path))
    assert "column group: '${c}' is not a key" in text


def test_a_port_grouping_by_a_fact_that_is_no_key_is_refused(tmp_path):
    extra = {"group.measurement.yml": MEASUREMENT.format(id="group", kind="integer")
             .replace("kind: integer\n", "kind: integer\nminimum: 0\n")}
    with pytest.raises(Exception, match="MD0343"):
        _built(tmp_path, extra)


@pytest.mark.slow
def test_each_group_runs_once_with_its_own_samples(tmp_path):
    if shutil.which("nextflow") is None or shutil.which("docker") is None:
        pytest.skip("needs Nextflow and Docker")
    from support.pipeline import _starter

    starter = _starter(tmp_path / "starter.yml", {"have": [{"type_id": "fastq.reads"}],
                                                  "want": ["assembly.fasta"]})
    out = tmp_path / "built"
    subprocess.run(["uv", "run", "mendel", "build", str(starter), "--registry", "registry",
                    "--registry", str(layer(tmp_path)), "--out", str(out)],
                   cwd=ROOT, check=True, capture_output=True)
    module(out, "modules/lab/coassemble/main", COASSEMBLE)
    data = tmp_path / "data"
    data.mkdir()
    rows = ["sample,reads_1,reads_2,group"]
    for sample, group in (("S1", "g1"), ("S2", "g1"), ("S3", "g2")):
        for mate in (1, 2):
            (data / f"{sample}_{mate}.fq.gz").write_text("stub\n")
        rows.append(f"{sample},{data}/{sample}_1.fq.gz,{data}/{sample}_2.fq.gz,{group}")
    (data / "sheet.csv").write_text("\n".join(rows) + "\n")
    done = subprocess.run(
        ["nextflow", "-q", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker",
         "--input", str(data / "sheet.csv"), "--outdir", str(tmp_path / "results")],
        cwd=out, capture_output=True, text=True, timeout=900)
    assert done.returncode == 0, done.stdout + done.stderr
    log = (out / ".nextflow.log").read_text()
    tags = sorted(line.split("Submitted process > COASSEMBLE (")[1].split(")")[0]
                  for line in log.splitlines() if "Submitted process > COASSEMBLE (" in line)
    assert tags == ["g1", "g2"]


def test_a_measurer_of_a_key_is_refused(tmp_path):
    """A key comes from the samplesheet only (MD0342)."""
    from mendel_resolver import layers as loader

    root = layer(tmp_path, {"group.measurer.yml": """declares: measurer
id: group_guess
version: 1.0.0
measures: group
by: code
record: sequence
runs: [server]
entry: piece/read_length.py
"""})
    with pytest.raises(ValueError, match="MD0342"):
        loader.load([ROOT / "registry", root])


def test_a_group_counts_samples_not_lanes(tmp_path):
    """Final review C1: with lanes, a group's size is its samples, or it never fills."""
    roots = [ROOT / "registry", layer(tmp_path)]
    goal = Goal.model_validate({"have": [{"type_id": "fastq.reads"}], "want": ["assembly.fasta"],
                                "constraints": {"units": ["fastq.reads"]}})
    text = emit(orchestrate.build(goal, registry_roots=roots).pipeline)
    assert "rs*.sample.unique().size()" in text


def test_a_port_that_selects_and_groups_is_refused(tmp_path):
    """Final review C1: a selection before a group gather would leave the group unfilled."""
    from emit.fixtures.relations import LAYER

    contract = LAYER["coassemble.contract.yml"].replace(
        "many: true, by: group}", "many: true, by: group, select: {group: present}}")
    with pytest.raises(Exception, match="MD0343"):
        _built(tmp_path, {"coassemble.contract.yml": contract})


def test_a_rule_reading_a_key_is_refused(tmp_path):
    """Final review: a key's value would ride on every sample's meta into the run's record."""
    from mendel_resolver import layers as loader

    root = layer(tmp_path)
    (root / "rules").mkdir()
    (root / "rules/key.yml").write_text("""declares: rule
version: 1
derives:
  - fact: one_group
    kind: key
    aggregate: {measurement: group, over: study, using: agree}
    because: a fixture
""")
    with pytest.raises(Exception, match="MD0345"):
        loader.load([ROOT / "registry", root])
