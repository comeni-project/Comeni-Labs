"""Registry releases, as the app and the Releases page see them (forge MVP 6, spec §2–3).

Pure: what a release is, how versions order, and how notes are written. `ReleaseSource` is public
data, read without a token, so an installation that cannot publish still follows releases.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

VERSION = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Release(_Frozen):
    tag: str
    notes: str = ""
    published_at: datetime | None = None


class Fragment(_Frozen):
    path: str
    text: str


class Unreleased(_Frozen):
    """`main` against the last tag."""

    last: str | None
    commit: str
    ahead: int
    """Commits on `main` since `last`. Zero means nothing to release."""
    checks: str
    says: str | None = None
    fragments: list[Fragment] = []


class ReleaseSource(Protocol):
    def releases(self) -> list[Release]:
        """Every published release. `ReleaseUnavailable` when it cannot be read."""
        ...

    def download(self, tag: str, into: Path) -> str:
        """Unpack `tag` into `into` and return its commit, verified."""
        ...

    def unreleased(self) -> Unreleased:
        ...


class ReleaseUnavailable(Exception):
    """GitHub could not be reached or refused. The message is safe to show a person."""


def key(tag: str) -> tuple[int, int, int] | None:
    found = VERSION.match(tag)
    return (int(found[1]), int(found[2]), int(found[3])) if found else None


def newest_first(releases: list[Release]) -> list[Release]:
    """Versioned releases, newest first. A tag outside the grammar is not one to follow."""
    versioned = [r for r in releases if key(r.tag) is not None]
    return sorted(versioned, key=lambda r: key(r.tag), reverse=True)


def next_version(last: str | None) -> str:
    """The next minor: a release adds tools, and a person can change it."""
    found = key(last) if last else None
    return f"v{found[0]}.{found[1] + 1}.0" if found else "v0.1.0"


def notes_from(fragments: list[Fragment]) -> str:
    return "\n".join(f.text.strip() for f in sorted(fragments, key=lambda f: f.path))
