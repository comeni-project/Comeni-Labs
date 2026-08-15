"""One package's notes, extracted from the shared changelog. `tools/changelog_section.py`.

The changelog is one file with a section per package under each version heading, rather than a
changelog per package: the repository is one repository today, and splitting it before splitting
the repository would leave four files describing the same commits. The release workflow reads a
section by heading, so the split can happen later without changing the mechanism.
"""

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).parent.parent
TOOL = ROOT / "tools" / "changelog_section.py"

SAMPLE = """\
# Changelog

## [Unreleased]

### comeni-core

- something not yet released

## [0.2.0] - 2026-09-01

### comeni-core

- a thing
- another thing

### mendel-compiler

- a compiler thing

## [0.1.0] - 2026-08-01

### comeni-core

- the first thing
"""


def _run(changelog: pathlib.Path, package: str, version: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), package, version, "--changelog", str(changelog)],
        capture_output=True, text=True, check=False,
    )


def test_the_tool_exists():
    """Every refusal test below asserts a non-zero exit, which a **missing** script also
    produces. Three of them passed before the script was written."""
    assert TOOL.is_file(), f"{TOOL} does not exist; the refusal tests below prove nothing"


@pytest.fixture
def changelog(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE)
    return path


def test_it_extracts_one_package_from_one_version(changelog):
    result = _run(changelog, "comeni-core", "0.2.0")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "- a thing\n- another thing"


def test_it_stops_at_the_next_package(changelog):
    """The bug this is really guarding: reading to the next `##` would swallow the sibling."""
    assert "compiler thing" not in _run(changelog, "comeni-core", "0.2.0").stdout


def test_it_stops_at_the_next_version(changelog):
    assert "the first thing" not in _run(changelog, "comeni-core", "0.2.0").stdout


def test_it_reads_the_right_version(changelog):
    result = _run(changelog, "comeni-core", "0.1.0")
    assert result.stdout.strip() == "- the first thing"


def test_a_missing_package_section_is_refused(changelog):
    """A release with empty notes is worse than a refused release: it looks finished."""
    result = _run(changelog, "mendel-resolver", "0.2.0")
    assert result.returncode != 0
    assert "mendel-resolver" in result.stderr and "0.2.0" in result.stderr


def test_a_missing_version_is_refused(changelog):
    result = _run(changelog, "comeni-core", "9.9.9")
    assert result.returncode != 0
    assert "9.9.9" in result.stderr


def test_unreleased_is_not_a_version(changelog):
    """`## [Unreleased]` must never satisfy a version lookup, or a release would ship the
    notes for everything that has *not* been released."""
    result = _run(changelog, "comeni-core", "Unreleased")
    assert result.returncode != 0
    assert "something not yet released" not in result.stdout
