"""Where to draw a directed graph. Moved from `mendel_compiler.layout` on 2026-08-24.

**The arithmetic is unchanged**, and that is the point: `docs/design/wiener.md` §9.1.1 chose an
extraction over two implementations, and a move that changes no behaviour is provable — the
thirteen tests in `packages/mendel-compiler/tests/test_layout.py` are what prove it.

What did change is the input. This took a `PipelineIR`; it now takes a `Graph`, because Wiener
has a `Pipeline` and may not reach for the resolver that turns one into the other (§3.3). The
`ports` parameter went with it: a node carries its own, so *which* ports — declared or wired —
is the adapter's question rather than the layout's.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from dag_core.graph import Graph

NODE_W = 172
NODE_H = 112
"""**One symbol, and its size is load-bearing** — `impl-geom` on the redesign canvas.

`BuilderCanvas.dc.html` declares `.node { width:172px; height:112px }` for every process, and
the reason is not tidiness: variable heights put a jog between every pair of nodes and the main
chain stops reading as a chain. The height used to be derived from the port count, which meant
a node's size advertised how many ports its CONTRACT declares — a fact nobody is reading the
canvas to learn.
"""

RANK_PITCH = 224
"""Between one rank and the next, along the flow. `194 → 418 → 642 → 866` in the artboard, so
the gutter either side of a 172-wide symbol is 52."""

SIBLING_PITCH = 170
"""Between two nodes sharing a rank, across the flow. `top:150` and `top:320` in the artboard."""

HEAD_H = 28
"""`.node .hd { height:28px }` — the header the `⋯` and the name sit in."""

PORT_ROW = 19
"""`.node .pr { height:19px }`. It no longer sizes the node; it spaces the rows inside one."""

SPINE = NODE_H // 2
"""**Every symbol connects here** — `impl-geom`, and it is the one derivation.

> Port positions are DERIVED from node geometry in one place. Never write a coordinate twice.

