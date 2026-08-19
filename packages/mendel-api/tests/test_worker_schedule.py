"""What the worker runs on its own.

`cron_jobs` was `[]` with a docstring naming this phase: *"the nightly schedule lands with
Compose, where there is a Redis to run it"*. There is one now.
"""

from mendel_api.worker import WorkerSettings, check_sources


def test_the_source_check_is_scheduled():
    assert WorkerSettings.cron_jobs, "nothing is scheduled"
    assert [job.coroutine for job in WorkerSettings.cron_jobs] == [check_sources]


def test_it_does_not_run_at_startup():
    """A container restart is not a check-worthy event, and a strip reading *checked 4 seconds
    ago* after every deploy is measuring deploys rather than sources."""
    assert all(not job.run_at_startup for job in WorkerSettings.cron_jobs)


def test_it_runs_nightly_rather_than_often():
    """`ops.check` walks every contract against its source — 0.48s over twelve, and roughly
    three minutes at the 5,800 the design talks about. Nightly is the cadence the strip
    promises and the one the cost affords."""
    job = WorkerSettings.cron_jobs[0]
    assert job.hour == 3
    assert job.minute == 0
