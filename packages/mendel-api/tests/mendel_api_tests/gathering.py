"""Reusable gathering scenarios and fixtures for API tests."""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal
from mendel_api.services import drafts
from mendel_api.services import session as facade
from mendel_api.stages import gathering
from mendel_authoring import commands
from mendel_authoring import state as st

from mendel_api_tests import session_setup as authoring_setup
from mendel_api_tests.database import truncate


@pytest.fixture
def clean():
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft, gate_run"
    )
    with session_scope() as session:
        session.execute(truncate(f"TRUNCATE TABLE {tables}"))
    yield


def _gathering(want: list[str], stated: list[dict] | None = None) -> str:
    """A session moved to GATHERING with a want and no facts, its first gap offered."""
    draft_id = drafts.create(DraftGraph(), "t", "ana")
    sid = facade.perform(commands.OpenSession(draft_id, "ana")).result
    authoring_setup.seed(sid, want, stated or [])
    authoring_setup.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring_setup.offer_next_gap(sid)
    return sid


def _payload(pid: str) -> dict:
    with session_scope() as db:
        return dict(db.get(PipelineAuthoringProposal, pid).payload)


def _pending_for(sid: str, subject: str) -> str:
    """Answer every earlier gap with its first ordinary option until `subject` is offered."""
    while (pid := facade.pending_id(sid)) and _payload(pid)["subject"] != subject:
        skip = ("dont_have", "value", "not_sure", "upload")
        options = [o for o in _payload(pid)["options"] if o not in skip]
        facade.perform(commands.AnswerGap(pid, options[0], None, "ana"))
    return facade.pending_id(sid)


def _answer_until(sid: str, subject: str, option: str) -> None:
    facade.perform(commands.AnswerGap(_pending_for(sid, subject), option, None, "ana"))


def _facts(sid: str) -> list[dict]:
    return facade.read(sid)["facts"]


def _typed(monkeypatch, sid: str, text: str, reply: dict) -> None:
    """The person types an answer; the job reads it with a recorded model reply."""
    import asyncio
    import json

    from comeni_ai import Client, ModelAccess
    from mendel_api.services import authoring_jobs

    class Once:
        def send(self, access, prompt: str) -> str:
            return json.dumps(reply)

    monkeypatch.setattr(
        authoring_jobs,
        "_client",
        lambda *_: Client(ModelAccess(model="fake/test"), transport=Once()),
    )
    seq = facade.perform(commands.Say(sid, text)).result
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))


# ── the session's calls, totalled and listed (14.7.4, #191) ───────────────────────────────
def _write_call(sid, *, input_tokens, output_tokens, cached, response=None, purpose="goal"):
    import secrets
    from datetime import UTC, datetime

    from mendel_api.models import AiInvocation

    now = datetime.now(UTC)
    with session_scope() as db:
        db.add(
            AiInvocation(
                id=secrets.token_hex(16),
                agent="builder",
                purpose=purpose,
                model="fake/test",
                provider="local",
                prompt_id="builder.goal.v4",
                prompt_version="v4",
                prompt_digest="0" * 64,
                input_digests={},
                temperature=0.0,
                state="succeeded",
                failure_code="",
                started_at=now,
                finished_at=now,
                duration_ms=10,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached,
                response=response,
                session_id=sid,
            )
        )


# ── each question phrased by a model (14.7.4, #167, #186) ─────────────────────────────────
def _asked(asks, option=None, value=None):
    from mendel_api.authoring.types import AskedGap

    return AskedGap(asks=asks, already_option=option, already_value=value)


async def _queue_phrasing(sid: str) -> None:
    """What `ask` queues on entering a question (plan 1c), through the facade's queue seam."""
    from mendel_api.services import session
    from mendel_api.stages import _jobs

    for subject in gathering.to_phrase(sid):
        await session._enqueue(_jobs.phrase(sid, subject))


# ── the read-back (14.7.4, #176) ──────────────────────────────────────────────────────────
def _to_card(sid):
    while (pid := facade.pending_id(sid)) and "subject" in _payload(pid):
        options = [o for o in _payload(pid)["options"] if o not in ("dont_have", "value", "upload")]
        facade.perform(commands.AnswerGap(pid, options[0], None, "ana"))
    return facade.pending_id(sid)
