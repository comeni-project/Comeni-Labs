"""Validation gates, cheapest first. Each is a subprocess call to nextflow."""

import subprocess
from pathlib import Path

from comeni_core.artifact.gates import Gate
from pydantic import BaseModel

__all__ = ["Gate", "GateResult", "materialise_stub_data", "run_gate"]

# `Gate` is re-exported, not redefined. It moved to `comeni_core.artifact.gates` so a
# `Pipeline` could record which gate it passed (audit A4) without the core depending
# on this package. The shim stays because a gate is something the *compiler* runs, and
# rewriting every import to relocate an enum is churn nobody reviews carefully — the same
# call made for `Goal` and `DataProfile`. `tests/regressions/test_gates_and_emit.py` asserts the two
# import paths are one class.


_ARGS: dict[Gate, list[str]] = {
    Gate.LINT: ["nextflow", "lint", "main.nf"],
    Gate.PREVIEW: ["nextflow", "run", "main.nf", "-preview", "-profile", "stub_data"],
    # `--outdir results` rather than a `params.outdir` in the `stub_data` profile, and the
    # difference is not cosmetic. `publishDir`'s `enabled:` is an EXPRESSION evaluated when
    # Nextflow reads the config, and the `process {` scope is read BEFORE `profiles {` — so a
    # profile setting `outdir` cannot switch publishing on, while a command-line `--outdir` can,
    # because CLI params are injected before parsing. Measured on 2026-08-30 against a real stub
    # run: profile + expression published nothing, CLI + expression published 41 files.
    #
    # It also keeps *where results go* out of the artifact entirely, including out of its
    # profiles — which is what the site-fact argument asks for and what a profile default was
    # quietly undermining.
    Gate.STUB: ["nextflow", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker",
                "--outdir", "results"],
    # `test,docker` for the same reason STUB uses `stub_data,docker`: without it Nextflow
    # runs the tools on the host and every process dies with `command not found` (exit
    # 127). This gate was defined without it and could therefore never have passed, which
    # went unnoticed because nothing had ever run it.
    #
    # `emit_config` now emits a `test` profile from each type's `test_data`, pinned to a
    # commit. It is a smoke test on a public dataset: it proves the pipeline runs and
    # produces output on data somebody else curated. It does not demonstrate biological
    # correctness, and the laboratory still supplies its own reference material.
    Gate.TEST: ["nextflow", "run", "main.nf", "-profile", "test,docker", "--outdir", "results"],
}

_TIMEOUTS: dict[Gate, int] = {
    Gate.LINT: 60,
    Gate.PREVIEW: 180,
    Gate.STUB: 900,
    Gate.TEST: 3600,
}


class GateResult(BaseModel):
    gate: Gate
    passed: bool
    stdout: str = ""
    stderr: str = ""

    @property
    def output(self) -> str:
        """Both streams, because Nextflow does not agree with itself about which to use.

        `nextflow lint` reports errors on stdout; `nextflow run` reports them on stderr.
        Anything reading a failure wants whichever one it landed in, and Plan 2's
        `classify` parses this same combined text.
        """
        return f"{self.stderr}\n{self.stdout}".strip()


def run_gate(gate: Gate, workdir: Path) -> GateResult:
    try:
        completed = subprocess.run(
            _ARGS[gate],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=_TIMEOUTS[gate],
            check=False,
        )
    except FileNotFoundError:
        return GateResult(gate=gate, passed=False, stderr="nextflow not found on PATH")
    except subprocess.TimeoutExpired:
        return GateResult(gate=gate, passed=False, stderr=f"{gate} timed out")
    return GateResult(
        gate=gate,
        passed=completed.returncode == 0,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def materialise_test_samplesheet(workdir: Path, pipeline) -> None:
    """Write the `test` profile's samplesheet beside the workflow, if this pipeline takes one.

    **A config block cannot write a file**, and `params.input` for a samplesheet pipeline is a
    path to one. So the emitter points at `test-samplesheet.csv` and this puts it there — the
    same split `materialise_stub_data` already makes, and for the same reason: the pipeline must
    stay free of data and of paths to data (invariant 15), so fixtures live in the harness.

    A no-op for a direct pipeline, whose `params.input` is a glob the profile can state inline.
    """
    from comeni_core.plan.tiers import InputForm

    from mendel_compiler.emit import TEST_SAMPLESHEET, test_samplesheet

    if pipeline.input_form is not InputForm.SAMPLESHEET:
        return
    (workdir / TEST_SAMPLESHEET).write_text(test_samplesheet(pipeline))


def materialise_stub_data(workdir: Path, params: list[str]) -> None:
    """Synthetic inputs for the `-stub-run` gate.

    The gate proves the DAG wires up and executes; nf-core stub blocks never read
    what they are handed, so empty files are enough and no genome is downloaded.

    This lives in the gate rather than in the emitted pipeline on purpose. The
    pipeline must stay free of data and of paths to data — invariant 15 — so the
    validation harness is where fixtures belong.
    """
    data = workdir / "stub-data"
    data.mkdir(parents=True, exist_ok=True)
    for name in params:
        if name == "input":
            # **Two pairs, not one, and that is the whole reason a live bug survived.**
            #
            # A Nextflow process with several *queue* inputs runs as many times as the shortest.
            # Every entry channel was a queue, so a reference genome — one item — capped the run
            # at one invocation and every sample after the first was silently dropped.
            #
            # With one pair, N = 1 and the shortest channel is every channel: the gate is green,
            # the counts matrix is right, and the pipeline is wrong for real data. Two is the
            # smallest fixture that can tell a value channel from a queue of one.
            for sample in ("sampleA", "sampleB"):
                for mate in ("R1", "R2"):
                    (data / f"{sample}_{mate}.fastq.gz").write_bytes(b"")
        else:
            (data / f"{name}.txt").write_text("")
