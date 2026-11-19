"""A finished run's process is reaped (#593)."""

import time


def test_a_finished_process_is_reaped_without_anyone_waiting(tmp_path):
    """`_spawn` started Nextflow and nothing waited on it, so a finished run stayed a zombie
    until the worker exited. A thread waits on it, and its exit status is collected."""
    from wiener_api.services import launcher

    spawned = launcher._spawn(["true"], tmp_path)
    deadline = time.monotonic() + 5
    while spawned.returncode is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert spawned.returncode == 0, "the finished process was never waited on"
