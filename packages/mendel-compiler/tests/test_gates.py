import pathlib
import shutil

import pytest
from mendel_compiler.gates import Gate, GateResult, run_gate

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
