"""Everything the page needs to draw a builder session, in one read (#463): the agent's thread,
the canvas, what was understood, and what the AI chose that nobody has reviewed."""

from comeni_core.plan.draft import DraftGraph, DraftProvenance
from mendel_authoring.blueprint import Blueprint
from sqlalchemy import func, select

from mendel_api.agent import chat
from mendel_api.authoring.canvas import OfferContext
from mendel_api.authoring.types import TurnState
from mendel_api.db import session_scope
from mendel_api.models import (
    AiInvocation,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)
from mendel_api.services import authoring_canvas, authoring_decisions, decisions, registry


def _placement(blueprint: dict | None, graph: dict | None) -> dict:
    """Where each step on the canvas sits in the built pipeline, so nothing moves as it grows."""
    placed = (blueprint or {}).get("placed") or {}
    visible = {n["id"] for n in (graph or {}).get("nodes", [])}
    return {node: {"x": at[0], "y": at[1]} for node, at in placed.items() if node in visible}


def tidy(session_id: str) -> None:
    """**Tidy** (#511): the drawing laid out again with the canvas's current geometry, and kept,
    so a pipeline built before a geometry change takes the new spacing. Layout only: nothing the
    pipeline is changes."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        if not row.blueprint:
            return  # drawn by hand: its layout is computed fresh on every read
        draft = db.get(PipelineDraft, row.draft_id)
        frame = authoring_canvas.frame_of(
            blueprint=Blueprint.model_validate(row.blueprint),
            graph=DraftGraph.model_validate(draft.graph or {}),
            provenance=DraftProvenance.model_validate(draft.provenance or {}),
            context=OfferContext(
                draft_revision=draft.revision, decision_revision=draft.decision_revision,
                session_version=row.row_version, registry=row.registry_digest or ""),
            current=draft.projection_current, placement={}, layers=registry.stack())
        if frame is None:
            return
        placed = {node: [at["x"], at["y"]] for node, at in sorted(frame.placement.items())}
        row.blueprint = {**row.blueprint, "placed": placed}


def read(session_id: str) -> dict:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        turns = db.scalars(select(PipelineAuthoringTurn)
                           .where(PipelineAuthoringTurn.session_id == session_id)
                           .order_by(PipelineAuthoringTurn.seq)).all()
        spent = db.execute(select(
            func.coalesce(func.sum(AiInvocation.input_tokens), 0),
            func.coalesce(func.sum(AiInvocation.output_tokens), 0),
            func.coalesce(func.sum(AiInvocation.cached_tokens), 0),
            func.count(AiInvocation.id),
        ).where(AiInvocation.session_id == session_id)).one()
        evidence_subjects = db.scalars(select(decisions.PipelineObservation.subject).join(
            decisions.PipelineEvidenceAccess,
            decisions.PipelineEvidenceAccess.observation_id == decisions.PipelineObservation.id
        ).where(decisions.PipelineEvidenceAccess.draft_id == row.draft_id).distinct()).all()
        blueprint_json, graph_json = row.blueprint or None, draft.graph or {}
        placement = _placement(blueprint_json, graph_json)
        try:
            canvas = authoring_canvas.frame_of(
                blueprint=Blueprint.model_validate(blueprint_json) if blueprint_json else None,
                graph=DraftGraph.model_validate(graph_json),
                provenance=DraftProvenance.model_validate(draft.provenance or {}),
                context=OfferContext(
                    draft_revision=draft.revision, decision_revision=draft.decision_revision,
                    session_version=row.row_version, registry=row.registry_digest or ""),
                current=draft.projection_current, placement=placement, layers=registry.stack())
        except (KeyError, ValueError):
            canvas = None
        selected = decisions.read(row.draft_id)
        thread = [{"seq": t.seq, "role": t.role, "state": t.state, "text": t.text,
                   "blocks": list(t.blocks or []), "base_revision": t.base_revision,
                   "at": t.at.isoformat()} for t in turns]
        return {
            "id": row.id,
            "draft_id": row.draft_id,
            "name": draft.name,
            "goal": (authoring_decisions.goal(row).model_dump(mode="json")
                     if any(w.present for w in selected.wants) else None),
            "facts": [f.model_dump(mode="json") for f in authoring_decisions.facts(row.draft_id)],
            "inputs": [i.model_dump(mode="json") for i in selected.inputs],
            "fact_subjects": sorted(set(evidence_subjects)
                                    | {f.subject for f in selected.facts}),
            "decision_revision": draft.decision_revision,
            "projection_current": draft.projection_current or draft.projection_revision is None,
            "retired": row.retired,
            "revision": draft.revision,
            "graph": graph_json,
            "canvas": canvas.model_dump(mode="json") if canvas is not None else None,
            "placement": placement,
            "steps_total": len((blueprint_json or {}).get("order") or []),
            "row_version": row.row_version,
            "usage": {"input": int(spent[0]), "output": int(spent[1]), "cached": int(spent[2]),
                      "calls": int(spent[3]),
                      "in_flight": any(t.state == TurnState.PENDING.value for t in turns)},
            "turns": thread,
            "working": chat.working(thread),
        }
