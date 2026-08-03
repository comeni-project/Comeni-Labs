import shutil

import pytest
from mendel_compiler.gates import Gate, GateResult, run_gate


@pytest.mark.skipif(shutil.which("nextflow") is None, reason="nextflow not installed")
def test_gate_result_reports_failure_with_output(tmp_path):
    """A failure must carry its diagnostics. Which stream they arrive on is Nextflow's business.

    `nextflow lint` writes errors to stdout while `nextflow run` writes them to stderr,
    so asserting on `stderr` alone passes for one gate and fails for another.
    """
    (tmp_path / "main.nf").write_text("this is not valid nextflow {{{\n")
    result = run_gate(Gate.LINT, tmp_path)
    assert isinstance(result, GateResult)
    assert result.passed is False
    assert result.output != ""
    assert "Unexpected input" in result.output


@pytest.mark.skipif(shutil.which("nextflow") is None, reason="nextflow not installed")
def test_lint_passes_on_a_trivial_valid_pipeline(tmp_path):
    (tmp_path / "main.nf").write_text(
        "nextflow.enable.dsl = 2\nworkflow { Channel.of(1).view() }\n"
    )
    assert run_gate(Gate.LINT, tmp_path).passed is True


def test_gates_are_ordered_cheapest_first():
    assert list(Gate) == [Gate.LINT, Gate.PREVIEW, Gate.STUB, Gate.TEST]
