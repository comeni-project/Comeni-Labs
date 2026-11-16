"""Compute deterministic positions and orthogonal wires for a directed graph.

The graph adapter owns domain-specific choices such as node identity, port order, and tier.
This module ranks, orders, places, and routes those neutral values using integer coordinates.
Geometry constants are duplicated in ``frontend/src/build/geometry.ts`` and guarded by the
package tests.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace

from dag_core.graph import Graph

NODE_W = 172
NODE_H = 136
"""Node width, and the height of a node with one or two ports a side, shared with the browser."""

RANK_PITCH = 224
"""Distance between ranks along the left-to-right flow."""

SIBLING_PITCH = 194
"""Minimum distance between nodes that share a rank."""

HEAD_H = 44
"""Height of the node header in the browser canvas: what the step does, then its tool."""

PORT_ROW = 19
"""Height of a port row in the browser canvas."""

SPINE = NODE_H // 2
"""Primary port anchor, derived from the node height."""

SECOND = SPINE + 22
"""Secondary port anchor, exported for the browser geometry guard."""

CORNER = 7
"""Corner radius used by the browser when rendering routed wires."""

ROW_FIRST = SPINE + 11 + 22
"""A one-port node's content height: the spine row's lower half and the footer below it."""

SIBLING_GAP = SIBLING_PITCH - NODE_H
"""The space left between a tall node and the next one in its rank."""


def node_height(ports: int) -> int:
    """A node's height for its larger side's port count (#494): tall enough that every port's
    row, anchored at `SPINE + index * PORT_GAP`, sits inside it above the footer. Anchors never
    move with the height, so a wire already drawn stays where it is."""
    return max(NODE_H, ROW_FIRST + PORT_GAP * (max(ports, 1) - 1))


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Placed:
    id: str
    rank: int
    """Depth in the left-to-right flow."""
    order: int
    """Relative position among nodes in the same rank."""
    x: int
    y: int
    width: int
    height: int
    tier: int
    """Renderer metadata copied from the input node."""


@dataclass(frozen=True)
class Wire:
    from_node: str
    from_port: str
    to_node: str
    to_port: str
    type_id: str
    points: tuple[Point, ...]
    """Points of an orthogonal path from source to target."""
    label_at: Point
    """Suggested position for the edge label."""


@dataclass(frozen=True)
class Layout:
    nodes: tuple[Placed, ...] = field(default_factory=tuple)
    wires: tuple[Wire, ...] = field(default_factory=tuple)

    @property
    def width(self) -> int:
        return max((node.x + node.width for node in self.nodes), default=0)

    @property
    def height(self) -> int:
        return max((node.y + node.height for node in self.nodes), default=0)


def _ranks(graph: Graph) -> dict[str, int]:
    """Return each node's longest-path depth from a root.

    Longest-path ranking places a consumer after every producer. Callers must reject cycles;
    the bounded relaxation here is layout arithmetic, not graph validation.
    """
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        incoming[edge.to_node].append(edge.from_node)

    rank = {node.id: 0 for node in graph.nodes}
    for _ in range(len(graph.nodes)):
        moved = False
        for node in graph.nodes:
            want = max((rank[p] + 1 for p in incoming[node.id]), default=0)
            if want > rank[node.id]:
                rank[node.id], moved = want, True
        if not moved:
            break
    return rank


def _order(
    graph: Graph, rank: dict[str, int], ins: dict[str, list[str]] | None = None
) -> dict[str, int]:
    """Return deterministic positions within each rank using a median heuristic.

    Downward passes align consumers with their producers. Upward passes align producers with
    the ordered ports they feed, reducing crossings at fan-in nodes. This is not a general
    crossing-minimization algorithm. Node identifiers break ties to keep results stable.
    """
    by_rank: dict[int, list[str]] = defaultdict(list)
    for node in graph.nodes:
        by_rank[rank[node.id]].append(node.id)
    for ids in by_rank.values():
        ids.sort()

    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in graph.edges:
        incoming[edge.to_node].append(edge.from_node)
        outgoing[edge.from_node].append((edge.to_node, edge.to_port))

    def port_slot(consumer: str, port: str) -> float:
        """Return a port's fractional position, or the midpoint for an unknown port."""
        names = (ins or {}).get(consumer)
        if not names or port not in names:
            return 0.5
        return (names.index(port) + 1) / (len(names) + 1)

    position = {nid: i for ids in by_rank.values() for i, nid in enumerate(ids)}
    depths = sorted(by_rank)
    for _ in range(2):
        # Align each node with the positions of its producers.
        for depth in depths[1:]:

            def median(nid: str) -> tuple[float, str]:
                feeders = sorted(position[p] for p in incoming[nid])
                return ((feeders[len(feeders) // 2] if feeders else 0.0), nid)

            by_rank[depth].sort(key=median)
            for i, nid in enumerate(by_rank[depth]):
                position[nid] = i

        # Align each producer with the ordered consumer ports it feeds.
        for depth in reversed(depths[:-1]):

            def by_port(nid: str) -> tuple[float, str]:
                targets = sorted(
                    position[consumer] + port_slot(consumer, port)
                    for consumer, port in outgoing[nid]
                )
                return ((targets[len(targets) // 2] if targets else 0.0), nid)

            by_rank[depth].sort(key=by_port)
            for i, nid in enumerate(by_rank[depth]):
                position[nid] = i
    return position


def _across(graph: Graph, rank: dict[str, int], order: dict[str, int]) -> dict[str, int]:
    """Return positions across the flow while preserving the chosen order.

    Each non-root node prefers the median centre of its producers. Nodes are then packed at
    ``SIBLING_PITCH`` so siblings do not overlap. The final coordinates are normalized to start
    at zero.
    """
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        incoming[edge.to_node].append(edge.from_node)

    tall = {node.id: node_height(max(len(node.inputs), len(node.outputs)))
            for node in graph.nodes}
    by_rank: dict[int, list[str]] = defaultdict(list)
    for node in graph.nodes:
        by_rank[rank[node.id]].append(node.id)
    for ids in by_rank.values():
        ids.sort(key=lambda nid: (order[nid], nid))

    x: dict[str, int] = {}
    for depth in sorted(by_rank):
        ids = by_rank[depth]
        if depth == 0:
            edge_x = 0
            for nid in ids:
                x[nid] = edge_x
                edge_x += max(SIBLING_PITCH, tall[nid] + SIBLING_GAP)
            continue
        wanted = []
        for nid in ids:
            centres = sorted(x[p] + NODE_H // 2 for p in incoming[nid] if p in x)
            # Average the middle pair so a node with two producers is centred between them.
            if not centres:
                middle = NODE_H // 2
            else:
                half = len(centres) // 2
                middle = (
                    centres[half]
                    if len(centres) % 2
                    else (centres[half - 1] + centres[half]) // 2
                )
            wanted.append((middle - NODE_H // 2, nid))
        # Preserve the chosen order while preventing sibling overlap: a tall node (#494) keeps
        # the same gap below it as a short one.
        edge_x = None
        for want, nid in wanted:
            x[nid] = want if edge_x is None else max(want, edge_x)
            edge_x = x[nid] + max(SIBLING_PITCH, tall[nid] + SIBLING_GAP)

    # Avoid leading empty space when centring a wider rank produces negative coordinates.
    shift = min(x.values(), default=0)
    return {nid: value - shift for nid, value in x.items()}


def _ports_of(graph: Graph) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Return each node's ports in the display order supplied by its adapter.

    An adapter with contract information should supply declared ports. An adapter that only has
    graph wiring may supply wired ports when the graph is fully wired.
    """
    return (
        {node.id: list(node.inputs) for node in graph.nodes},
        {node.id: list(node.outputs) for node in graph.nodes},
    )


def _anchor(ports: list[str], name: str) -> int:
    """Return a port anchor in node coordinates, falling back to the spine if unknown."""
    if name not in ports:
        return SPINE
    return _port_offset(ports.index(name))


PORT_GAP = 22
"""Distance between adjacent port anchors."""


def _port_offset(index: int) -> int:
    """Return a stable anchor offset for a port index.

    The first port sits on the spine and later ports use a fixed gap, so adding a port does not
    move existing anchors.
    """
    return SPINE + index * PORT_GAP


HANG_GAP = 48
"""Between a step and the measuring step hung under it."""

HANG_REACH = 14
"""How far a hung step's wire runs out before it turns down, and in before its port."""


def _hang(graph: Graph, placed: tuple[Placed, ...]) -> tuple[Placed, ...]:
    """Move each measuring step under the one step it reads, in that step's column, and push
    down whatever shared the column below it (#517)."""
    by_id = {node.id: node for node in placed}
    for node in sorted((n for n in graph.nodes if n.hangs), key=lambda n: n.id):
        sources = sorted({e.from_node for e in graph.edges if e.to_node == node.id})
        if len(sources) != 1 or sources[0] not in by_id:
            continue
        above = by_id[sources[0]]
        hung = replace(by_id[node.id], rank=above.rank, x=above.x,
                       y=above.y + above.height + HANG_GAP)
        by_id[node.id] = hung
        bottom = hung.y + hung.height + SIBLING_GAP
        for other in sorted((n for n in by_id.values() if n.x == hung.x and n.id != hung.id
                             and n.y >= above.y + above.height), key=lambda n: n.y):
            if other.y < bottom:
                by_id[other.id] = replace(other, y=bottom)
            bottom = by_id[other.id].y + by_id[other.id].height + SIBLING_GAP
    return tuple(by_id[n.id] for n in placed)


def of(graph: Graph = None) -> Layout:
    """Lay out an acyclic graph with deterministic integer coordinates."""
    ins, outs = _ports_of(graph)
    rank = _ranks(graph)
    order = _order(graph, rank, ins)
    across = _across(graph, rank, order)

    # Ranks flow left to right; all nodes use the shared fixed dimensions.
    placed = tuple(
        Placed(
            id=node.id,
            rank=rank[node.id],
            order=order[node.id],
            x=rank[node.id] * RANK_PITCH,
            y=across[node.id],
            width=NODE_W,
            height=node_height(max(len(node.inputs), len(node.outputs))),
            tier=node.tier,
        )
        # Keep tuple order stable as well as coordinates.
        for node in sorted(graph.nodes, key=lambda n: (rank[n.id], order[n.id], n.id))
    )
    placed = _hang(graph, placed)
    by_id = {node.id: node for node in placed}

    wires = []
    for edge in sorted(graph.edges, key=lambda e: (e.from_node, e.from_port, e.to_node, e.to_port)):
        source, target = by_id[edge.from_node], by_id[edge.to_node]
        # Port order comes from the adapter. Unknown names fall back to the spine because graph
        # validation belongs to the caller.
        source_ports = outs.get(edge.from_node, [])
        target_ports = ins.get(edge.to_node, [])
        # Wires leave the right edge and enter the left edge of the next rank.
        start = Point(
            source.x + source.width,
            source.y + _anchor(source_ports, edge.from_port),
        )
        end = Point(
            target.x,
            target.y + _anchor(target_ports, edge.to_port),
        )
        # Route orthogonally through the midpoint between ranks.
        mid = (start.x + end.x) // 2
        # Omit duplicate corners from a straight run so the renderer has no zero-length segment.
        points = (
            (start, end)
            if start.y == end.y
            else (start, Point(mid, start.y), Point(mid, end.y), end)
        )
        if end.x <= start.x:
            # A step hung under the one it reads: out to the right, down past its source, back
            # along the gap between them, and into its port from the left.
            below = (source.y + source.height + target.y) // 2
            out, back = start.x + HANG_REACH, end.x - HANG_REACH
            points = (start, Point(out, start.y), Point(out, below),
                      Point(back, below), Point(back, end.y), end)
            mid = start.x + HANG_REACH
        wires.append(
            Wire(
                from_node=edge.from_node,
                from_port=edge.from_port,
                to_node=edge.to_node,
                to_port=edge.to_port,
                type_id=edge.type_id,
                points=points,
                label_at=Point(mid, (start.y + end.y) // 2 - 6),
            )
        )

    return Layout(nodes=placed, wires=tuple(wires))
