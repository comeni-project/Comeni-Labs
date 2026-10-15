"""Reusable disagreements scenarios and fixtures for API tests."""

from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import session
from mendel_authoring import commands as c

from mendel_api_tests.samples import _gathering, _measured, _pending_for
from mendel_api_tests.samples import clean as clean


def _conflict():
    sid = _gathering(["counts.matrix"])
    session.perform(c.AnswerGap(_pending_for(sid, "paired"), "no", None, "ana"))
    pid = _pending_for(sid, "read_length")
    session.perform(
        c.SampleInspected(
            pid, _measured(read_length=150, paired=True).model_dump(mode="json"), "ana"
        )
    )
    return sid


def _answer(sid, option, value=None):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        command = c.AnswerDisagreement(
            session.pending_id(sid),
            option,
            value,
            "ana",
            draft.decision_revision,
            draft.revision,
            row.row_version,
        )
    return session.perform(command).result
