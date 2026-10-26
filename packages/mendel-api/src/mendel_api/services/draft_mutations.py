"""One lock order and revision owner for authoring projections and checked saves."""

from datetime import UTC, datetime

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from sqlalchemy import select

from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft


class Conflict(ValueError):
    """A valid save its version or an open conversation refuses."""


def lock(db, draft_id, *, expected_revision=None):
    draft = db.get(PipelineDraft, draft_id, with_for_update=True, populate_existing=True)
    if draft is None:
        raise KeyError(draft_id)
    if expected_revision is not None and expected_revision != draft.revision:
        raise Conflict(coded("MI0201", "this draft changed; reload before saving again"))
    return draft


def lock_session(db, session_id):
    # Read the identity first, acquire locks only in draft → session order.
    row = db.get(PipelineAuthoringSession, session_id)
    if row is None:
        raise KeyError(session_id)
    lock(db, row.draft_id)
    return db.get(PipelineAuthoringSession, session_id, with_for_update=True,
                  populate_existing=True)


def touch(db, draft):
    stamps = db.info.setdefault("draft_mutation_stamps", {})
    key = (draft.id, db.get_transaction())
    if stamps.get(key) != draft.revision:
        draft.revision += 1
        stamps[key] = draft.revision
    draft.updated_at = datetime.now(UTC)


def project(db, draft, graph, *, provenance):
    dumped = graph.model_dump(mode="json")
    if dumped != draft.graph or provenance != draft.provenance:
        draft.graph = dumped
        draft.provenance = provenance
        touch(db, draft)
    draft.projection_revision = draft.decision_revision
    draft.projection_current = True


def _semantic(graph):
    return graph.model_dump(mode="json", exclude={"labels"})


def save(draft_id, *, expected_revision, graph=None, name=None):
    with session_scope() as db:
        draft = lock(db, draft_id, expected_revision=expected_revision)
        return save_in(db, draft, graph=graph, name=name)


def save_in(db, draft, *, graph=None, name=None):
    """Apply a locked save in the caller's unit of work, without opening another session."""
    from mendel_api.services import drafts

    authoring = db.scalar(select(PipelineAuthoringSession).where(
        PipelineAuthoringSession.draft_id == draft.id).with_for_update())
    if (graph is not None and authoring is not None and not authoring.retired
            and authoring.phase not in ("complete", "stopped")):
        raise Conflict(coded("MI0217", "editing opens when the authored work is done"))
    before = DraftGraph.model_validate(draft.graph)
    if graph is not None and graph != before:
        draft.graph = graph.model_dump(mode="json")
        prior = DraftProvenance.model_validate(draft.provenance or {})
        draft.provenance = drafts._restamped(graph, before, prior).model_dump(mode="json")
        touch(db, draft)
    if name is not None and name != draft.name:
        draft.name = name
        touch(db, draft)
    return draft
