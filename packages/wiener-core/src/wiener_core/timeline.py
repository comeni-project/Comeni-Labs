"""Where every attempt sat in time, packed into lanes — Plan 6 phase 3.

═══ THE RULES, AND THEY ARE THE ARTBOARD'S ════════════════════════════════════════════════

`.design/canvas.json`, `page-5`, *"THE TIMELINE, RULE BY RULE"*. Each is quoted where it is
implemented, because each was arrived at by drawing the wrong thing first:

1. **A LANE IS A PROCESS**, in the order the artifact declares — *"so a process that has not
   been reached still has a lane, exactly as `overview()` gives it a row before the run gets
   there. The chart's height is known before the first event."* That is why `lanes()` takes
   `declared` and does not derive its lanes from the attempts it was given.

2. **SUB-ROWS ARE CONCURRENCY**, greedily packed — *"a finished row is reused."* Two attempts
   overlapping in time need two rows; two that do not, share one. Above `MAX_ROWS` the stack
   stops and the remainder is counted into a **density band**: *"never 5,000 rows."*

3. **A RETRY IS A SEPARATE BAR in the same lane.** *"`Attempt` is per-attempt precisely so the
   try that asked for more memory is visible; collapsing them loses the only interesting
   thing."* One `Bar` per attempt, never one per task.

4. **COLOUR IS STATUS, NEVER PROCESS** — the lane already carries identity, and *"the first
   draft coloured by process and a finished STAR task was indistinguishable from a running
   one."* A `Bar` therefore carries its status and nothing about which process it belongs to.

═══ NO CLOCK, AND IT IS THE SAME RULE `series.py` KEEPS ═══════════════════════════════════

`wiener-core` reads no clock (invariant 1's neighbour — `docs/design/wiener.md` §6.1: same
events in, same decisions out). A running attempt has **no `complete_ms`**, and closing it at
`now` inside this function would make the same events fold to a different picture every second.

So an open bar carries `end_ms: None` and `Timeline.open` says at least one exists. **The
renderer extends it to the right edge**, which is exactly what the envelope already does with
an open reservation — `series.py` keeps a running attempt's reservation to the right edge for
the same reason, and `curve.ts` draws it.

For **packing** an open bar occupies its sub-row forever, which is the truth: a running task
has not released its row.
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from wiener_core.state import Attempt, TaskStatus

# **Above this the stack stops and the remainder becomes a density band.** The artboard says
# *"above roughly 40 concurrent"*; the number is here rather than in the renderer because the
# decision is about what is honest to draw, not about how tall a div is.
MAX_ROWS = 40


class Bar(BaseModel):
    """One attempt, where it sat. **Not one task** — see rule 3."""

    model_config = ConfigDict(frozen=True)

    task_id: int
    attempt: int
    status: TaskStatus
    start_ms: int
    end_ms: int | None = None
    """`None` means *still running*, never *zero length*. The renderer extends it to the right
    edge; this module will not invent an end it was not told."""
    row: int = 0
    """Which sub-row inside the lane, from the greedy pack."""


class Lane(BaseModel):
    """One process, and every attempt of it."""

    model_config = ConfigDict(frozen=True)

    process: str
    declared: bool
    """False for a process the run ran that the artifact does not describe — `overview()` makes
    the same distinction and for the same reason: the artifact is the denominator."""
    bars: tuple[Bar, ...] = ()
    rows: int = 0
    dense: int = 0
    """How many attempts did not fit inside `MAX_ROWS` sub-rows. **Reported, never dropped
    silently** — a chart that quietly omits 4,960 bars is a chart that lies about a run."""


class Timeline(BaseModel):
    model_config = ConfigDict(frozen=True)

    lanes: tuple[Lane, ...] = ()
    from_ms: int = 0
    to_ms: int = 0
    open: bool = False
    """At least one attempt has no recorded end. The renderer draws to its own clock from here;
    this module does not have one."""


def _pack(bars: list[Bar]) -> tuple[tuple[Bar, ...], int, int]:
    """Greedy interval packing — *"a finished row is reused"*.

    Earliest start first, then into the first sub-row whose last bar has already ended. An
    **open** bar (`end_ms is None`) never frees its row, which is the honest reading: a running
    task still holds it.

    Returns the placed bars, how many rows were used, and how many bars did not fit.
    """
    bars.sort(key=lambda bar: (bar.start_ms, bar.task_id, bar.attempt))
    # `ends[i]` is when sub-row `i` came free. `None` means it never does.
    ends: list[int | None] = []
    placed: list[Bar] = []
    dense = 0

    for bar in bars:
        for row, free in enumerate(ends):
            if free is not None and free <= bar.start_ms:
                ends[row] = bar.end_ms
                placed.append(bar.model_copy(update={"row": row}))
                break
        else:
            if len(ends) >= MAX_ROWS:
                # The stack stops. Counted, so the lane can say so.
                dense += 1
                continue
            ends.append(bar.end_ms)
            placed.append(bar.model_copy(update={"row": len(ends) - 1}))

    return tuple(placed), len(ends), dense


def lanes(rows: Sequence[tuple[int, str, Sequence[Attempt]]],
          declared: Sequence[str]) -> Timeline:
    """Every attempt, packed into a lane per process.

    `rows` is `(task_id, process, attempts)` per task — the shape one indexed `SELECT` over
    `run_task` yields. **The task id is carried because a bar is a thing you click**: the
    artboard's *drill down in place* filters the table below by what you picked, and a bar that
    cannot name its task can only filter by process, which the lane label already does.

    **It takes rows rather than a `RunState` for the reason `series()` does**: a board is a
    query, never a fold in the request (A191), and taking a folded state would force the caller
    to replay every event a run ever produced.

    `declared` is the artifact's process list, in order, so a lane exists before the run reaches
    it and the chart's height is known before the first event.
    """
    by_process: dict[str, list[Bar]] = {}
    starts: list[int] = []
    ends: list[int] = []
    still_open = False

    for task_id, process, attempts in rows:
        for attempt in attempts:
            if attempt.start_ms is None:
                # Submitted and never started — it has no place on a time axis. It is still in
                # `overview()`'s counts, which is where *how many are waiting* is answered.
                continue
            bar = Bar(task_id=task_id, attempt=attempt.n, status=attempt.status,
                      start_ms=attempt.start_ms, end_ms=attempt.complete_ms)
            by_process.setdefault(process, []).append(bar)
            starts.append(attempt.start_ms)
            if attempt.complete_ms is None:
                still_open = True
            else:
                ends.append(attempt.complete_ms)

    if not starts:
        # **Lanes without bars, not an empty timeline.** The artboard's whole point is that the
        # height is known before the first event; a run that has started nothing still shows
        # what it is going to do.
        return Timeline(
            lanes=tuple(Lane(process=name, declared=True) for name in declared),
        )

    named = set(declared)
    order = list(declared) + [p for p in by_process if p not in named]

    built: list[Lane] = []
    for process in order:
        packed, used, dense = _pack(by_process.get(process, []))
        built.append(Lane(process=process, declared=process in named,
                          bars=packed, rows=used, dense=dense))

    return Timeline(
        lanes=tuple(built),
        from_ms=min(starts),
        # **The last RECORDED boundary, never a clock.** With everything still running this is
        # the latest start, which is right: it is the last thing the record actually says.
        to_ms=max(ends + starts),
        open=still_open,
    )
