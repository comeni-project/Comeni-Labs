"""Launching the head process, and the config that makes it report.

**Two things go in `-c site.config` and neither may enter the artifact**
(`docs/design/execution-boundary.md` §6): where the executor runs, and where to post events.
`trace.enabled` is the third, and it is what `docs/design/wiener.md` §4.3 finding 6 is about —
without it fifteen resource fields never arrive and the dashboard is empty for a reason nothing
on screen would explain.
"""

import json
import logging
import pathlib
import shutil
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from comeni_core.diagnostics import coded
from wiener_core.state import RunPhase

from wiener_api import db, repository
from wiener_api.models import Run
from wiener_api.services.artifacts import declared_holes
from wiener_api.settings import settings

log = logging.getLogger(__name__)


def work_dir(run_id: str) -> Path:
    """Server-chosen, from an opaque id. Never a client-supplied path."""
    return settings.work_root / run_id


def params_path(run_id: str) -> Path:
    """Where a run's parameters wait for launch: in its own directory, never in a table
    (invariant 15), so deleting the run deletes them and a lost queue loses none (#273)."""
    return work_dir(run_id) / "params.json"


def write_params(run_id: str, params: dict[str, object]) -> None:
    path = params_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(params, indent=2, sort_keys=True))


def results_dir(run_id: str) -> Path:
    """Where this run's published outputs land — **a site fact, chosen here.**

    The emitted pipeline publishes to `params.outdir` and declares it `null`, because where a
    laboratory keeps its results is not a property of the pipeline (`emit.py`'s `PUBLISH_DIR`).
    Wiener supplies the value, from the same server-chosen opaque id `work_dir` uses, so no path
    is ever accepted from a client.

    Inside the run's own directory rather than beside it: a run's outputs, its work directory,
    its `site.config` and its `params.json` are one thing to keep or delete.
    """
    return work_dir(run_id) / "results"


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
        # **`--outdir` here and NOT in `site.config`, and it is not a preference.**
        # `publishDir`'s `enabled:` is an expression Nextflow evaluates while reading the
        # `process {` scope. A `-c` file is layered on top, and a `profiles {` block is read
        # after — so neither can switch publishing on, while a command-line param can, because
        # those are injected before parsing. Measured against a real stub run on 2026-08-30: a
        # profile-set `outdir` published nothing with every process green; the same config with
        # `--outdir` published 41 files. `gates.py` carries the same line for the same reason.
        "--outdir", str(results_dir(run.id)),
        "-name", f"wiener-{run.id}",
    ]
    if has_params:
        argv += ["-params-file", f"{workdir}/params.json"]
    return argv


