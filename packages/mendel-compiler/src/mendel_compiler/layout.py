"""Where the boxes go, and how the wires get between them.

**In Python rather than in the browser, and that is a decision rather than a convenience.** Same
IR → same coordinates, held by a test, exactly as `.nf` is. A layout library in the page — dagre,
elkjs — would put the position of every node outside the guarantee the rest of this system keeps,
and the canvas is the thing a person screenshots and puts in a paper.

**The graph flows downward.** Read off `docs/design/dashboard.html` rather than assumed: its
`elbow()` routes vertical → horizontal at the midpoint → vertical, and its two hand-placed nodes
share `top:6` at different `left`. A first pass at this planned it left-to-right, and every
structural assertion would have passed on the sideways graph — the design is the only thing that
says which way is down.

**The geometry is the design's, to the pixel.** `NW = 232` and the two sample nodes at
`left:14` and `left:352` give a column pitch of 338. `CR = 7`. `portX(count, i) =
NW * (i + 1) / (count + 1)`. Those are not defaults chosen here; changing one means changing
`dashboard.html` too, or the two stop being the same screen.

`dashboard.md` §9 calls automatic layout "the largest outstanding piece". It is the only part of
3C that is an algorithm rather than a rendering, which is why it comes before any interface.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from comeni_core.plan.ir import PipelineIR

NODE_W = 232
"""`NW` in `dashboard.html`. The node is a fixed width so a rank is a predictable pitch."""

COL_PITCH = 338
"""14 → 352 between the design's two hand-placed nodes. `COL_PITCH - NODE_W` is the gutter."""

HEAD_H = 34
PORT_ROW = 22
MIN_H = 56
RANK_GAP = 72
"""Vertical room for the elbow's horizontal run to sit clear of both nodes."""

CORNER = 7
"""`CR`. Rounded so the graph reads as drawn rather than as a schematic — `dashboard.md` §4."""


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Placed:
    id: str
    rank: int
    """Depth. **Down the page**, not across it."""
    order: int
    """Position within the rank, left to right."""
    x: int
    y: int
    width: int
    height: int
    tier: int
    """What tier this module was chosen at, so the node can carry its stripe without the
    frontend joining back to the decisions."""


@dataclass(frozen=True)
class Wire:
    from_node: str
    from_port: str
    to_node: str
    to_port: str
    type_id: str
    points: tuple[Point, ...]
    """Corner points of an orthogonal path, start to end. **Not an SVG string** — the renderer
    decides how to round the corners, and a `d` attribute computed here would put presentation
    in the compiler."""
    label_at: Point
    """Centred on the horizontal run, which is the only stretch with room for it."""


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


def _ranks(ir: PipelineIR) -> dict[str, int]:
    """Longest path from a root. **Longest, not shortest**: a node must sit below *every*
    producer it has, and shortest-path would draw `star_align` level with the sorter that feeds
    the counter.

    Iterative relaxation rather than recursion — an IR is small and a cycle would recurse
    forever, whereas this simply stops moving. Routing already forbids cycles
    (`producers_of` excludes the node itself), so this is a floor rather than a check.
    """
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in ir.edges:
        incoming[edge.to_node].append(edge.from_node)

    rank = {node.id: 0 for node in ir.nodes}
    for _ in range(len(ir.nodes)):
        moved = False
        for node in ir.nodes:
            want = max((rank[p] + 1 for p in incoming[node.id]), default=0)
            if want > rank[node.id]:
                rank[node.id], moved = want, True
        if not moved:
            break
    return rank


