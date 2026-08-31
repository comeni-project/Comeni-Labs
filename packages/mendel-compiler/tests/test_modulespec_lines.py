"""`ModuleSpec` records where it read each fact.

Without this every `Fact` in an `Observation` cites the same location, which is enough for a
human to find the file and not enough for anyone — or anything — to read the evidence.
"""

from pathlib import Path

import pytest
from mendel_compiler.modulespec import ModuleSpec

ROOT = Path(__file__).resolve().parents[3]
# The layer, since Plan 5A. `vendor/` was a copy of this in the engine's repository, on a
# different release cadence from the contracts describing it.
TOOLS = ROOT / "registry" / "tools" / "nf-core"
FASTQC = TOOLS / "fastqc" / "module" / "main.nf"
SAMTOOLS_INDEX = TOOLS / "samtools" / "index" / "module" / "main.nf"


@pytest.fixture(scope="module")
def spec() -> ModuleSpec:
    return ModuleSpec.parse(FASTQC)


def _line(text: str, number: int) -> str:
    return text.splitlines()[number - 1]


def test_the_process_line_holds_the_process_declaration(spec: ModuleSpec) -> None:
    source = FASTQC.read_text()
    assert "process" in _line(source, spec.lines["process"])
    assert spec.process in _line(source, spec.lines["process"])


def test_every_recorded_line_is_within_the_file(spec: ModuleSpec) -> None:
    total = len(FASTQC.read_text().splitlines())
    assert spec.lines, "no positions were recorded at all"
    for key, number in spec.lines.items():
        assert 1 <= number <= total, f"{key} points at line {number} of a {total}-line file"


def test_every_emit_has_a_line_naming_it(spec: ModuleSpec) -> None:
    source = FASTQC.read_text()
    assert spec.emits, "fixture has no emits; pick a different module"
    for name in spec.emits:
        assert name in _line(source, spec.lines[f"emits.{name}"])


def test_the_container_line_holds_the_container(spec: ModuleSpec) -> None:
    assert spec.container is not None
    assert "container" in _line(FASTQC.read_text(), spec.lines["container"])


def test_the_input_block_line_holds_the_input_keyword(spec: ModuleSpec) -> None:
    assert "input:" in _line(FASTQC.read_text(), spec.lines["inputs"])


def test_every_input_slot_has_a_line_naming_one_of_its_elements(spec: ModuleSpec) -> None:
    source = FASTQC.read_text()
    for slot in spec.inputs:
        named = [name for name in slot.names if name]
        if not named:
            continue
        line = _line(source, spec.lines[f"inputs.{slot.position}"])
        assert any(name in line for name in named), f"slot {slot.position}: {line!r}"


def test_every_meta_read_has_a_line_naming_it(spec: ModuleSpec) -> None:
    source = FASTQC.read_text()
    assert spec.meta_reads, "fixture reads no meta keys; pick a different module"
    for read in spec.meta_reads:
        line = _line(source, spec.lines[f"meta_reads.{read.variable}.{read.key}"])
        assert f"{read.variable}.{read.key}" in line


def test_an_ext_args_read_is_located(spec: ModuleSpec) -> None:
    assert spec.reads_ext_args
    assert "task.ext.args" in _line(FASTQC.read_text(), spec.lines["reads_ext_args"])


def test_a_fact_the_module_lacks_has_no_key() -> None:
    """`reads_ext_prefix` is absent from three of the ten vendored modules — MD0108's real
    negatives. An absent fact must have no position rather than a zero.

    `samtools/index` rather than `fastqc`, which *does* read `task.ext.prefix`: guarding this
    with `if not spec.reads_ext_prefix` on a module that has one asserts nothing at all.
    """
    spec = ModuleSpec.parse(SAMTOOLS_INDEX)
    assert not spec.reads_ext_prefix, "fixture changed; pick another module without ext.prefix"
    assert "reads_ext_prefix" not in spec.lines


def test_positions_are_stable_across_two_parses(spec: ModuleSpec) -> None:
    """Byte-identical emission is a hard requirement, and these reach a golden file."""
    assert ModuleSpec.parse(FASTQC).lines == spec.lines
