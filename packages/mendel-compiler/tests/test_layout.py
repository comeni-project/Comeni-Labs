"""Where the boxes go.

**Deterministic, and in Python for that reason.** A browser layout library would put the
position of every node outside the guarantee the rest of the system keeps — same input, same
output, byte for byte — and the canvas is the thing a person screenshots. `dashboard.md` §9 calls
this the largest outstanding piece; it is the one part of 3C that is an algorithm rather than a
rendering.

**The graph flows LEFT TO RIGHT, and it used to flow downward.** Plan 3C read the direction off
`dashboard.html`'s `elbow()` and its two hand-placed nodes, and this docstring warned that a
sideways graph would have passed every assertion in the file. That warning was right and it is
why this rewrite touched eight of them.

**The 2026-08-29 redesign canvas supersedes `dashboard.html`.** `impl-settled` says *CANVAS IS
LEFT-TO-RIGHT* under a heading reading *please do not re-litigate*, and `BuilderCanvas.dc.html`
is unambiguous: four ranks at x = 194, 418, 642, 866, and two siblings sharing an x at tops 150
and 320. The operator confirmed it by driving the built page and calling the difference
incredible. Plan 4 phase 6.

**Every symbol is now the same size**, 172×112, which is `impl-geom`'s load-bearing claim rather
than a tidiness one: variable heights put a jog between every pair and the main chain stops
reading as a chain.
"""

from pathlib import Path

