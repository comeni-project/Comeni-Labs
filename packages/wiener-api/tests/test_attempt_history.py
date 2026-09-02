"""A retry that asked for more memory is the whole reason retries are kept as history (§5.1) —
and until now the escalation was in a JSON blob and out of reach of every reader.
"""

import json
from pathlib import Path

from wiener_api.services import projection
from wiener_api.settings import settings
from wiener_core.events import RunEvent

SPINE = Path(__file__).parents[3] / "tests/fixtures/weblog/spine-run.events.jsonl"


def _replay_into(session, run_id: str) -> None:
    for line in SPINE.read_text().splitlines():
        if line.strip():
            projection.append(session, settings.lab_id, run_id,
                              RunEvent.model_validate({**json.loads(line), "run_id": run_id}))


def _rows(client, run_id: str) -> list[dict]:
    return client.get(f"/api/runs/{run_id}/tasks").json()["tasks"]


def _kill_a_task(session, run_id: str) -> None:
    """Replay one more `process_completed`, for a task that exited on a signal.

    `137` and nothing else: it is 128+9, and `wiener_core.signals` glosses it `SIGKILL` while
    refusing to say what sent it. A preemption, a `kill -9` and a cgroup limit are the same code.
    """
    last = [json.loads(line) for line in SPINE.read_text().splitlines() if line.strip()][-2]
    killed = {
        **last,
        "seq": last["seq"] + 100,
        "at_ms": last["at_ms"] + 1000,
        "trace": {**last["trace"], "task_id": 99, "process": "STAR_ALIGN",
                  "name": "STAR_ALIGN (killed)", "status": "FAILED", "exit": 137},
    }
    projection.append(session, settings.lab_id, run_id,
                      RunEvent.model_validate({**killed, "run_id": run_id}))


def test_a_row_carries_what_each_attempt_asked_for_beside_what_it_touched(client, session,
                                                                         a_run):
    """**Both halves, or neither is worth showing.** `peak_rss_bytes` alone says a task touched
    47 GB and leaves *was that a lot?* to the reader; the reservation is the other half, and it
    was on `Attempt` and on no row anybody could read."""
    _replay_into(session, a_run.id)
    rows = _rows(client, a_run.id)

    assert rows, "the fixture produced tasks"
    for row in rows:
        assert len(row["history"]) == row["attempts"], "the count and the history agree"
        assert [one["n"] for one in row["history"]] == sorted(one["n"] for one in row["history"])

    touched = [one for row in rows for one in row["history"] if one["peak_rss_bytes"]]
    assert touched, "this fixture recorded resources"
    assert any(one["memory_bytes"] for one in touched), (
        "and the reservation travels with the peak, which is the pair the panel needs"
    )


def test_a_single_attempt_task_still_ships_its_history(client, session, a_run):
    """It is not only for retries. One try still carries asked beside touched, which no other
    field on the row does — dropping it for unretried tasks would make the common row the one
    that cannot answer the question."""
    _replay_into(session, a_run.id)
    once = [row for row in _rows(client, a_run.id) if row["attempts"] == 1]

    assert once, "the fixture has tasks that succeeded first time"
    assert all(len(row["history"]) == 1 for row in once)


def test_the_row_glosses_a_signal_and_names_no_cause(client, session, a_run):
    """§18.1. `137` reaches the browser as `SIGKILL` — the 128+n convention — and never as a
    reason. Nothing explains a failure until W3, and the row must not be where that slips in.

    **The spine fixture has no signalled attempt**, so the `if one["signal"]` branch below — the
    whole §18.1 rule — never ran, and the test passed while glossing nothing. One killed attempt
    is appended here rather than added to the shared fixture: `spine-run.events.jsonl` is a real
    recorded run and the value of a recording is that nobody edits it.
    """
    _replay_into(session, a_run.id)
    _kill_a_task(session, a_run.id)
    rows = _rows(client, a_run.id)

    glossed = [one for row in rows for one in row["history"] if one["signal"]]
    assert glossed, "no attempt was signalled — the rule this test holds would not be exercised"
    assert [one["signal"] for one in glossed] == ["SIGKILL"]

    for one in (one for row in rows for one in row["history"]):
        if one["exit"] in (None, 0):
            assert one["signal"] is None, "an ordinary exit is not a signal"
        if one["signal"]:
            assert one["signal"].startswith("SIG") and " " not in one["signal"], (
                f"a gloss, not a sentence: {one['signal']!r}"
            )
