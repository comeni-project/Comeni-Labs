"""A hand-drawn graph states four names per edge and derives nothing.

`IREdge` carries `type_id` and `states` because the resolver *computed* them from the source
port. A person drawing a wire has not computed anything, and a draft that carried those fields
could disagree with the contract it points at — a lie the validator would then have to catch.
Four names is the whole of what a drawn wire knows.
"""

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from comeni_core.review.verdict import Finding, Level, Verdict


def test_review_does_not_import_plan():
    """A146. `plan/` imports `review/`; the reverse edge is a cycle, and `plan/tiers.py` says so.
    A guard here rather than a convention, because the tempting field is `Finding.target`."""
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
    node = DraftNode(id="align", contract_id="nf-core/star/align@1.11.0")
    assert node.params == []


def test_a_graph_holds_nodes_and_edges():
    graph = DraftGraph(
        nodes=[DraftNode(id="a", contract_id="nf-core/star/align@1.11.0")],
        edges=[],
    )
    assert graph.nodes[0].id == "a"


def test_a_verdict_is_illegal_when_any_finding_is():
    ok = Verdict(findings=[Finding(code="MD0507", level=Level.ADVISORY, message="unconventional")])
    assert ok.illegal == []
    assert ok.emittable is True

    bad = Verdict(findings=[Finding(code="MD0503", level=Level.ILLEGAL, message="state missing")])
    assert [f.code for f in bad.illegal] == ["MD0503"]
    assert bad.emittable is False


def test_a_finding_names_each_end_of_a_wire_separately():
    """A157. An `EdgeRef` is `<node>.<port>` — one endpoint. A wire is two of them."""
    finding = Finding(
        code="MD0504", level=Level.ILLEGAL, message="m", source="align.bam", target="counts.bam"
    )
    assert finding.source == "align.bam"
    with pytest.raises(ValidationError):
        Finding(code="MD0504", level=Level.ILLEGAL, message="m", source="align:bam->counts:bam")


def test_a_finding_must_cite_a_declared_code():
    with pytest.raises(ValidationError, match="not a declared diagnostic"):
        Finding(code="MD9999", level=Level.ILLEGAL, message="nope")
