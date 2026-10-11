"""Every draft writer shares revision checks and one transaction stamp."""

from datetime import UTC, datetime
from importlib import import_module

import pytest
from comeni_core.plan.draft import DraftGraph, DraftNode
from mendel_api.db import session_scope, transaction
from mendel_api.models import PipelineDraft
from mendel_api.services import drafts
from mendel_postgres import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="needs throwaway Postgres")


def _service():
    return import_module("mendel_api.services.draft_mutations")


def _graph():
    return DraftGraph(nodes=[DraftNode(id="align", contract_id="nf-core/star/align@1.11.0")])


def test_an_ordinary_save_bumps_once_and_cannot_replace_a_newer_graph():
    service = _service()
    draft = drafts.create(DraftGraph(), "draft", "ana")
    service.save(draft, graph=_graph(), expected_revision=0)
    with pytest.raises(ValueError, match="MI0201"):
        service.save(draft, graph=DraftGraph(), expected_revision=0)
    assert drafts.read(draft).revision == 1
    assert drafts.read(draft).graph == _graph().model_dump(mode="json")


def test_two_internal_writes_in_an_action_stamp_the_revision_once():
    service = _service()
    draft = drafts.create(DraftGraph(), "draft", "ana")
    with transaction(), session_scope() as db:
        row = service.lock(db, draft)
        service.touch(db, row)
        service.project(db, row, _graph(), provenance={})
    assert drafts.read(draft).revision == 1


def test_unchanged_graph_is_a_noop_and_rename_does_not_replace_it():
    service = _service()
    draft = drafts.create(_graph(), "draft", "ana")
    service.save(draft, graph=_graph(), expected_revision=0)
    assert drafts.read(draft).revision == 0
    service.save(draft, name="new", expected_revision=0)
    row = drafts.read(draft)
    assert row.name == "new" and row.revision == 1
    assert row.graph == _graph().model_dump(mode="json")


def test_unfinished_authored_work_refuses_external_graph_replacement():
    from mendel_api.models import PipelineAuthoringSession

    service = _service()
    draft = drafts.create(DraftGraph(), "draft", "ana")
    with session_scope() as db:
        db.get(PipelineDraft, draft).ownership = "authored"
        db.add(PipelineAuthoringSession(id="mutation-" + draft[:23], draft_id=draft,
                                       phase="gathering", at="list_needs", who="ana",
                                       created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
    with pytest.raises(ValueError, match="MI0217"):
        service.save(draft, graph=_graph(), expected_revision=0)
    service.save(draft, name="new", expected_revision=0)
    assert drafts.read(draft).ownership == "authored"
    assert drafts.read(draft).graph == DraftGraph().model_dump(mode="json")


def test_only_semantic_edits_after_completion_make_the_draft_manual():
    service = _service()
    draft = drafts.create(_graph(), "draft", "ana")
    with session_scope() as db:
        db.get(PipelineDraft, draft).ownership = "authored"
    moved = DraftGraph.model_validate({**_graph().model_dump(mode="json"),
                                      "labels": [{"key": "align.out", "label": "alignment"}]})
    # Use the real graph model's layout field, not a client-owned ownership claim.
    service.save(draft, graph=moved, expected_revision=0)
    assert drafts.read(draft).ownership == "authored"
    revision = drafts.read(draft).revision
    service.save(draft, graph=DraftGraph(), expected_revision=revision)
    assert drafts.read(draft).ownership == "manual"


def test_http_save_requires_a_revision_and_returns_conflict_for_a_stale_tab():
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    client = TestClient(create_app())
    made = client.post('/api/pipeline/drafts', json={"graph": {}}).json()
    url = f'/api/pipeline/drafts/{made["id"]}'
    assert made["revision"] == 0
    assert client.put(url, json={"graph": {}}).status_code == 422
    saved = client.put(url, json={"graph": _graph().model_dump(mode="json"),
                                 "expected_revision": 0})
    assert saved.status_code == 200 and saved.json()["revision"] == 1
    stale = client.put(url, json={"graph": {}, "expected_revision": 0})
    assert stale.status_code == 409 and "MI0201" in stale.json()["detail"]
    renamed = client.put(url, json={"name": "new", "expected_revision": 1})
    assert renamed.status_code == 200
    assert renamed.json()["graph"] == _graph().model_dump(mode="json")
