"""Protect the public layout values that consumers serialize and render."""

from dag_core import Edge, Graph, Layout, Node, Point, of
from dag_core.layout import NODE_H, NODE_W, SIBLING_PITCH, SPINE


def test_an_empty_graph_has_an_empty_zero_sized_layout():
    laid = of(Graph())

    assert laid == Layout()
    assert (laid.width, laid.height) == (0, 0)


def test_layout_extent_includes_the_full_node_boxes():
    laid = of(Graph(nodes=(Node("a"), Node("b"))))

    assert laid.width == NODE_W
    assert laid.height == SIBLING_PITCH + NODE_H


def test_unknown_ports_fall_back_to_each_nodes_spine():
    laid = of(
        Graph(
            nodes=(Node("source"), Node("target")),
            edges=(Edge("source", "unknown-out", "target", "unknown-in"),),
        )
    )
    source, target = (
        next(node for node in laid.nodes if node.id == node_id) for node_id in ("source", "target")
    )
    wire = laid.wires[0]

    assert wire.points[0].y == source.y + SPINE
    assert wire.points[-1].y == target.y + SPINE


def test_wire_label_position_is_part_of_the_returned_layout():
    laid = of(
        Graph(
            nodes=(Node("source"), Node("target")),
            edges=(Edge("source", "out", "target", "in"),),
        )
    )
    wire = laid.wires[0]
    start, end = wire.points[0], wire.points[-1]

    assert wire.label_at == Point((start.x + end.x) // 2, (start.y + end.y) // 2 - 6)


def test_a_tall_step_grows_and_its_siblings_make_room():
    """#494: a step with six inputs is drawn whole, and the next step in its rank sits below
    it rather than over it; ports keep their anchors, so wires do not move."""
    from dag_core.layout import node_height

    many = Node("quast", inputs=tuple(f"in{i}" for i in range(6)), outputs=("report",))
    laid = of(Graph(nodes=(many, Node("other"))))
    quast, other = (next(n for n in laid.nodes if n.id == i) for i in ("quast", "other"))
    assert quast.height == node_height(6) == 89 + 22 * 5
    assert other.height == NODE_H
    top, below = sorted((quast, other), key=lambda n: n.y)
    assert below.y >= top.y + top.height + 58
