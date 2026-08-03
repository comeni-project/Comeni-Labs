"""Validation gates, cheapest first. Each is a subprocess call to nextflow."""

import subprocess
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel


class Gate(StrEnum):
    LINT = "lint"
    PREVIEW = "preview"
    STUB = "stub"
    TEST = "test"


_ARGS: dict[Gate, list[str]] = {
    Gate.LINT: ["nextflow", "lint", "main.nf"],
    Gate.PREVIEW: ["nextflow", "run", "main.nf", "-preview", "-profile", "stub_data"],
    Gate.STUB: ["nextflow", "run", "main.nf", "-stub-run", "-profile", "stub_data,docker"],
    # TEST alone keeps `-profile test`, which `emit_config` deliberately does not emit:
    # a real test profile needs real reference data, and shipping fixtures as if they
    # demonstrated biological correctness would be the dishonest kind of green. The
    # laboratory supplies it. Until then this gate cannot pass, and the v1 criterion —
    # stated in terms of `-profile test` — is not reachable from this repository alone.
    Gate.TEST: ["nextflow", "run", "main.nf", "-profile", "test"],
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
            for mate in ("R1", "R2"):
                (data / f"sample_{mate}.fastq.gz").write_bytes(b"")
        else:
            (data / f"{name}.txt").write_text("")
