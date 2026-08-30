"""Only the curves the record can honestly support.

`rn-series`: a scalar becomes an honest curve or it does not, and which depends on how it
distributes over its window. These hold all three branches.
"""

from wiener_core.series import Kind, series
from wiener_core.state import Attempt, TaskStatus


def _attempt(n=1, start=None, complete=None, **fields) -> Attempt:
    return Attempt(n=n, status=TaskStatus.COMPLETED, at_ms=start or 0,
                   start_ms=start, complete_ms=complete, **fields)


def test_a_reservation_is_exact_at_every_breakpoint():
    """**Boundaries, not bins.** Two attempts overlapping in the middle: 4 cpus, then 12, then 8.

    Binning first would smear the step across a bucket and report a number nobody reserved. The
    sweep puts a point at every instant the total actually changed.
    """
    got = series([
        _attempt(start=0, complete=300, cpus=4),
        _attempt(start=100, complete=200, cpus=8),
    ])
    cpu = next(c for c in got.curves if c.name == "cpu reserved")

    assert cpu.kind is Kind.EXACT
    assert [(p.at_ms, p.value) for p in cpu.points] == [
        (0, 4.0), (100, 12.0), (200, 4.0), (300, 0.0),
    ]


def test_a_running_task_does_not_release_at_the_edge():
    """**The artefact found by rendering the design boards.**

    Closing an open interval at the end of the window made the reservation curve fall to zero at
    the right edge — the exact artefact the derived curve is hatched to avoid, arriving on the
    half that is supposed to be exact. An attempt with no `complete_ms` is still holding.
    """
    got = series([
        _attempt(start=0, complete=100, cpus=2),
        _attempt(start=50, complete=None, cpus=6),
    ])
    cpu = next(c for c in got.curves if c.name == "cpu reserved")

    assert cpu.points[-1].value == 6.0, "the running attempt still holds its reservation"
    assert got.open is True, "and the page must be able to say why the edge is high"


def test_there_is_no_memory_over_time_curve():
    """**The absence is the design**, and it is the tempting one.

    `peak_rss_bytes` is on `Attempt`, summing it is one more line, and every dashboard in this
    space draws it. It is the highest value a task ever *touched* — summing peaks across live
    attempts describes an instant that never happened.

    `Kind` has two members and no third, so there is nowhere in the type to record a curve whose
    shape cannot be trusted. This asserts the same thing from outside.
    """
    got = series([_attempt(start=0, complete=100, cpus=1, peak_rss_bytes=8_000_000_000)])

    names = [c.name for c in got.curves]
    assert not any("peak" in n for n in names)
    assert not any("rss" in n for n in names)
    assert [k.value for k in Kind] == ["exact", "derived"], (
        "a third Kind is somewhere to put a curve that should not exist"
    )


def test_a_total_is_derived_and_says_so():
    """`read_bytes` is a TOTAL divided over its window: area-true, shape-false."""
    got = series([_attempt(start=0, complete=2000, cpus=1, read_bytes=1000)])
    read = next(c for c in got.curves if c.name == "read")

    assert read.kind is Kind.DERIVED
    assert read.unit == "bytes/s"
    # 1000 bytes over 2 seconds — the integral is preserved, the shape is invented.
    assert read.points[0].value == 500.0


def test_a_running_attempt_contributes_no_derived_curve():
    """**`RunEarly`, in the pure layer.** A total divided by an unknown duration is not
    area-true, so an attempt still in flight contributes nothing to a derived curve — the
    reservation is live and exact and the derived half arrives at the first completion.

    That is why the panel is *cpu reserved* before any task ends and gains its second curve and
    its second name later, rather than being a two-curve chart with one curve missing."""
    got = series([_attempt(start=0, complete=None, cpus=4, read_bytes=1000)])

    assert [c.name for c in got.curves] == ["attempts in flight", "cpu reserved"]


def test_a_run_without_trace_says_so_rather_than_drawing_zeroes():
    """§4.3 finding 6: without `trace.enabled` the resource fields are absent entirely. **Absent
    is not zero** — an empty curve claims a run that used nothing."""
    got = series([_attempt(start=0, complete=100)])

    assert got.reported_resources is False
    assert [c.name for c in got.curves] == ["attempts in flight"], (
        "the countable curve is still exact and still honest"
    )


def test_nothing_started_is_an_empty_series_and_not_a_crash():
    assert series([]).curves == []
    assert series([_attempt(start=None)]).curves == []


def test_it_reads_no_clock():
    """Invariant 1, and §6.1's *same events in, same decisions out*. The window ends at the last
    RECORDED boundary, so the answer does not change between two calls a second apart."""
    attempts = [_attempt(start=0, complete=None, cpus=2)]
    assert series(attempts) == series(attempts)
    assert series(attempts).to_ms == 0, "the last recorded boundary, not a clock"
