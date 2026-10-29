"""Where upstream modules come from: one interface, one implementation per source.

nf-core is the only source today; pegi3s (#65) becomes a second implementation of the same
`Protocol`, not a rewrite. **Nothing outside a source knows its layout.**
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from mendel_forge.model import UpstreamModule


@dataclass(frozen=True)
class Snapshot:
    """One synced state of a source: the commit read, and where its files are on disk."""

    source: str
    commit: str
    root: Path


class SourceUnavailable(Exception):
    """A sync could not reach or update its source. The message is the tool's own words."""


class CatalogueSource(Protocol):
    name: str

    def sync(self, cache: Path) -> Snapshot:
        """Bring the source's newest state into `cache` and say which state it is."""
        ...

    def modules(self, snapshot: Snapshot) -> Iterator[UpstreamModule]:
        """Every module in that state, read; one that cannot be read carries its problems."""
        ...
