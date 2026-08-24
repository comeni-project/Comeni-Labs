"""§9.3's numbers. Held to two real captures — one with resources and one without."""

import json
from pathlib import Path

from wiener_core.events import RunEvent, admit
from wiener_core.state import replay
from wiener_core.stats import stats

ROOT = Path(__file__).parents[3]
SPINE = ROOT / "tests/fixtures/weblog/spine-run.events.jsonl"
PLAIN = ROOT / "tests/fixtures/weblog/failing-run.jsonl"


def _spine():
    return replay([RunEvent.model_validate(json.loads(line))
                   for line in SPINE.read_text().splitlines() if line.strip()])


def _plain():
    bodies = [json.loads(line) for line in PLAIN.read_text().splitlines() if line.strip()]
    return replay([admit(b, run_id="r1", seq=i) for i, b in enumerate(bodies)])


def test_the_slowest_process_comes_first():
    """A reader opens this to find what took the time, so it is not sorted alphabetically."""
    rows = stats(_spine())
    assert rows[0].process == "STAR_ALIGN"
    assert rows[0].realtime_ms and rows[0].realtime_ms > 20_000


def test_both_halves_of_every_comparison_are_present():
    """A bare peak means nothing without what was asked for — §9.3."""
    star = next(row for row in stats(_spine()) if row.process == "STAR_ALIGN")
    assert star.memory_asked_bytes and star.memory_peak_bytes
    assert star.cpus_asked and star.cpu_used_pct
    assert star.realtime_ms and star.queue_wait_ms is not None


def test_a_run_without_trace_enabled_reports_absent_rather_than_zero():
    """§4.3 finding 6: the resource fields are opt-in. A zero would read as "this task used no
    memory", and a reader cannot tell a true zero from a missing one."""
    row = stats(_plain())[0]
    assert row.memory_peak_bytes is None and row.cpu_used_pct is None
    assert row.reported_resources is False
    assert row.tasks, "the tasks are still counted — only the resources are absent"


def test_the_maximum_is_kept_rather_than_the_mean():
    """The maximum is what kills a run and the mean is what hides it — §9.3, and this is the
    test that stops somebody averaging it later."""
    state = _spine()
    star = next(row for row in stats(state) if row.process == "STAR_ALIGN")
    peaks = [a.peak_rss_bytes for t in state.tasks.values() if t.process == "STAR_ALIGN"
             for a in t.attempts if a.peak_rss_bytes]
    assert star.memory_peak_bytes == max(peaks)
