"""The interpreter: the protocol run as a program (14.7.8.1). Pure — `enter` is the shell's."""

import pytest
from comeni_flow.interpret import Refused, follow, run
from comeni_flow.protocol import Actor, Edge, Node, Stage
from mendel_authoring.protocol import authoring_protocol
from mendel_authoring.types import Command, Event, Phase


def _n(id, **kw):
    return Node(id=id, stage="s", actor=Actor.ENGINE, label=id, phase=Phase.GATHERING,
                built=True, **kw)


def _e(a, b, on=None):
    return Edge(source=a, target=b, on=on, built=True)


GATHER = authoring_protocol(
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
    loop = authoring_protocol(
        stages=(Stage(id="s", title="s"),),
        nodes=(_n("a", waits=True), _n("b", acts=True), _n("c", acts=True)),
        edges=(_e("a", "b", Command.CONTINUE.value), _e("b", "c", "on"), _e("c", "b", "on")),
    )
    with pytest.raises(Refused, match="MI0216.*64"):
        run(loop, "a", Command.CONTINUE.value, lambda node: "on")


def test_a_planned_arrow_is_never_followed():
    planned = authoring_protocol(
        stages=(Stage(id="s", title="s"),),
        nodes=(_n("a", waits=True), _n("b")),
        edges=(Edge(source="a", target="b", on=Command.CONTINUE.value),),
    )
    with pytest.raises(Refused, match="MI0216"):
        follow(planned, "a", Command.CONTINUE.value)


def _phased(id, phase, **kw):
    return Node(id=id, stage="s", actor=Actor.ENGINE, label=id, phase=phase, built=True, **kw)


RETRYING = authoring_protocol(
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


SECTIONED = authoring_protocol(
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


PASSING = authoring_protocol(
    stages=(Stage(id="s", title="s"),),
    nodes=(_n("next_gap", acts=True), _n("ask", acts=True), _n("reply", waits=True),
           _n("family", acts=True, waits=True)),
    edges=(_e("next_gap", "ask", "a_gap"), _e("ask", "reply"),
           _e("reply", "family", Command.DESCRIBE.value), _e("family", "reply", "understood")),
)


def test_an_acting_node_that_does_not_wait_passes_straight_on_when_its_work_names_nothing():
    """`ask` queues the phrasing and the session goes on to the question (plan 1c)."""
    entered = []

    def enter(node):
        entered.append(node)
        return {"next_gap": "a_gap"}.get(node)

    ran = run(PASSING, "next_gap", None, enter)
    assert ran.at == "reply" and entered == ["next_gap", "ask"]


def test_an_acting_node_that_waits_still_rests_when_its_work_names_nothing():
    ran = run(PASSING, "reply", Command.DESCRIBE.value, lambda node: None)
    assert ran.at == "family"


# ── forks (spec §12) ─────────────────────────────────────────────────────────────────────────

from comeni_core.settings.declare import Setting  # noqa: E402
from comeni_flow.forks import DEFAULT  # noqa: E402
from mendel_authoring.forks import SettingSubject, Snapshot  # noqa: E402

_PACING = Setting.choice(
    key="building.pacing", label="Pacing", help="A setting used by the fork tests.",
    options=[("together", "T"), ("stop_where_needed", "S")], default="together",
)
_NAME = Setting.text(
    key="dev.name", label="A name", help="A setting used by the fork tests.", default=""
)


def _forking(subject, cases):
    nodes = (
        _n("go", waits=True),
        Node(id="pace", stage="s", actor=Actor.ENGINE, label=subject.title,
             phase=Phase.GATHERING, built=True, fork=subject),
        *[_n(target, waits=True) for target in dict.fromkeys(cases.values())],
    )
    edges = (
        _e("go", "pace", Command.ANSWER_GAP.value),
        *[Edge(source="pace", target=t, case=c, built=True) for c, t in cases.items()],
    )
    return authoring_protocol(stages=(Stage(id="s", title="s"),), nodes=nodes, edges=edges)


PACED = _forking(SettingSubject.of(_PACING), {"together": "walk", "stop_where_needed": "quiet"})


def test_a_fork_takes_the_case_its_setting_is_in():
    ran = run(PACED, "go", Command.ANSWER_GAP.value, lambda node: None,
              snapshot=Snapshot(settings={"building.pacing": "stop_where_needed"}))
    assert ran.at == "quiet" and ran.path == ["pace", "quiet"]


def test_a_fork_with_no_snapshot_takes_its_settings_default():
    """Review Focus 5: until 3b passes one, the shell passes none."""
    assert run(PACED, "go", Command.ANSWER_GAP.value, lambda node: None).at == "walk"


def test_an_open_subject_takes_its_default_for_an_unlisted_value():
    named = _forking(SettingSubject.of(_NAME), {"alice": "walk", DEFAULT: "quiet"})
    ran = run(named, "go", Command.ANSWER_GAP.value, lambda node: None,
              snapshot=Snapshot(settings={"dev.name": "bob"}))
    assert ran.at == "quiet"


def test_a_value_no_edge_takes_is_refused_naming_the_fork_and_the_value():
    with pytest.raises(Refused, match="MI0216") as caught:
        run(PACED, "go", Command.ANSWER_GAP.value, lambda node: None,
            snapshot=Snapshot(settings={"building.pacing": "sometimes"}))
    assert "pace" in str(caught.value) and "sometimes" in str(caught.value)


def test_a_fork_is_never_entered():
    entered = []
    run(PACED, "go", Command.ANSWER_GAP.value, lambda node: entered.append(node))
    assert entered == []


def test_a_case_whose_edge_is_still_planned_is_refused():
    nodes = (
        _n("go", waits=True),
        Node(id="pace", stage="s", actor=Actor.ENGINE, label="Pacing",
             phase=Phase.GATHERING, built=True, fork=SettingSubject.of(_PACING)),
        _n("walk", waits=True),
        Node(id="quiet", stage="s", actor=Actor.ENGINE, label="quiet"),
    )
    edges = (
        _e("go", "pace", Command.ANSWER_GAP.value),
        Edge(source="pace", target="walk", case="together", built=True),
        Edge(source="pace", target="quiet", case="stop_where_needed"),
    )
    half = authoring_protocol(stages=(Stage(id="s", title="s"),), nodes=nodes, edges=edges)
    with pytest.raises(Refused, match="MI0216") as caught:
        run(half, "go", Command.ANSWER_GAP.value, lambda node: None,
            snapshot=Snapshot(settings={"building.pacing": "stop_where_needed"}))
    assert "pace" in str(caught.value) and "stop_where_needed" in str(caught.value)
