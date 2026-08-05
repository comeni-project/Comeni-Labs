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
