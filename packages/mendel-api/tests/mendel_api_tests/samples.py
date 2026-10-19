"""Reusable samples scenarios and fixtures for API tests."""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession
from mendel_api.services import drafts, inspect
from mendel_api.services import session as facade
from mendel_authoring import commands
from mendel_authoring import state as st

from mendel_api_tests import session_setup as authoring_setup
from mendel_api_tests.database import truncate


@pytest.fixture
def clean():
    tables = (
        "ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft, gate_run"
    )
    with session_scope() as session:
        session.execute(truncate(f"TRUNCATE TABLE {tables}"))
    yield


def _gathering(want: list[str]) -> str:
    draft_id = drafts.create(DraftGraph(), "t", "ana")
    sid = facade.perform(commands.OpenSession(draft_id, "ana")).result
    authoring_setup.seed(sid, want)
    authoring_setup.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring_setup.offer_next_gap(sid)
    return sid


def _payload(pid: str) -> dict:
    with session_scope() as db:
        return dict(db.get(PipelineAuthoringProposal, pid).payload)


def _pending_for(sid: str, subject: str) -> str:
    while (pid := facade.pending_id(sid)) and _payload(pid)["subject"] != subject:
        skip = ("dont_have", "value", "not_sure", "upload")
        drawn = [o["id"] for o in _payload(pid)["block"]["options"]]  # the card's order
        options = [o for o in drawn if o not in skip]
        facade.perform(commands.AnswerGap(pid, options[0], None, "ana"))
    return facade.pending_id(sid)


def _facts(sid: str) -> list[dict]:
    return facade.read(sid)["facts"]


def _measured(**values) -> inspect.Inspection:
    return inspect.Inspection(
        outcome="measured",
        type_id="fastq.reads",
        steps=[],
        facts=[
            inspect.InspectedFact(
                measurement=k,
                value=v,
                pieces=["fastq@1.0.0", f"{k}@1.0.0"],
                evidence={"records": 2000, "rows": 1000, "shorter_file": "x_R2.fq"},
            )
            for k, v in values.items()
        ],
    )


def _version(sid: str) -> int:
    with session_scope() as db:
        return db.get(PipelineAuthoringSession, sid).row_version
