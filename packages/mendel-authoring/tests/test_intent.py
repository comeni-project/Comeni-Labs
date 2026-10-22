"""A canvas edit read as a person's intent (A1, the one-builder design): one test per row of the
spec's table. The plan is the rnaseq example resolved over the shipped registry."""

import pytest
from comeni_core.goal.asked import Goal, ProducerExclusion, ProducerPin, RoleAbsence, SourcePin
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from mendel_authoring.intent import read_edit, read_graph
from mendel_resolver import layers
from mendel_resolver.resolve import resolve
from support.example import example_mapping
from support.paths import REGISTRY

STAR = "nf-core/star/align@1.11.0"
HISAT2 = "nf-core/hisat2/align@2.2.2"
FASTQC = "nf-core/fastqc@0.12.1"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
SORT = "nf-core/samtools/sort@1.21.0"


@pytest.fixture(scope="module")
def planned():
    stack = layers.load(REGISTRY)
    ir = resolve(Goal.model_validate(example_mapping()), stack.registry, stack.rules,
                 stack.measurements, vocabulary=stack.vocabulary)
    graph = DraftGraph(
        nodes=[DraftNode(id=n.id, contract_id=n.contract_id) for n in ir.nodes],
        edges=[DraftEdge(from_node=e.from_node, from_port=e.from_port, to_node=e.to_node,
                         to_port=e.to_port) for e in ir.edges],
    )
    return graph, {n.id: n.site for n in ir.nodes if n.site is not None}, stack.registry, ir


def _without(graph, node_id):
    return DraftGraph(
        nodes=[n for n in graph.nodes if n.id != node_id],
        edges=[e for e in graph.edges if node_id not in (e.from_node, e.to_node)],
    )


def _node(ir, node_id):
    return next(n for n in ir.nodes if n.id == node_id)


def test_removing_trimgalore_reads_as_trimming_switched_off(planned):
    graph, sites, registry, ir = planned
    [reading] = read_edit(graph, _without(graph, "trimgalore"), sites, registry)
    assert (reading.kind, reading.intent) == ("role_absent", RoleAbsence(role="trimming"))
    assert reading.said == "So you never want trimming here — right?"


def test_removing_star_reads_as_star_excluded_at_its_site(planned):
    graph, sites, registry, ir = planned
    [reading] = read_edit(graph, _without(graph, "star_align"), sites, registry)
    star = _node(ir, "star_align")
    assert (reading.kind, reading.intent) == (
        "exclude", ProducerExclusion(site=star.site, contract=STAR))
    assert "STAR_ALIGN" in reading.said


def test_removing_the_counts_step_reads_as_no_longer_wanting_counts(planned):
    graph, sites, registry, ir = planned
    [reading] = read_edit(graph, _without(graph, "subread_featurecounts"), sites, registry)
    assert (reading.kind, reading.intent) == ("unwant", "counts.matrix")


def test_adding_fastqc_reads_as_wanting_qc_from_fastqc(planned):
    graph, sites, registry, ir = planned
    after = graph.model_copy(update={"nodes": [*graph.nodes,
                                               DraftNode(id="fastqc", contract_id=FASTQC)]})
    readings = read_edit(graph, after, sites, registry)
    assert [(r.kind, r.intent) for r in readings] == [
        ("want", "qc.report"),
        ("pin", ProducerPin(site={"type_id": "qc.report"}, contract=FASTQC)),
    ]


def test_rewiring_a_port_reads_as_a_source_pin(planned):
    graph, sites, registry, ir = planned
    edges = [e for e in graph.edges
             if not (e.to_node == "subread_featurecounts" and e.to_port == "bam")]
    edges.append(DraftEdge(from_node="star_align", from_port="bam",
                           to_node="subread_featurecounts", to_port="bam"))
    [reading] = read_edit(graph, graph.model_copy(update={"edges": edges}), sites, registry)
    assert (reading.kind, reading.intent) == (
        "source", SourcePin(consumer=COUNTS, port="bam", producer=STAR))


def test_swapping_a_tool_reads_as_a_pin(planned):
    graph, sites, registry, ir = planned
    nodes = [n.model_copy(update={"contract_id": HISAT2}) if n.id == "star_align" else n
             for n in graph.nodes]
    [reading] = read_edit(graph, graph.model_copy(update={"nodes": nodes}), sites, registry)
    assert (reading.kind, reading.intent) == (
        "pin", ProducerPin(site=_node(ir, "star_align").site, contract=HISAT2))


def test_an_unchanged_graph_reads_as_nothing(planned):
    graph, sites, registry, ir = planned
    assert read_edit(graph, graph, sites, registry) == []


def test_swapping_the_tool_on_a_step_you_added_reads_as_a_pin_at_its_output(planned):
    """Self-review: a hand-added step has no site in the plan; its swap must not read as nothing."""
    graph, sites, registry, ir = planned
    added = graph.model_copy(update={"nodes": [*graph.nodes,
                                               DraftNode(id="qc", contract_id=FASTQC)]})
    swapped = added.model_copy(update={"nodes": [
        *graph.nodes, DraftNode(id="qc", contract_id="nf-core/multiqc@1.25.1")]})
    [reading] = read_edit(added, swapped, sites, registry)
    assert reading.kind == "pin"
    assert reading.intent.contract == "nf-core/multiqc@1.25.1"


def test_a_drawn_pipeline_reads_as_every_tool_pinned_and_its_ends_wanted(planned):
    graph, _, registry, _ = planned
    readings = read_graph(graph, registry)
    pinned = {r.intent.contract for r in readings if r.kind == "pin"}
    assert pinned == {n.contract_id for n in graph.nodes}
    assert [r.intent for r in readings if r.kind == "want"] == ["counts.matrix"]
    assert readings[0].said.startswith("So this is your pipeline")


def test_an_empty_drawing_reads_as_nothing(planned):
    assert read_graph(DraftGraph(), planned[2]) == []
