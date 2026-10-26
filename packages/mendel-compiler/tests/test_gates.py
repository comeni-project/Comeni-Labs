"""Gate command, fixture preparation, failure, and timeout contracts."""

import pathlib
import shutil
import subprocess

import pytest
from comeni_core import yaml_strict
from comeni_core.artifact.pipeline import InputForm, Pipeline
from mendel_compiler.gates import (
    Gate,
    GateResult,
    materialise_gate_inputs,
    run_gate,
)

ROOT = pathlib.Path(__file__).parents[3]
SPINE = ROOT / "tests/fixtures/pipeline/rnaseq-spine.yml"

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/fastqc.contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


@pytest.mark.skipif(shutil.which("nextflow") is None, reason="nextflow not installed")
def test_gate_result_reports_failure_with_output(tmp_path):
    """A failure must carry its diagnostics. Which stream they arrive on is Nextflow's business.

    `nextflow lint` writes errors to stdout while `nextflow run` writes them to stderr,
    so asserting on `stderr` alone passes for one gate and fails for another.
    """
    (tmp_path / "main.nf").write_text(
        _declared(
            tmp_path / "main.nf",
            "this is not valid nextflow {{{\n"))
    result = run_gate(Gate.LINT, tmp_path)
    assert isinstance(result, GateResult)
    assert result.passed is False
    assert result.output != ""
    assert "Unexpected input" in result.output


@pytest.mark.skipif(shutil.which("nextflow") is None, reason="nextflow not installed")
def test_lint_passes_on_a_trivial_valid_pipeline(tmp_path):
    (tmp_path / "main.nf").write_text(
        _declared(
            tmp_path / "main.nf",
            "nextflow.enable.dsl = 2\nworkflow { Channel.of(1).view() }\n")
    )
    assert run_gate(Gate.LINT, tmp_path).passed is True


def test_gates_are_ordered_cheapest_first():
    assert list(Gate) == [Gate.LINT, Gate.PREVIEW, Gate.STUB, Gate.TEST]


def test_every_gate_that_executes_processes_names_a_container_engine():
    """Gate.TEST ran `-profile test` with no docker for its whole existence and could
    never have passed. It had never been run, so nothing noticed."""
    from mendel_compiler.gates import _ARGS, Gate

    for gate in (Gate.STUB, Gate.TEST):
        profile = _ARGS[gate][_ARGS[gate].index("-profile") + 1]
        # `gate.name`, not `gate`: Gate is a StrEnum, so the bare value renders as
        # "test" — indistinguishable from the profile it is complaining about. Watched
        # failing, which is the only way that was visible.
        assert "docker" in profile or "singularity" in profile, (
            f"Gate.{gate.name} executes processes under `-profile {profile}`, "
            f"which names no container engine, so every process dies with "
            f"`command not found`"
        )


def test_preview_needs_no_container_engine():
    """It does dataflow analysis without executing, which is why it can sit in the fast
    lane. Adding docker here would cost minutes and buy nothing."""
    from mendel_compiler.gates import _ARGS, Gate

    profile = _ARGS[Gate.PREVIEW][_ARGS[Gate.PREVIEW].index("-profile") + 1]
    assert "docker" not in profile


def test_a_stub_gate_materialises_every_local_input(tmp_path):
    pipeline = Pipeline.model_validate(yaml_strict.load(SPINE)).model_copy(
        update={"input_form": InputForm.SAMPLESHEET}
    )

    materialise_gate_inputs(Gate.STUB, tmp_path, pipeline)

    assert (tmp_path / "test-samplesheet.csv").is_file()
    assert sorted(path.name for path in (tmp_path / "stub-data").glob("*.fastq.gz")) == [
        "sampleA_R1.fastq.gz",
        "sampleA_R2.fastq.gz",
        "sampleB_R1.fastq.gz",
        "sampleB_R2.fastq.gz",
    ]
    assert (tmp_path / "stub-data/fasta.txt").is_file()
    assert (tmp_path / "stub-data/gtf.txt").is_file()


def test_a_test_gate_materialises_the_samplesheet_without_stub_data(tmp_path):
    pipeline = Pipeline.model_validate(yaml_strict.load(SPINE)).model_copy(
        update={"input_form": InputForm.SAMPLESHEET}
    )

    materialise_gate_inputs(Gate.TEST, tmp_path, pipeline)

    assert (tmp_path / "test-samplesheet.csv").is_file()
    assert not (tmp_path / "stub-data").exists()


def test_a_missing_nextflow_is_a_gate_result(monkeypatch, tmp_path):
    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)

    result = run_gate(Gate.LINT, tmp_path)

    assert result.passed is False
    assert result.stderr == "nextflow not found on PATH"


def test_a_gate_timeout_is_a_gate_result(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)

    result = run_gate(Gate.PREVIEW, tmp_path)

    assert result.passed is False
    assert result.stderr == "preview timed out"
