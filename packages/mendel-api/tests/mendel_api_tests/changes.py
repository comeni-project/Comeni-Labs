"""Reusable changes scenarios and fixtures for API tests."""

from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import session
from mendel_authoring import commands as c
from mendel_authoring.payloads import DecisionChange

from mendel_api_tests.building import (  # noqa: F401
    _answer_all,
    _resolving,
    authoring_setup,
)
from mendel_api_tests.building import clean as clean


def _versions(sid):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        return row.draft_id, draft.decision_revision, draft.revision, row.row_version


def _change(sid, change: DecisionChange, *, stale=False):
    _draft_id, decision, revision, version = _versions(sid)
    return session.perform(
        c.Change(
            sid,
            change.model_dump(mode="json"),
            "ana",
            decision - 1 if stale else decision,
            revision,
            version,
        )
    ).result
