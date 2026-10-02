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


def test_a_want_nothing_makes_asks_rather_than_fails():
    """#202: `list_needs → failed` became a question back to the person."""
    edges = {(e.source, e.target, e.event) for e in p.PROTOCOL.edges}
    assert ("list_needs", "say", Event.WANT_UNREACHABLE) in edges
    assert not any(s == "list_needs" and t == "failed" for s, t, _ in edges)


# ── a node may carry a detailed diagram of its own steps (14.7.6.5) ──────────────────────────

Actor, Edge, Node, Protocol, Stage = p.Actor, p.Edge, p.Node, p.Protocol, p.Stage


def _detail(phase=Phase.GATHERING, built=True, event=None):
    return Protocol(
        title="Inside",
        slug="inside",
        stages=(Stage(id="s", title="On our server"),),
        nodes=(
            Node(id="a", stage="s", actor=Actor.ENGINE, label="A", phase=phase, built=built),
            Node(id="b", stage="s", actor=Actor.ENGINE, label="B", phase=phase, built=built),
        ),
        edges=(Edge(source="a", target="b", event=event, built=built),),
    )


def _with(detail, parent_built=True):
    return Protocol(
        stages=(Stage(id="g", title="G"),),
        nodes=(
            Node(
                id="p", stage="g", actor=Actor.ENGINE, label="P",
                phase=Phase.GATHERING if parent_built else None, built=parent_built,
                detail=detail,
            ),
        ),
        edges=(),
    )


def test_a_node_may_carry_a_detail():
    assert [d.slug for d in _with(_detail()).details()] == ["inside"]


def test_a_detail_edge_cannot_move_the_session():
    with pytest.raises(ValueError, match="cannot move the session"):
        _with(_detail(event=Event.FACT_ADDED))


def test_a_detail_step_is_in_its_parents_phase():
    with pytest.raises(ValueError, match="phase"):
        _with(_detail(phase=Phase.BUILDING))


def test_a_built_detail_under_a_planned_node_is_refused():
    """Review focus 1."""
    with pytest.raises(ValueError, match="planned"):
        _with(_detail(), parent_built=False)


def test_the_machine_ignores_details():
    assert _with(_detail()).transitions() == {}


# ── the upload, built (14.7.6.5) ─────────────────────────────────────────────────────────────


def test_the_upload_branch_is_built_and_the_characteriser_is_not():
    nodes = {n.id: n for n in p.PROTOCOL.nodes}
    assert nodes["upload"].built and nodes["safety"].built and nodes["read_engine"].built
    assert not nodes["read_ai"].built


def test_reading_a_sample_has_its_detailed_diagram():
    detail = {n.id: n for n in p.PROTOCOL.nodes}["read_engine"].detail
    assert detail is not None and detail.slug == "inspecting-a-sample"
    labels = " ".join(n.label for n in detail.nodes).lower()
    for step in ("4 mb", "protection", "extension", "unpack", "confirm", "measure",
                 "undetermined", "admit", "nothing reads"):
        assert step in labels, f"the detail does not draw {step!r}"
    assert detail.stages and all(s.title.startswith("On our server") for s in detail.stages)


def test_the_protection_level_is_asked_before_a_byte_is_kept():
    detail = {n.id: n for n in p.PROTOCOL.nodes}["read_engine"].detail
    order = [(e.source, e.target) for e in detail.edges]
    assert ("got", "level") in order and ("level", "head") in order


def test_the_machine_did_not_change():
    """Review focus 5: the upload's edges carry no events of their own."""
    assert p.PROTOCOL.transitions() == st.TRANSITIONS
    assert (Phase.GATHERING, Event.FACT_ADDED) in st.TRANSITIONS


def test_a_stage_and_a_node_cannot_share_an_id():
    """Found drawing *Inspecting a sample*: a stage and a node both called `admit` made Mermaid
    refuse the diagram (*setting admit as parent of admit would create a cycle*)."""
    with pytest.raises(ValueError, match="both a stage and a node"):
        Protocol(
            stages=(Stage(id="admit", title="A"),),
            nodes=(Node(id="admit", stage="admit", actor=Actor.ENGINE, label="A"),),
            edges=(),
        )