def _order(ir: PipelineIR, rank: dict[str, int]) -> dict[str, int]:
    """Position within a rank, by the median of what feeds each node.

    **Two passes of the median heuristic, and saying so is the point.** It is enough for a
    pipeline — the spine is a chain with one convergence — and it is not a crossing-minimisation
    algorithm. If a graph ever arrives where it is visibly wrong, the honest fix is a real
    ordering pass, not more passes of this one.

    Ties break on node id so the result is total: two nodes with the same median must still land
    in the same order on every machine, which is what makes the golden comparison possible.
    """
    by_rank: dict[int, list[str]] = defaultdict(list)
    for node in ir.nodes:
        by_rank[rank[node.id]].append(node.id)
    for ids in by_rank.values():
        ids.sort()

    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in ir.edges:
        incoming[edge.to_node].append(edge.from_node)

    position = {nid: i for ids in by_rank.values() for i, nid in enumerate(ids)}
    for _ in range(2):
        for depth in sorted(by_rank)[1:]:
            def median(nid: str) -> tuple[float, str]:
                feeders = sorted(position[p] for p in incoming[nid])
                return ((feeders[len(feeders) // 2] if feeders else 0.0), nid)

            by_rank[depth].sort(key=median)
            for i, nid in enumerate(by_rank[depth]):
                position[nid] = i
    return position


def _x_of(ir: PipelineIR, rank: dict[str, int], order: dict[str, int]) -> dict[str, int]:
    """Horizontal placement: **centre a node under what feeds it.**

    Ordering alone is not placement, and the difference is visible rather than theoretical. With
    `x = order * COL_PITCH`, `star_align` — the one node both roots converge on — landed at x=0
    while its feeders sat at 0 and 338, so the whole spine hung off the left edge and one wire
    travelled the full width to reach it. Every structural assertion passed on that graph. Reading
    the golden file is what found it.

    A node's wanted x is the **median** of its feeders' centres; ties and collisions are then
    packed left to right at `COL_PITCH`, which keeps the ordering the crossing pass chose while
    letting a rank sit where its parents are. Sugiyama's fourth step, in the smallest form that
    is honest for a pipeline.
    """
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in ir.edges:
        incoming[edge.to_node].append(edge.from_node)

    by_rank: dict[int, list[str]] = defaultdict(list)
    for node in ir.nodes:
        by_rank[rank[node.id]].append(node.id)
    for ids in by_rank.values():
        ids.sort(key=lambda nid: (order[nid], nid))

    x: dict[str, int] = {}
    for depth in sorted(by_rank):
        ids = by_rank[depth]
        if depth == 0:
            for i, nid in enumerate(ids):
                x[nid] = i * COL_PITCH
            continue
        wanted = []
        for nid in ids:
            centres = sorted(x[p] + NODE_W // 2 for p in incoming[nid] if p in x)
            # **The mean of the middle two when the count is even**, not the upper one. With two
            # feeders a bare median picks one of them and the node hangs under it: `star_align`
            # sat directly below `trimgalore` while `star_genomegenerate`'s wire crossed the full
            # width to reach it. Averaging puts it between them and halves both runs. For odd
            # counts this is the plain median, which is what the heuristic is.
            if not centres:
                middle = NODE_W // 2
            else:
                half = len(centres) // 2
                middle = (
                    centres[half]
                    if len(centres) % 2
                    else (centres[half - 1] + centres[half]) // 2
                )
            wanted.append((middle - NODE_W // 2, nid))
        # Pack in the order the crossing pass chose, never below the previous node's right edge.
        edge_x = None
        for want, nid in wanted:
            x[nid] = want if edge_x is None else max(want, edge_x)
            edge_x = x[nid] + COL_PITCH

    # Normalise so the leftmost node sits at 0 — a canvas should not open on empty space, and a
    # median can go negative when a rank is wider than the one that feeds it.
    shift = min(x.values(), default=0)
    return {nid: value - shift for nid, value in x.items()}


def _height(ir: PipelineIR, node_id: str) -> int:
    """Tall enough for its ports, so a rank of wide-fanned nodes cannot overlap the next."""
    ins = sum(1 for e in ir.edges if e.to_node == node_id)
    outs = sum(1 for e in ir.edges if e.from_node == node_id)
    return max(MIN_H, HEAD_H + max(ins, outs, 1) * PORT_ROW)


def _port_x(count: int, index: int) -> int:
    """`portX` in `dashboard.html`: ports spread evenly across the node's edge."""
    return round(NODE_W * (index + 1) / (count + 1))


def of(ir: PipelineIR) -> Layout:
    """Lay out an IR. Pure, integer coordinates, stable under repetition."""
    rank = _ranks(ir)
    order = _order(ir, rank)
    across = _x_of(ir, rank, order)

    heights = {node.id: _height(ir, node.id) for node in ir.nodes}
    tall: dict[int, int] = defaultdict(int)
    for node in ir.nodes:
        tall[rank[node.id]] = max(tall[rank[node.id]], heights[node.id])

    top: dict[int, int] = {}
    y = 0
    for depth in sorted(tall):
        top[depth] = y
        y += tall[depth] + RANK_GAP

    placed = tuple(
        Placed(
            id=node.id,
            rank=rank[node.id],
            order=order[node.id],
            x=across[node.id],
            y=top[rank[node.id]],
            width=NODE_W,
            height=heights[node.id],
            tier=int(node.selection.tier),
        )
        # Sorted so the tuple itself is stable, not merely its contents.
        for node in sorted(ir.nodes, key=lambda n: (rank[n.id], order[n.id], n.id))
    )
    by_id = {node.id: node for node in placed}

    # Which port is which, so an anchor lands where the design puts it rather than in the middle.
    outs: dict[str, list[str]] = defaultdict(list)
    ins: dict[str, list[str]] = defaultdict(list)
    for edge in sorted(ir.edges, key=lambda e: (e.from_node, e.from_port, e.to_node, e.to_port)):
        if edge.from_port not in outs[edge.from_node]:
            outs[edge.from_node].append(edge.from_port)
        if edge.to_port not in ins[edge.to_node]:
            ins[edge.to_node].append(edge.to_port)

    wires = []
    for edge in sorted(ir.edges, key=lambda e: (e.from_node, e.from_port, e.to_node, e.to_port)):
        source, target = by_id[edge.from_node], by_id[edge.to_node]
        start = Point(
            source.x
            + _port_x(len(outs[edge.from_node]), outs[edge.from_node].index(edge.from_port)),
            source.y + source.height,
        )
        end = Point(
            target.x + _port_x(len(ins[edge.to_node]), ins[edge.to_node].index(edge.to_port)),
            target.y,
        )
        # Vertical, across at the midpoint, vertical — `elbow()` in the design, and orthogonal
        # because two curves meeting at a shallow angle are indistinguishable at the crossing.
        mid = (start.y + end.y) // 2
        # **A straight drop is two points, not four.** When the ports line up the two elbow
        # corners are the same coordinate, and emitting them anyway gives the renderer a
        # zero-length segment to round — which is how a 7px corner becomes a visible nick on a
        # wire that should be plumb.
        points = (
            (start, end)
            if start.x == end.x
            else (start, Point(start.x, mid), Point(end.x, mid), end)
        )
        wires.append(
            Wire(
                from_node=edge.from_node,
                from_port=edge.from_port,
                to_node=edge.to_node,
                to_port=edge.to_port,
                type_id=edge.type_id,
                points=points,
                label_at=Point((start.x + end.x) // 2, mid - 6),
            )
        )

    return Layout(nodes=placed, wires=tuple(wires))
