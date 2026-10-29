"""nf-core/modules as a catalogue source, read from a git clone.

**A blobless clone** (`--filter=blob:none`): every commit and tree, so one `git log` gives each
module's last change, but file contents only for the checked-out `modules/nf-core`. About 2,100
modules then cost one fetch, not one API call each (forge MVP design, answer 6).
"""

import subprocess
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from comeni_vendor.ops import PREFIX, REPOS

from mendel_forge.model import UpstreamModule
from mendel_forge.nfcore.parse import parse_module
from mendel_forge.source import Snapshot, SourceUnavailable

NAME = "nf-core"
CLONE = "nf-core-modules"


class NfCoreSource:
    name = NAME

    def __init__(self, url: str = REPOS[NAME]) -> None:
        self.url = url

    def sync(self, cache: Path) -> Snapshot:
        repo = cache / CLONE
        if not (repo / ".git").is_dir():
            cache.mkdir(parents=True, exist_ok=True)
            _git(None, "clone", "--quiet", "--filter=blob:none", "--no-checkout", self.url,
                 str(repo))
            _git(repo, "sparse-checkout", "set", PREFIX[NAME])
        else:
            _git(repo, "remote", "set-url", "origin", self.url)
            _git(repo, "fetch", "--quiet", "origin")
            _git(repo, "remote", "set-head", "origin", "--auto")
        _git(repo, "checkout", "--quiet", "--detach", "origin/HEAD")
        return Snapshot(source=NAME, commit=_git(repo, "rev-parse", "HEAD"), root=repo)

    def modules(self, snapshot: Snapshot) -> Iterator[UpstreamModule]:
        base = snapshot.root / PREFIX[NAME]
        paths = sorted(meta.parent.relative_to(base).as_posix() for meta in base.rglob("meta.yml"))
        changed = _last_changes(snapshot.root, set(paths))
        for path in paths:
            module = parse_module(base / path, path, source=NAME)
            yield module.model_copy(update={"upstream_changed": changed.get(path)})


def _last_changes(repo: Path, paths: set[str]) -> dict[str, datetime]:
    """Each module's newest commit date, from one pass over history (newest first)."""
    log = _git(repo, "log", "--format=%x00%cI", "--name-only", "--", PREFIX[NAME])
    prefix = PREFIX[NAME] + "/"
    changed: dict[str, datetime] = {}
    for record in log.split("\0")[1:]:
        date, *files = record.strip().splitlines()
        when = datetime.fromisoformat(date)
        for file in files:
            module = _owner(file.removeprefix(prefix), paths)
            if module is not None:
                changed.setdefault(module, when)
    return changed


def _owner(file: str, paths: set[str]) -> str | None:
    """The deepest module folder holding `file` (`star/align/tests/x` → `star/align`)."""
    parts = file.split("/")
    owners = ["/".join(parts[:n]) for n in range(len(parts) - 1, 0, -1)]
    return next((owner for owner in owners if owner in paths), None)


def _git(repo: Path | None, *args: str) -> str:
    command = ["git", *(["-C", str(repo)] if repo else []), *args]
    try:
        done = subprocess.run(command, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as error:
        said = getattr(error, "stderr", None) or str(error)
        raise SourceUnavailable(f"`git {args[0]}` failed: {said.strip()}") from error
    return done.stdout.strip()
