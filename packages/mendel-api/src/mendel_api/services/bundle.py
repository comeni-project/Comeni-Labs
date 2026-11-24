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
whatever a stub gate materialised, none of which is the pipeline. The archive holds the four
entries §12's diagram names, plus what makes a download usable on its own (#619): a README,
and the `test` profile's samplesheet when there is one. That is the same reason
`declared_entries()` replaced a `rglob("*")` when the registry became a submodule: a directory
grows things nobody chose. Each added entry is derived from `pipeline.yml`, like the rest.
"""

import io
import zipfile
from collections.abc import Iterable
from pathlib import Path

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.tiers import InputForm
from mendel_compiler import pipeline_file, readme, report
from mendel_compiler.emit import (
    TEST_SAMPLESHEET,
    emit,
    emit_config,
    test_profile_missing,
    test_samplesheet,
)

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

    modules = directory / MODULES
    return archive(artifact.read_text(), pipeline_file.load(artifact), [
        (f"{MODULES}/{path.relative_to(modules)}", path)
        for path in sorted(p for p in modules.rglob("*") if p.is_file())
    ])


def decisions(draft_id: str) -> str:
    """The kept pipeline's decisions report (#619), the page the bundle carries as
    `decisions.html`. Raises `KeyError` when nothing has been kept under this id."""
    artifact = _directory(draft_id) / pipeline_file.FILENAME
    if not artifact.is_file():
        raise KeyError(draft_id)
    return report.render(pipeline_file.load(artifact))


def archive(artifact: str, pipeline: Pipeline,
            modules: Iterable[tuple[str, Path | bytes]]) -> bytes:
    """The zip of one pipeline: its file, what it emits, and `modules` as (name, file), or
    (name, bytes) for a module that is generated rather than vendored (#487)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
        _write(zipped, pipeline_file.FILENAME, artifact)
        _write(zipped, "main.nf", emit(pipeline))
        _write(zipped, "nextflow.config", emit_config(pipeline))
        _write(zipped, "README.md", readme.render(pipeline))
        _write(zipped, readme.DECISIONS, report.render(pipeline))
        # Pinned public URLs, never anybody's samples: the file the `test` profile names, which
        # only the gate used to write, so a downloaded zip could not run its own test.
        if pipeline.input_form is InputForm.SAMPLESHEET and not test_profile_missing(pipeline):
            _write(zipped, TEST_SAMPLESHEET, test_samplesheet(pipeline))
        for name, source in modules:
            _write(zipped, name, source if isinstance(source, bytes) else source.read_bytes())
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
