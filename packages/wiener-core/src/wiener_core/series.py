"""What a run held over time — and only the curves the record can honestly support.

═══ THE RULE, AND IT HAS THREE BRANCHES ═══════════════════════════════════════════════════

Wiener has **no samples**. The trace gives one summary row per task attempt, so every series
here is derived from task *windows*, and whether that is honest depends on how the scalar
distributes over its window (`rn-series`):

1. **A RESERVATION is constant over the window → the series is EXACT.** `cpus` and
   `memory_bytes` are what Nextflow *held* for the whole task lifetime, so summing them over
   live attempts is the true reservation curve — not synthetic at all. The same is true of
   anything **countable**: attempts in flight, completions, queue depth.

2. **A TOTAL divides over the window → area-true, shape-false.** `read_bytes` is a total and
   `pct_cpu` a mean. Spreading either uniformly preserves the integral and **invents the
   shape**. Drawable, and it must be drawn **stepped** and labelled derived — smoothness is the
   visual grammar of *I measured this*.

3. **A PEAK does not distribute at all → it is a bound, not a series.** `peak_rss_bytes` is the
   highest value a task ever touched; summing peaks across live attempts describes an instant
   that never happened. **There is no memory-over-time curve at any fidelity**, and `Kind` has
   no third member to put one in. Drawing it would be exactly the failure the product claim
   exists to prevent, and it is the tempting one — it is the number everybody asks for.

═══ BOUNDARIES, NOT BINS ══════════════════════════════════════════════════════════════════

`+delta` at the start of an interval, `−delta` at its end, sort, prefix-sum. Exact at every
breakpoint, no bucketing artefacts, and 5,000 tasks is 10,000 events rather than a scan per bin.
**Bin only to render** — and size the bin off the run's own duration, or a 40-second stub run
collapses to a single point.

═══ NO CLOCK ═════════════════════════════════════════════════════════════════════════════

`wiener_core` is pure (invariant 1) and a separate scan holds `datetime.now` out of it. A series
is the most tempting place in this package to read one, because *how long has this been running*
is a question about now — and §6.1's claim that the same events give the same decisions dies the
first week one is read. The window ends at the last **recorded** boundary, never at a clock.

**A running attempt does not release its reservation at the end of the window.** Closing an open
interval at `now` made the reservation curve fall to zero at the right edge — the exact artefact
the derived curve is hatched to avoid, arriving on the half that is supposed to be exact. It was
found by rendering the design boards, and `.design/runs_boards.py` carries the same note.
"""

from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from wiener_core.state import Attempt


class Kind(StrEnum):
    """How much a curve's shape can be trusted.

    **Two members, and the absence of a third is the design.** A peak has no honest shape, so
    there is nowhere in this type to record one — which is a stronger guarantee than a comment
    asking nobody to try.
    """

    EXACT = "exact"
    """A reservation or a count. Constant across its window, so the sum is the truth."""
    DERIVED = "derived"
    """A total or a mean, spread uniformly. **Area-true, shape-false.** Draw it stepped."""


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    at_ms: int
    value: float


