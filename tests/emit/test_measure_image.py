"""The image every generated measuring step runs on can run under a traced run (#506).

Wiener always turns `trace.enabled` on, and Nextflow then needs `ps` inside the task's
container to collect its metrics; without it the task exits 1 before its script starts. The
emit tests check the container string only, so this asks the pinned image itself."""

import shutil
import subprocess

import pytest
from mendel_resolver.measure_steps import RUNNER_IMAGE

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("docker") is None, reason="needs Docker"),
]


def test_the_measuring_image_has_what_a_traced_task_needs():
    found = subprocess.run(
        ["docker", "run", "--rm", RUNNER_IMAGE, "sh", "-c", "command -v ps python3 bash"],
        capture_output=True, text=True, check=False)
    paths = found.stdout.split()
    assert paths, found.stderr
    assert [p.rsplit("/", 1)[-1] for p in paths] == ["ps", "python3", "bash"], found.stdout
