"""Stage ④ over the real protocol, with a fake `enter` (spec §14.4): the arrows, not the work.

Pacing, then Dev mode, both decided before the walk; then `step` places what does not stop and
rests on one card, which a person continues or changes; a change runs through `amend`."""

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
    ("pacing", "through"), [("together", "together"), ("stop_where_needed", "quiet")]
)
@pytest.mark.parametrize(("dev", "gaps"), [(True, "show_gaps"), (False, "hide_gaps")])
def test_each_pacing_and_dev_case_reaches_the_first_card(pacing, through, dev, gaps):
    ran, entered = _walk(
        "card", Command.CONFIRM_GOAL.value, {"resolve": "stored", "step": "stops"},
        **{"building.pacing": pacing, "dev.mode": dev},
    )
    assert through in entered and gaps in entered and ran.at == "step_card"
    assert entered.index(through) < entered.index(gaps) < entered.index("step"), (
        "both forks are decided before the walk"
    )


def test_ask_rests_on_the_pacing_question_and_its_answer_reaches_dev():
    ran, _ = _walk("card", Command.CONFIRM_GOAL.value, {"resolve": "stored"},
                   **{"building.pacing": "ask"})
    assert ran.at == "pace_q"
    ran, entered = _walk("pace_q", Command.CHOOSE_PACING.value, {"step": "stops"},
                         **{"dev.mode": False})
    assert "hide_gaps" in entered and ran.at == "step_card"


def test_continue_walks_on_to_the_wrap_up():
    ran, _ = _walk("step_card", Command.CONTINUE.value, {"step": "none_left"})
    assert ran.at == "wrap"


def test_a_change_is_resolved_again_before_the_walk_goes_on():
    ran, entered = _walk("step_card", Command.AMEND.value, {"amend": "amended", "step": "stops"})
    assert entered[:2] == ["amend", "step"] and ran.at == "step_card"


def test_the_two_forks_read_pacing_and_dev_mode():
    assert PROTOCOL.fork_keys() == {"building.pacing", "dev.mode"}


def test_a_quiet_walk_of_any_length_is_one_entry_of_step():
    """Review Focus 5 (issue 258): no arrow leads from `step` back to itself, and nothing
    between a gap and the next step passes the interpreter — so a walk with nothing to stop on is
    one entry of `step`, however many steps (the handler places them all inside it)."""
    assert not any(e.source == "step" and e.target == "step" for e in PROTOCOL.edges)
    assert not {"route_around", "show_gap", "held", "fact", "reresolve", "choice"} & {
        n.id for n in PROTOCOL.nodes
    }
    ran, entered = _walk("hide_gaps", None, {"step": "none_left"})
    assert entered.count("step") == 1 and ran.at == "wrap"


@pytest.mark.parametrize('at', ['reply', 'card', 'step_card', 'wrap', 'stopped'])
def test_corrections_from_each_resting_phase_resolve_and_cascade_before_the_walk(at):
    ran, entered = _walk(at, 'correct_fact', {
        'correct_fact': 'selected', 'resolve_correction': 'resolved',
        'cascade_reviews': 'review_again', 'step': 'stops',
    })
    assert entered[:3] == ['correct_fact', 'resolve_correction', 'cascade_reviews']
    assert ran.at == 'step_card'


def test_an_unbuildable_correction_can_stop_and_then_be_corrected_again():
    ran, entered = _walk('wrap', 'correct_fact', {
        'correct_fact': 'selected', 'resolve_correction': 'blocked',
        'correction_blocked': 'essential_missing',
    })
    assert ran.at == 'stopped'
    assert 'correction_blocked' in entered
    ran, _ = _walk(ran.at, 'correct_fact', {
        'correct_fact': 'gather_again', 'list_needs': 'listed', 'next_gap': 'a_gap',
    })
    assert ran.at == 'reply'


@pytest.mark.parametrize('suffix', ['gather', 'goal', 'build', 'complete'])
def test_each_disagreement_returns_through_a_declared_correction_path(suffix):
    ran, entered = _walk('disagree_' + suffix, 'answer_disagreement', {
        'correct_fact': 'selected', 'resolve_correction': 'resolved',
        'cascade_reviews': 'review_again', 'step': 'stops',
    })
    assert 'cascade_reviews' in entered and ran.at == 'step_card'


def test_busy_resolver_refuses_competing_corrections():
    from mendel_authoring.interpret import Refused

    with pytest.raises(Refused, match='MI0216'):
        _walk('resolve', 'correct_fact', {})
