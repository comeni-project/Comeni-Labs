"""What Wiener agrees to accept, held to a real capture.

`docs/design/wiener.md` §4.4. The fixture is thirteen events from an actual Nextflow 25.10.4
run — `tests/fixtures/weblog/failing-run.jsonl` — and every assertion here is about that file
rather than about what a designer imagined a run looks like.
"""

import json
from pathlib import Path

import pytest
from wiener_core.events import EventKind, admit, heartbeat

FIXTURE = Path(__file__).parents[3] / "tests/fixtures/weblog/failing-run.jsonl"


def _bodies() -> list[dict]:
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]


def test_every_event_in_a_real_capture_is_admitted():
    """If admit() refuses one, either the allowlist is wrong or Nextflow changed — and both
    are worth failing over rather than dropping silently."""
    events = [admit(b, run_id="r1", seq=i) for i, b in enumerate(_bodies())]
    assert len(events) == 13
    assert events[0].kind is EventKind.STARTED
    assert [e.kind for e in events].count(EventKind.COMPLETED) == 2
    assert events[-1].kind is EventKind.ERROR


def test_the_error_event_carries_no_trace():
    """§4.3 finding 1: `error` is {runId, runName, event, utcTime} and nothing else. A design
    that waits for it to learn what broke learns nothing."""
    err = next(admit(b, run_id="r1", seq=0) for b in _bodies() if b["event"] == "error")
    assert err.trace is None


def test_an_undeclared_field_is_dropped_rather_than_stored():
    body = dict(_bodies()[1])
    body["trace"] = dict(body["trace"], invented_by_a_future_nextflow="danger")
    event = admit(body, run_id="r1", seq=1)
    assert not hasattr(event.trace, "invented_by_a_future_nextflow")


def test_an_unknown_event_kind_is_refused_not_ignored():
    with pytest.raises(ValueError, match="MW0001"):
        admit({"event": "process_teleported", "runId": "x", "utcTime": "2026-08-23T20:00:00Z"},
              run_id="r1", seq=0)


def test_a_heartbeat_may_not_arrive_from_the_network():
    """A175. The heartbeat is Wiener's own timer speaking — §6.1 — and `EventKind` declaring
    it must not make it postable. The ingest endpoint is loopback behind a per-run secret
    (§13.1), so this is not the last line of defence; it is the line that does not depend on
    remembering, which is the whole argument for an allowlist."""
    with pytest.raises(ValueError, match="MW0002"):
        admit({"event": "heartbeat", "runId": "x", "utcTime": "2026-08-23T20:00:00Z"},
              run_id="r1", seq=0)


def test_the_timer_can_make_one_and_the_fold_will_see_it():
    beat = heartbeat(run_id="r1", at_ms=1_787_517_650_000, seq=7)
    assert beat.kind is EventKind.HEARTBEAT and beat.trace is None and beat.at_ms


def test_a_lab_string_is_marked_on_the_type():
    """§4.3 finding 4: the dangerous fields are STRUCTURED. `script` holds the command
    including file names, `workdir` is a path, `name` and `tag` carry the sample tag. §10.2's
    redactor filters on this marking, so a field that gains laboratory words without gaining
    the mark leaks quietly — this is what makes that a test rather than a habit."""
    from typing import get_args, get_type_hints

    from wiener_core.events import LabString, TaskTrace

    def marked(hint) -> bool:
        # `script` and friends are `Annotated[str, LAB_STRING] | None`, so the metadata sits
        # one level inside the union — a check that only reads `__metadata__` sees `name` and
        # misses the three optional fields, which are the ones carrying paths.
        if any(isinstance(m, LabString) for m in getattr(hint, "__metadata__", ())):
            return True
        return any(marked(arg) for arg in get_args(hint))

    hints = get_type_hints(TaskTrace, include_extras=True)
    assert {n for n, h in hints.items() if marked(h)} == {"name", "script", "workdir", "tag"}
