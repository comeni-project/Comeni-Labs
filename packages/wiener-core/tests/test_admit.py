"""What Wiener agrees to accept, held to a real capture.

`docs/design/wiener.md` §4.4. The fixture is thirteen events from an actual Nextflow 25.10.4
run — `tests/fixtures/weblog/failing-run.jsonl` — and every assertion here is about that file
rather than about what a designer imagined a run looks like.
"""

import json
from pathlib import Path

import pytest
from wiener_core.events import EventKind, RunEvent, admit, heartbeat

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


RESOURCED = Path(__file__).parents[3] / "tests/fixtures/weblog/resourced-run.jsonl"


def test_the_resource_fields_survive_admit():
    """§4.3 finding 6 and §9.4. **The record cannot be back-filled**, so this is not a phase-3
    display concern: a run admitted without these has no resource history ever.

    The fixture is a second real capture, taken 2026-08-24 with `trace.enabled = true` — the
    committed `failing-run.jsonl` was taken *without* it, which is exactly why the first
    version of `TaskTrace` could drop all fifteen and every test still passed.
    """
    bodies = [json.loads(line) for line in RESOURCED.read_text().splitlines() if line.strip()]
    done = next(b for b in bodies if b["event"] == "process_completed")
    trace = admit(done, run_id="r1", seq=0).trace

    assert trace.pct_cpu is not None, "%cpu was dropped — §9.3's cpu comparison has no `got`"
    assert trace.peak_rss_bytes is not None, "peak_rss was dropped — the OOM story is gone"
    assert trace.rchar and trace.wchar, "the i/o counters were dropped"
    assert trace.cpu_model, "cpu_model was dropped"


def test_the_two_captures_differ_in_exactly_the_way_finding_6_says():
    """One run with `trace.enabled`, one without. If a future Nextflow starts sending the
    resource fields unconditionally, this fails and finding 6 gets revisited rather than
    quietly staying in the document as folklore."""
    without = [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]
    plain = next(b for b in without if b["event"] == "process_completed")
    assert "peak_rss" not in plain["trace"], (
        "the trace-less capture now carries peak_rss — finding 6 said the fields are opt-in, "
        "and that is no longer true of this Nextflow"
    )


def test_the_record_survives_being_read_back():
    """**`run_event` is the source of truth and everything else is a projection** — §7.1 — so
    an event that does not survive the round trip makes that sentence false.

    It did not. `payload` is written with `model_dump()`, which uses FIELD names, and
    `TaskTrace` validated only by ALIAS — so every aliased field came back `None` and
    `extra="ignore"` swallowed the evidence. `cpus`, `read_bytes` and `write_bytes` have no
    alias and survived, which is exactly why it was invisible: a span carried three of the nine
    resource attributes and looked merely sparse.

    Found by printing the spans at a checkpoint and asking why one number was missing.
    """
    body = next(b for b in _bodies() if b["event"] == "process_completed")
    once = admit(body, run_id="r1", seq=1)
    twice = RunEvent.model_validate(once.model_dump(mode="json"))
    assert twice == once, "the record does not survive being read back"


def test_a_resourced_event_survives_it_too():
    bodies = [json.loads(line) for line in RESOURCED.read_text().splitlines() if line.strip()]
    done = next(b for b in bodies if b["event"] == "process_completed")
    once = admit(done, run_id="r1", seq=1)
    twice = RunEvent.model_validate(once.model_dump(mode="json"))
    assert twice.trace.pct_cpu == once.trace.pct_cpu
    assert twice.trace.peak_rss_bytes == once.trace.peak_rss_bytes
    assert twice.trace.start_ms == once.trace.start_ms