class Curve(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: Kind
    unit: str
    points: list[Point] = []


class Series(BaseModel):
    """Every curve a run's attempts can honestly support, and the window they cover."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    curves: list[Curve] = []
    from_ms: int = 0
    to_ms: int = 0
    open: bool = False
    """Whether any attempt was still running at `to_ms`.

    **The right edge means something different when this is true.** A curve that ends high
    because work is still in flight reads identically to one that ends high because the run
    stopped badly, and only this field distinguishes them.
    """
    bin_ms: int = 0
    """**How wide a rendering bin should be — a suggestion, not something already applied.**

    The sweep is exact at every breakpoint and stays that way; this is the *renderer's* bin,
    derived from the run's own recorded span so it scales with the run rather than with a
    constant somebody picked for a four-hour job. A 40-second stub run gets sub-second bins and
    keeps its shape, where a fixed minute would collapse it to one point (`rn-series`).

    `0` when nothing started, which is the same absence the empty curve list reports.
    """
    reported_resources: bool = False
    """Whether any attempt carried the `trace.enabled` fields at all.

    `False` means the run was launched without them — §4.3 finding 6 — and the page owes one
    sentence rather than four empty charts. **Absent is not zero**, and an empty curve claims a
    run that used nothing.
    """


def _sweep(events: list[tuple[int, float]]) -> list[Point]:
    """Prefix-sum a list of `(at_ms, delta)` boundaries into a step curve."""
    events.sort()
    out: list[Point] = []
    running = 0.0
    for at_ms, delta in events:
        running += delta
        # One point per distinct instant: several attempts starting together are one step, not
        # a stack of coincident points a renderer would draw over itself.
        if out and out[-1].at_ms == at_ms:
            out[-1] = Point(at_ms=at_ms, value=running)
        else:
            out.append(Point(at_ms=at_ms, value=running))
    return out


def series(attempts: Sequence[Attempt]) -> Series:
    """Every honest curve over these attempts.

    **It takes attempts, not a `RunState`, and that is deliberate.** `overview()` and `spans()`
    both take the folded state and `rn-series` describes this as *the same shape* — but
    `rn-blocked` says this one must not be a fold in the request, and taking a `RunState` forces
    the caller to have folded one. Attempts are the minimum this needs, and they are a column:
    `run_task.attempts`. `TaskState` could not be rebuilt from that projection anyway, since
    `first_seen_ms` is not stored.
    """
    started = [a for a in attempts if a.start_ms is not None]
    if not started:
        return Series()

    from_ms = min(a.start_ms for a in started)  # type: ignore[type-var]
    # **The window ends at the last RECORDED boundary.** Not a clock — see the module header.
    to_ms = max(
        [a.complete_ms for a in started if a.complete_ms is not None]
        + [a.start_ms for a in started],  # type: ignore[list-item]
    )
    still_running = any(a.complete_ms is None for a in started)

    in_flight: list[tuple[int, float]] = []
    cpus: list[tuple[int, float]] = []
    memory: list[tuple[int, float]] = []
    read: list[tuple[int, float]] = []
    write: list[tuple[int, float]] = []
    reported = False

    for a in started:
        start = a.start_ms
        assert start is not None
        # **An open interval stays open.** `complete_ms is None` means the reservation is still
        # held; the curve does not fall at the right edge because the clock says so.
        end = a.complete_ms

        in_flight.append((start, 1.0))
        if end is not None:
            in_flight.append((end, -1.0))

        if a.cpus is not None:
            reported = True
            cpus.append((start, float(a.cpus)))
            if end is not None:
                cpus.append((end, -float(a.cpus)))

        if a.memory_bytes is not None:
            reported = True
            memory.append((start, float(a.memory_bytes)))
            if end is not None:
                memory.append((end, -float(a.memory_bytes)))

        # **Totals only where the window is closed.** A total divided by an unknown duration is
        # not area-true, so a running attempt contributes no derived curve at all — which is
        # `RunEarly`'s state: the reservation is live and exact, and the derived half arrives at
        # the first completion.
        if end is not None and end > start:
            span = (end - start) / 1000.0
            for total, into in ((a.read_bytes, read), (a.write_bytes, write)):
                if total is None:
                    continue
                reported = True
                rate = total / span
                into += [(start, rate), (end, -rate)]

    curves = [
        Curve(name="attempts in flight", kind=Kind.EXACT, unit="tasks",
              points=_sweep(in_flight)),
    ]
    if cpus:
        curves.append(Curve(name="cpu reserved", kind=Kind.EXACT, unit="cpus",
                            points=_sweep(cpus)))
    if memory:
        curves.append(Curve(name="memory reserved", kind=Kind.EXACT, unit="bytes",
                            points=_sweep(memory)))
    if read:
        curves.append(Curve(name="read", kind=Kind.DERIVED, unit="bytes/s",
                            points=_sweep(read)))
    if write:
        curves.append(Curve(name="written", kind=Kind.DERIVED, unit="bytes/s",
                            points=_sweep(write)))

    # **There is deliberately no `peak_rss_bytes` curve here.** `Attempt` carries it, summing it
    # would be one more line, and every dashboard in this space draws it. It describes an instant
    # that never happened. `test_there_is_no_memory_over_time_curve` holds the absence.

    # **Derived from the recorded span, never from a clock or a constant.** ~120 buckets is a
    # width a chart can draw; the floor keeps a run that recorded a single instant from asking
    # for a zero-width bin.
    span = max(to_ms - from_ms, 0)
    bin_ms = max(span // 120, 1)

    return Series(
        curves=curves,
        from_ms=from_ms,
        to_ms=to_ms,
        bin_ms=bin_ms,
        open=still_running,
        reported_resources=reported,
    )