That rule was written after the 2026-08-29 walk found every wire sitting 6px above its port and
every source wire starting 27px short of the box it left, because the endpoints had been typed
separately from the node positions.
"""

SECOND = SPINE + 22
"""A secondary input sits 22px below the spine. `impl-geom` again, and the same rule: derived."""

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


def _ranks(graph: Graph) -> dict[str, int]:
    """Longest path from a root. **Longest, not shortest**: a node must sit below *every*
    producer it has, and shortest-path would draw `star_align` level with the sorter that feeds
    the counter.

    Iterative relaxation rather than recursion — an IR is small and a cycle would recurse
    forever, whereas this simply stops moving. Routing already forbids cycles
    (`producers_of` excludes the node itself), so this is a floor rather than a check.
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
    """Position within a rank: the median of what feeds each node, **and of the ports it feeds.**

    **The upward pass is new, and it is the fix the old docstring asked for.** That docstring
    said this was two passes of a median heuristic, was not a crossing-minimisation algorithm,
    and that *"if a graph ever arrives where it is visibly wrong, the honest fix is a real
    ordering pass"*. The shipped spine is that graph:

    `star_align` declares `reads`, `index`, `gtf`, so its chevrons sit left to right in that
    order. Both its producers are roots, nothing feeds them, so the downward pass had no opinion
    and they sorted by id — `star_genomegenerate` before `trimgalore`. Genomegenerate feeds
    `index` (middle) and trimgalore feeds `reads` (left), so the two wires crossed on every
    render of the canonical pipeline.

    So a rank is now also ordered by **where its consumers' ports are**: a node feeding a
    left-hand port belongs on the left. Downward and upward passes alternate, which is the
    ordinary Sugiyama arrangement — this is still not a general crossing minimiser, and the
    honest claim is that it now handles a fan-in whose consumer declares its ports in an order
    the producers do not happen to match.

    Ties break on node id so the result is total: two nodes with the same median must still land
    in the same order on every machine, which is what makes the golden comparison possible.
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
        """Where this port sits along its node's edge, as a fraction. Falls back to the middle
        for a port the declared list does not carry — `validate` reports that as MD0501."""
        names = (ins or {}).get(consumer)
        if not names or port not in names:
            return 0.5
        return (names.index(port) + 1) / (len(names) + 1)

    position = {nid: i for ids in by_rank.values() for i, nid in enumerate(ids)}
    depths = sorted(by_rank)
    for _ in range(2):
        # Downward: a node sits under what feeds it.
        for depth in depths[1:]:

            def median(nid: str) -> tuple[float, str]:
                feeders = sorted(position[p] for p in incoming[nid])
                return ((feeders[len(feeders) // 2] if feeders else 0.0), nid)

            by_rank[depth].sort(key=median)
            for i, nid in enumerate(by_rank[depth]):
                position[nid] = i

        # Upward: a node sits over the ports it feeds. **This is the pass that was missing.**
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
    """Placement ACROSS the flow: **centre a node against what feeds it.**

    Left-to-right since Plan 4 phase 6, so "across" is now the y axis — the function is unchanged
    arithmetic on a renamed axis, which is why it is `_across` rather than `_x_of`.

    Ordering alone is not placement, and the difference is visible rather than theoretical. With
    `across = order * SIBLING_PITCH`, `star_align` — the one node both roots converge on —
    landed at 0 while its feeders sat at 0 and 338, so the whole spine hung off one edge and a
    wire travelled the full extent to reach it. Every structural assertion passed on that graph.
    Reading the golden file is what found it.

    A node's wanted x is the **median** of its feeders' centres; ties and collisions are then
    packed in order at `SIBLING_PITCH`, which keeps the ordering the crossing pass chose while
    letting a rank sit where its parents are. Sugiyama's fourth step, in the smallest form that
    is honest for a pipeline.
    """
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        incoming[edge.to_node].append(edge.from_node)

    by_rank: dict[int, list[str]] = defaultdict(list)
    for node in graph.nodes:
        by_rank[rank[node.id]].append(node.id)
    for ids in by_rank.values():
        ids.sort(key=lambda nid: (order[nid], nid))

    x: dict[str, int] = {}
    for depth in sorted(by_rank):
        ids = by_rank[depth]
        if depth == 0:
            for i, nid in enumerate(ids):
                x[nid] = i * SIBLING_PITCH
            continue
        wanted = []
        for nid in ids:
            centres = sorted(x[p] + NODE_H // 2 for p in incoming[nid] if p in x)
            # **The mean of the middle two when the count is even**, not the upper one. With two
            # feeders a bare median picks one of them and the node hangs under it: `star_align`
            # sat directly below `trimgalore` while `star_genomegenerate`'s wire crossed the full
            # width to reach it. Averaging puts it between them and halves both runs. For odd
            # counts this is the plain median, which is what the heuristic is.
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
        # Pack in the order the crossing pass chose, never below the previous node's right edge.
        edge_x = None
        for want, nid in wanted:
            x[nid] = want if edge_x is None else max(want, edge_x)
            edge_x = x[nid] + SIBLING_PITCH

    # Normalise so the first node sits at 0 — a canvas should not open on empty space, and a
    # median can go negative when a rank is wider than the one that feeds it.
    shift = min(x.values(), default=0)
    return {nid: value - shift for nid, value in x.items()}


def _ports_of(graph: Graph) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Every node's input and output port names, in the order the canvas draws them.

    **The node carries them, and the adapter decided which they are.** This module used to take
    a `ports` mapping and fall back to the wired ports when it was absent — and that fallback is
    why a wire landed 39 pixels from its chevron in Plan 3C: the canvas spreads `portX(count, i)`
    over the DECLARED ports and the layout spread it over the wired ones, so the two agreed only
    when every declared port had a wire.

    Moving the choice to the adapter does not make that trap go away; it puts it where the
    answer is known. A caller with no registry to hand still supplies wired ports — the golden
    layout test among them — and it is still correct whenever the graph is fully wired.
    """
    return (
        {node.id: list(node.inputs) for node in graph.nodes},
        {node.id: list(node.outputs) for node in graph.nodes},
    )


