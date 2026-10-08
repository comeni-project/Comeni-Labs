"""Rows the tests build by hand, built whole: a run's artifact is a key (issue 274).

A module rather than `conftest.py`, so a test can import it: two packages' `conftest` modules
share one name on `sys.path`.
"""

import secrets
from datetime import UTC, datetime

from wiener_api.models import Run, RunArtifact
from wiener_api.settings import settings


def an_artifact(session, lab_id: str = settings.lab_id) -> str:
    """A `run_artifact` row for a run to point at."""
    artifact_id = secrets.token_hex(16)
    session.add(RunArtifact(id=artifact_id, lab_id=lab_id, uploaded_by="test",
                            uploaded_at=datetime.now(UTC), digest="sha256:" + "0" * 64,
                            size_bytes=0))
    session.flush()
    return artifact_id


def a_run(session, lab_id: str = settings.lab_id, **overrides) -> Run:
    """A run in `lab_id`, with its artifact, committed."""
    fields = {
        "id": secrets.token_hex(16), "lab_id": lab_id,
        "artifact_id": an_artifact(session, lab_id), "submitted_by": "test",
        "submitted_at": datetime.now(UTC), "phase": "queued", "executor": "local",
        "ingest_secret": secrets.token_hex(16),
    }
    row = Run(**{**fields, **overrides})
    session.add(row)
    session.commit()
    return row
