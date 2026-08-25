"""§9.3's numbers, per declared process. Held to two real captures — one with resources
and one without."""

import json
from pathlib import Path

from wiener_core.events import RunEvent, TaskStatus, admit
from wiener_core.overview import overview
from wiener_core.state import Attempt, RunState, TaskState, replay

ROOT = Path(__file__).parents[3]
SPINE = ROOT / "tests/fixtures/weblog/spine-run.events.jsonl"
PLAIN = ROOT / "tests/fixtures/weblog/failing-run.jsonl"


def _spine():
    return replay([RunEvent.model_validate(json.loads(line))
                   for line in SPINE.read_text().splitlines() if line.strip()])


def _plain():
    bodies = [json.loads(line) for line in PLAIN.read_text().splitlines() if line.strip()]
    return replay([admit(b, run_id="r1", seq=i) for i, b in enumerate(bodies)])


def test_a_declared_process_has_a_row_before_the_run_reaches_it():
    """The table's length is known before the first event. That is the whole reason the
    overview can be the front door: it does not grow as the run discovers work."""
    got = overview(RunState(), ["STAR_ALIGN", "MULTIQC"])
    assert [row.process for row in got.rows] == ["STAR_ALIGN", "MULTIQC"]
    assert all(row.declared and not row.reached for row in got.rows)
    assert got.steps_declared == 2 and got.steps_finished == 0


SPINE_DECLARED = ["TRIMGALORE", "STAR_GENOMEGENERATE", "STAR_ALIGN", "SAMTOOLS_SORT",
                  "SUBREAD_FEATURECOUNTS", "MULTIQC"]


def test_the_rows_keep_the_artifact_s_order_rather_than_sorting_by_time():
    """`stats()` put the slowest first, because it was a panel a reader scanned once. The
    overview is the front door and gets read repeatedly while a run moves, so it is ordered by
    the pipeline's own shape — a table that reorders itself cannot be scanned twice.

    STAR_ALIGN is the slowest process in this capture and it is third, which is the point."""
    got = overview(_spine(), SPINE_DECLARED)
    assert [row.process for row in got.rows] == SPINE_DECLARED
    star = next(row for row in got.rows if row.process == "STAR_ALIGN")
    assert star.realtime_ms and star.realtime_ms == max(
        row.realtime_ms or 0 for row in got.rows
    )


def test_a_declared_process_the_run_never_reached_is_a_row_and_not_a_gap():
    """MULTIQC is declared and this capture never ran it. It is the row that says so."""
    got = overview(_spine(), SPINE_DECLARED)
    multiqc = next(row for row in got.rows if row.process == "MULTIQC")
    assert multiqc.declared and not multiqc.reached
    assert multiqc.tasks == 0 and multiqc.memory_peak_bytes is None
    assert got.steps_declared == 6 and got.steps_finished == 5


def test_both_halves_of_every_comparison_are_present():
    """A bare peak means nothing without what was asked for — §9.3."""
    star = next(row for row in overview(_spine(), SPINE_DECLARED).rows
                if row.process == "STAR_ALIGN")
    assert star.memory_asked_bytes and star.memory_peak_bytes
    assert star.cpus_asked and star.cpu_used_pct
    assert star.realtime_ms and star.queue_wait_ms is not None


def test_absence_is_none_and_never_zero():
    """A run launched without `trace.enabled` reports nothing. A zero would read as
    'this process used no memory' — a lie a reader cannot tell from a true number."""
    row = overview(_plain(), ["GREET"]).rows[0]
    assert row.memory_peak_bytes is None
    assert row.cpu_used_pct is None
    assert row.reported_resources is False
    assert row.tasks > 0            # it ran; it just reported no resources


def test_the_maximum_is_kept_rather_than_the_mean():
    """The maximum is what kills a run and the mean is what hides it — §9.3, and this is the
    test that stops somebody averaging it later."""
    state = _spine()
    star = next(row for row in overview(state, SPINE_DECLARED).rows
                if row.process == "STAR_ALIGN")
    peaks = [a.peak_rss_bytes for t in state.tasks.values() if t.process == "STAR_ALIGN"
             for a in t.attempts if a.peak_rss_bytes]
    assert star.memory_peak_bytes == max(peaks)


def test_a_process_the_artifact_does_not_declare_still_gets_a_row():
    """A192's other half. An unreadable artifact means `declared` is empty, and the run's own
    processes must still be listed — the counts are folded from events and are still true."""
    got = overview(_spine(), [])
    assert {row.process for row in got.rows} == set(SPINE_DECLARED) - {"MULTIQC"}
    assert all(row.declared is False and row.reached is True for row in got.rows)
    assert got.steps_declared == 0
    assert got.steps_finished == 0, "nothing is finished against a denominator nobody declared"


