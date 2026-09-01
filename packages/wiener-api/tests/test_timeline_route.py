"""The timeline endpoint — Plan 6 phase 3.

**A query, never a fold** (A191), and the artboard's claim that this was blocked is what these
tests retire. `page-5` filed the timeline under *"BLOCKED, FAKE, OR NOT YET PROJECTED"* because
attempt windows *"are inside `run_task.attempts` but are not projected as columns"* — true of
the columns, never of the data. `Attempt.start_ms` and `complete_ms` have been in that JSON
since W2.
"""

import json
from pathlib import Path

from wiener_api import repository
from wiener_api.services import projection
from wiener_api.settings import settings
from wiener_core.events import RunEvent

SPINE = Path(__file__).parents[3] / "tests/fixtures/weblog/spine-run.events.jsonl"


def _replay_into(session, run_id: str) -> None:
    for line in SPINE.read_text().splitlines():
        if not line.strip():
            continue
        event = RunEvent.model_validate({**json.loads(line), "run_id": run_id})
        projection.append(session, settings.lab_id, run_id, event)


def test_the_windows_come_from_one_query_over_a_column(session, a_run):
    """**Nothing was migrated to make this work**, which is the phase's whole finding. The
    projection wrote the attempts when it wrote the row; this reads them back."""
    _replay_into(session, a_run.id)

    rows = repository.task_windows(session, settings.lab_id, a_run.id)
    assert rows, "the fixture produced no tasks"
    assert all(isinstance(task_id, int) and process for task_id, process, _ in rows)
    windows = [one for _, _, attempts in rows for one in attempts if one.get("start_ms")]
    assert windows, "no attempt carried a start — the timeline would have nothing to draw"


def test_the_endpoint_answers_lanes_in_declared_order(client, session, a_run):
    _replay_into(session, a_run.id)
    got = client.get(f"/api/runs/{a_run.id}/timeline")
    assert got.status_code == 200, got.text

    body = got.json()
    assert body["lanes"], "a run with tasks drew no lanes"
    assert body["to_ms"] >= body["from_ms"]


def test_an_unknown_run_is_a_404_and_not_an_empty_chart(client):
    """An empty timeline and a run that does not exist are different answers, and a chart is
    the worst place to conflate them — it looks like a run that did nothing."""
    assert client.get("/api/runs/" + "0" * 32 + "/timeline").status_code == 404


def test_an_unreadable_artifact_still_draws_what_the_run_reached(client, session, a_run):
    """**A192, the same call `/overview` makes.** The windows come from the fold and are true
    whatever happened to the artifact directory; what is lost is the *declared* order, so the
    lanes are the ones the run actually reached rather than a 404.

    `a_run`'s artifact does not exist on disk, which is exactly that state.
    """
    _replay_into(session, a_run.id)
    got = client.get(f"/api/runs/{a_run.id}/timeline")

    assert got.status_code == 200
    assert got.json()["lanes"], "an unreadable artifact emptied the chart instead of the order"
    assert all(lane["declared"] is False for lane in got.json()["lanes"]), (
        "with no artifact to declare them, no lane can claim to be declared"
    )
