"""A tumour and a normal of one patient go into one call; a sample may name its control
(#466, stage 5 part B)."""

import shutil
import subprocess

import pytest
from comeni_core.artifact.pipeline import Pipeline
from mendel_compiler import orchestrate
from mendel_compiler.emit import emit
from mendel_resolver.goal import Goal
from support.paths import ROOT

from emit.fixtures.relations import CHIP, PAIR_CALL, PAIRS, PEAKS, layer, module


def _built(tmp_path, files, want) -> Pipeline:
    roots = [ROOT / "registry", layer(tmp_path, files)]
    goal = Goal.model_validate({"have": [{"type_id": "fastq.reads"}], "want": [want]})
    return orchestrate.build(goal, registry_roots=roots).pipeline


def test_a_pair_selects_its_members_and_joins_on_the_key(tmp_path):
    pipeline = _built(tmp_path, PAIRS, "calls.vcf")
    assert {f.measurement for f in pipeline.sheet_facts} == {"patient", "status"}
    call = next(line.strip() for line in emit(pipeline).splitlines()
                if line.strip().startswith("PAIR_CALL("))
    assert "meta.status == 'tumor'" in call and "meta.status == 'normal'" in call
    assert ".map { it -> [ it[0].patient, it ] }" in call
    assert "failOnDuplicate: true, failOnMismatch: true" in call


def test_a_reference_joins_the_named_samples_item(tmp_path):
    pipeline = _built(tmp_path, CHIP, "peaks.bed")
    (control,) = pipeline.sheet_facts
    assert (control.measurement, control.required) == ("control", False)
    text = emit(pipeline)
    call = next(line.strip() for line in text.splitlines() if line.strip().startswith("PEAKS("))
    assert "(meta.control != null)" in call
    assert ".combine(" in call and "by: 0" in call
    assert "names ${row.control}, which is no row of this samplesheet" in text


def test_a_by_key_join_needs_a_key(tmp_path):
    files = {**PAIRS, "pair.contract.yml": PAIRS["pair.contract.yml"].replace(
        "key: patient", "key: status")}
    with pytest.raises(Exception, match="MD0344"):
        _built(tmp_path, files, "calls.vcf")


def _run(tmp_path, out, header, rows):
    data = tmp_path / "data"
    data.mkdir()
    lines = [header]
    for sample, *rest in rows:
        for mate in (1, 2):
            (data / f"{sample}_{mate}.fq.gz").write_text("stub\n")
        lines.append(",".join([sample, f"{data}/{sample}_1.fq.gz", f"{data}/{sample}_2.fq.gz",
                               *rest]))
    (data / "sheet.csv").write_text("\n".join(lines) + "\n")
    done = subprocess.run(
        ["nextflow", "-q", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker",
         "--input", str(data / "sheet.csv"), "--outdir", str(tmp_path / "results")],
        cwd=out, capture_output=True, text=True, timeout=900)
    log = (out / ".nextflow.log").read_text() if (out / ".nextflow.log").exists() else ""
    return done, log


def _built_dir(tmp_path, files, want, include, source):
    if shutil.which("nextflow") is None or shutil.which("docker") is None:
        pytest.skip("needs Nextflow and Docker")
    from support.pipeline import _starter

    starter = _starter(tmp_path / "starter.yml", {"have": [{"type_id": "fastq.reads"}],
                                                  "want": [want]})
    out = tmp_path / "built"
    subprocess.run(["uv", "run", "mendel", "build", str(starter), "--registry", "registry",
                    "--registry", str(layer(tmp_path, files)), "--out", str(out)],
                   cwd=ROOT, check=True, capture_output=True)
    module(out, include, source)
    return out


def _tags(log: str, process: str) -> list[str]:
    return sorted(line.split(f"Submitted process > {process} (")[1].split(")")[0]
                  for line in log.splitlines() if f"Submitted process > {process} (" in line)


@pytest.mark.slow
def test_each_patients_tumour_and_normal_go_in_together(tmp_path):
    out = _built_dir(tmp_path, PAIRS, "calls.vcf", "modules/lab/pair_call/main", PAIR_CALL)
    done, log = _run(tmp_path, out, "sample,reads_1,reads_2,patient,status", [
        ("S1", "P1", "tumor"), ("S2", "P1", "normal"),
        ("S3", "P2", "tumor"), ("S4", "P2", "normal")])
    assert done.returncode == 0, done.stdout + done.stderr
    assert _tags(log, "PAIR_CALL") == ["P1", "P2"]


@pytest.mark.slow
def test_a_patient_with_two_normals_stops_the_run_naming_it(tmp_path):
    """Review Focus 4."""
    out = _built_dir(tmp_path, PAIRS, "calls.vcf", "modules/lab/pair_call/main", PAIR_CALL)
    done, _ = _run(tmp_path, out, "sample,reads_1,reads_2,patient,status", [
        ("S1", "P1", "tumor"), ("S2", "P1", "normal"), ("S3", "P1", "normal")])
    assert done.returncode != 0
    assert "P1" in done.stdout + done.stderr


@pytest.mark.slow
def test_each_sample_reads_the_control_it_names(tmp_path):
    out = _built_dir(tmp_path, CHIP, "peaks.bed", "modules/lab/peaks/main", PEAKS)
    done, log = _run(tmp_path, out, "sample,reads_1,reads_2,control", [
        ("IN", ""), ("C1", "IN"), ("C2", "IN")])
    assert done.returncode == 0, done.stdout + done.stderr
    assert _tags(log, "PEAKS") == ["C1", "C2"]


@pytest.mark.slow
def test_a_control_that_names_no_row_stops_the_run_naming_both(tmp_path):
    """Review Focus 5."""
    out = _built_dir(tmp_path, CHIP, "peaks.bed", "modules/lab/peaks/main", PEAKS)
    done, _ = _run(tmp_path, out, "sample,reads_1,reads_2,control", [("IN", ""), ("C1", "XX")])
    assert done.returncode != 0
    said = done.stdout + done.stderr
    assert "sample C1" in said and "XX" in said
