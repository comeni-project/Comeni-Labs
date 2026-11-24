"""The downloaded zip runs its own test (#619).

A samplesheet pipeline's `test` profile names `test-samplesheet.csv`, which only the gate used
to write, so the zip somebody downloaded could not run the test its own config offers. The
bundle now carries that samplesheet — pinned public URLs, never anybody's samples — and a
README saying how to run it, or which inputs have no example data when it cannot.
"""

import io
import zipfile

import pytest
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.draft import DraftChannel, DraftEdge, DraftGraph, DraftNode
from comeni_core.plan.tiers import InputForm
from mendel_api.services import bundle
from mendel_compiler import pipeline_file, readme

# Aliased: pytest would collect a `test_*` name imported into this module as a test.
from mendel_compiler.emit import TEST_SAMPLESHEET
from mendel_compiler.emit import test_profile_missing as missing_examples
from mendel_compiler.emit import test_samplesheet as samplesheet_of
from mendel_resolver import layers
from mendel_resolver.materialise import goal_of, ir_of
from support.paths import ROOT

STAR = "nf-core/star/align@2.7.11b"
GENOME = "nf-core/star/genomegenerate@2.7.11b"
RUN_TEST = "nextflow run . -profile test,docker"


@pytest.fixture(scope="module")
def stack():
    return layers.load(ROOT / "registry")


def _graph(with_index: bool) -> DraftGraph:
    """STAR with a per-sample GTF, so the pipeline takes a samplesheet. Built with its index,
    every input has a public example; given a prebuilt index, `genome.index.star` has none."""
    nodes = [DraftNode(id="align", contract_id=STAR)]
    edges = []
    if with_index:
        nodes.insert(0, DraftNode(id="index", contract_id=GENOME))
        edges = [DraftEdge(from_node="index", from_port="index", to_node="align",
                           to_port="index")]
    return DraftGraph(nodes=nodes, edges=edges, channels=[
        DraftChannel(ports=("align.gtf",), grain="sample", why="each sample has its own GTF")])


def _built(graph: DraftGraph, stack) -> Pipeline:
    return Pipeline.of(ir_of(graph, stack), stack.registry, stack.vocabulary,
                       stack.measurements, stack.paths, goal=goal_of(graph, stack))


@pytest.fixture(scope="module")
def runnable(stack) -> Pipeline:
    pipeline = _built(_graph(with_index=True), stack)
    assert pipeline.input_form is InputForm.SAMPLESHEET
    assert missing_examples(pipeline) == []
    return pipeline


@pytest.fixture(scope="module")
def untestable(stack) -> Pipeline:
    pipeline = _built(_graph(with_index=False), stack)
    assert pipeline.input_form is InputForm.SAMPLESHEET
    assert missing_examples(pipeline), "a prebuilt index was expected to lack test data"
    return pipeline


def _entries(pipeline: Pipeline) -> dict[str, bytes]:
    archive = bundle.archive(pipeline_file.dump(pipeline), pipeline, [])
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def test_a_runnable_pipeline_says_how_to_run_its_test(runnable):
    text = readme.render(runnable)
    assert RUN_TEST in text
    for step in runnable.steps:
        assert step.id in text


def test_without_example_data_it_names_what_is_missing(untestable):
    text = readme.render(untestable)
    assert "-profile test" not in text
    missing = missing_examples(untestable)
    assert missing
    for name in missing:
        assert name in text


def test_the_bundle_carries_its_test_samplesheet(runnable):
    entries = _entries(runnable)
    assert entries[TEST_SAMPLESHEET].decode() == samplesheet_of(runnable)
    assert RUN_TEST in entries["README.md"].decode()


def test_no_samplesheet_entry_without_a_test_profile(untestable):
    entries = _entries(untestable)
    assert TEST_SAMPLESHEET not in entries
    assert "README.md" in entries


def test_the_test_profile_names_the_samplesheet_the_bundle_carries(runnable):
    """The config and the zip agree on the file's name, or the test reads nothing."""
    entries = _entries(runnable)
    assert f"${{projectDir}}/{TEST_SAMPLESHEET}" in entries["nextflow.config"].decode()


def test_the_readme_is_the_same_bytes_every_time(runnable):
    assert readme.render(runnable) == readme.render(runnable)
