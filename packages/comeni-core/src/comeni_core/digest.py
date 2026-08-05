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
    """Content digest of every file under `path`, name and bytes alike.

    Names are included because renaming a contract file changes which layer it belongs to
    and can change load order, even when no byte of content moved.

    Sorted by relative path so two copies of the same layer digest identically regardless
    of the order the filesystem happened to hand them over. A missing directory digests to
    the digest of nothing, because a layer with no `rules/` is ordinary rather than broken.
    """
    parts: list[str] = []
    if path.exists():
        for file in sorted(p for p in path.rglob("*") if p.is_file()):
            hasher = hashlib.sha256()
            with file.open("rb") as handle:
                while chunk := handle.read(_CHUNK):
                    hasher.update(chunk)
            parts.append(f"{file.relative_to(path).as_posix()}:{hasher.hexdigest()}")
    joined = "\n".join(parts)
    return f"{_ALGORITHM}:{_hex(joined.encode())}"
