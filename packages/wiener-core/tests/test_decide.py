"""What Wiener wants done, and the fact that it only ever *wants* it.

`decide()` returns typed intents; `wiener-api` performs them. `docs/design/wiener.md` §5.2.
"""

from wiener_core.policy import IntentKind, Policy, decide
from wiener_core.state import EMPTY, RunPhase

RUNNING = EMPTY.model_copy(update={"phase": RunPhase.RUNNING, "started_at_ms": 0})
FAILED = EMPTY.model_copy(update={"phase": RunPhase.FAILED, "ended_at_ms": 1000})


def test_a_healthy_run_needs_nothing():
    assert decide(RUNNING, Policy(), now_ms=5_000) == []


def test_a_failed_run_escalates_once():
    kinds = [i.kind for i in decide(FAILED, Policy(), now_ms=5_000)]
    assert IntentKind.ESCALATE in kinds


def test_a_silent_run_is_declared_lost_after_the_policy_says_so():
    stale = RUNNING.model_copy(update={"tasks": {}, "last_seq": 3})
    intents = decide(stale, Policy(lost_after_ms=1_000), now_ms=999_999)
    assert IntentKind.GIVE_UP in [i.kind for i in intents]


def test_the_same_state_and_clock_give_the_same_decisions():
    """§6: same events in -> same decisions out. Two calls, byte-identical."""
    assert decide(FAILED, Policy(), now_ms=42) == decide(FAILED, Policy(), now_ms=42)


def test_a_heartbeat_is_not_a_sign_of_life():
    """**The whole of `LOST` detection turns on this** — §17 and `RunState.last_activity_ms`.

    The timer's heartbeat is what wakes the check. If it also counted as activity the check
    could never fire: a dead head process would look alive precisely because Wiener kept
    talking to itself.
    """
    from wiener_core.events import heartbeat
    from wiener_core.state import fold

    quiet = RUNNING.model_copy(update={"last_activity_ms": 1_000})
    later = fold(quiet, heartbeat(run_id="r1", at_ms=9_000_000, seq=99))
    assert later.last_activity_ms == 1_000, "a heartbeat moved the liveness clock"


def test_a_run_that_submitted_tasks_and_went_quiet_is_lost():
    """It read `not state.tasks`, so the only run it could call lost was one that never started
    a task — and a head process that dies mid-run is the actual shape of the problem."""
    busy = RUNNING.model_copy(update={
        "tasks": {1: object()}, "last_activity_ms": 1_000,
    })
    intents = decide(busy, Policy(lost_after_ms=60_000), now_ms=1_000 + 60_001)
    assert IntentKind.GIVE_UP in [i.kind for i in intents]


def test_a_run_that_spoke_recently_is_not_lost():
    busy = RUNNING.model_copy(update={"last_activity_ms": 1_000})
    assert decide(busy, Policy(lost_after_ms=60_000), now_ms=1_000 + 59_000) == []