def process_started_at(pid: int) -> float | None:
    """When this pid began, from `/proc/<pid>/stat` field 22 — **the thing that makes a pid an
    identity**.

    Pids are reused. A cancel that signals a recycled one kills a stranger's process, which on
    a laptop is plausibly the user's editor and on a shared host is somebody else's run. The
    number alone cannot tell the two apart; the number *and* the start time can, because a
    process cannot inherit both.

    `None` where `/proc` is not readable — macOS, or a hardened container. The caller treats
    that as *cannot verify*, and `cancel` refuses rather than signalling on a pid alone:
    refusing costs a person one manual `kill`, and guessing wrong costs somebody a process
    they never offered up.
    """
    try:
        fields = pathlib.Path(f"/proc/{pid}/stat").read_text()
        # The comm field is parenthesised and may contain spaces, so split after its close.
        return float(fields[fields.rindex(")") + 2:].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _spawn(argv: list[str], cwd: Path) -> subprocess.Popen[bytes]:
    """The subprocess seam, so a test can stand in for Nextflow — the same reason
    `mendel_api.services.gates._run` exists: CI has no Nextflow and a rule only a developer
    machine can check is a rule nobody checks."""
    return subprocess.Popen(argv, cwd=cwd)


def _materialise_tables(params: dict[str, object], workdir: pathlib.Path) -> dict[str, object]:
    """Turn a submitted samplesheet into a CSV in the workdir, and point the param at it.

    ═══ WHY WIENER WRITES IT AND MENDEL NEVER SEES IT ════════════════════════════════════════

    A samplesheet is a table of sample identifiers and paths — **data**. Mendel emits a pipeline
    that *references* `params.input` and never receives one (invariant 15); Wiener is the half
    that launches runs and is allowed to hold run data, which is the whole reason the two are
    separate services.

    **Written into the workdir, never into a table** (invariant 15,
    `docs/design/invariants.md`): no table holds a samplesheet. The workdir is transient by
    nature and is deleted with the run, which is the right lifetime for the one artefact that
    names a laboratory's files.

    A `str` value is passed through unchanged — that is a path the laboratory already has, and
    a person who wants to point at their own samplesheet still can. The browser's table editor
    is a convenience over this, not a gate in front of it.
    """
    written: dict[str, object] = {}
    for name, value in params.items():
        rows = value if isinstance(value, list) else None
        if not rows or not all(isinstance(row, dict) for row in rows):
            written[name] = value
            continue
        columns = list(rows[0])
        path = workdir / f"{name}.csv"
        lines = [",".join(columns)]
        lines += [",".join(str(row.get(column, "")) for column in columns) for row in rows]
        path.write_text("\n".join(lines) + "\n")
        written[name] = str(path)
    return written


def launch(run_id: str) -> bool:
    """Copy the artifact somewhere Wiener owns, write the site config, and start Nextflow.
    Answers whether it launched.

    The artifact is COPIED rather than run in place: a second run of the same artifact must not
    share a working directory with the first, and Wiener owns what it executes — §12.

    **Only a `queued` run is launched, and claimed first** (issue 273). arq delivers at least
    once, so a worker restarted mid-launch re-delivers this job; without the claim a second
    Nextflow started in the same work directory. The row is locked, the phase read, and
    `launching` written in one transaction, so a redelivery waits on the lock and then finds the
    run claimed. A run claimed already is skipped, not failed: failing would make arq retry.
    """
    with db.session_scope() as session:
        run = repository.run(session, settings.lab_id, run_id, lock=True)
        if run is None:
            raise LookupError(f"no run {run_id}")
        if run.phase != "queued":
            log.info("run %s is %s, not queued: already claimed, not launched again",
                     run_id, run.phase)
            return False
        run.phase = "launching"
        artifact = repository.artifact(session, settings.lab_id, run.artifact_id)
        if artifact is None:
            raise LookupError(f"run {run_id} names artifact {run.artifact_id}, which is gone")

        workdir = work_dir(run_id)
        workdir.mkdir(parents=True, exist_ok=True)
        # Made now rather than left to Nextflow, so a run that publishes nothing has an empty
        # directory rather than none. `/results` can then answer *this run produced no output*
        # instead of 404ing, which reads as *no such run* — absence is absence, and the two
        # absences are different facts.
        results_dir(run_id).mkdir(parents=True, exist_ok=True)
        stored = params_path(run_id)
        params = json.loads(stored.read_text()) if stored.exists() else {}
        if not params and declared_holes(artifact.id):
            # **Failed, said so, never launched empty** (review finding 3): a declared input
            # with nothing to fill it would run with every one of them null. An observation
            # written on the row, as the heartbeat writes `lost`; no event will come.
            log.error(coded("MW0102", f"run {run_id} has no parameters to launch with"))
            run.phase = RunPhase.FAILED
            run.ended_at = datetime.now(UTC)
            return False
        shutil.copytree(settings.artifact_root / artifact.id, workdir, dirs_exist_ok=True)
        (workdir / "site.config").write_text(site_config(run))
        if params:
            params = _materialise_tables(params, workdir)
            stored.write_text(json.dumps(params, indent=2, sort_keys=True))
        argv = command(run, workdir=str(workdir), has_params=bool(params))

    spawned = _spawn(argv, cwd=workdir)

    # **What was spawned, remembered — Plan 6 phase 1.** Until this line the `Popen` was
    # discarded where it was created, so nothing in Wiener could act on a running pipeline:
    # there was no pid anywhere and `cancel` had nothing to signal.
    #
    # **Recorded after the spawn and in its own transaction**, because the first one is closed
    # by then — and because a pid written before the process exists would name nothing if the
    # spawn threw.
    with db.session_scope() as session:
        run = repository.run(session, settings.lab_id, run_id)
        if run is not None:
            run.pid = spawned.pid
            run.pid_started_at = process_started_at(spawned.pid)
            run.pid_host = socket.gethostname()
    return True
