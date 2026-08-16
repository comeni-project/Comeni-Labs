"""What a layer's files are must not depend on where the layer is checked out.

Two definitions had drifted apart and both were wrong, in opposite directions:

- `_declared()` — used by the digest and the symlink scan — excluded any path with a
  dot-prefixed *component*, judged on the **absolute** path. A layer under `.worktrees/`,
  `.cache/` or `~/.local/` therefore contained **nothing**, and its digest was the SHA-256 of
  the empty string. `CLAUDE.md` requires work to happen in `.worktrees/`, so this fired on the
  sanctioned workflow and `make verify` was green throughout.

- `_files()` — used by `stack()` to actually load — applied no dot-exclusion at all, so a
  layer repository's own `.github/workflows/ci.yml` was read as declared data and refused with
  `MD0010`.

This is the same defect `test_architecture.py` shipped and had to fix: a filter on absolute
path parts matches the whole tree. It is A67's silent direction — the digest went *empty*
rather than wrong-looking — and issue #46's machine-dependent digest arriving a second time by
a different route.

The fix is that both judge a path **relative to the layer root**, so where the layer sits
cannot change what it contains.
"""

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
    """`.worktrees/` is where this repository requires plans to execute."""
    under_dot = _registry_under(tmp_path, ".worktrees", "some-plan")
    plain = _registry_under(tmp_path, "plain")
    assert len(declared_entries(under_dot)) == len(declared_entries(plain))
    assert len(declared_entries(under_dot)) > 0


def test_a_layers_digest_does_not_depend_on_where_it_is_checked_out(tmp_path):
    """The whole point of a content digest. Issue #46 found this once already, via a
    submodule's `.git` file; this is the same failure by a different route."""
    under_dot = _registry_under(tmp_path, ".worktrees", "some-plan")
    plain = _registry_under(tmp_path, "plain")
    assert digest_of_directory(under_dot) == digest_of_directory(plain)


def test_an_empty_digest_is_refused_as_an_answer(tmp_path):
    """The failure was silent because hashing nothing succeeds. A digest equal to SHA-256 of
    the empty string means the allowlist matched no file, which is never a real layer."""
    under_dot = _registry_under(tmp_path, ".worktrees", "some-plan")
    assert digest_of_directory(under_dot) != f"sha256:{EMPTY_SHA256}"


def test_a_layers_own_github_directory_is_not_declared_data(tmp_path):
    """A layer repository carries CI of its own. `comeni-registry` is the first one to, and
    `.github/workflows/ci.yml` was read as a contract and refused with `MD0010`."""
    layer = _registry_under(tmp_path, "plain")
    # `exist_ok`: since comeni-registry#3 the real layer *has* a `.github/workflows/`, which
    # is the situation this test was written for. Constructing it anyway keeps the test true
    # if the fixture ever loses one.
    workflow = layer / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("name: check\non: [push]\njobs: {}\n")
    assert workflow not in declared_entries(layer)


def test_a_dot_directory_inside_a_layer_is_still_excluded(tmp_path):
    """The exclusion must survive the fix — it is what keeps a submodule's `.git` file and a
    layer's `.github/` out. Only the *frame of reference* changes, from absolute to relative."""
    layer = _registry_under(tmp_path, ".worktrees", "some-plan")
    stray = layer / ".github" / "ci.yml"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("name: check\n")
    entries = declared_entries(layer)
    assert stray not in entries
    assert len(entries) > 0