def test_a_retried_task_is_counted_once_and_its_attempts_are_remembered():
    """`attempts_max` is what draws §9.1's retry ring, and a retried task must not read as two.

    **Built by hand rather than replayed**, because no committed capture has a retry in it —
    `attempt` is 1 everywhere in all three weblog fixtures. W1 found the same absence from the
    other side: `* task.attempt` was decoration until an `errorStrategy` made a retry possible.
    """
    task = TaskState(
        task_id=1, process="STAR_ALIGN", status=TaskStatus.COMPLETED,
        first_seen_ms=0, last_change_ms=9,
        attempts=(
            Attempt(n=1, status=TaskStatus.FAILED, exit=137, at_ms=4, peak_rss_bytes=8),
            Attempt(n=2, status=TaskStatus.COMPLETED, exit=0, at_ms=9, peak_rss_bytes=12),
        ),
    )
    row = overview(RunState(tasks={1: task}), ["STAR_ALIGN"]).rows[0]
    assert row.tasks == 1 and row.attempts_max == 2
    assert row.memory_peak_bytes == 12, "the worst is taken across attempts, not the last"


def test_a_step_that_failed_is_not_a_step_that_finished():
    """**Found at Checkpoint 1, against a real failed run.** The plan's rule was `reached and
    nothing running and tasks > 0`, which counts a *failed* process as finished — so run
    `0d3a4e3d` reported `steps_finished: 2` of 5 with zero successes, and §5's one honest bar
    advanced on failure.

    A bar that moves when nothing succeeded is the worst direction for this number to be wrong
    in: it claims progress where there was none.
    """
    failed = TaskState(task_id=1, process="TRIMGALORE", status=TaskStatus.FAILED,
                       first_seen_ms=0, last_change_ms=1,
                       attempts=(Attempt(n=1, status=TaskStatus.FAILED, exit=1, at_ms=1),))
    done = TaskState(task_id=2, process="MULTIQC", status=TaskStatus.COMPLETED,
                     first_seen_ms=0, last_change_ms=1,
                     attempts=(Attempt(n=1, status=TaskStatus.COMPLETED, exit=0, at_ms=1),))
    got = overview(RunState(tasks={1: failed, 2: done}), ["TRIMGALORE", "MULTIQC"])
    assert got.steps_finished == 1, "the failed step is not finished; the completed one is"


def test_a_step_is_not_finished_while_one_of_its_tasks_still_fails():
    """Per process, not per task. Nine of ten samples through and one failed is not a step
    that finished — and `running == 0` is true of it, which is how the first rule missed it."""
    tasks = {
        n: TaskState(task_id=n, process="STAR_ALIGN",
                     status=TaskStatus.COMPLETED if n < 9 else TaskStatus.FAILED,
                     first_seen_ms=0, last_change_ms=1,
                     attempts=(Attempt(n=1, status=TaskStatus.COMPLETED, at_ms=1),))
        for n in range(10)
    }
    assert overview(RunState(tasks=tasks), ["STAR_ALIGN"]).steps_finished == 0


def test_steps_finished_can_go_backwards_and_that_is_the_honest_answer():
    """**Checkpoint 1 asks whether `steps_finished` is monotonic. It is not, and cannot be.**

    Nextflow discovers tasks as channels emit (§5), so a process with three tasks all done is
    finished until a fourth is submitted. The count then drops, and the bar moves left.

    The alternative — remembering that a step was once finished — is monotonic and *false*: it
    would show a step as complete while it is running, which is the same lie as counting a
    failure. This is pinned rather than fixed so that nobody 'fixes' it later, and so the
    interface knows not to animate this number as a bar that only fills.
    """
    def _task(n: int, status: TaskStatus) -> TaskState:
        return TaskState(task_id=n, process="STAR_ALIGN", status=status,
                         first_seen_ms=0, last_change_ms=1,
                         attempts=(Attempt(n=1, status=status, at_ms=1),))

    three_done = {n: _task(n, TaskStatus.COMPLETED) for n in range(3)}
    assert overview(RunState(tasks=three_done), ["STAR_ALIGN"]).steps_finished == 1

    a_fourth_arrives = {**three_done, 3: _task(3, TaskStatus.RUNNING)}
    assert overview(RunState(tasks=a_fourth_arrives), ["STAR_ALIGN"]).steps_finished == 0
