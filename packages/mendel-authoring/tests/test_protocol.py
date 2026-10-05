"""The protocol is one object: the machine is derived from it and the diagram is drawn from it.

A drawing mistake is now a behaviour mistake, so the object refuses to exist when it is
inconsistent. Each refusal below is watched failing against a deliberately broken protocol.
"""

import pytest
from mendel_authoring import protocol as p
from mendel_authoring import state as st
from mendel_authoring.protocol import Actor, Node, Protocol, Stage
from mendel_authoring.types import Command, Event, Phase

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


# ── one diagram, with sections (14.7.8.1) ───────────────────────────────────────────────────


def _sample():
    return [n for n in p.PROTOCOL.nodes if n.stage == "sample"]


def test_the_sample_inside_is_a_section_of_the_one_protocol():
    stages = {s.id: s for s in p.PROTOCOL.stages}
    assert stages["sample"].within_request
    assert _sample(), "a loop over no nodes asserts nothing"
    labels = " ".join(n.label for n in _sample()).lower()
    for step in ("4 mb", "protection", "extension", "unpack", "confirm", "measure",
                 "undetermined", "admit", "nothing reads", "8 kb", "families", "read by ai"):
        assert step in labels, f"the section does not draw {step!r}"
    assert all(n.id.startswith("sample_") for n in _sample())


def test_the_sample_section_sits_after_gathering():
    order = [s.id for s in p.PROTOCOL.stages]
    assert order.index("sample") == order.index("gather") + 1


def test_a_section_within_a_request_never_moves_the_session():
    inside = {n.id for n in _sample()}
    moving = [e for e in p.PROTOCOL.edges if e.event is not None
              and e.source in inside and e.target in inside]
    assert moving == []


def test_the_validator_refuses_an_event_inside_a_within_request_section():
    with pytest.raises(ValueError, match="never moves the session"):
        p.Protocol(
            stages=(p.Stage(id="w", title="W", within_request=True),),
            nodes=(_node("a", stage="w"), _node("b", stage="w")),
            edges=(p.Edge(source="a", target="b", event=Event.FACT_ADDED, built=True),),
        )


def test_the_upload_enters_the_section_and_the_section_returns_to_the_questions():
    edges = {(e.source, e.target) for e in p.PROTOCOL.edges}
    assert ("upload", "sample_level") in edges and ("sample_back", "next_gap") in edges
    assert not {"safety", "read_engine", "read_ai"} & {n.id for n in p.PROTOCOL.nodes}


def test_there_is_one_diagram():
    assert not hasattr(p.PROTOCOL, "details") and not hasattr(p, "INSPECTING")
    assert "detail" not in p.Node.model_fields


def test_the_protection_level_is_asked_before_a_byte_is_kept():
    order = [(e.source, e.target) for e in p.PROTOCOL.edges]
    assert ("upload", "sample_level") in order and ("sample_level", "sample_head") in order


_MACHINE = {
    (Phase.BUILDING, Event.GOAL_ACCEPTED): Phase.RESOLVING,
    (Phase.BUILDING, Event.NOTHING_LEFT): Phase.COMPLETE,
    (Phase.BUILDING, Event.PROPOSAL_SETTLED): Phase.BUILDING,
    (Phase.COMPLETE, Event.GOAL_ACCEPTED): Phase.RESOLVING,
    (Phase.GATHERING, Event.FACT_ADDED): Phase.GATHERING,
    (Phase.GATHERING, Event.INPUT_UNAVAILABLE): Phase.STOPPED,
    (Phase.GATHERING, Event.NOTHING_MISSING): Phase.GOAL_REVIEW,
    (Phase.GATHERING, Event.WANT_UNREACHABLE): Phase.UNDERSTANDING,
    (Phase.GOAL_REVIEW, Event.GOAL_ACCEPTED): Phase.RESOLVING,
    (Phase.GOAL_REVIEW, Event.GOAL_REVISED): Phase.UNDERSTANDING,
    (Phase.RESOLVING, Event.BLUEPRINT_STORED): Phase.BUILDING,
    (Phase.RESOLVING, Event.BUILD_FAILED): Phase.FAILED,
    (Phase.RESOLVING, Event.PROVIDER_FAILED): Phase.FAILED,
    (Phase.UNDERSTANDING, Event.PROVIDER_FAILED): Phase.FAILED,
    (Phase.UNDERSTANDING, Event.WANT_RETURNED): Phase.GATHERING,
}
"""The machine as it stood before 14.7.6.5, printed then and pinned here. **A literal**: the
first version compared `st.TRANSITIONS` with `PROTOCOL.transitions()`, which is the same value,
so it could not fail (review of #134)."""


