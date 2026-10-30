"""What the worker runs on its own. Every assertion is **per job**: each schedule answers its
own question, and a test about the whole list would break whenever a job is added.
"""


from mendel_api.worker import WorkerSettings


def _by_name() -> dict:
    return {job.coroutine.__name__: job for job in WorkerSettings.cron_jobs}


def test_these_are_the_scheduled_jobs():
    """Named literally, so adding one means editing this test — which is where somebody
    notices that a new job needs a cadence argued for rather than copied."""
    assert WorkerSettings.cron_jobs, "nothing is scheduled"
    assert sorted(_by_name()) == ["follow_registry_releases", "poll_forge_pull_requests",
                                  "poll_forge_tests",
                                  "retention_sweep", "sweep_lost_gates",
                                  "sync_catalogue_job"]


def test_retention_runs_daily_and_not_at_startup():
    """Part H. Daily is the granularity every limit is stated in (days), and a restart is not
    a reason to delete anything: a deploy must never be what clears a laboratory's data."""
    job = _by_name()["retention_sweep"]
    assert job.hour == 4 and job.minute == 0
    assert not job.run_at_startup


def test_a_gate_job_outlasts_the_longest_gate_and_runs_once():
    """Issue 278: arq's default job timeout (300s) is below the stub gate's own (900s) and the
    test gate's (3600s), so it cancelled them. Only the gate job gets the long limit, since the
    worker is shared; and it is never re-run unasked, since two runs share one directory."""
    from mendel_compiler.gates import LONGEST

    [entry] = [f for f in WorkerSettings.functions if getattr(f, "name", None) == "run_gate_job"]
    assert entry.timeout_s is not None and entry.timeout_s > LONGEST
    assert entry.max_tries == 1


def test_lost_gates_are_swept_every_quarter_hour_and_at_startup():
    job = _by_name()["sweep_lost_gates"]
    assert job.minute == {0, 15, 30, 45} and job.run_at_startup


def test_the_catalogue_syncs_daily_once_and_not_at_startup():
    """Forge part 1. nf-core/modules changes daily at most in ways that matter here, a restart
    is not a reason to re-clone, and a failed sync waits for tomorrow or Sync now, not a retry."""
    job = _by_name()["sync_catalogue_job"]
    assert job.hour == 3 and job.minute == 0
    assert not job.run_at_startup
    [entry] = [f for f in WorkerSettings.functions
               if getattr(f, "name", None) == "sync_catalogue_job"]
    assert entry.max_tries == 1
