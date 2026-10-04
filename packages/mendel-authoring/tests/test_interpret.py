"""The interpreter: the protocol run as a program (14.7.8.1). Pure — `enter` is the shell's."""

import pytest
from mendel_authoring.interpret import Refused, follow, run
from mendel_authoring.protocol import Actor, Edge, Node, Protocol, Stage
from mendel_authoring.types import Command, Phase


def _n(id, **kw):
    return Node(id=id, stage="s", actor=Actor.ENGINE, label=id, phase=Phase.GATHERING,
                built=True, **kw)


def _e(a, b, on=None):
    return Edge(source=a, target=b, on=on, built=True)


GATHER = Protocol(
    stages=(Stage(id="s", title="s"),),
    nodes=(
        _n("reply", waits=True), _n("said"), _n("next_gap", acts=True),
        _n("ask", acts=True, waits=True), _n("card", waits=True),
    ),
    edges=(
        _e("reply", "said", Command.ANSWER_GAP.value), _e("said", "next_gap"),
        _e("next_gap", "ask", "a_gap"), _e("next_gap", "card", "nothing_missing"),
        _e("ask", "reply", "phrased"),
    ),
)


def test_an_answer_runs_to_the_next_question_and_rests_there():
    entered = []

    def enter(node):
        entered.append(node)
        return {"next_gap": "a_gap"}.get(node)  # ask queues phrasing and rests

    ran = run(GATHER, "reply", Command.ANSWER_GAP.value, enter)
    assert ran.at == "ask" and ran.path == ["said", "next_gap", "ask"]
    assert entered == ["next_gap", "ask"], "only acting nodes are entered"


def test_the_last_answer_runs_to_the_goal_card():
    ran = run(GATHER, "reply", Command.ANSWER_GAP.value,
              lambda node: {"next_gap": "nothing_missing"}.get(node))
    assert ran.at == "card"


def test_a_command_no_arrow_names_is_refused_by_name():
    with pytest.raises(Refused, match="MI0216") as caught:
        run(GATHER, "card", Command.ANSWER_GAP.value, lambda node: None)
    assert "card" in str(caught.value) and "answer_gap" in str(caught.value)


def test_an_outcome_no_arrow_names_is_refused_by_name():
    with pytest.raises(Refused, match="MI0216") as caught:
        run(GATHER, "reply", Command.ANSWER_GAP.value, lambda node: "a_typo")
    assert "next_gap" in str(caught.value) and "a_typo" in str(caught.value)


def test_a_cycle_stops_at_the_limit_and_says_so():
    loop = Protocol(
        stages=(Stage(id="s", title="s"),),
        nodes=(_n("a", waits=True), _n("b", acts=True), _n("c", acts=True)),
        edges=(_e("a", "b", Command.CONTINUE.value), _e("b", "c", "on"), _e("c", "b", "on")),
    )
    with pytest.raises(Refused, match="MI0216.*64"):
        run(loop, "a", Command.CONTINUE.value, lambda node: "on")


def test_a_planned_arrow_is_never_followed():
    planned = Protocol(
        stages=(Stage(id="s", title="s"),),
        nodes=(_n("a", waits=True), _n("b")),
        edges=(Edge(source="a", target="b", on=Command.CONTINUE.value),),
    )
    with pytest.raises(Refused, match="MI0216"):
        follow(planned, "a", Command.CONTINUE.value)
