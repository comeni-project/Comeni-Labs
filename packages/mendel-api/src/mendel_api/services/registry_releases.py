"""The app follows registry releases (forge MVP 6, spec §3).

`follow`, on the worker's cron, reads what is published, fetches what it wants into a read-only
folder of its own, and switches `current` only to a release that **loads**. Everything else stays
as it was: offline keeps the newest it has, a pinned installation never moves, and with no release
at all the configured root runs. `status.json` is how the other services learn why.
"""

import logging
import os
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path

import yaml
from comeni_core.artifact.digest import digest_of_directory
from comeni_core.settings import catalogue
from mendel_compiler.locate import RELEASE_FILE
from mendel_forge.releases import Release, ReleaseUnavailable, newest_first
from mendel_resolver import layers
from pydantic import BaseModel

from mendel_api.services.github_releases import source
from mendel_api.services.installation import installation
from mendel_api.settings import CURRENT, settings

log = logging.getLogger(__name__)

STATUS = "status.json"
LATEST = "latest"


class FollowStatus(BaseModel):
    using: str | None = None
    """The tag in use, or `None` for the configured root."""
    wanted: str = LATEST
    checked_at: datetime | None = None
    problem: str | None = None
    """Why the app is not on what it wants, when it is not."""
    refused: dict[str, str] = {}
    """Releases that failed to fetch or load, by tag, and why."""


def _wanted() -> str:
    said = installation().get(catalogue.REGISTRY_RELEASE)
    return said.strip() if isinstance(said, str) and said.strip() else LATEST


def status() -> FollowStatus:
    path = _root() / STATUS if settings.registries_root else None
    if path is None or not path.is_file():
        return FollowStatus(wanted=_wanted())
    return FollowStatus.model_validate_json(path.read_text())


def _root() -> Path:
    return Path(settings.registries_root)


def _write_status(found: FollowStatus) -> None:
    temporary = _root() / f"{STATUS}.new"
    temporary.write_text(found.model_dump_json())
    temporary.replace(_root() / STATUS)


def _using() -> str | None:
    current = _root() / CURRENT
    return current.read_text().strip() if current.is_file() else None


def _switch(tag: str) -> None:
    temporary = _root() / f"{CURRENT}.new"
    temporary.write_text(tag)
    temporary.replace(_root() / CURRENT)  # atomic: a reader sees one tag or the other


def _fetched(tag: str) -> Path:
    return _root() / tag / "layer"


def _fetch(tag: str) -> Path:
    """The release's layer on disk, fetched once, read-only, with its `release.yml` beside it."""
    layer = _fetched(tag)
    if layer.is_dir():
        return layer
    _discard(tag)
    partial = _root() / f".{tag}.partial"
    commit = source().download(tag, partial / "layer")
    (partial / RELEASE_FILE).write_text(yaml.safe_dump({
        "repository": f"https://github.com/{settings.registry_repo}", "tag": tag, "commit": commit,
        "digest": str(digest_of_directory(partial / "layer")),
    }))
    _read_only(partial)
    os.chmod(partial, stat.S_IRWXU)
    partial.rename(_root() / tag)
    return layer


def _read_only(folder: Path) -> None:
    for path in sorted(folder.rglob("*"), reverse=True):
        path.chmod(path.stat().st_mode & ~0o222)


def _writable(folder: Path) -> None:
    folder.chmod(folder.stat().st_mode | stat.S_IRWXU)
    for path in folder.rglob("*"):
        path.chmod(path.stat().st_mode | stat.S_IRWXU)


def _discard(tag: str) -> None:
    """Whatever a failed fetch left: a folder that holds no release must not look like one."""
    partial = _root() / f".{tag}.partial"
    if partial.exists():
        _writable(partial)
        shutil.rmtree(partial)


def _usable(tag: str, refused: dict[str, str]) -> bool:
    try:
        layers.load([_fetch(tag)])
    except (ValueError, OSError, ReleaseUnavailable) as error:
        log.warning("registry release %s is not usable: %s", tag, error)
        refused[tag] = str(error).splitlines()[0]
        _discard(tag)
        return False
    return True


def follow() -> str | None:
    """One look at what is published. Returns the tag in use, or `None` for the configured root."""
    if not settings.registries_root:
        return None
    _root().mkdir(parents=True, exist_ok=True)
    wanted, problem, refused = _wanted(), None, {}
    try:
        published = newest_first(source().releases())
    except ReleaseUnavailable as error:
        published, problem = _on_disk(), f"keeping what is here: {error}"
    chosen = _choose(wanted, published, refused)
    if chosen is not None and chosen != _using():
        _switch(chosen)
    if chosen is None and wanted != LATEST:
        problem = problem or f"release {wanted} is not available; nothing changed"
    elif refused and problem is None:
        problem = f"{len(refused)} release(s) could not be used"
    _write_status(FollowStatus(using=_using(), wanted=wanted, checked_at=datetime.now(UTC),
                               problem=problem, refused=refused))
    return _using()


def _choose(wanted: str, published: list[Release], refused: dict[str, str]) -> str | None:
    if wanted != LATEST:
        here = wanted in {r.tag for r in published} or _fetched(wanted).is_dir()
        return wanted if here and _usable(wanted, refused) else None
    return next((r.tag for r in published if _usable(r.tag, refused)), None)


def _on_disk() -> list[Release]:
    folders = [p.name for p in _root().iterdir() if (p / "layer").is_dir()]
    return newest_first([Release(tag=name) for name in folders])


def describe() -> str:
    """What Settings says about following releases."""
    found = status()
    said = f"Using {found.using or 'the configured folder'}, following {found.wanted}"
    return f"{said}. {found.problem}" if found.problem else f"{said}."
