"""Wiring an aligner straight into featureCounts is the canonical hand-drawn mistake.

It is invisible in `meta.yml` — nf-core declares both ports as `type: file, *.bam` and the word
"sorted" lives only in the English description — so it is exactly the error a semantic state
overlay exists to make checkable.

`stack` comes from the conftest.
"""

from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from mendel_resolver.validate import validate

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"


def _graph(nodes, edges):
    return DraftGraph(
        nodes=[DraftNode(id=i, contract_id=c) for i, c in nodes],
        edges=[DraftEdge(from_node=a, from_port=b, to_node=c, to_port=d) for a, b, c, d in edges],
    )


def test_an_unsorted_bam_into_featurecounts_is_illegal(stack):
    graph = _graph(
        [("align", STAR), ("counts", COUNTS)],
        [("align", "bam", "counts", "bam")],
    )
    verdict = validate(graph, stack)
    codes = {f.code for f in verdict.illegal}
    assert "MD0504" in codes, verdict.findings
    assert "coordinate_sorted" in next(f for f in verdict.illegal if f.code == "MD0504").message


def test_the_same_bam_through_a_sorter_is_legal(stack):
    graph = _graph(
        [("align", STAR), ("sort", SORT), ("counts", COUNTS)],
        [("align", "bam", "sort", "bam"), ("sort", "bam", "counts", "bam")],
    )
    verdict = validate(graph, stack)
    assert [f for f in verdict.illegal if f.code in {"MD0503", "MD0504"}] == []


def test_a_port_that_does_not_exist(stack):
    graph = _graph(
        [("align", STAR), ("sort", SORT)],
        [("align", "bamm", "sort", "bam")],
    )
    verdict = validate(graph, stack)
    assert [f.code for f in verdict.illegal if f.code == "MD0501"] == ["MD0501"]


def test_a_wire_running_backwards(stack):
    """`sort.bam` is BOTH an input and an output port name on samtools/sort, which is why this
    check reads the direction rather than the name."""
    graph = _graph(
        [("align", STAR), ("sort", SORT)],
        [("sort", "bam", "align", "bam")],
    )
    verdict = validate(graph, stack)
    assert "MD0502" in {f.code for f in verdict.illegal}


def test_a_wrong_type_is_MD0503_not_MD0504(stack):
    """Type identity and state are different failures and must not collapse into one code —
    "wire a sorter in" is the fix for one of them and useless for the other."""
    graph = _graph(
        [("counts", COUNTS), ("sort", SORT)],
        [("counts", "counts", "sort", "bam")],
    )
    verdict = validate(graph, stack)
    assert "MD0503" in {f.code for f in verdict.illegal}
    assert "MD0504" not in {f.code for f in verdict.illegal}


def test_every_finding_carries_the_edge_it_is_about(stack):
    """A verdict a canvas can draw. A finding with no anchor is a sentence in a log."""
    graph = _graph(
        [("align", STAR), ("counts", COUNTS)],
        [("align", "bam", "counts", "bam")],
    )
    for finding in validate(graph, stack).findings:
        assert finding.target is not None or finding.node is not None


def test_a_node_naming_an_unknown_contract_is_reported_once(stack):
    """Once per node, not once per edge. A renamed contract with four wires on it would
    otherwise print the same failure four times and bury it."""
    graph = _graph(
        [("gone", "nf-core/nothing/here@1.0.0"), ("sort", SORT)],
        [("gone", "bam", "sort", "bam")],
    )
    codes = [f.code for f in validate(graph, stack).findings]
    assert codes.count("MD0509") == 1


def test_it_reports_every_problem_rather_than_the_first(stack):
    """The forge's `verify` ladder is the precedent. Three problems in one pass."""
    graph = _graph(
        [("align", STAR), ("counts", COUNTS), ("sort", SORT)],
        [("align", "bam", "counts", "bam"), ("align", "nope", "sort", "bam")],
    )
    codes = {f.code for f in validate(graph, stack).findings}
    assert {"MD0501", "MD0504"} <= codes
