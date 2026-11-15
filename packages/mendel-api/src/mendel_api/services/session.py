"""What a builder session keeps beside the agent's thread (#463): the model calls it made, for
the call panel, and which AI points a draft used, for `pipeline.yml`."""

from comeni_core.plan.draft import DraftProvenance
from sqlalchemy import select

from mendel_api.db import session_scope
from mendel_api.models import AiInvocation, PipelineAuthoringSession, PipelineDraft


def calls(session_id: str) -> list[dict]:
    """The session's model calls, oldest first, with each reply (#182, #191). Fetched only when
    the page opens its call panel, never on the poll."""
    with session_scope() as db:
        if db.get(PipelineAuthoringSession, session_id) is None:
            raise KeyError(session_id)
        rows = db.scalars(select(AiInvocation).where(AiInvocation.session_id == session_id)
                          .order_by(AiInvocation.started_at)).all()
        return [{"id": r.id, "purpose": r.purpose, "model": r.model, "input": r.input_tokens,
                 "output": r.output_tokens, "cached": r.cached_tokens,
                 "duration_ms": r.duration_ms, "state": r.state, "response": r.response,
                 "cleared": r.response_cleared, "reply_format": r.reply_format,
                 "at": r.started_at.isoformat()} for r in rows]


def ai_for(provenance: DraftProvenance):
    """What AI points this installation offers, and which this draft used. For `pipeline.yml`.

    **One function for the preview and for Keep**, so the two cannot disagree. The builder
    agent is the prompt point; a tool or value it chose is the tier-4 point, read from the
    draft's sidecar."""
    from comeni_core.artifact.pipeline import AiPoint, AiProvenance
    from comeni_core.plan.tiers import ValueSource

    from mendel_api.settings import model_access

    if model_access("builder", "agent") is None:
        return AiProvenance(available=[], used=[])
    modelled = any(
        entry.selection is not None and entry.selection.source is ValueSource.MODEL
        for entry in provenance.nodes
    ) or any(entry.settled.source is ValueSource.MODEL for entry in provenance.params)
    return AiProvenance(available=[AiPoint.PROMPT, AiPoint.TIER_4],
                        used=[AiPoint.PROMPT] + ([AiPoint.TIER_4] if modelled else []))


def ai_choices_for_draft(draft_id: str) -> list[dict]:
    """What the builder agent chose in a draft a session owns, and whether each was reviewed
    (#463); nothing for a hand-drawn draft."""
    from mendel_api.agent import chat

    with session_scope() as db:
        owned = db.scalar(select(PipelineAuthoringSession.id)
                          .where(PipelineAuthoringSession.draft_id == draft_id))
    return chat.choices(owned) if owned else []


def ai_for_draft(draft_id: str):
    """`ai_for` for a draft a builder session owns, or `None` for a hand-drawn one."""
    with session_scope() as db:
        owned = db.scalar(select(PipelineAuthoringSession)
                          .where(PipelineAuthoringSession.draft_id == draft_id))
        if owned is None:
            return None
        draft = db.get(PipelineDraft, draft_id)
        return ai_for(DraftProvenance.model_validate(draft.provenance or {}))
