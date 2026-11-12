"""The samplesheet carries the facts that differ between samples, checked when the run starts
(#466, per-sample design C).

A person says strandedness differs between samples. The pipeline then takes a samplesheet whose
`strandedness` column each row fills in, with its allowed values; each sample's value reaches
its `meta` under the fact's id and the module's key; a cell outside them stops the run before any
process starts, naming the row, the sample and the column.
"""

import pytest
from comeni_core.artifact.pipeline import InputForm, Pipeline
from comeni_core.declared.measurement import MeasurementKind
from mendel_compiler import orchestrate
from mendel_compiler.emit import emit
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from support.paths import ROOT

STACK = layers.load(ROOT / "registry")
INPUTS = ("fastq.reads", "genome.fasta", "annotation.gtf")


def _built(varies: list[str], profile: dict | None = None, roots=None) -> Pipeline:
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in INPUTS], "want": ["counts.matrix"],
        "constraints": {"varies": varies},
        "profile": STACK.measurements.profile({"read_length": 150} if profile is None else profile)
        .model_dump(mode="json")})
    return orchestrate.build(goal, registry_roots=roots or [ROOT / "registry"]).pipeline


@pytest.fixture(scope="module")
def stranded() -> Pipeline:
    return _built(["strandedness"])


def test_varying_strandedness_is_a_required_column(stranded):
    (fact,) = stranded.sheet_facts
    assert (fact.measurement, fact.column, fact.kind, fact.values, fact.required, fact.auto) == (
        "strandedness", "strandedness", MeasurementKind.ENUM,
        ["forward", "reverse", "unstranded"], True, False)
    assert stranded.input_form is InputForm.SAMPLESHEET
    reads = next(c for c in stranded.channels if c.type_id == "fastq.reads")
    assert "strandedness" not in {m.key for m in reads.meta}


def test_cells_reach_meta(stranded):
    text = emit(stranded)
    assert "(row.strandedness ?: '').trim()" in text
    assert "row.comeni" in text and "strandedness:" in text


def test_a_bad_cell_is_checked_before_any_process(stranded):
    text = emit(stranded)
    assert ("samplesheet row ${n} (sample ${row.sample}), column strandedness: '${c}' is not one "
            "of forward, reverse, unstranded") in text
    assert "column strandedness is required" in text


def test_a_measured_fact_that_varies_is_optional_and_auto():
    """Read length has a pipeline measurer: a blank or `auto` cell is measured (#466)."""
    rule = """declares: rule
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: min_mqs}
    rows:
      - {when: {read_length: ">= 70"}, then: 10, because: a fixture}
      - {when: {read_length: "< 70"}, then: 5, because: a fixture}
"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        layer = Path(tmp) / "quant"
        (layer / "rules").mkdir(parents=True)
        (layer / "rules/quant.yml").write_text(rule)
        pipeline = _built(["read_length"], profile={}, roots=[ROOT / "registry", layer])
    (fact,) = pipeline.sheet_facts
    assert (fact.measurement, fact.kind, fact.required, fact.auto, fact.minimum) == (
        "read_length", MeasurementKind.INTEGER, False, True, 1)
    text = emit(pipeline)
    assert "c == 'auto' ? null" in text
    # Only rows whose cell is blank go through the measuring step.
    assert "ch_reads_unstated" in text
    # Each sample's value is recorded with where it came from.
    assert "read_length=${meta.read_length}:" in text
    # A lookup reading a cell needs the column, or every sample would read nothing.
    with pytest.raises(ValueError, match="MD0335"):
        emit(pipeline.model_copy(update={"sheet_facts": []}))




def test_the_test_profile_fills_every_fact_column(stranded):
    from mendel_compiler.emit import test_samplesheet

    header, row, _ = test_samplesheet(stranded).split("\n")
    cells = dict(zip(header.split(","), row.split(","), strict=True))
    assert cells["strandedness"] == "forward"