def test_the_machine_did_not_change():
    """Review focus 5: the upload's edges carry no events of their own."""
    assert p.PROTOCOL.transitions() == _MACHINE


def test_a_stage_and_a_node_cannot_share_an_id():
    """Found drawing *Inspecting a sample*: a stage and a node both called `admit` made Mermaid
    refuse the diagram (*setting admit as parent of admit would create a cycle*)."""
    with pytest.raises(ValueError, match="both a stage and a node"):
        Protocol(
            stages=(Stage(id="admit", title="A"),),
            nodes=(Node(id="admit", stage="admit", actor=Actor.ENGINE, label="A"),),
            edges=(),
        )


def test_every_way_out_of_an_upload_is_drawn():
    """Review of #134: the tie, a refusal after the inspection, an unreadable sample and a
    value the registry refuses all leave the question open today, and each is drawn so."""
    built = {(e.source, e.target) for e in p.PROTOCOL.edges if e.built}
    assert {("sample_confirm", "sample_back"), ("sample_admit", "sample_refused"),
            ("sample_unreadable", "sample_back")} <= built
    assert any(e.source == "sample_admit" and e.target == "sample_back" and "dropped" in e.label
               for e in p.PROTOCOL.edges)


# ── the characteriser (14.7.7) ──────────────────────────────────────────────────────────────


CHARACTERISER = {"door", "excerpt", "families", "types", "ai_admit", "ai_stamped", "hand_back"}


def test_the_characteriser_is_drawn_step_by_step_and_built():
    nodes = {n.id: n for n in p.PROTOCOL.nodes}
    for step in CHARACTERISER:
        assert nodes[f"sample_{step}"].built, step
    edges = {(e.source, e.target) for e in p.PROTOCOL.edges}
    for a, b in [
        ("claim", "door"), ("door", "nothing"), ("door", "excerpt"), ("excerpt", "nothing"),
        ("excerpt", "families"), ("families", "back"), ("families", "types"),
        ("types", "ai_admit"), ("ai_admit", "back"), ("ai_admit", "kept"),
        ("ai_admit", "ai_stamped"), ("ai_admit", "hand_back"), ("hand_back", "confirm"),
        ("ai_stamped", "back"),
    ]:
        assert (f"sample_{a}", f"sample_{b}") in edges, f"{a}→{b} is not drawn"


def test_the_model_reads_through_a_door_the_diagram_names():
    nodes = {n.id: n for n in p.PROTOCOL.nodes}
    for step in ("families", "types"):
        assert "door 6" in nodes[f"sample_{step}"].label.lower(), step


# ── a node acts or waits; an arrow names what takes it (14.7.8.1) ───────────────────────────


def _proto(nodes, edges):
    return Protocol(stages=(Stage(id="s", title="s"),), nodes=tuple(nodes), edges=tuple(edges))


def _taking(id, **kw):
    return Node(id=id, stage="s", actor=Actor.ENGINE, label=id, phase=Phase.GATHERING,
                built=True, **kw)


def test_two_arrows_out_of_one_node_cannot_answer_to_the_same_name():
    with pytest.raises(ValueError, match="twice"):
        _proto([_taking("a", acts=True), _taking("b"), _taking("c")],
               [p.Edge(source="a", target="b", on="yes", built=True),
                p.Edge(source="a", target="c", on="yes", built=True)])


def test_a_waiting_node_is_left_only_by_a_declared_command():
    with pytest.raises(ValueError, match="not a command"):
        _proto([_taking("a", waits=True), _taking("b")],
               [p.Edge(source="a", target="b", on="whatever", built=True)])
    _proto([_taking("a", waits=True), _taking("b")],
           [p.Edge(source="a", target="b", on=Command.CONTINUE.value, built=True)])


def test_a_node_has_at_most_one_way_straight_through():
    with pytest.raises(ValueError, match="straight through"):
        _proto([_taking("a", waits=True), _taking("b"), _taking("c")],
               [p.Edge(source="a", target="b", built=True),
                p.Edge(source="a", target="c", built=True)])


def test_a_node_that_takes_no_part_may_still_fan_out_unnamed():
    """Today's protocol: no node marked, no arrow named. 1b turns the rule on as it marks each."""
    _proto([_taking("a"), _taking("b"), _taking("c")],
           [p.Edge(source="a", target="b", built=True), p.Edge(source="a", target="c", built=True)])


def test_the_real_protocol_still_loads():
    assert p.PROTOCOL.nodes


