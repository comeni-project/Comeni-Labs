# packages/wiener-core/tests/test_fold.py
import json
from pathlib import Path

from wiener_core.events import admit, heartbeat
from wiener_core.state import EMPTY, RunPhase, replay

FIXTURE = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"


def _attempts(state) -> dict[int, list[int]]:
    return {t.task_id: [a.n for a in t.attempts] for t in state.tasks.values()}


def _events():
    bodies = [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]
    return [admit(b, run_id="r1", seq=i) for i, b in enumerate(bodies)]


def test_a_real_run_folds_to_the_state_it_ended_in():
    state = replay(_events())
    assert state.phase is RunPhase.FAILED
    assert state.counts.succeeded == 2
    assert state.counts.failed == 1


def test_the_fold_is_idempotent():
    """§4.3 finding 2: `completed` arrived TWICE with byte-identical payloads. This is that
    finding as a property rather than as an `if` somewhere."""
    events = _events()
    assert replay(events) == replay(events + events)


def test_terminality_does_not_depend_on_arrival_order():
    """§4.3 finding 3: `error` arrived AFTER `completed`. Anything that closes a run on
    `completed` and stops listening records a failed run as successful."""
    events = _events()
    reversed_tail = events[:-2] + list(reversed(events[-2:]))
    assert replay(events).phase is replay(reversed_tail).phase is RunPhase.FAILED


def test_a_retry_is_history_rather_than_an_overwrite():
    """A176. `>= 1` was the original assertion and it passed for the wrong reason: a task
    that ran ONCE is described by three events — submitted, started, completed — and an
    append-per-event fold gave it three attempts. One attempt per `trace.attempt`, whatever
    the event count."""
    state = replay(_events())
    counted = {t.task_id: [a.n for a in t.attempts] for t in state.tasks.values()}
    assert all(len(ns) == len(set(ns)) for ns in counted.values()), (
        f"a task carries the same attempt number twice: {counted}. Three events describe one "
        "try — submitted, started, completed — so an append-per-event fold gives a task that "
        "never retried three attempts, and §9.1 draws a retry ring on it. Key by "
        "trace.attempt; do not append."
    )
    assert all(len(ns) == 1 for ns in counted.values()), (
        f"no task in this capture was retried, so each must carry one attempt: {counted}"
    )


def test_a_redelivered_event_does_not_invent_an_attempt():
    """A176. §4.3 finding 2 is that Nextflow sent an identical event twice — over HTTP, so
    the copy is assigned a FRESH seq at ingest (§6.2) and `seq <= last_seq` never sees it.
    Duplicating the list is what the idempotence test does; this is what the network does."""
    events = _events()
    done = next(e for e in events if e.trace and e.trace.status.name == "COMPLETED")
    again = done.model_copy(update={"seq": len(events)})
    once, twice = replay(events), replay([*events, again])
    # `last_seq` is the one field that legitimately moves: a second body really did arrive.
    assert once == twice.model_copy(update={"last_seq": once.last_seq}), (
        "folding a redelivered body changed the run. seq <= last_seq cannot catch this — the "
        "copy is assigned a fresh seq at ingest — so every field the fold writes must be a "
        "function of what has been seen rather than of how often. A176.\n"
        f"  attempts once:  {_attempts(once)}\n"
        f"  attempts twice: {_attempts(twice)}"
    )


def test_a_heartbeat_does_not_start_a_run_that_has_not_started():
    """A175's consequence: the fold now sees a kind carrying no trace and no manifest, and
    the phase must come from what the run has done rather than from time passing."""
    assert replay([heartbeat(run_id="r1", at_ms=1, seq=0)]).phase is RunPhase.QUEUED


def test_an_empty_run_is_queued():
    assert EMPTY.phase is RunPhase.QUEUED and EMPTY.counts.succeeded == 0
