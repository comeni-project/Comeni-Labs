"""Where a tool comes from, and how one is read.

**Pluggable by decision, not by prediction.** nf-core is what is vendored and what
`modulespec.py` parses; pegi3s is issue #65 and is designed for rather than built. A
protocol with one implementation is a protocol designed against imagination, so the test
suite ships a second — `tests/fixtures/opaque` — whose shape is pegi3s's: no module, almost
everything a hole.

A `Source` returns an `Observation` and nothing contract-shaped. Keeping the two apart is
what lets a source for something nobody has written yet need no change here.
"""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.observe import Observation

if TYPE_CHECKING:  # a module every CLI verb imports must not pull in a transport
    import httpx

    from mendel_forge.sources.base import BaseSourceAdapter

GITHUB_TOKEN = "COMENI_FORGE_GITHUB_TOKEN"
"""The environment variable holding an upstream GitHub credential.

**A rate limit, not an access grant.** Both catalogue adapters read public repositories:
nf-core's modules, and pegi3s's Dockerfiles and central metadata. Anonymous GitHub allows sixty
requests an hour and one full nf-core sync costs roughly two thousand — a commit, a tree, and a
`meta.yml` per module — so the token is what makes a full catalogue possible at all, and it
needs no scopes whatsoever. Docker Hub's namespace API is not authenticated here and does not
need to be.

Spelled `COMENI_` rather than `MENDEL_` because it belongs to the forge's upstream lane
alongside `COMENI_AI_*`, and it is declared here — beside the adapters that spend it — for the
reason `access.py` gives for its own names: so a second consumer does not invent a second
spelling."""



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


# ── the catalogue adapters ─────────────────────────────────────────────────────────────
#
# **A second registry, deliberately.** `_REGISTERED` above holds `Source` implementations for
# the deprecated `forge draft` path, which reads a local layer. `BaseSourceAdapter` answers a
# different question — what exists *upstream* — and needs an injected HTTP client, so it cannot
# be constructed at import time the way a `Source` is.
#
# `adapters()` names the classes rather than instances for exactly that reason: the caller owns
# the client's lifetime, and a module-level `httpx.AsyncClient` created at import would outlive
# every event loop that ever used it. Task 13 retires the older half.


def adapters() -> dict[str, type]:
    """Every upstream catalogue adapter, by source name.

    Imported inside the function so `import mendel_forge.sources` stays cheap and so the
    `httpx` dependency is not pulled in by a caller that only wants `ToolRef`.
    """
    from mendel_forge.sources.nfcore_catalogue import NfCoreAdapter
    from mendel_forge.sources.pegi3s import Pegi3sAdapter

    return {NfCoreAdapter.name: NfCoreAdapter, Pegi3sAdapter.name: Pegi3sAdapter}


def upstream_token(env: Mapping[str, str] | None = None) -> str | None:
    """The configured upstream credential, or `None`.

    An empty or whitespace-only value is `None` rather than a token, because `.env` files hold
    `COMENI_FORGE_GITHUB_TOKEN=` far more often than they hold a secret, and `Bearer ` with
    nothing after it is a 401 where no header at all is a working anonymous request.
    """
    return ((env if env is not None else os.environ).get(GITHUB_TOKEN) or "").strip() or None


def open_adapter(
    name: str,
    client: "httpx.AsyncClient",
    *,
    env: Mapping[str, str] | None = None,
) -> "BaseSourceAdapter":
    """The one way to construct a catalogue adapter, credential included.

    **Every construction site was `adapter_for(client)` and every one dropped the token.** Both
    adapters declared the parameter, both built the header correctly, and nothing had ever
    passed one — so the whole authenticated path was dead code that read as working. A
    constructor a caller can spell correctly-but-incompletely is a constructor that will be, and
    the fix is to leave one spelling rather than to remember the keyword.
    """
    kinds = adapters()
    if name not in kinds:
        raise ValueError(
            coded("MF0001", f"{name!r} is not a catalogue source")
            + f"\n  known: {', '.join(sorted(kinds)) or '(none)'}"
        )
    return kinds[name](client, token=upstream_token(env))
