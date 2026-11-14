"""A sample's lanes merged in the run (#466, stage 5).

The samplesheet takes a `unit` column; rows sharing `sample` are one sample's lanes. A one-lane
sample passes straight on; a sample over several is merged by cat/fastq first, gathered with a
`groupKey` sized from the sheet, so neither waits for the other.
"""

import pytest
from comeni_core.artifact.pipeline import Pipeline
from mendel_compiler import orchestrate
from mendel_compiler.emit import emit
from mendel_compiler.emit import test_samplesheet as sheet_of
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from support.paths import ROOT

STACK = layers.load(ROOT / "registry")
INPUTS = ("fastq.reads", "genome.fasta", "annotation.gtf")


def _built(units=("fastq.reads",), varies=()) -> Pipeline:
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in INPUTS], "want": ["counts.matrix"],
        "constraints": {"units": list(units), "varies": list(varies)},
        "profile": STACK.measurements.profile({"read_length": 150}).model_dump(mode="json")})
    return orchestrate.build(goal, registry_roots=[ROOT / "registry"]).pipeline


@pytest.fixture(scope="module")
def lanes() -> Pipeline:
    return _built()


def test_the_reads_may_span_several_rows(lanes):
    reads = next(c for c in lanes.channels if c.type_id == "fastq.reads")
    assert reads.units
    assert "merge_fastq_reads" in {s.id for s in lanes.steps}


def test_a_samples_lanes_are_gathered_and_merged(lanes):
    text = emit(lanes)
    assert "groupKey(meta.id, meta.comeni_units)" in text
    assert "CAT_FASTQ(" in text
    assert "ch_reads = ch_reads_units.one.mix(CAT_FASTQ.out.reads)" in text
    assert "TRIMGALORE(ch_reads" in text
    lines = [line.strip() for line in text.splitlines()]
    merged = next(n for n, line in enumerate(lines) if line.startswith("ch_reads = "))
    trimmed = next(n for n, line in enumerate(lines) if line.startswith("TRIMGALORE("))
    assert merged < trimmed


def test_a_repeated_sample_is_its_lanes_and_a_repeated_lane_is_refused(lanes):
    text = emit(lanes)
    assert "samplesheet has a repeated sample and unit" in text
    assert "comeni_units:" in text


def test_lanes_that_disagree_stop_the_run_naming_the_sample(lanes):
    assert "its rows disagree on" in emit(lanes)


def test_the_test_samplesheet_has_a_unit_column(lanes):
    header = sheet_of(lanes).splitlines()[0].split(",")
    assert "unit" in header


def test_without_units_the_reads_are_one_row_per_sample():
    text = emit(_built(units=(), varies=("strandedness",)))
    assert "groupKey(" not in text and "CAT_FASTQ" not in text
    assert "samplesheet has duplicate sample ids" in text
