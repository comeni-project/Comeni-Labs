"""No test may call a live model. `CLAUDE.md` says so; until forge Phase 2 nothing enforced it,
because until then there was no model to reach.

A static scan, and it is deliberately narrow: it looks for the two names that actually reach a
provider — `LiteLLMTransport` and `RecordingTransport` — in any test file. It cannot see a
transport built dynamically, and it is not trying to. The point is that reaching a model from
the suite has to be **deliberate and visible**, which is the same standing invariant 1's scan
has: cost-raising, not a proof.

**Why a name scan rather than a network sandbox.** A sandbox would be stronger and is not free:
it has to allow the Docker socket the gate tests use and the filesystem everything uses, so it
becomes a second allowlist to maintain. This catches the thing that actually happens — somebody
reaches for the real transport in a test because the fake was inconvenient — and it names the
file and line when it does.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN = {"LiteLLMTransport", "RecordingTransport"}
"""The two ways to reach a provider.

`LiteLLMTransport` is the real transport. `RecordingTransport` wraps one to capture a fixture,
which is a developer's tool run by hand — a test that used it would reach the network *and*
rewrite the fixtures underneath every other test.

`RecordedTransport` is deliberately absent: replaying a committed recording is the supported
way to test, and it reaches nothing.
"""

EXEMPT = {Path(__file__).resolve()}
"""This file names them in prose and in `FORBIDDEN`, and is the one file exempt from its rule."""


def _test_files() -> list[Path]:
    """Every test file, scoped to where tests live.

    Not `ROOT.rglob` — `.venv` is inside the worktree and carries thousands of third-party
    test files, which would make this slow and would fail on somebody else's fixtures.
    """
    roots = [ROOT / "tests", *sorted((ROOT / "packages").glob("*/tests"))]
    found: set[Path] = set()
    for root in roots:
        found.update(path.resolve() for path in root.rglob("*.py"))
    return sorted(found - EXEMPT)


def test_no_test_file_names_a_live_transport() -> None:
    offenders: list[str] = []
    for path in _test_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            name = getattr(node, "id", None) or getattr(node, "attr", None)
            if name in FORBIDDEN:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} names {name}")
    assert not offenders, (
        "a test reaches a live model:\n  "
        + "\n  ".join(offenders)
        + "\n\nUse RecordedTransport with a committed fixture, or an injected fake."
    )


def test_the_scan_sees_the_names_it_is_looking_for() -> None:
    """A scan that matches nothing passes vacuously.

    Same lesson as A67: a guard running over an empty list goes green *faster*, which is the
    direction nobody investigates. This asserts the matcher works on text that should trip it.
    """
    tree = ast.parse("LiteLLMTransport()\nx.RecordingTransport\n")
    found = {getattr(node, "id", None) or getattr(node, "attr", None) for node in ast.walk(tree)}
    assert found >= FORBIDDEN


def test_the_scan_actually_reads_some_files() -> None:
    """The other half of the same lesson: the file list must not be empty."""
    files = _test_files()
    assert len(files) > 20, f"the scan found only {len(files)} test files"
    assert any("mendel-ai" in str(path) for path in files), "mendel-ai's tests are not scanned"
