"""Pairing read off each row: a blank second reads cell is a single-end sample (#466, stage 3)."""

import pytest
from comeni_core.artifact.pipeline import Pipeline
from mendel_compiler import orchestrate
from mendel_compiler.emit import emit
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from support.paths import ROOT

STACK = layers.load(ROOT / "registry")
INPUTS = ("fastq.reads", "genome.fasta", "annotation.gtf")


def _built(varies: list[str], profile: dict) -> Pipeline:
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in INPUTS], "want": ["counts.matrix"],
        "constraints": {"varies": varies},
        "profile": STACK.measurements.profile(profile).model_dump(mode="json")})
    return orchestrate.build(goal, registry_roots=[ROOT / "registry"]).pipeline


@pytest.fixture(scope="module")
def mixed() -> Pipeline:
    return _built(["paired"], {"read_length": 150})


def test_pairing_that_varies_has_no_column_of_its_own(mixed):
    (fact,) = mixed.sheet_facts
    assert fact.measurement == "paired" and fact.from_row == "second_file_present"
    assert fact.column == "reads_2" and not fact.required


def test_pairing_is_read_off_the_row_and_reaches_single_end(mixed):
    text = emit(mixed)
    assert "paired: (row.reads_2 != null && row.reads_2.trim() != '')" in text
    assert ("single_end: (v.paired == null ? null : [(true): false, (false): true][v.paired])"
            in text)


def test_a_single_end_row_passes_one_file(mixed):
    text = emit(mixed)
    given = "row.reads_2 != null && row.reads_2.trim()"
    line = next(one for one in text.splitlines() if given in one and "file(row.reads_2)" in one)
    assert ", file(row.reads_2) ] : [ file(row.reads_1 ?: error(" in line


def test_a_blank_file_cell_stops_the_run_naming_it_when_pairing_is_stated():
    text = emit(_built(["strandedness"], {"read_length": 150, "paired": True}))
    assert "column reads_2 is required" in text
