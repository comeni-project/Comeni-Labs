"""Reusable manual forks scenarios and fixtures for API tests."""

from comeni_core.plan.draft import DraftGraph
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import session
from mendel_authoring import commands as c

from mendel_api_tests.building import _answer_all, _resolving, authoring_setup
from mendel_api_tests.building import clean as clean


def _manual():
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    graph = DraftGraph.model_validate(session.read(sid)["graph"])
    removed = graph.nodes[-1].id
    graph = graph.model_copy(
        update={
            "nodes": graph.nodes[:-1],
            "edges": [e for e in graph.edges if e.from_node != removed and e.to_node != removed],
        }
    )
    session.perform(c.RecordEdit(sid, graph.model_dump(mode="json"), "ana"))
    return sid


def _command(sid):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        return c.ForkCorrection(
            sid, "read_length", 50, "ana", draft.decision_revision, draft.revision, row.row_version
        )
