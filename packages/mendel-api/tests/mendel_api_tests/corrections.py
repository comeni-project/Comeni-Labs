"""Reusable corrections scenarios and fixtures for API tests."""

from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import session
from mendel_authoring import commands as c

from mendel_api_tests.building import (  # noqa: F401
    _answer_all,
    _draft,
    _phase,
    _proposal,
    _resolving,
    authoring_setup,
)
from mendel_api_tests.building import clean as clean


def _correct(sid, subject, value, *, kind="measurement"):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        command = c.CorrectFact(
            sid,
            subject,
            value,
            "ana",
            draft.decision_revision,
            draft.revision,
            row.row_version,
            kind,
        )
    return session.perform(command).result
