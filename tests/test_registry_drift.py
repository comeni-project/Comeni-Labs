"""The drift detector, tested against a doctored copy.

A detector nobody has watched detect anything is a detector that reports success. These
build a second layer by hand and break it one way at a time.
"""

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent.parent
TOOL = ROOT / "tools" / "check_registry_drift.py"


def _run(other: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), str(other)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )


def test_an_identical_copy_has_no_drift(tmp_path):
    other = tmp_path / "comeni-registry"
    shutil.copytree(ROOT / "registry", other)
    result = _run(other)
    assert result.returncode == 0, result.stderr
    assert "no drift" in result.stdout


def test_a_changed_shared_file_is_drift(tmp_path):
    """The failure this exists for: a fix landed in one repository and not the other."""
    other = tmp_path / "comeni-registry"
    shutil.copytree(ROOT / "registry", other)
    sort = next(other.rglob("samtools-sort.yml"))
    sort.write_text(sort.read_text().replace("priority: 0", "priority: 9"))

    result = _run(other)
    assert result.returncode == 1
    assert "samtools-sort.yml" in result.stderr
    assert "DRIFT" in result.stderr


def test_a_file_only_one_side_has_is_reported_but_not_a_failure(tmp_path):
    """The two are *meant* to diverge — the published registry grows into a real one while
    this repo keeps fixtures. Failing on growth would train everyone to ignore this."""
    other = tmp_path / "comeni-registry"
    shutil.copytree(ROOT / "registry", other)
    (other / "contracts" / "nf-core" / "brand-new.yml").write_text("id: whatever\n")

    result = _run(other)
    assert result.returncode == 0, result.stderr
    assert "only in comeni-registry" in result.stdout
    assert "brand-new.yml" in result.stdout


def test_a_directory_that_is_not_a_layer_is_refused(tmp_path):
    """Pointed at the wrong path, it must say so rather than report a clean run — which is
    what comparing against an empty directory would otherwise look like."""
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "registry.yml" in result.stderr


def test_readmes_and_licences_are_not_compared(tmp_path):
    """The two repositories have different audiences and different front matter. Comparing
    those would fail permanently and immediately, for no reason."""
    other = tmp_path / "comeni-registry"
    shutil.copytree(ROOT / "registry", other)
    (other / "README.md").write_text("a completely different readme")
    (other / "LICENSE").write_text("different licence text")

    assert _run(other).returncode == 0
