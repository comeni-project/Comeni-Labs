"""Layer file identity is relative to the layer root, never its checkout location."""

import hashlib
import shutil
from pathlib import Path

from comeni_core.artifact.digest import digest_of_directory
from comeni_core.declared.layered import declared_entries

ROOT = Path(__file__).parent.parent.parent.parent
REGISTRY = ROOT / "registry"

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _registry_under(tmp_path: Path, *parts: str) -> Path:
    target = tmp_path.joinpath(*parts) / "registry"
    shutil.copytree(REGISTRY, target)
    return target


def test_a_layer_under_a_dot_directory_still_has_its_files(tmp_path):
    """A dot-prefixed ancestor outside the layer does not hide declared files."""
    under_dot = _registry_under(tmp_path, ".worktrees", "some-plan")
    plain = _registry_under(tmp_path, "plain")
    assert len(declared_entries(under_dot)) == len(declared_entries(plain))
    assert len(declared_entries(under_dot)) > 0


def test_a_layers_digest_does_not_depend_on_where_it_is_checked_out(tmp_path):
    """Identical layer content has one digest across checkout locations."""
    under_dot = _registry_under(tmp_path, ".worktrees", "some-plan")
    plain = _registry_under(tmp_path, "plain")
    assert digest_of_directory(under_dot) == digest_of_directory(plain)


def test_an_empty_digest_is_refused_as_an_answer(tmp_path):
    """A real layer under a dot-prefixed ancestor cannot collapse to the empty digest."""
    under_dot = _registry_under(tmp_path, ".worktrees", "some-plan")
    assert digest_of_directory(under_dot) != f"sha256:{EMPTY_SHA256}"


def test_a_layers_own_github_directory_is_not_declared_data(tmp_path):
    """Repository CI metadata is not a declaration."""
    layer = _registry_under(tmp_path, "plain")
    # Construct the path even when the copied registry already carries CI metadata.
    workflow = layer / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("name: check\non: [push]\njobs: {}\n")
    assert workflow not in declared_entries(layer)


def test_a_dot_directory_inside_a_layer_is_still_excluded(tmp_path):
    """Dot-prefixed paths inside the layer remain excluded repository metadata."""
    layer = _registry_under(tmp_path, ".worktrees", "some-plan")
    stray = layer / ".github" / "ci.yml"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("name: check\n")
    entries = declared_entries(layer)
    assert stray not in entries
    assert len(entries) > 0
