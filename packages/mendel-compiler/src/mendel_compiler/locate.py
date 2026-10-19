"""Where each registry layer can be fetched, read with git (Part I.0 Plan B, spec §8.2).

Here and not in `comeni-core`, which runs no processes: `Pipeline.of` takes the locators its
caller read. A layer outside git, or with no network remote, records less, never a guess.
"""

import subprocess
from collections.abc import Sequence
from pathlib import Path

from comeni_core.artifact.lockfile import Locator, LockedLayer
from comeni_core.declared.layer import layer_name
from comeni_core.diagnostics import coded
from comeni_core.spell.marks import LayerName, RepoUrl
from pydantic import TypeAdapter, ValidationError

_URL = TypeAdapter(RepoUrl)


def _git(layer: Path, *args: str) -> str | None:
    done = subprocess.run(["git", "-C", str(layer), *args], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def _without_credentials(url: str) -> str:
    """`https://bot:token@host/x` as `https://host/x`; an ssh user without a password stays."""
    scheme, found, rest = url.partition("://")
    if not found:
        return url
    host, slash, path = rest.partition("/")
    user, at, bare = host.rpartition("@")
    if at and (scheme != "ssh" or ":" in user):
        host = bare if scheme != "ssh" else f"{user.partition(':')[0]}@{bare}"
    return f"{scheme}://{host}{slash}{path}"


def _source(layer: Path) -> str | None:
    url = _git(layer, "remote", "get-url", "origin")
    if not url:
        return None
    try:
        return _URL.validate_python(_without_credentials(url))
    except ValidationError:
        return None  # a local path or `file://`: somebody's machine, not a source


def locate(layer: Path) -> Locator:
    """The layer's remote, commit, folder in the repository, and whether it has uncommitted
    edits under it."""
    if _git(layer, "rev-parse", "--show-toplevel") is None:
        return Locator()
    folder = (_git(layer, "rev-parse", "--show-prefix") or "").rstrip("/")
    return Locator(source=_source(layer), commit=_git(layer, "rev-parse", "HEAD"),
                   dirty=bool(_git(layer, "status", "--porcelain", "--", ".")),
                   path=folder or None)


def locators(layers: Sequence[Path]) -> dict[LayerName, Locator]:
    return {layer_name(layer): locate(layer) for layer in layers}


def findings(layers: Sequence[LockedLayer]) -> list[str]:
    """What a built file cannot do on its own, one coded sentence each (MD0231, MD0232): said by
    the CLI on `build` and `upgrade`, and by keep and preview in the app (review #3)."""
    said = []
    for layer in layers:
        if layer.source is None:
            said.append(coded("MD0231", f"layer {layer.name} has no network source in git; "
                              "this pipeline cannot be rebuilt from its file alone"))
        if layer.dirty:
            held = (f"commit {layer.commit[:12]} does not hold what was built" if layer.commit
                    else "it has no commit yet")
            said.append(coded("MD0232", f"layer {layer.name} has uncommitted edits; {held}"))
    return said
