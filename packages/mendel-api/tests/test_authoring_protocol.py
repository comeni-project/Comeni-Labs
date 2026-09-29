"""The protocol is one object: the machine is derived from it and the diagram is drawn from it.

A drawing mistake is now a behaviour mistake, so the object refuses to exist when it is
inconsistent. Each refusal below is watched failing against a deliberately broken protocol.
"""

import pytest
from mendel_api.authoring import protocol as p
from mendel_api.authoring import state as st
from mendel_api.authoring.types import Event, Phase

S = (p.Stage(id="s", title="S"),)


def _node(id, phase=Phase.UNDERSTANDING, *, built=True, stage="s"):
    return p.Node(id=id, stage=stage, actor=p.Actor.ENGINE, label=id, phase=phase, built=built)


def test_the_real_protocol_loads_and_has_built_and_planned_parts():
    assert p.PROTOCOL.edges, "a loop over no edges asserts nothing"
    assert any(n.built for n in p.PROTOCOL.nodes)
    assert any(not n.built for n in p.PROTOCOL.nodes), "the design is in the object, planned"


def test_an_edge_to_an_undeclared_node_is_refused():
    with pytest.raises(ValueError, match="undeclared node 'ghost'"):
        p.Protocol(stages=S, nodes=(_node("a"),), edges=(p.Edge(source="a", target="ghost"),))


def test_a_node_in_an_undeclared_stage_is_refused():
    with pytest.raises(ValueError, match="undeclared stage 'nowhere'"):
        p.Protocol(stages=S, nodes=(_node("a", stage="nowhere"),), edges=())


def test_a_built_node_without_a_phase_is_refused():
    with pytest.raises(ValueError, match="built node 'a' has no phase"):
        p.Protocol(stages=S, nodes=(_node("a", phase=None),), edges=())


def test_a_built_edge_touching_a_planned_node_is_refused():
    nodes = (_node("a"), _node("b", Phase.GOAL_REVIEW, built=False))
    edge = p.Edge(source="a", target="b", event=Event.WANT_RETURNED, built=True)
    with pytest.raises(ValueError, match="built edge a→b touches a planned node"):
        p.Protocol(stages=S, nodes=nodes, edges=(edge,))


def test_one_phase_and_event_with_two_targets_is_refused():
    nodes = (_node("a"), _node("b", Phase.GOAL_REVIEW), _node("c", Phase.FAILED))
    edges = (
        p.Edge(source="a", target="b", event=Event.WANT_RETURNED, built=True),
        p.Edge(source="a", target="c", event=Event.WANT_RETURNED, built=True),
    )
    with pytest.raises(ValueError, match="understanding on want_returned leads to both"):
        p.Protocol(stages=S, nodes=nodes, edges=edges)


def test_a_return_edge_must_leave_failed_on_retry():
    nodes = (_node("a"), _node("b", Phase.RESOLVING))
    edge = p.Edge(source="a", target="b", event=Event.RETRY, returns=True, built=True)
    with pytest.raises(ValueError, match="return edge a→b does not leave failed"):
        p.Protocol(stages=S, nodes=nodes, edges=(edge,))


def test_retry_is_only_ever_a_return_edge():
    nodes = (_node("f", Phase.FAILED), _node("b", Phase.RESOLVING))
    edge = p.Edge(source="f", target="b", event=Event.RETRY, built=True)
    with pytest.raises(ValueError, match="f→b carries retry without returns"):
        p.Protocol(stages=S, nodes=nodes, edges=(edge,))


def test_planned_parts_are_left_out_of_the_machine():
    nodes = (_node("a"), _node("b", Phase.GOAL_REVIEW), _node("c", None, built=False))
    edges = (
        p.Edge(source="a", target="b", event=Event.WANT_RETURNED, built=True),
        p.Edge(source="b", target="c", label="later"),
    )
    proto = p.Protocol(stages=S, nodes=nodes, edges=edges)
    assert proto.transitions() == {(Phase.UNDERSTANDING, Event.WANT_RETURNED): Phase.GOAL_REVIEW}


def test_the_key_names_every_actor_every_border_and_planned():
    """A new actor cannot be drawn without the key saying what its colour means."""
    rendered = p.to_mermaid(p.PROTOCOL)
    for actor in p.Actor:
        assert f"key_{actor.value}" in rendered
    for border in p.Border:
        if border is not p.Border.NONE:
            assert f"key_{border.value}" in rendered
    assert "key_planned" in rendered


def test_planned_parts_are_drawn_dashed():
    nodes = (_node("a"), _node("c", None, built=False))
    proto = p.Protocol(stages=S, nodes=nodes, edges=(p.Edge(source="a", target="c", label="x"),))
    rendered = p.to_mermaid(proto)
    assert 'a -. "x" .-> c' in rendered
    assert "style c stroke-dasharray" in rendered


def test_rendering_is_deterministic():
    assert p.to_mermaid(p.PROTOCOL) == p.to_mermaid(p.PROTOCOL)



def test_the_machine_is_read_from_the_protocol():
    assert p.PROTOCOL.transitions() == st.TRANSITIONS
    assert st.RETRY_TARGETS == p.PROTOCOL.retry_targets() == {Phase.UNDERSTANDING, Phase.RESOLVING}
    assert st.RETRY_FALLBACK in st.RETRY_TARGETS


def test_the_type_is_chosen_by_family_first():
    """#194: a built AI step before the goal call; a revision and a retry re-run both steps."""
    nodes = {n.id: n for n in p.PROTOCOL.nodes}
    family = nodes["family"]
    assert family.built and family.actor is p.Actor.AI and family.stage == "describe"
    edges = {(e.source, e.target, e.event) for e in p.PROTOCOL.edges}
    assert ("say", "family", None) in edges and ("say", "read_goal", None) not in edges
    assert ("family", "read_goal", None) in edges
    assert ("family", "say", None) in edges, "none fits: a question back to the person"
    assert ("card", "family", Event.GOAL_REVISED) in edges
    assert ("failed", "family", Event.RETRY) in edges
    assert ("family", "failed", Event.PROVIDER_FAILED) in edges
