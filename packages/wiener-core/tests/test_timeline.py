"""The timeline's rules are the artboard's, and each of these names the one it holds.

`.design/canvas.json`, `page-5`, *"THE TIMELINE, RULE BY RULE"*. That annotation records that
each rule was arrived at by drawing the wrong thing first, so each is a defect somebody already
paid for once.
"""

from wiener_core.state import Attempt, TaskStatus
from wiener_core.timeline import MAX_ROWS, lanes

DECLARED = ["TRIMGALORE", "STAR_ALIGN", "SAMTOOLS_SORT"]


def _try(n: int, start: int | None, end: int | None,
         status: TaskStatus = TaskStatus.COMPLETED) -> Attempt:
    return Attempt(n=n, status=status, at_ms=start or 0, start_ms=start, complete_ms=end)


def test_a_lane_exists_before_the_run_reaches_it():
    """*"A process that has not been reached still has a lane... The chart's height is known
    before the first event."* A timeline that grew lanes as tasks arrived would resize under a
    reader, which is the thing `overview()` already refuses to do with its rows."""
    got = lanes([], DECLARED)
    assert [lane.process for lane in got.lanes] == DECLARED
    assert all(lane.bars == () for lane in got.lanes)


def test_lanes_are_in_declared_order_and_a_stranger_goes_last():
    """The artifact is the order. A process the run ran that the artifact does not describe is
    still drawn — `overview()` makes the same split — but it cannot claim a declared position."""
    got = lanes([(1, "MULTIQC", [_try(1, 0, 5)])], DECLARED)
    assert [lane.process for lane in got.lanes] == [*DECLARED, "MULTIQC"]
    assert got.lanes[-1].declared is False
    assert all(lane.declared for lane in got.lanes[:-1])


def test_a_retry_is_a_separate_bar_in_the_same_lane():
    """*"`Attempt` is per-attempt precisely so the try that asked for more memory is visible;
    collapsing them loses the only interesting thing."* One task, two tries, two bars."""
    got = lanes(
        [(7, "STAR_ALIGN", [_try(1, 0, 10, TaskStatus.FAILED), _try(2, 12, 30)])],
        DECLARED,
    )
    lane = next(one for one in got.lanes if one.process == "STAR_ALIGN")
    assert len(lane.bars) == 2
    assert {bar.attempt for bar in lane.bars} == {1, 2}
    assert {bar.task_id for bar in lane.bars} == {7}, "both bars name the task they retried"


def test_overlapping_attempts_get_their_own_sub_rows():
    """*"SUB-ROWS ARE CONCURRENCY, greedily packed."* Two tasks running at once cannot share a
    row without one drawing over the other."""
    got = lanes(
        [(1, "STAR_ALIGN", [_try(1, 0, 100)]), (2, "STAR_ALIGN", [_try(1, 10, 90)])],
        DECLARED,
    )
    lane = next(one for one in got.lanes if one.process == "STAR_ALIGN")
    assert {bar.row for bar in lane.bars} == {0, 1}
    assert lane.rows == 2


def test_a_finished_row_is_reused():
    """The other half, and the one that makes it *packing* rather than *one row per task*. A
    lane of 500 sequential tasks is one row, not 500."""
    sequential = [(n, "TRIMGALORE", [_try(1, n * 10, n * 10 + 5)]) for n in range(50)]
    lane = next(one for one in lanes(sequential, DECLARED).lanes
                if one.process == "TRIMGALORE")
    assert lane.rows == 1, "nothing overlaps, so nothing needs a second row"
    assert len(lane.bars) == 50


def test_a_running_attempt_never_frees_its_row():
    """An open bar has not ended, so the row is still occupied. Treating `None` as *ends now*
    would let a later task draw over a task that is still running."""
    got = lanes(
        [(1, "STAR_ALIGN", [_try(1, 0, None, TaskStatus.RUNNING)]),
         (2, "STAR_ALIGN", [_try(1, 50, 60)])],
        DECLARED,
    )
    lane = next(one for one in got.lanes if one.process == "STAR_ALIGN")
    assert lane.rows == 2
    assert got.open is True


def test_the_stack_stops_and_says_how_much_it_dropped():
    """*"Above roughly 40 concurrent the stack stops and the remainder becomes a density band —
    never 5,000 rows."* **Counted, never silently dropped**: a chart that omits bars without
    saying so is a chart that lies about a run."""
    concurrent = [(n, "STAR_ALIGN", [_try(1, 0, 1000)]) for n in range(MAX_ROWS + 15)]
    lane = next(one for one in lanes(concurrent, DECLARED).lanes
                if one.process == "STAR_ALIGN")
    assert lane.rows == MAX_ROWS
    assert lane.dense == 15
    assert len(lane.bars) == MAX_ROWS


def test_no_clock_is_read_and_an_open_bar_keeps_its_none():
    """**The rule `series.py` keeps, in a second place.** Closing a running attempt at `now`
    inside a pure function makes the same events fold to a different picture every second, and
    §6.1's *same events in, same decisions out* dies the first week one is read.

    The renderer extends an open bar to the right edge — `curve.ts` already does exactly this
    with an open reservation.
    """
    got = lanes([(1, "STAR_ALIGN", [_try(1, 5, None, TaskStatus.RUNNING)])], DECLARED)
    bar = next(one for one in got.lanes if one.process == "STAR_ALIGN").bars[0]
    assert bar.end_ms is None
    # The window's right edge is the last thing the RECORD says, which here is the last start.
    assert got.to_ms == 5


def test_an_attempt_that_never_started_has_no_place_on_a_time_axis():
    """Submitted and never started has no `start_ms`. It is still counted by `overview()`,
    which is where *how many are waiting* is answered — a bar of zero width at zero would put
    it at the beginning of the run, which is a claim about when it ran."""
    got = lanes([(1, "STAR_ALIGN", [_try(1, None, None, TaskStatus.SUBMITTED)])], DECLARED)
    assert all(lane.bars == () for lane in got.lanes)


def test_the_same_rows_in_any_order_give_the_same_timeline():
    """Determinism, which is what makes this `wiener-core`'s to own. A chart that redraws
    differently on a refresh is one nobody can compare against a screenshot."""
    rows = [(1, "STAR_ALIGN", [_try(1, 0, 10)]), (2, "STAR_ALIGN", [_try(1, 5, 20)]),
            (3, "TRIMGALORE", [_try(1, 0, 3)])]
    assert lanes(rows, DECLARED) == lanes(list(reversed(rows)), DECLARED)
