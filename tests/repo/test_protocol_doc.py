"""The protocol diagram is generated from `protocol.py`, and a stale one fails the build."""

import subprocess
import sys

from support.paths import ROOT


def test_the_protocol_diagram_is_fresh():
    run = subprocess.run(
        [sys.executable, "tools/generate_protocol_doc.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
