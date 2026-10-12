"""Deleting a run a person asks to delete (Part H spec §5.1). Only a finished one; permanent.

Its rows, its whole directory (working files, results, `params.json`, `site.config`) and its
stream go. Its pipeline goes with it when no other run uses that pipeline — *kept while any run
references it*, the rule Wiener's design recorded for artifacts.
"""

import shutil

from wiener_core.state import RunPhase

from wiener_api import db, repository
from wiener_api.services import launcher, stream
from wiener_api.settings import settings

FINISHED = {RunPhase.SUCCEEDED, RunPhase.FAILED, RunPhase.CANCELLED, RunPhase.LOST}


class Refused(Exception):
    """A run that is not finished. Said in words, because the remedy is an action."""


def delete_run(run_id: str) -> None:
    with db.session_scope() as session:
        run = repository.run(session, settings.lab_id, run_id, lock=True)
        if run is None:
            raise LookupError(run_id)
        if RunPhase(run.phase) not in FINISHED:
            raise Refused(f"this run is {run.phase}: cancel it first, then delete it")
        artifact_id = run.artifact_id
        repository.delete_run(session, settings.lab_id, run_id)
        orphaned = not repository.artifact_in_use(session, settings.lab_id, artifact_id)
        if orphaned:
            repository.delete_artifact(session, settings.lab_id, artifact_id)
    shutil.rmtree(launcher.work_dir(run_id), ignore_errors=True)
    stream.drop(run_id)
    if orphaned:
        shutil.rmtree(settings.artifact_root / artifact_id, ignore_errors=True)
