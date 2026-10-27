"""Draft graphs contain user-authored structure but no resolver-derived facts."""

import ast
from pathlib import Path

import pytest
from comeni_core.plan.draft import (
    ChannelSettled,
    DraftEdge,
    DraftGraph,
    DraftNode,
    DraftProvenance,
    NodeSettled,
    ParamSettled,
    Settled,
)
from comeni_core.plan.tiers import Tier, ValueSource
from comeni_core.review.verdict import Finding, Level, Verdict
from pydantic import ValidationError


def test_review_does_not_import_plan():
    """Review remains below plan in the dependency graph."""
    root = Path(__file__).resolve().parents[1] / "src" / "comeni_core" / "review"
    for module in root.rglob("*.py"):
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "comeni_core.plan"
            ):
                raise AssertionError(f"{module.name} imports {node.module}")


def test_a_drawn_edge_is_four_names():
    edge = DraftEdge(from_node="align", from_port="bam", to_node="sort", to_port="bam")
    assert edge.from_port == "bam"
    with pytest.raises(ValidationError):
        DraftEdge(  # type: ignore[call-arg]
            from_node="align",
            from_port="bam",
            to_node="sort",
            to_port="bam",
            type_id="alignment.bam",
        )


def test_a_draft_node_needs_only_an_id_and_a_contract():
    node = DraftNode(id="align", contract_id="nf-core/star/align@2.7.11b")
    assert node.params == []


def test_a_graph_holds_nodes_and_edges():
    graph = DraftGraph(
        nodes=[DraftNode(id="a", contract_id="nf-core/star/align@2.7.11b")],
        edges=[],
    )
    assert graph.nodes[0].id == "a"


def test_provenance_retains_only_subjects_still_in_the_graph():
    settled = Settled(source=ValueSource.HUMAN, tier=Tier.AMBIGUOUS)
    provenance = DraftProvenance(
        nodes=[NodeSettled(node="keep"), NodeSettled(node="drop")],
        params=[
            ParamSettled(key="keep.value", settled=settled),
            ParamSettled(key="drop.value", settled=settled),
        ],
        channels=[
            ChannelSettled(ports=("keep.input",), settled=settled),
            ChannelSettled(ports=("drop.input",), settled=settled),
        ],
    )

    retained = provenance.retaining(
        nodes={"keep"}, params={"keep.value"}, channels={("keep.input",)}
    )

    assert [entry.node for entry in retained.nodes] == ["keep"]
    assert [entry.key for entry in retained.params] == ["keep.value"]
    assert [entry.ports for entry in retained.channels] == [("keep.input",)]


def test_a_verdict_is_illegal_when_any_finding_is():
    ok = Verdict(findings=[Finding(code="MD0507", level=Level.ADVISORY, message="unconventional")])
    assert ok.illegal == []
    assert ok.emittable is True

    bad = Verdict(findings=[Finding(code="MD0503", level=Level.ILLEGAL, message="state missing")])
    assert [f.code for f in bad.illegal] == ["MD0503"]
    assert bad.emittable is False


def test_a_finding_names_each_end_of_a_wire_separately():
    """A finding records each `<node>.<port>` endpoint independently."""
    finding = Finding(
        code="MD0504", level=Level.ILLEGAL, message="m", source="align.bam", target="counts.bam"
    )
    assert finding.source == "align.bam"
    with pytest.raises(ValidationError):
        Finding(code="MD0504", level=Level.ILLEGAL, message="m", source="align:bam->counts:bam")


def test_a_finding_must_cite_a_declared_code():
    with pytest.raises(ValidationError, match="not a declared diagnostic"):
        Finding(code="MD9999", level=Level.ILLEGAL, message="nope")
