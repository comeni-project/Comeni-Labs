"""The three digests a pure reorganisation must not move. Issue #41, Task 0.

`pipeline.yml` carries no paths and no timestamps by design, and `main.nf` and
`nextflow.config` are golden-file tested — so the same goal against the same registry produces
the same three files, byte for byte, whatever the module layout underneath. That makes a
reorganisation checkable in a way "the tests pass" is not: a moved digest is a behaviour change
hiding in a large diff, which is the only real risk in this work.

**Plan-local. Task 10 deletes it.** There is no single determinism test to extend — the property
is asserted across `test_resolve`, `test_emit`'s golden files and `test_counts` — and a
permanent digest test would need re-blessing on every legitimate behaviour change, which is the
kind of gate people learn to re-bless without reading.
"""

import hashlib
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).parent.parent
WATCHED = ("pipeline.yml", "main.nf", "nextflow.config")

BASELINE = {
    "pipeline.yml": "f1f2d7e5e9cca6a3",
    "main.nf": "76355bbf9f10d6e6",
    "nextflow.config": "72ddb081638edf76",
}
"""Recorded on `main` at 7315347, from two independent builds that agreed."""


def main() -> int:
    with tempfile.TemporaryDirectory() as out:
        built = subprocess.run(
            [
                "uv", "run", "mendel", "build",
                "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
                "--registry", str(ROOT / "registry"),
                "--root", str(ROOT),
                "--out", out,
                "--gate", "lint",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if built.returncode != 0:
            print(built.stderr, file=sys.stderr)
            return built.returncode
        moved = []
        for name in WATCHED:
            digest = hashlib.sha256((pathlib.Path(out) / name).read_bytes()).hexdigest()[:16]
            mark = "  " if digest == BASELINE[name] else "! "
            print(f"{mark}{name:<18} {digest}")
            if digest != BASELINE[name]:
                moved.append(f"{name}: {BASELINE[name]} -> {digest}")
    if moved:
        print(
            "\nA digest moved. This task was supposed to relocate code and change no "
            "behaviour, so\nsomething else changed too — find it before going on:\n  "
            + "\n  ".join(moved),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