import pytest
from comeni_core import yaml_strict
from mendel_compiler import layout, orchestrate
from mendel_resolver.goal import Goal

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def spine():
    goal = Goal.model_validate(yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml"))
    return orchestrate.build(
        goal, registry_root=ROOT / "registry", vendor_root=ROOT / "vendor"
    ).ir


def test_a_producer_sits_LEFT_of_its_consumer(spine):
    """The only structural claim a reader relies on: flow is rightward, so a step that feeds
    another is drawn before it.

    **The rank half of this passed on a downward graph too**, which is exactly the blind spot
    this file's header warned about — a rank is an ordering and says nothing about an axis. The
    `x` assertion is the one that can tell the two layouts apart.
    """
    placed = {node.id: node for node in layout.of(spine).nodes}
    for wire in layout.of(spine).wires:
        source, target = placed[wire.from_node], placed[wire.to_node]
        assert source.rank < target.rank
        assert source.x < target.x, f"{wire.from_node} is not left of {wire.to_node}"


def test_the_two_roots_share_a_rank(spine):
    """`trimgalore` and `star_genomegenerate` both feed `star_align` and neither feeds the
    other, so they are the same depth and must be drawn side by side. This is the case
    crossing-reduction exists for, and a layout that stacked them would still pass every other
    assertion here."""
    placed = {node.id: node for node in layout.of(spine).nodes}
    assert placed["trimgalore"].rank == placed["star_genomegenerate"].rank
    # Same rank is the same COLUMN now, so they are separated across the flow rather than along
    # it — one x, two ys.
    assert placed["trimgalore"].x == placed["star_genomegenerate"].x
    assert placed["trimgalore"].y != placed["star_genomegenerate"].y


def test_a_converging_node_sits_between_what_feeds_it(spine):
    """**Found by reading the golden file, not by a failing assertion.**

    Ordering is not placement. With `across = order * SIBLING_PITCH` every rank started at zero,
    so `star_align` — the node both roots converge on — hung off one edge while one of its two
    feeders sat 338px away, and its wire crossed the whole graph to reach it. Every other test
    here passed on that layout.

    The node must sit between its feeders, not under one of them: a bare median picks the upper
    of two and reproduces the same lopsidedness one step less obviously.
    """
    placed = {node.id: node for node in layout.of(spine).nodes}
    feeders = sorted(
        placed[nid].y + placed[nid].height / 2 for nid in ("trimgalore", "star_genomegenerate")
    )
    centre = placed["star_align"].y + placed["star_align"].height / 2
    assert feeders[0] < centre < feeders[1], "star_align hangs off one of its feeders"


def test_a_straight_run_is_two_points(spine):
    """When the ports line up, both elbow corners are the same coordinate. Emitting them anyway
    hands the renderer a zero-length segment to round, which is how a 7px corner becomes a
    visible nick in a wire that should be straight."""
    for wire in layout.of(spine).wires:
        if wire.points[0].y == wire.points[-1].y:
            assert len(wire.points) == 2


def test_nothing_overlaps(spine):
    """Two nodes at one rank may not share a `y`. The failure that makes a graph unreadable
    rather than merely ugly, and the one `impl-walkbugs` reports from the walk: *every step
    landed on identical coordinates — two nodes, one visible.*"""
    seen = set()
    for node in layout.of(spine).nodes:
        assert (node.rank, node.y) not in seen, f"{node.id} lands on another node"
        seen.add((node.rank, node.y))


def test_the_same_ir_lays_out_identically(spine):
    """Invariant 10's discipline, extended to the thing a person screenshots."""
    assert layout.of(spine) == layout.of(spine)


def test_every_coordinate_is_an_integer(spine):
    """So a golden file compares exactly and no float formatting can drift between machines —
    the same reason `IREdge.states` carries a field serialiser."""
    placed = layout.of(spine)
    for node in placed.nodes:
        assert isinstance(node.x, int) and isinstance(node.y, int)
    for wire in placed.wires:
        for point in wire.points:
            assert isinstance(point.x, int) and isinstance(point.y, int)


def test_a_wire_leaves_the_right_edge_and_arrives_at_the_left(spine):
    """An out port sits at `n.x + width`, an in port at `n.x` — the flow read as geometry.

    This is also the guard on `impl-geom`'s rule that **port positions are derived from node
    geometry in one place**: an endpoint typed separately from the node it belongs to is what put
    every wire 6px above its port on the 2026-08-29 walk.
    """
    placed = {node.id: node for node in layout.of(spine).nodes}
    for wire in layout.of(spine).wires:
        start, end = wire.points[0], wire.points[-1]
        assert start.x == placed[wire.from_node].x + placed[wire.from_node].width
        assert end.x == placed[wire.to_node].x


def test_a_wire_is_orthogonal(spine):
    """Every segment runs along one axis. `dashboard.md` §4: two curves meeting at a shallow
    angle are indistinguishable at the crossing and two right angles are not — so a later
    refactor to beziers has to argue with this test rather than only with a comment."""
    for wire in layout.of(spine).wires:
        for a, b in zip(wire.points, wire.points[1:], strict=False):
            assert a.x == b.x or a.y == b.y, "a diagonal segment"


GOLDEN = Path(__file__).parent / "golden" / "rnaseq-spine.layout.json"


def _as_json(placed: layout.Layout) -> str:
    import json

    return json.dumps(
        {
            "nodes": [
                {
                    "id": n.id, "rank": n.rank, "order": n.order,
                    "x": n.x, "y": n.y, "w": n.width, "h": n.height, "tier": n.tier,
                }
                for n in placed.nodes
            ],
            "wires": [
                {
                    "from": f"{w.from_node}.{w.from_port}",
                    "to": f"{w.to_node}.{w.to_port}",
                    "type": w.type_id,
                    "points": [[p.x, p.y] for p in w.points],
                }
                for w in placed.wires
            ],
        },
        indent=2,
    ) + "\n"


def test_the_layout_matches_the_golden_file(spine):
    """A layout change is a **visual** change, and this file is the only place it is reviewable
    before somebody sees it. Regenerate with `LAYOUT_GOLDEN=update` and **read the diff** — the
    same discipline as the emitted `.nf`, and for the same reason: nothing else in the suite can
    tell a better arrangement from a worse one.
    """
    import os

    produced = _as_json(layout.of(spine))
    if os.environ.get("LAYOUT_GOLDEN") == "update":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(produced)
    assert produced == GOLDEN.read_text()


# --- A wire must land on the port it names, not on the middle of the node -----------------


def test_a_wire_lands_on_the_port_the_canvas_draws(spine):
    """**The defect the operator found by dragging.**

    `layout` anchored a wire using only the ports that *have wires*, in edge order. The canvas
    draws every port the *contract declares*, in contract order. For `featurecounts` — two
    declared inputs, one of them wired — the chevron sat at 77 and the wire ended at 116.
    **39 pixels onto nothing.**

    The two agree only when the wired count equals the declared count, which is almost never.
    Both formulas were the same spread; what differed was the `count`. Since phase 6 the
    offset is index-only, so the two cannot disagree about a count at all.
    """
    # `_port_x` moved to dag-core on 2026-08-24 with the rest of the arithmetic; `of`
    # stays here because it is the adapter. The assertions below are unchanged.
    from dag_core.layout import _port_offset
    from mendel_compiler.layout import of

    declared = {
        "a": ([], ["out"]),
        "b": (["first", "second"], []),  # two declared inputs, one of them wired
    }
    ir = _two_nodes()
    laid = of(ir, ports=declared)
    node = next(n for n in laid.nodes if n.id == "b")
    wire = laid.wires[0]

    # Where the canvas puts `first`: index 0, so the spine. The offset no longer depends on how
    # many siblings a port has — which is the point of anchoring the first one on the spine.
    drawn = node.y + _port_offset(0)
    assert wire.points[-1].y == drawn, (
        f"wire ends at {wire.points[-1].y}, canvas draws the port at {drawn}"
    )


def _two_nodes():
    """`a` feeds `b`, and `b` declares a second input nothing wires. The smallest graph that can
    tell a wire anchored on DECLARED ports apart from one anchored on wired ones."""
    from comeni_core.plan.ir import IREdge, IRNode, PipelineIR

    return PipelineIR(
        nodes=[
            IRNode(id="a", contract_id="x/a@1"),
            IRNode(id="b", contract_id="x/b@1"),
        ],
        edges=[IREdge(from_node="a", from_port="out", to_node="b", to_port="first",
                      type_id="t.x")],
    )


def test_every_symbol_is_the_same_size(spine):
    """**The opposite of what this file used to assert**, and the change is deliberate.

    A node used to be sized from its declared port count, so the symbol advertised a fact about
    the CONTRACT that nobody reads a canvas to learn — and `impl-geom` is blunt about the cost:

    > UNIFORM SYMBOL SIZE IS LOAD-BEARING. 172 x 112 for every process node. It is what makes the
    > main chain dead straight — variable heights put a jog between every pair and the whole thing
    > reads sloppy again.

    Ports are spread ALONG the edge instead, which is what `_port_offset` does.
    """
    from dag_core import layout as dag_layout

    for node in layout.of(spine).nodes:
        assert (node.width, node.height) == (dag_layout.NODE_W, dag_layout.NODE_H), node.id


def test_producers_are_ordered_to_match_the_ports_they_feed(spine):
    """**The crossing the operator saw.**

    `star_align` declares `reads`, `index`, `gtf` in that order, so its chevrons sit left to
    right in that order. `_order` placed `star_genomegenerate` left of `trimgalore` — by node id,
    because roots have nothing feeding them — and genomegenerate feeds `index` (middle) while
    trimgalore feeds `reads` (left). The two wires cross, every time, on the shipped spine.

    `_order`'s own docstring said it: *"it is not a crossing-minimisation algorithm. If a graph
    ever arrives where it is visibly wrong, the honest fix is a real ordering pass."*

    The rule this asserts is local and checkable: **for two wires into one node, the one whose
    source sits further left must land on the further-left port.** That is exactly what "they do
    not cross" means for a layered graph, without needing a general planarity test.
    """
    from mendel_compiler.layout import of

    # **With the DECLARED ports**, which is what the API passes and what the canvas draws.
    # Without them the fallback orders a node's inputs by the edges that happen to exist, which
    # hides this: the wired order and the declared order coincide on a fully wired node.
    declared = {
        "star_align": (["reads", "index", "gtf"], ["bam"]),
        "star_genomegenerate": (["fasta", "gtf"], ["index"]),
        "trimgalore": (["reads"], ["reads"]),
        "samtools_sort": (["bam"], ["bam"]),
        "subread_featurecounts": (["bam", "annotation"], ["counts"]),
    }
    laid = of(spine, ports={k: v for k, v in declared.items() if any(
        n.id == k for n in spine.nodes)})
    at = {node.id: node for node in laid.nodes}

    into: dict[str, list] = {}
    for wire in laid.wires:
        into.setdefault(wire.to_node, []).append(wire)

    crossings = []
    for target, arriving in into.items():
        for a in arriving:
            for b in arriving:
                if a is b:
                    continue
                if at[a.from_node].x < at[b.from_node].x and a.points[-1].x > b.points[-1].x:
                    crossings.append(
                        f"{a.from_node}->{target}.{a.to_port} crosses "
                        f"{b.from_node}->{target}.{b.to_port}"
                    )
    assert not crossings, "\n".join(sorted(set(crossings)))
