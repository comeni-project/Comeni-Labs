"""What a gate does, with the storage and the subprocess stubbed out.

`services/drafts.py` records why the seams exist: CI has no Postgres and no Nextflow, so a rule
that could only be checked on a developer machine is a rule nobody checks. These tests exercise
`of` — the half with no database — and stub `_run` where a real Nextflow would be needed.
"""

import pathlib

import pytest
from comeni_core.artifact.gates import Gate
from mendel_compiler.cli import main
from mendel_compiler.gates import GateResult

from mendel_api.services import gates

ROOT = pathlib.Path(__file__).parent.parent.parent.parent
GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _kept(tmp_path):
    """A real kept directory, because `of` loads and re-emits the artifact.

    Built through the same verb the product uses rather than by hand-writing a `pipeline.yml`:
    a fixture that is not a real artifact tests a code path nothing takes. This is
    `tests/test_pipeline_file.py::_build` verbatim.

    **No `--gate`.** CI installs neither Nextflow nor Docker, so any test passing one is green
    locally and red in CI — `CLAUDE.md`, Gotchas.
    """
    out = tmp_path / "kept"
    assert main(["build", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)]) == 0
    return out


def test_a_gate_refuses_a_draft_that_was_never_kept(tmp_path):
    """A draft is a row; a gate runs on an artifact. `keep` is the boundary between them
    (`docs/design/execution-boundary.md` §4), so gating something never kept has no directory
    to run in — and Nextflow's own error would blame the pipeline for a missing file rather
    than saying the pipeline was never written.

    **No monkeypatch.** `of` takes the directory as an argument and never calls `_directory`,
    so patching that seam here would change nothing and the test would pass for a reason
    unrelated to what it claims to check. That is A172.
    """
    with pytest.raises(ValueError, match="MI0001"):
        gates.of(tmp_path / "never-kept", Gate.LINT)


def test_a_gate_reports_a_missing_nextflow_as_a_failed_gate_not_a_crash(tmp_path, monkeypatch):
    """`run_gate` already degrades honestly — `nextflow not found on PATH`. The service must
    carry that through as a FAILED result with that text, because an exception here reaches the
    person as a 500 with no message: the failure mode forge phase 2 shipped and spent an
    evening on."""
    monkeypatch.setattr(
        gates,
        "_run",
        lambda gate, d: GateResult(gate=gate, passed=False, stderr="nextflow not found on PATH"),
    )
    result = gates.of(_kept(tmp_path), Gate.LINT)
    assert result.passed is False
    assert "nextflow not found on PATH" in result.output


def test_a_gate_regenerates_the_nextflow_from_the_artifact(tmp_path, monkeypatch):
    """A gate certifies what `pipeline.yml` describes, so it re-emits rather than trusting
    whatever `.nf` happens to be on disk. Deleting both and gating must put them back."""
    directory = _kept(tmp_path)
    monkeypatch.setattr(gates, "_run", lambda gate, d: GateResult(gate=gate, passed=True))

    (directory / "main.nf").unlink()
    (directory / "nextflow.config").unlink()
    gates.of(directory, Gate.LINT)

    assert (directory / "main.nf").exists()
    assert "process.executor = 'awsbatch'" in (directory / "nextflow.config").read_text()


def test_the_stub_gate_gets_its_stub_inputs_and_the_others_do_not(tmp_path, monkeypatch):
    """`materialise_stub_data` writes the empty files the `stub_data` profile points at. Only
    `STUB` needs them — `_publish_verb` makes the same distinction."""
    monkeypatch.setattr(gates, "_run", lambda gate, d: GateResult(gate=gate, passed=True))

    lint_dir = _kept(tmp_path / "a")
    gates.of(lint_dir, Gate.LINT)
    assert not (lint_dir / "stub-data").exists()

    stub_dir = _kept(tmp_path / "b")
    gates.of(stub_dir, Gate.STUB)
    assert (stub_dir / "stub-data").exists()
