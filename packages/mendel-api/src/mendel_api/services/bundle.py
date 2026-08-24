"""A kept pipeline, as a zip somebody else can run.

**Mendel's half of the courier — A179.** `docs/design/wiener.md` §12: the browser fetches the
artifact from here and posts it to Wiener, so `mendel-api` never learns Wiener exists and
`execution-boundary.md` §9's rejection of a Mendel→Wiener API stays intact rather than quietly
bending. Nothing in this module knows a Wiener URL, a Wiener id, or that a run is what happens
next.

**The Nextflow is re-emitted rather than copied**, which is the one decision here worth stating.
A gate writes `main.nf` and `nextflow.config` into the draft directory as a side effect of
running, so copying them would make the bundle's contents depend on whether somebody had gated —
and an un-gated draft would ship a directory with no workflow in it. Emitting from `pipeline.yml`
is exactly what `mendel emit` does: no registry, no network, byte-identical for the same
artifact. **The artifact is the pipeline**, and everything else in the zip is derived from it.

**An allowlist, not a sweep.** The draft directory accumulates `work/`, `.nextflow.log` and
whatever a stub gate materialised, none of which is the pipeline. Four entries go in the
archive — the four §12's diagram names — for the same reason `declared_entries()` replaced a
`rglob("*")` when the registry became a submodule: a directory grows things nobody chose.
"""

import io
import zipfile
from pathlib import Path

from mendel_compiler import pipeline_file
from mendel_compiler.emit import emit, emit_config

from mendel_api.settings import settings

MODULES = "modules"
"""Where `keep` puts the vendored source, and where every `include` in the emitted workflow
points. Named once so the archive and `services/drafts.py` cannot disagree about it."""


def _directory(draft_id: str) -> Path:
    """The source seam. Server-chosen, never client-supplied — invariant 15, and the same
    derivation `drafts._output_root` and `gates._directory` already make."""
    return settings.draft_root / draft_id


def of(draft_id: str) -> bytes:
    """The zip. Raises `KeyError` when nothing has been kept under this id.

    **Deterministic, and that is load-bearing rather than tidy.** Wiener content-addresses what
    it is handed over the sorted (path, sha256) pairs, so two people submitting the same
    pipeline must produce the same digest. A zip carries timestamps; these entries are written
    with a fixed one, in sorted order, so the archive says nothing the tree does not.
    """
    directory = _directory(draft_id)
    artifact = directory / pipeline_file.FILENAME
    if not artifact.is_file():
        raise KeyError(draft_id)

    pipeline = pipeline_file.load(artifact)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        _write(archive, pipeline_file.FILENAME, artifact.read_text())
        _write(archive, "main.nf", emit(pipeline))
        _write(archive, "nextflow.config", emit_config(pipeline))

        modules = directory / MODULES
        for path in sorted(p for p in modules.rglob("*") if p.is_file()):
            _write(archive, f"{MODULES}/{path.relative_to(modules)}", path.read_bytes())
    return buffer.getvalue()


def _write(archive: zipfile.ZipFile, name: str, data: str | bytes) -> None:
    """One entry, with a fixed timestamp so the same tree is the same archive.

    `1980-01-01` is the zero of the zip epoch — the value the format uses when it has nothing
    to say — rather than a date anybody should read as when this was built.

    **A `ZipInfo` is what makes it deterministic, not the date argument.** `writestr(name, data)`
    with a plain string builds its own `ZipInfo` from the clock; a `ZipInfo` constructed here
    already defaults to the epoch. The date is passed explicitly anyway, because a reader should
    not have to know that default to see what the guarantee is.
    """
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)
