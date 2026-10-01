"""What Mendel reports in the read-only sections (spec §7).

**A token is reported as set or not set, never as itself**, and is never a declaration's `env`
(which would make the resolver serve it). Every reporter is cheap or bounded: the menu calls
each one on every read.
"""

import asyncio
import contextlib
import os
from collections.abc import Callable
from importlib import metadata

from sqlalchemy import text

from mendel_api import db, worker
from mendel_api.settings import settings

PARTS = (
    "comeni-core", "comeni-ai", "mendel-resolver", "mendel-compiler", "mendel-forge",
    "mendel-api", "dag-core",
)


def token_state(*names: str) -> str:
    present = [bool(os.environ.get(n, "").strip()) for n in names]
    if all(present):
        return "set"
    if any(present):
        return "not set (needs both the user and the token)"
    return "not set"


def _versions() -> list[dict]:
    rows = []
    for part in PARTS:
        try:
            rows.append({"part": part, "version": metadata.version(part)})
        except metadata.PackageNotFoundError:
            rows.append({"part": part, "version": "not installed"})
    return rows


def _layers() -> object:
    from mendel_api.services import registry

    # **Checked first**: a missing folder loads as an empty registry rather than raising, which
    # would report the path as though all were well.
    if not settings.registry_root.is_dir():
        return f"not readable (no such folder) at {settings.registry_root}"
    try:
        return [str(p) for p in registry.stack().paths]
    except Exception as failed:
        return f"not readable ({type(failed).__name__}) at {settings.registry_root}"


def _first(value: int | set[int] | None) -> int:
    """arq keeps `hour`/`minute` as given: a number (checked 2026-10-01: `hour: 3`) or a set."""
    if value is None:
        return 0
    return value if isinstance(value, int) else min(value)


def _source_check() -> str:
    for job in worker.WorkerSettings.cron_jobs:
        if job.coroutine.__name__ == "check_sources":
            return f"every day at {_first(job.hour):02d}:{_first(job.minute):02d}"
    return "not scheduled"


def _database() -> str:
    try:
        with db.session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return "not reachable"
    return "answers"


def _redis() -> str:
    from mendel_api.routes.health import _worker_and_depth

    try:
        alive, depth = asyncio.run(_worker_and_depth())
    except Exception:
        return "not reachable"
    return f"answers; worker {'running' if alive else 'not running'}; {depth} waiting"


def _model() -> str:
    from mendel_api.services import probe
    from mendel_api.settings import model_access

    access = model_access()
    if access is None:
        return "no model configured"
    if not access.base_url:
        return f"{access.model}: a hosted provider, not probed"
    with contextlib.suppress(Exception):
        if asyncio.run(probe.answers(access.base_url)):
            return f"{access.model}: answers"
    return f"{access.model}: nothing answered"


REPORTERS: dict[str, Callable[[], object]] = {
    "registry.root": lambda: str(settings.registry_root),
    "registry.layers": _layers,
    "registry.github": lambda: token_state("COMENI_FORGE_GITHUB_TOKEN"),
    "registry.dockerhub": lambda: token_state(
        "COMENI_FORGE_DOCKERHUB_USER", "COMENI_FORGE_DOCKERHUB_TOKEN"
    ),
    "registry.source_check": _source_check,
    "system.versions": _versions,
    "system.database": _database,
    "system.redis": _redis,
    "system.model": _model,
}
