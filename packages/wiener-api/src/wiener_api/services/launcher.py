"""Launching the head process, and the config that makes it report.

**Two things go in `-c site.config` and neither may enter the artifact**
(`docs/design/execution-boundary.md` §6): where the executor runs, and where to post events.
`trace.enabled` is the third, and it is what `docs/design/wiener.md` §4.3 finding 6 is about —
without it fifteen resource fields never arrive and the dashboard is empty for a reason nothing
on screen would explain.
"""

import json
import shutil
import subprocess
from pathlib import Path

from wiener_api import db, repository
from wiener_api.models import Run
from wiener_api.settings import settings


def work_dir(run_id: str) -> Path:
    """Server-chosen, from an opaque id. Never a client-supplied path."""
    return settings.work_root / run_id


def _resource_limits() -> str:
    """How big this machine is — **the definitive site fact**, and the reason the emitted
    config may state what a process *asks for* without knowing what it can *have*.

    `execution-boundary.md` §6: site facts live here and never in the artifact. nf-core's
    convention asks `process_medium` for 36 GB, which is right on a cluster and unschedulable on
    a laptop — Nextflow refuses rather than clamping, so without this the labels Mendel now
    emits would stop every local run dead.

    `resourceLimits` is Nextflow's own clamp and replaced the old `check_max` helper.
    """
    import os

    cpus = os.cpu_count() or 1
    try:
        pages = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        gigabytes = max(1, int(pages / 1024**3))
    except (ValueError, OSError):  # a platform without sysconf; be conservative rather than wrong
        gigabytes = 4
    return f"process.resourceLimits = [ cpus: {cpus}, memory: {gigabytes}.GB, time: 24.h ]\n"


def site_config(run: Run) -> str:
    url = f"{settings.ingest_base_url}/events/{run.id}/{run.ingest_secret}"
    return (
        _resource_limits() +
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


def command(run: Run, workdir: str, has_params: bool = False) -> list[str]:
    """The head process's argv.

    **Two profiles, never one.** The emitted config separates the executor from the container
    runtime, and its own `k8s` profile says so: `-profile k8s,docker -c site.config`. Site
    facts name *which* profile, never restate what it means.

    **`-params-file`, not a splice of `--input`.** The values a laboratory supplies fill the
    artifact's declared nulls, and there may be any number of them — a file is Nextflow's own
    mechanism for that, it survives values a shell would mangle, and it leaves a readable
    record of what this run was given beside the config that ran it.
    """
    argv = [
        "nextflow", "run", ".",
        "-profile", f"{run.executor},{settings.container_profile}",
        "-c", f"{workdir}/site.config",
        "-w", f"{workdir}/work",
        "-name", f"wiener-{run.id}",
    ]
    if has_params:
        argv += ["-params-file", f"{workdir}/params.json"]
    return argv


def _spawn(argv: list[str], cwd: Path) -> subprocess.Popen[bytes]:
    """The subprocess seam, so a test can stand in for Nextflow — the same reason
    `mendel_api.services.gates._run` exists: CI has no Nextflow and a rule only a developer
    machine can check is a rule nobody checks."""
    return subprocess.Popen(argv, cwd=cwd)


def launch(run_id: str, params: dict[str, object] | None = None) -> None:
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
        if params:
            (workdir / "params.json").write_text(json.dumps(params, indent=2, sort_keys=True))
        run.phase = "launching"
        argv = command(run, workdir=str(workdir), has_params=bool(params))

    _spawn(argv, cwd=workdir)
