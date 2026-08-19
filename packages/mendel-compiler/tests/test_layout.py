"""Where the boxes go.

**Deterministic, and in Python for that reason.** A browser layout library would put the
position of every node outside the guarantee the rest of the system keeps — same input, same
output, byte for byte — and the canvas is the thing a person screenshots. `dashboard.md` §9 calls
this the largest outstanding piece; it is the one part of 3C that is an algorithm rather than a
rendering.

**The graph flows downward.** Read off `dashboard.html`'s own `elbow()`, which routes vertical →
horizontal at the midpoint → vertical, and off its two hand-placed nodes, which share `top:6` at
different `left`. The first draft of this plan assumed left-to-right and would have been wrong in
a way no test here would have caught — the assertions would all have passed on a sideways graph.
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


def test_a_producer_sits_above_its_consumer(spine):
    """The only structural claim a reader relies on: flow is down, so a step that feeds another
    is drawn before it."""
    placed = {node.id: node for node in layout.of(spine).nodes}
    for wire in layout.of(spine).wires:
        assert placed[wire.from_node].rank < placed[wire.to_node].rank


def test_the_two_roots_share_a_rank(spine):
    """`trimgalore` and `star_genomegenerate` both feed `star_align` and neither feeds the
    other, so they are the same depth and must be drawn side by side. This is the case
    crossing-reduction exists for, and a layout that stacked them would still pass every other
    assertion here."""
    placed = {node.id: node for node in layout.of(spine).nodes}
    assert placed["trimgalore"].rank == placed["star_genomegenerate"].rank
    assert placed["trimgalore"].x != placed["star_genomegenerate"].x


def test_a_converging_node_sits_between_what_feeds_it(spine):
    """**Found by reading the golden file, not by a failing assertion.**

    Ordering is not placement. With `x = order * COL_PITCH` every rank started at zero, so
    `star_align` — the node both roots converge on — hung off the left edge while one of its two
    feeders sat 338px away, and its wire crossed the whole graph to reach it. Every other test
    here passed on that layout.

    The node must sit between its feeders, not under one of them: a bare median picks the upper
    of two and reproduces the same lopsidedness one step less obviously.
    """
    placed = {node.id: node for node in layout.of(spine).nodes}
    feeders = sorted(
        placed[nid].x + placed[nid].width / 2 for nid in ("trimgalore", "star_genomegenerate")
    )
    centre = placed["star_align"].x + placed["star_align"].width / 2
    assert feeders[0] < centre < feeders[1], "star_align hangs off one of its feeders"


def test_a_straight_drop_is_two_points(spine):
    """When the ports line up, both elbow corners are the same coordinate. Emitting them anyway
    hands the renderer a zero-length segment to round, which is how a 7px corner becomes a
    visible nick in a wire that should be plumb."""
    for wire in layout.of(spine).wires:
        if wire.points[0].x == wire.points[-1].x:
            assert len(wire.points) == 2


def test_nothing_overlaps(spine):
    """Two nodes at one rank may not share an x. The failure that makes a graph unreadable
    rather than merely ugly."""
    seen = set()
    for node in layout.of(spine).nodes:
        assert (node.rank, node.x) not in seen, f"{node.id} lands on another node"
        seen.add((node.rank, node.x))


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


def test_a_wire_leaves_the_bottom_and_arrives_at_the_top(spine):
    """`dashboard.html`'s `anchor()`: an out port sits at `n.y + height`, an in port at `n.y`."""
    placed = {node.id: node for node in layout.of(spine).nodes}
    for wire in layout.of(spine).wires:
        start, end = wire.points[0], wire.points[-1]
        assert start.y == placed[wire.from_node].y + placed[wire.from_node].height
        assert end.y == placed[wire.to_node].y


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
