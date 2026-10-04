"""The interpreter: the protocol run as a program (14.7.8.1). Pure — `enter` is the shell's."""

import pytest
from mendel_authoring.interpret import Refused, follow, run
from mendel_authoring.protocol import Actor, Edge, Node, Protocol, Stage
from mendel_authoring.types import Command, Event, Phase


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


def _phased(id, phase, **kw):
    return Node(id=id, stage="s", actor=Actor.ENGINE, label=id, phase=phase, built=True, **kw)


RETRYING = Protocol(
    stages=(Stage(id="s", title="s"),),
    nodes=(
        _phased("failed", Phase.FAILED, waits=True),
        _phased("family", Phase.UNDERSTANDING, waits=True),
        _phased("resolve", Phase.RESOLVING, waits=True),
    ),
    edges=(
        Edge(source="failed", target="family", on="retry", event=Event.RETRY, returns=True,
             built=True),
        Edge(source="failed", target="resolve", on="retry", event=Event.RETRY, returns=True,
             built=True),
    ),
)


def test_two_return_arrows_share_the_retry_name_and_the_failure_chooses():
    assert follow(RETRYING, "failed", "retry", returning_to=Phase.RESOLVING).target == "resolve"
    assert follow(RETRYING, "failed", "retry", returning_to=Phase.UNDERSTANDING).target == "family"


SECTIONED = Protocol(
    stages=(Stage(id="s", title="s"), Stage(id="w", title="w", within_request=True)),
    nodes=(
        _n("reply", waits=True), _n("upload", acts=True), _n("next"),
        Node(id="w_in", stage="w", actor=Actor.ENGINE, label="in", phase=Phase.GATHERING,
             built=True),
        Node(id="w_back", stage="w", actor=Actor.ENGINE, label="back", phase=Phase.GATHERING,
             built=True),
    ),
    edges=(
        _e("reply", "upload", Command.UPLOAD_SAMPLE.value), _e("upload", "w_in"),
        _e("w_in", "w_back"), _e("w_back", "next", "answered"), _e("w_back", "reply", "stays"),
    ),
)


def test_a_section_within_a_request_is_one_step_and_its_ways_out_are_the_entry_nodes():
    ran = run(SECTIONED, "reply", Command.UPLOAD_SAMPLE.value, lambda node: "answered")
    assert ran.at == "next" and ran.path == ["upload", "next"]
    stays = run(SECTIONED, "reply", Command.UPLOAD_SAMPLE.value, lambda node: "stays")
    assert stays.at == "reply"


def test_resuming_enters_where_the_session_rests():
    ran = run(GATHER, "next_gap", None, lambda node: {"next_gap": "a_gap"}.get(node))
    assert ran.at == "ask" and ran.path == ["next_gap", "ask"]
