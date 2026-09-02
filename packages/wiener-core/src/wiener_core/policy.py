"""What to do about a run — decided, never performed.

`decide()` returns typed `Intent`s; `wiener-api` carries them out. That split is what keeps
§6's replay claim exact: a model in this function would make the same events produce different
decisions, and an approximate replay cannot answer *why did it give up at 04:12*.

**`now_ms` is a parameter.** §6.1 — this package does not read a clock, and
`tests/guards/test_no_clock.py` is what holds that rather than this sentence.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from wiener_core.state import RunPhase, RunState


class IntentKind(StrEnum):
    RELAUNCH = "relaunch"
    CANCEL = "cancel"
    ESCALATE = "escalate"
    NOTIFY = "notify"
    GIVE_UP = "give_up"


class Reason(StrEnum):
    """Why an intent exists. **A declared enum, never free text** — §5.2.

    An intent is replayed and audited, so its reason has to mean the same thing to the console,
    the audit row and the test that asserts a three-day run decided what it decided. A sentence
    would mean whichever of those the author was looking at.
    """

    RUN_FAILED = "run_failed"
    NO_EVENTS = "no_events"
    OPERATOR_REQUEST = "operator_request"


class Intent(BaseModel):
    """Something Wiener wants done. Produced here; performed by `wiener-api`."""

    model_config = ConfigDict(frozen=True)

    kind: IntentKind
    because: Reason
    at_ms: int
    needs_approval: bool = True


class Policy(BaseModel):
    """Declared data, not code. What a laboratory is willing to have decided for it."""

    model_config = ConfigDict(frozen=True)

    lost_after_ms: int = 30 * 60 * 1000
    """**Blunt on purpose** — §17. A six-hour STAR align emits nothing while it runs and looks
    identical to a dead head process, so this window must exceed the slowest single task."""
    escalate_on_failure: bool = True


def decide(state: RunState, policy: Policy, now_ms: int) -> list[Intent]:
    """Every action Wiener would take, given this state and this clock reading.

    Pure and total: no I/O, no clock, no randomness, and the same arguments give the same list
    in the same order. That is what makes §10.1's token cost a testable property rather than an
    invoice surprise, and it is why the model sits beside this function rather than inside it.
    """
    intents: list[Intent] = []

    if state.phase is RunPhase.FAILED and policy.escalate_on_failure:
        intents.append(Intent(kind=IntentKind.ESCALATE, because=Reason.RUN_FAILED,
                              at_ms=now_ms, needs_approval=False))

    if state.phase is RunPhase.RUNNING:
        # **Silence, not emptiness.** This read `not state.tasks`, so a run that submitted four
        # hundred tasks and then went quiet — the actual shape of a dead head process — was
        # never lost, and only a run that never started one could be. Silence is measured from
        # the last thing NEXTFLOW said; the heartbeat that wakes this check is deliberately not
        # one of those things (§17, and `RunState.last_activity_ms`).
        silent_since = state.last_activity_ms or state.started_at_ms or 0
        if now_ms - silent_since > policy.lost_after_ms:
            intents.append(Intent(kind=IntentKind.GIVE_UP, because=Reason.NO_EVENTS,
                                  at_ms=now_ms))

    return intents
