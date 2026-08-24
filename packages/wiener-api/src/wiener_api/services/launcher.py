"""Launching the head process, and the config that makes it report.

**Two things go in `-c site.config` and neither may enter the artifact**
(`docs/design/execution-boundary.md` §6): where the executor runs, and where to post events.
`trace.enabled` is the third, and it is what `docs/design/wiener.md` §4.3 finding 6 is about —
without it fifteen resource fields never arrive and the dashboard is empty for a reason nothing
on screen would explain.
"""

import shutil
import subprocess
from pathlib import Path

from wiener_api import db, repository
from wiener_api.models import Run
from wiener_api.settings import settings


def work_dir(run_id: str) -> Path:
    """Server-chosen, from an opaque id. Never a client-supplied path."""
    return settings.work_root / run_id


def site_config(run: Run) -> str:
    url = f"{settings.ingest_base_url}/events/{run.id}/{run.ingest_secret}"
    return (
        "// Written by Wiener at launch. Site facts only — never the artifact.\n"
        "weblog {\n"
        "    enabled = true\n"
        f"    url = '{url}'\n"
        "}\n"
        "trace {\n"
        "    enabled = true\n"
        "    overwrite = true\n"
        "}\n"
    )


def command(run: Run, workdir: str, samplesheet: str = "-") -> list[str]:
    """The head process's argv.

    **`--input` is here because nothing else carries it.** The submit body takes a samplesheet
    and §7.1 forbids a column for it, so it rides to the launcher as a job argument and lands
    on the command line — which is where `params.input` expects it: the emitted pipeline
    references it as a placeholder the lab fills at run time (invariant 15). The plan accepted
    a samplesheet at `POST /api/runs` and passed it to nothing, and Checkpoint 2's own script
    submits `"-"`, so no step in this phase would have noticed.
    """
    argv = [
        "nextflow", "run", ".",
        "-profile", f"{run.executor},{settings.container_profile}",
        "-c", f"{workdir}/site.config",
        "-w", f"{workdir}/work",
        "-name", f"wiener-{run.id}",
    ]
    if samplesheet and samplesheet != "-":
        argv += ["--input", samplesheet]
    return argv


def _spawn(argv: list[str], cwd: Path) -> subprocess.Popen[bytes]:
    """The subprocess seam, so a test can stand in for Nextflow — the same reason
    `mendel_api.services.gates._run` exists: CI has no Nextflow and a rule only a developer
    machine can check is a rule nobody checks."""
    return subprocess.Popen(argv, cwd=cwd)


def launch(run_id: str, samplesheet: str = "-") -> None:
    """Copy the artifact somewhere Wiener owns, write the site config, and start Nextflow.

    The artifact is COPIED rather than run in place: a second run of the same artifact must not
    share a working directory with the first, and Wiener owns what it executes — §12.
    """
    with db.session_scope() as session:
        run = repository.run(session, settings.lab_id, run_id)
        if run is None:
            raise LookupError(f"no run {run_id}")
        artifact = repository.artifact(session, settings.lab_id, run.artifact_id)
        if artifact is None:
            raise LookupError(f"run {run_id} names artifact {run.artifact_id}, which is gone")

        workdir = work_dir(run_id)
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(settings.artifact_root / artifact.id, workdir, dirs_exist_ok=True)
        (workdir / "site.config").write_text(site_config(run))
        run.phase = "launching"
        argv = command(run, workdir=str(workdir), samplesheet=samplesheet)

    _spawn(argv, cwd=workdir)
