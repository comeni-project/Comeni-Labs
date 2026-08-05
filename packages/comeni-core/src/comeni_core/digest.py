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

# Domain separation tags. A regular file and a symlink are different things and must not be
# able to hash alike, however either one is spelled. NUL because no path or YAML document
# contains one, so neither tag can be produced by the data it prefixes.
_FILE = b"file\x00"
_LINK = b"link\x00"


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

    **A symlink is hashed as its target path, never followed.** Following one makes the
    digest depend on bytes outside the layer, so the same directory digests differently on
    two machines — which is precisely what a lockfile exists to rule out. This is what git
    does with symlinks, and layers are distributed by git.

    **The two kinds are domain-separated.** Hashing a link as `"symlink:" + target` and a
    file as its raw bytes let a regular file impersonate a link: `a.yml` containing the text
    `symlink:/etc/passwd` digested identically to `a.yml` symlinked to `/etc/passwd`. That
    is the same defect as the filename forgery above, one layer down — a hash over
    concatenated fields means nothing unless each field can only be read one way.
    """
    parts: list[str] = []
    if path.exists():
        for entry in sorted(p for p in path.rglob("*") if p.is_symlink() or p.is_file()):
            name = entry.relative_to(path).as_posix()
            if entry.is_symlink():
                content = _hex(_LINK + entry.readlink().as_posix().encode())
            else:
                hasher = hashlib.sha256()
                hasher.update(_FILE)
                with entry.open("rb") as handle:
                    while chunk := handle.read(_CHUNK):
                        hasher.update(chunk)
                content = hasher.hexdigest()
            parts.append(f"{_hex(name.encode())}:{content}")
    joined = "\n".join(parts)
    return f"{_ALGORITHM}:{_hex(joined.encode())}"
