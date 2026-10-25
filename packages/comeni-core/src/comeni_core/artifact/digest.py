"""Deterministic SHA-256 content addressing for models, files, and registry layers.

Layer digests cover the declarations and vendored module sources selected by
``declared_entries``. The implementation reads only local paths and never uses the network.
"""

import hashlib
from pathlib import Path

from pydantic import BaseModel

from comeni_core.declared.layered import declared_entries
from comeni_core.spell.marks import Digest

_ALGORITHM = "sha256"
_CHUNK = 65536

# This persisted file-kind tag separates file bytes from any future entry kind. NUL prevents
# ordinary path or document data from reproducing the prefix.
_FILE = b"file\x00"


def _hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_of_bytes(data: bytes) -> Digest:
    """Content digest of a generated file, as written.

    Public because `Emitted` records what `mendel publish` wrote, and a bundle's own digests
    have to be reproducible by whoever received it — with the file, not with our code.
    """
    return f"{_ALGORITHM}:{_hex(data)}"


def digest_of(model: BaseModel) -> Digest:
    """Content digest of a Pydantic model, stable across processes.

    `model_dump_json` emits fields in declaration order, and every `frozenset` in this
    codebase carries a `field_serializer` that sorts — which is what makes this stable
    rather than hash-seed dependent. Anything new that serialises a set needs the same
    treatment or it silently breaks this function and every lockfile made with it.
    """
    return f"{_ALGORITHM}:{_hex(model.model_dump_json().encode())}"


def content_hash(data: bytes) -> str:
    """Hash in-memory file content using the directory digest's file-kind prefix."""
    hasher = hashlib.sha256()
    hasher.update(_FILE)
    hasher.update(data)
    return hasher.hexdigest()


def entry_hash(name: str, content_digest: str) -> str:
    """Encode one directory entry from fixed-width name and content hashes.

    Verification code can use this helper instead of duplicating the persisted entry format.
    """
    return f"{_hex(name.encode())}:{content_digest}"


def digest_of_directory(path: Path) -> Digest:
    """Content digest of every entry under `path`, name and bytes alike.

    Relative names are included because renames can change layer meaning even when bytes do not.
    Entries are sorted by relative path, and both name and content are hashed to fixed-width
    fields so a filename cannot forge an entry boundary. A missing directory has the digest of
    an empty entry list.

    Symlinks are refused. Following one would make the digest depend on bytes outside the layer;
    hashing only its target path would differ from the loader, which reads the target bytes.
    """
    parts: list[str] = []
    if path.exists():
        for entry in sorted(declared_entries(path)):
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
            # Keep the streaming calculation equivalent to `content_hash` without buffering a
            # complete registry file.
            parts.append(entry_hash(name, hasher.hexdigest()))
    joined = "\n".join(parts)
    return f"{_ALGORITHM}:{_hex(joined.encode())}"