def _anchor(ports: list[str], name: str) -> int:
    """Where a wire meets a node, **along its edge, in the node's own coordinates.**

    A port the graph names but the contract does not falls back to the spine rather than
    raising: `validate` reports that as MD0501, and a layout is not the place to refuse it.
    """
    if name not in ports:
        return SPINE
    return _port_offset(ports.index(name))


PORT_GAP = 22
"""Between one port and the next along an edge. `impl-geom`: `second = spine + 22`."""


def _port_offset(index: int) -> int:
    """**The one derivation, and the whole of it** — `impl-geom`:

    > spine  = node.y + NODE_H/2        every symbol connects here
    > second = node.y + NODE_H/2 + 22   a secondary input sits below it

    It used to spread ports evenly across the edge, which made a port's position depend on how
    many siblings it had — so adding a declared input moved every existing wire. Anchoring the
    first on the spine means the main chain is dead straight and a second input hangs off it,
    which is what the artboard draws and what makes the chain readable.
    """
    return SPINE + index * PORT_GAP


def of(graph: Graph = None) -> Layout:
    """Lay out an IR. Pure, integer coordinates, stable under repetition.

    Each node carries its own ports, in the order the canvas draws them — see `_ports_of` for
    why that choice belongs to whoever built the graph rather than to this function.
    """
    ins, outs = _ports_of(graph)
    rank = _ranks(graph)
    order = _order(graph, rank, ins)
    across = _across(graph, rank, order)

    # **Left to right** — `impl-settled` on the redesign canvas, under *do not re-litigate*.
    #
    # It flowed DOWNWARD from Plan 3C until 2026-08-30, and that was a considered decision read
    # off `dashboard.html`'s hand-placed nodes; `test_layout.py`'s header still records the
    # reasoning. The 2026-08-29 canvas supersedes it, and `BuilderCanvas.dc.html` is unambiguous:
    # four ranks at x = 194, 418, 642, 866, siblings at the same x with tops 150 and 320.
    #
    # **Every symbol is the same size**, so a rank's extent is arithmetic rather than a maximum.
    placed = tuple(
        Placed(
            id=node.id,
            rank=rank[node.id],
            order=order[node.id],
            x=rank[node.id] * RANK_PITCH,
            y=across[node.id],
            width=NODE_W,
            height=NODE_H,
            tier=node.tier,
        )
        # Sorted so the tuple itself is stable, not merely its contents.
        for node in sorted(graph.nodes, key=lambda n: (rank[n.id], order[n.id], n.id))
    )
    by_id = {node.id: node for node in placed}

    wires = []
    for edge in sorted(graph.edges, key=lambda e: (e.from_node, e.from_port, e.to_node, e.to_port)):
        source, target = by_id[edge.from_node], by_id[edge.to_node]
        # **Index within the DECLARED ports**, which is what the canvas spreads its chevrons
        # over. A port the graph names but the contract does not falls back to the middle
        # rather than raising: `validate` reports that as MD0501 and a layout is not the place
        # to refuse it.
        source_ports = outs.get(edge.from_node, [])
        target_ports = ins.get(edge.to_node, [])
        # **Out of the right edge, into the left edge**, and the offset ALONG the edge is the
        # one derivation `impl-geom` names: a single port sits on the spine, and additional
        # ports are spread from it. Nothing here recomputes a node's geometry.
        start = Point(
            source.x + source.width,
            source.y + _anchor(source_ports, edge.from_port),
        )
        end = Point(
            target.x,
            target.y + _anchor(target_ports, edge.to_port),
        )
        # Horizontal, across at the midpoint, horizontal — `impl-geom`: **right angles read
        # engineered; beziers read playful.** Two curves meeting at a shallow angle are also
        # indistinguishable at the crossing, which matters on a graph that fans in.
        mid = (start.x + end.x) // 2
        # **A straight run is two points, not four.** When the ports line up the two elbow
        # corners are the same coordinate, and emitting them anyway gives the renderer a
        # zero-length segment to round — which is how a 7px corner becomes a visible nick on a
        # wire that should be plumb.
        points = (
            (start, end)
            if start.y == end.y
            else (start, Point(mid, start.y), Point(mid, end.y), end)
        )
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
