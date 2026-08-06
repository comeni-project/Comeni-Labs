"""Content addressing for contracts and registry layers.

A lockfile has to be able to say "this pipeline was built against exactly this contract",
and a version string cannot say that — a contract can be edited without its `@version`
moving, and in a private overlay it routinely is.

`hashlib` and `pathlib` are on `comeni-core`'s purity allowlist deliberately; this is what
they were put there for. Nothing here reads the network.
"""

import hashlib
from pathlib import Path

from pydantic import BaseModel

from comeni_core.marks import Digest

_ALGORITHM = "sha256"
_CHUNK = 65536

# Domain separation tag. Its sibling `_LINK` is gone with the symlink branch it tagged —
# a layer may no longer contain one (A9) — but this stays: it is in every digest ever
# written, and the moment a second entry kind is added it is what keeps the two from
# hashing alike. NUL because no path or YAML document contains one, so the tag cannot be
# produced by the data it prefixes.
_FILE = b"file\x00"


def _hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_of(model: BaseModel) -> Digest:
    """Content digest of a Pydantic model, stable across processes.

    `model_dump_json` emits fields in declaration order, and every `frozenset` in this
    codebase carries a `field_serializer` that sorts — which is what makes this stable
    rather than hash-seed dependent. Anything new that serialises a set needs the same
    treatment or it silently breaks this function and every lockfile made with it.
    """
    return f"{_ALGORITHM}:{_hex(model.model_dump_json().encode())}"


def digest_of_directory(path: Path) -> Digest:
    """Content digest of every entry under `path`, name and bytes alike.

    Names are included because renaming a contract file changes which layer it belongs to
    and can change load order, even when no byte of content moved.

    Sorted by relative path so two copies of the same layer digest identically regardless
    of the order the filesystem happened to hand them over. A missing directory digests to
    the digest of nothing, because a layer with no `rules/` is ordinary rather than broken.

    **The name is hashed, not embedded.** An earlier version joined `f"{name}:{hash}"` with
    newlines, which let a filename forge an entry boundary: a single file named
    `a.yml:<sha of alpha>\\nb.yml` containing "beta" digests identically to a two-file layer
    holding `a.yml`/"alpha" and `b.yml`/"beta". Measured, not theorised. A forgeable digest
    is not a digest, and Task 8 makes layers a thing strangers distribute. Hashing both
    halves makes every field fixed-width hex, so no content can span a delimiter.

    **A layer may not contain a symlink at all, and this raises on one.** An earlier
    version hashed a link as its target path and never followed it — correct about the
    hazard of following one (the digest would depend on bytes outside the layer, so the
    same directory would digest differently on two machines) and wrong about the remedy.
    `Registry.load` opens the same path with `read_text()`, which *does* follow it, so the
    bytes routed on were not the bytes pinned: a symlinked contract whose target was
    rewritten to `priority: 999` rerouted the pipeline with a byte-identical layer digest
    and no drift. That is invariant 11's closing sentence — never let an installed overlay
    reroute a pipeline silently — defeated by the mechanism written to uphold it.

    Refusing is smaller than resolving and it is honest: a layer is a unit strangers
    distribute, so a link out of it is already meaningless to whoever receives it, and a
    link inside it is a copy with extra steps. Audit 2026-08-06, A9.

    A symlinked *directory* was never exploitable — `rglob` does not descend into one, so
    neither this nor `Registry.load` saw anything inside it — but it is refused too,
    because "the layer contains a link" is a simpler rule to state and to check than "the
    layer contains a link to a file".
    """
    parts: list[str] = []
    if path.exists():
        for entry in sorted(p for p in path.rglob("*") if p.is_symlink() or p.is_file()):
            name = entry.relative_to(path).as_posix()
            if entry.is_symlink():
                raise ValueError(
                    f"{name} is a symlink; a registry layer may not contain one. The "
                    "loader follows it and this digest cannot, so the bytes routed on "
                    "would not be the bytes pinned (audit 2026-08-06, A9)."
                )
            hasher = hashlib.sha256()
            hasher.update(_FILE)
            with entry.open("rb") as handle:
                while chunk := handle.read(_CHUNK):
                    hasher.update(chunk)
            parts.append(f"{_hex(name.encode())}:{hasher.hexdigest()}")
    joined = "\n".join(parts)
    return f"{_ALGORITHM}:{_hex(joined.encode())}"
