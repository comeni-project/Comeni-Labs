"""Mendel's compiler: pipeline IR to Nextflow DSL2, plus the validation gates.

Emission is deterministic — the same IR produces byte-identical output, proven across
`PYTHONHASHSEED` values rather than assumed. Anything that serialises a `frozenset` needs
a serialiser that sorts, because `frozenset` iterates in hash order::

    from mendel_compiler import emit, emit_config

    source = emit(ir, registry, vocabulary)

`cli.main` is the only thing here that touches disk; everything else takes objects and
returns strings, which is what makes the golden-file tests possible.

This package is **pure** in the sense of `tests/test_purity.py`, under a banlist rather
than an allowlist: it has to run Nextflow, so it needs `subprocess`, and `subprocess` can
shell out to `curl`. An honest banlist beats an allowlist with a hole in it.
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
