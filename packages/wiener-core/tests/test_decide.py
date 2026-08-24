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
