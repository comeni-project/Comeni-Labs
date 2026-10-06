"""Stage ④ over the real protocol, with a fake `enter` (spec §13.2): the arrows, not the work."""

import pytest
from mendel_authoring.forks import Snapshot
from mendel_authoring.interpret import run
from mendel_authoring.protocol import PROTOCOL
from mendel_authoring.types import Command


def _walk(at, command, outcomes, **settings):
    """Run from `at`; `outcomes` maps an acting node to what it returns (default `None`)."""
    entered = []

    def enter(node):
        entered.append(node)
        return outcomes.get(node)

    ran = run(PROTOCOL, at, command, enter, snapshot=Snapshot(settings=settings))
    return ran, entered


@pytest.mark.parametrize(
    ("pacing", "through"),
    [("together", "together"), ("stop_where_needed", "quiet")],
)
def test_each_pacing_reaches_the_first_step(pacing, through):
    ran, entered = _walk(
        "card", Command.CONFIRM_GOAL.value,
        {"resolve": "stored", "step": "held"}, **{"building.pacing": pacing},
    )
    assert through in entered and ran.at == "held"


def test_ask_rests_on_the_pacing_question():
    ran, _ = _walk("card", Command.CONFIRM_GOAL.value, {"resolve": "stored"},
                   **{"building.pacing": "ask"})
    assert ran.at == "pace_q"


def test_the_pacing_answer_goes_on_to_the_first_step():
    ran, _ = _walk("pace_q", Command.CHOOSE_PACING.value, {"step": "held"})
    assert ran.at == "held"


def test_dev_on_rests_on_the_gap_card():
    ran, entered = _walk("held", Command.CONTINUE.value, {"step": "a_gap"},
                         **{"dev.mode": True})
    assert "show_gap" in entered and ran.at == "held"


def test_dev_off_under_together_still_rests_on_the_steps_card():
    """Dev off hides the gap, not the step: under *together* the card still waits (found by
    the shell test, 3b run 2)."""
    ran, entered = _walk("held", Command.CONTINUE.value, {"step": "a_gap", "route_around": "held"},
                         **{"dev.mode": False})
    assert "route_around" in entered and ran.at == "held"


def test_dev_off_routes_around_and_walks_on():
    outcomes = {"step": "a_gap", "route_around": "placed"}
    calls = iter(["a_gap", "none_left"])
    entered = []

    def enter(node):
        entered.append(node)
        return next(calls) if node == "step" else outcomes.get(node)

    ran = run(PROTOCOL, "held", Command.CONTINUE.value, enter,
              snapshot=Snapshot(settings={"dev.mode": False}))
    assert "route_around" in entered and ran.at == "wrap"


def test_a_fact_runs_through_reresolve_back_to_the_step():
    ran, entered = _walk("fact", Command.ANSWER_GAP.value, {"step": "needs_choice"})
    assert entered[:2] == ["reresolve", "step"] and ran.at == "choice"


def test_a_choice_goes_on_to_the_next_step():
    ran, _ = _walk("choice", Command.CHOOSE.value, {"step": "none_left"})
    assert ran.at == "wrap"


def test_the_two_forks_read_pacing_and_dev_mode():
    assert PROTOCOL.fork_keys() == {"building.pacing", "dev.mode"}


def test_a_quiet_walk_enters_step_once_and_reaches_the_wrap_up():
    """Review Focus 3, the protocol's half: no arrow leads from `step` back to itself, so a walk
    with nothing to stop on is one entry of `step`, whatever its length. The handler's half (it
    places every quiet step inside that one entry) is the shell test
    `test_stop_where_needed_with_a_read_length_reaches_the_wrap_up`."""
    assert not any(e.source == "step" and e.target == "step" for e in PROTOCOL.edges)
    ran, entered = _walk("quiet", None, {"step": "none_left"})
    assert entered.count("step") == 1 and ran.at == "wrap"
