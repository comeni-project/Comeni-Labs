"""Where a tool comes from, and how one is read.

**Pluggable by decision, not by prediction.** nf-core is what is vendored and what
`modulespec.py` parses; pegi3s is issue #65 and is designed for rather than built. A
protocol with one implementation is a protocol designed against imagination, so the test
suite ships a second — `tests/fixtures/opaque` — whose shape is pegi3s's: no module, almost
everything a hole.

A `Source` returns an `Observation` and nothing contract-shaped. Keeping the two apart is
what lets a source for something nobody has written yet need no change here.
"""

from pathlib import Path
from typing import Protocol

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.observe import Observation


class ToolRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    ident: str

    def __str__(self) -> str:
        return f"{self.source}:{self.ident}"

    @classmethod
    def parse(cls, text: str) -> "ToolRef":
        source, sep, ident = text.partition(":")
        if not sep or not source or not ident:
            raise ValueError(
                coded("MF0001", f"{text!r} does not name a source")
                + f"\n  spell it <source>:<tool> — known sources: {', '.join(names())}"
            )
        return cls(source=source, ident=ident)


class Source(Protocol):
    """One place tools are read from."""

    name: str

    def discover(self, root: Path) -> list[ToolRef]:
        """Every tool this source can ingest under `root`. Sorted."""
        ...

    def ingest(self, ref: ToolRef, root: Path) -> Observation:
        """What can be proven about one tool. Never a guess: a fact with no evidence
        does not belong in an `Observation`."""
        ...


_REGISTERED: dict[str, Source] = {}


def register(source: Source) -> None:
    _REGISTERED[source.name] = source


def names() -> list[str]:
    return sorted(_REGISTERED)


def get(name: str) -> Source:
    if name not in _REGISTERED:
        raise ValueError(
            coded("MF0001", f"{name!r} is not a registered source")
            + f"\n  known: {', '.join(names()) or '(none)'}"
        )
    return _REGISTERED[name]


def discover_all(root: Path) -> list[ToolRef]:
    found = [ref for name in names() for ref in _REGISTERED[name].discover(root)]
    return sorted(found, key=lambda r: (r.source, r.ident))
