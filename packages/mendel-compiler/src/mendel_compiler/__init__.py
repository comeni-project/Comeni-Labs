"""Compile resolved pipeline artifacts to deterministic Nextflow DSL2.

The top-level API exposes emission and layout helpers. Explicit adapter modules own artifact
files, Git inspection, source staging, validation subprocesses, and the command-line interface.
"""

from mendel_compiler.cli import main
from mendel_compiler.emit import emit, emit_config, entry_params
from mendel_compiler.gates import Gate, GateResult, materialise_stub_data, run_gate

__version__ = "0.1.0"

__all__ = [
    "Gate",
    "GateResult",
    "emit",
    "emit_config",
    "entry_params",
    "main",
    "materialise_stub_data",
    "run_gate",
]
