"""The pipeline's graph, and the run drawn onto it. §9.1."""

import json
from pathlib import Path

import dag_core
import pytest
from comeni_core import yaml_strict
from comeni_core.artifact.pipeline import Pipeline
from wiener_core.events import RunEvent
from wiener_core.graph import coloured, graph_of
from wiener_core.state import replay

SPINE = Path(__file__).parents[3] / "tests/fixtures/pipeline/rnaseq-spine.yml"
SPINE_RUN = Path(__file__).parents[3] / "tests/fixtures/weblog/spine-run.events.jsonl"
"""**A real run of this exact spine**, exported from Postgres on 2026-08-24 — seventeen events,
five processes, all green. The other two captures are a toy pipeline and a two-task failure;
neither shares a process name with the artifact, so neither can test a colouring.

These are ADMITTED events rather than raw weblog bodies, because that is what the record holds
and what `fold` consumes. `admit()` has its own fixtures."""


@pytest.fixture
def spine() -> Pipeline:
    return Pipeline.model_validate(yaml_strict.load(SPINE))


def _events() -> list[RunEvent]:
    return [RunEvent.model_validate(json.loads(line))
            for line in SPINE_RUN.read_text().splitlines() if line.strip()]


def test_the_artifact_lays_out_without_an_ir(spine):
    """§9.1.1: Wiener has a `Pipeline`, not a `PipelineIR`, and may not reach for the resolver
    that turns one into the other. The adapter is the whole reason `dag-core` takes a neutral
    graph rather than an IR."""
    laid = dag_core.of(graph_of(spine))
    assert len(laid.nodes) == len(spine.steps)
    assert laid.wires, "a five-step spine has wires"
    assert all(isinstance(node.x, int) and isinstance(node.y, int) for node in laid.nodes)


def test_a_producer_is_drawn_above_its_consumer(spine):
    """The one property that makes a pipeline graph readable, asserted here rather than assumed
    from the fact that `dag-core`'s own tests hold it for an IR."""
    laid = dag_core.of(graph_of(spine))
    rank = {node.id: node.rank for node in laid.nodes}
    assert rank["trimgalore"] < rank["star_align"] < rank["samtools_sort"]


def test_an_entry_channel_is_not_a_node(spine):
    """`params.input` is a value the laboratory fills, not a step that ran. A step fed only by
    one is a root, which is what it is on the builder's canvas too."""
    ids = {node.id for node in graph_of(spine).nodes}
    assert "fastq.reads" not in ids and "genome.fasta" not in ids
    assert "trimgalore" in ids


def test_the_colouring_says_what_the_run_did_and_nothing_else(spine):
    """A node's counts are its tasks' aggregate; `attempts` is the most any one needed. Neither
    is a duration and neither is a rate — §9.2."""
    laid = dag_core.of(graph_of(spine))
    run = coloured(spine, laid, replay(_events()))

    star = next(node for node in run.nodes if node.process == "STAR_ALIGN")
    assert (star.done, star.failed, star.running, star.total) == (1, 0, 0, 1)
    assert star.attempts == 1

    assert not any(hasattr(node, "duration") or hasattr(node, "rate") for node in run.nodes)


def test_a_step_that_never_ran_is_drawn_as_nothing_rather_than_omitted(spine):
    """A run that failed early still has a whole pipeline; the steps that never started are
    what tell you where it stopped."""
    empty = coloured(spine, dag_core.of(graph_of(spine)), replay([]))
    assert len(empty.nodes) == len(spine.steps)
    assert all(node.total == 0 for node in empty.nodes)
