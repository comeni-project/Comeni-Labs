"""A gated pipeline directory, uploaded and content-addressed.

**Wiener owns what it runs** — §12. The browser is the courier, so nothing here reads a path
the client chose and nothing here reaches back into Mendel's storage.
"""

import hashlib
import io
import secrets
import zipfile
from pathlib import Path

from wiener_api.settings import settings


def _digest_of_tree(root: Path) -> tuple[str, int]:
    """Over the SORTED (relative path, sha256) pairs, not over the zip.

    Two uploads of the same tree must agree even when the archives differ byte for byte —
    zip carries timestamps, ordering and compression choices that say nothing about content.
    Same argument as `digest_of_directory` in the resolver, and the same shape.
    """
    running, size = hashlib.sha256(), 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        data = path.read_bytes()
        size += len(data)
        running.update(str(path.relative_to(root)).encode())
        running.update(hashlib.sha256(data).digest())
    return f"sha256:{running.hexdigest()}", size


def store(bundle: bytes) -> tuple[str, str, int]:
    """Unpack an uploaded pipeline directory and content-address it."""
    artifact_id = secrets.token_hex(16)
    root = settings.artifact_root / artifact_id
    root.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        for member in archive.infolist():
            # A zip may name `../../etc/passwd`, and `extractall` on some versions will write
            # it. The upload is authenticated by nothing in W1 (§12.1), so the check is here
            # rather than trusted to the caller.
            target = (root / member.filename).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError(f"archive member escapes the artifact directory: "
                                 f"{member.filename!r}")
        archive.extractall(root)
    digest, size = _digest_of_tree(root)
    return artifact_id, digest, size
