"""A `PipelineIR`, laid out. **The arithmetic lives in `dag-core` now** — 2026-08-24.

`docs/design/wiener.md` §9.1.1: the builder's canvas and Wiener's run graph are the same picture
from two sources, so the layout is a shared package and each half brings the adapter that knows
what its own artifact is. This is Mendel's adapter, and `of(ir, ports)` keeps its signature so
`mendel_api.services.build` — the one caller — does not change.

**What belongs here rather than there** is the question `_declared` answers: what a node's ports
*are*. The IR knows what a wire uses; only the caller knows what a contract declares, and the
difference is why a wire once landed 39 pixels from its chevron.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from comeni_core.plan.ir import PipelineIR
from dag_core import Edge, Graph, Node
from dag_core.layout import Layout, Placed, Point, Wire
from dag_core.layout import of as _lay_out

__all__ = ["Layout", "Placed", "Point", "Ports", "Wire", "of"]

Ports = Mapping[str, tuple[list[str], list[str]]]
"""A node id to its **declared** `(inputs, outputs)`, in the order the canvas draws them.

Stays on this side of the split: it describes a *pipeline's* ports, and `dag-core` lays out a
graph whose nodes already carry theirs.
"""


def _declared(
    ir: PipelineIR, ports: Ports | None
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Every node's input and output port names.

    **Given by the caller when it can be**, because the IR does not know what a contract
    declares — only what a wire happens to use. The fallback survives for callers with no
    registry to hand, the golden layout test among them, and it is correct whenever the graph is
    fully wired.
    """
    if ports is not None:
        return (
            {node: list(inputs) for node, (inputs, _) in ports.items()},
            {node: list(outputs) for node, (_, outputs) in ports.items()},
        )
    ins: dict[str, list[str]] = defaultdict(list)
    outs: dict[str, list[str]] = defaultdict(list)
    for edge in sorted(ir.edges, key=lambda e: (e.from_node, e.from_port, e.to_node, e.to_port)):
        if edge.from_port not in outs[edge.from_node]:
            outs[edge.from_node].append(edge.from_port)
        if edge.to_port not in ins[edge.to_node]:
            ins[edge.to_node].append(edge.to_port)
    return ins, outs


def graph_of(ir: PipelineIR, ports: Ports | None = None) -> Graph:
    """The IR as a neutral graph: ids, ports and edges, plus the tier as the node's stripe."""
    ins, outs = _declared(ir, ports)
    return Graph(
        nodes=tuple(
            Node(
                id=node.id,
                inputs=tuple(ins.get(node.id, [])),
                outputs=tuple(outs.get(node.id, [])),
                tier=int(node.selection.tier),
            )
            for node in ir.nodes
        ),
        edges=tuple(
            Edge(
                from_node=edge.from_node,
                from_port=edge.from_port,
                to_node=edge.to_node,
                to_port=edge.to_port,
                type_id=edge.type_id,
            )
            for edge in ir.edges
        ),
    )


def of(ir: PipelineIR, ports: Ports | None = None) -> Layout:
    """Lay out an IR. Pure, integer coordinates, stable under repetition."""
    return _lay_out(graph_of(ir, ports))
