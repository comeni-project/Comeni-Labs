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


def pipeline_digest(artifact_id: str) -> str | None:
    """Which *pipeline* this artifact is — **the join key between the two halves.**

    `RunArtifact.pipeline_digest` was declared in W1 and **never written**: a column with the
    right type, the right nullability, and no assignment anywhere in the repository. Plan 4
    phase 2 is what needed it, twice — *runs per pipeline* on the front door and *vs usual* on
    the board — and both are impossible without a key that survives the trip.

    **Not the tree digest.** `store()` already returns one, and it covers the whole uploaded
    directory including the vendored `modules/` tree — so re-vendoring a module makes the same
    pipeline look like a different one. `Pipeline.content_digest()` is over the artifact's own
    document, which is what *the same pipeline* means.

    **This is deliberately the opposite of what a LAYER digest does, and both are right.**
    `comeni_core.artifact.digest.digest_of_directory` covers a layer's `module/` trees since
    Plan 5A, so a byte of a vendored `main.nf` *does* move the layer digest — a `pipeline.yml`
    pins a layer, and a digest covering the declarations but not the code they describe would
    read as a guarantee and not be one.

    The two answer different questions. *Is this the same layer* has to move when the code
    moves; *is this the same pipeline* must not. Written down here as well as in
    `docs/design/federation.md` §3.6, so that nobody reconciles one into the other on the
    reasonable-sounding grounds that two digests over the same subject ought to agree.

    **Neither server has to learn the other's identifiers.** Mendel reports the same value in
    `GET /api/pipeline/drafts`, computed by the same method over the same file, so the browser
    joins them on content alone — `wiener.md` §12's whole shape, and the reason `useSubmit.ts`
    can be the only place that touches both.

    `None` when the artifact carries no readable `pipeline.yml`. **A wrong key is worse than an
    absent one**, and the column is already nullable: a run that cannot be attributed to a
    pipeline shows under *every run* without one, which is true, rather than under somebody
    else's, which is not.
    """
    from comeni_core import yaml_strict
    from comeni_core.artifact.pipeline import Pipeline

    path = settings.artifact_root / artifact_id / "pipeline.yml"
    try:
        return Pipeline.model_validate(yaml_strict.load(path)).content_digest()
    except Exception:  # noqa: BLE001 — an unreadable artifact is not a reason to refuse a run
        return None


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