def test_the_commands_are_the_specs_and_1bs():
    assert {c.value for c in Command} == {
        "describe", "answer_gap", "upload_sample", "confirm_goal", "revise_goal",
        "choose_pacing", "continue", "answer_fact", "choose", "ask", "keep", "retry",
        "reply_in_words", "settle_step", "understood", "asked_back", "revised",
        "provider_failed",
    }


def test_the_ways_out_of_a_section_are_named_once_each():
    with pytest.raises(ValueError, match="ways out of section"):
        Protocol(
            stages=(Stage(id="s", title="s"), Stage(id="w", title="w", within_request=True)),
            nodes=(_taking("a", acts=True), _taking("b"), _taking("c"),
                   Node(id="w1", stage="w", actor=Actor.ENGINE, label="w1",
                        phase=Phase.GATHERING, built=True)),
            edges=(p.Edge(source="a", target="w1", built=True),
                   p.Edge(source="w1", target="b", on="answered", built=True),
                   p.Edge(source="w1", target="c", built=True)),
        )


def test_a_named_arrow_out_of_a_node_that_neither_acts_nor_waits_is_refused():
    """Final review of 1a: nothing could take it, and a session run there would rest on a node
    no command leaves. A forgotten `acts=True` is a drawing mistake, so it refuses to load."""
    with pytest.raises(ValueError, match="neither acts nor waits"):
        _proto([_taking("a", waits=True), _taking("b"), _taking("c", waits=True)],
               [p.Edge(source="a", target="b", on=Command.CONTINUE.value, built=True),
                p.Edge(source="b", target="c", on="done", built=True)])


# ── the protocol, marked (14.7.8.1b) ────────────────────────────────────────────────────────

WAITS = {"say", "family", "reply", "card", "resolve", "step_settled", "step_rule",
         "step_choice", "done", "failed"}
ACTS = {"family", "read_goal", "list_needs", "next_gap", "ask", "answered", "suggest", "upload",
        "resolve", "offer"}


def _main():
    return {n.id: n for n in p.PROTOCOL.nodes if n.built and n.stage != "sample"}


def test_each_built_node_acts_waits_or_passes_as_drawn():
    nodes = _main()
    assert {i for i, n in nodes.items() if n.waits} == WAITS
    assert {i for i, n in nodes.items() if n.acts} == ACTS


def test_every_named_arrow_is_taken_by_its_name():
    """Spec §9: every arrow of the protocol taken once, in a table."""
    from mendel_authoring.interpret import follow

    named = [e for e in p.PROTOCOL.edges if e.built and e.on is not None
             and not e.source.startswith("sample_")]
    assert len(named) > 30, "the table is suspiciously short"
    phase = {n.id: n.phase for n in p.PROTOCOL.nodes}
    for edge in named:
        back = phase[edge.target] if edge.returns else None
        assert follow(p.PROTOCOL, edge.source, edge.on, returning_to=back) is edge, edge


def test_a_sample_leaves_its_section_answered_or_stays_on_the_question():
    from mendel_authoring.interpret import follow

    assert follow(p.PROTOCOL, "upload", "answered").target == "next_gap"
    assert follow(p.PROTOCOL, "upload", "stays").target == "reply"


def test_every_other_command_is_refused_where_a_session_waits():
    from mendel_authoring.interpret import Refused, follow

    for node in WAITS:
        drawn = {e.on for e in p.PROTOCOL.edges if e.built and e.source == node}
        for command in Command:
            if command.value not in drawn:
                with pytest.raises(Refused, match="MI0216"):
                    follow(p.PROTOCOL, node, command.value)


def test_a_node_that_neither_acts_nor_waits_passes_straight_on_or_ends():
    for node in _main().values():
        if node.acts or node.waits:
            continue
        out = [e for e in p.PROTOCOL.edges if e.built and e.source == node.id]
        assert len(out) <= 1 and all(e.on is None for e in out), node.id


def test_the_redrawn_arrows():
    edges = {(e.source, e.target, e.on) for e in p.PROTOCOL.edges if e.built}
    assert ("reply", "answered", "answer_gap") in edges
    assert {("answered", "said", "said"), ("answered", "left_open", "left_open"),
            ("answered", "stopped", "no_input")} <= edges
    assert ("card", "say", "revise_goal") in edges and ("card", "family", "revised") in edges
    assert ("next_gap", "readback", "nothing_missing") in edges
    assert ("sample_back", "reply", "stays") in edges
    assert not {(s, t) for s, t, _ in edges} & {("read_goal", "suggest"),
                                                ("read_goal", "failed"), ("next_gap", "card")}
