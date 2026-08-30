"""A gated pipeline directory, uploaded and content-addressed.

**Wiener owns what it runs** — §12. The browser is the courier, so nothing here reads a path
the client chose and nothing here reaches back into Mendel's storage.
"""

import hashlib
import io
import re
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


SUPPLIED_BY_WIENER = frozenset({"outdir"})
"""Nulls in the artifact that are **site facts Wiener fills**, not questions for a laboratory.

`outdir` arrived on 2026-08-30 with `publishDir`. It is emitted `= null` exactly as `input` is —
the artifact must not name a destination — so `declared_holes` picked it up and the run sheet
would have asked a person to type a path into the API.

**That is worse than an odd field.** `docs/design/wiener.md` §12's whole shape is that the
browser posts an artifact and Wiener reads the artifact's own holes back out; a hole that is
really a server's own business turns into a client-supplied filesystem path, which is the thing
invariant 15 exists to prevent on Mendel's side and the thing `work_dir`'s docstring refuses on
this one. Wiener already knows where the run's directory is, and passes `--outdir` itself.

**A set rather than a special case**, because the next site fact emitted as a null belongs here
too and should not need this argument made again.
"""


def declared_holes(artifact_id: str) -> set[str]:
    """The parameters this artifact says only the laboratory can supply.

    **The artifact is the schema for a submission.** Mendel emits every value it can justify
    and a placeholder — `= null` — for every value it cannot: `params.input` is the one
    invariant 15 names, and `fasta` and `gtf` are emitted exactly the same way because a
    `Goal` says *`have: genome.fasta`*, a type rather than a file. So a run supplies precisely
    the nulls, and Wiener can check that without knowing anything about the pipeline.

    Only the **top-level** `params` block is read. A profile that assigns `params.fasta` is
    *filling* a hole, not declaring one — which is what the artifact's own `test` profile does.

    `SUPPLIED_BY_WIENER` is subtracted: a null that is a *site* fact is this server's business,
    not a question for anybody.
    """
    config = settings.artifact_root / artifact_id / "nextflow.config"
    if not config.is_file():
        return set()

    text = config.read_text()
    start = None
    for match in re.finditer(r"^params\s*\{", text, re.MULTILINE):
        start = match.end()
        break
    if start is None:
        return set()

    depth, end = 1, start
    while end < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[end], 0)
        end += 1

    nulls = set(re.findall(r"^\s*(\w+)\s*=\s*null\s*$", text[start:end - 1], re.MULTILINE))
    return nulls - SUPPLIED_BY_WIENER
