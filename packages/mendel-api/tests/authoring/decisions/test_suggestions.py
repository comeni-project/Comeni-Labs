"""The model's suggestions wait for one click: applied as the person's own change, or set aside
(Part I.0 spec §5.3)."""

import asyncio

import pytest
from mendel_api.services import decisions, suggestions
from mendel_api.services import session as facade
from mendel_api_tests.building import (  # noqa: F401
    _answer_all,
    _resolving,
    authoring_setup,
)
from mendel_api_tests.building import clean as clean
from mendel_api_tests.changes import _change, _versions
from mendel_authoring.payloads import DecisionChange


def _built():
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    return sid


FIFTY = DecisionChange(
    kind="measurement",
    subject="read_length",
    value=50,
    heard="50 bp",
    heard_seq=1,
    actor="model",
    invocation_id="inv-1",
)


def test_an_offer_waits_and_says_what_it_would_change(clean):
    sid = _built()
    sid_offer = suggestions.offer(sid, FIFTY, heard=True, invocation_id="inv-1")
    [view] = suggestions.pending(sid)
    assert view.id == sid_offer and view.heard and view.says == "read length is 50"
    draft = _versions(sid)[0]
    assert next(f.value for f in decisions.read(draft).facts if f.subject == "read_length") != 50


def test_applying_it_is_the_persons_change(clean):
    sid = _built()
    offered = suggestions.offer(sid, FIFTY, heard=True, invocation_id="inv-1")
    result = asyncio.run(suggestions.apply(sid, offered, by="ana"))
    draft = _versions(sid)[0]
    assert next(f.value for f in decisions.read(draft).facts if f.subject == "read_length") == 50
    assert result["phase"] == "building"
    assert suggestions.pending(sid) == []
    assert suggestions.state(offered) == "applied"


def test_dismissing_it_records_nothing(clean):
    sid = _built()
    before = _versions(sid)
    offered = suggestions.offer(sid, FIFTY, heard=False, invocation_id="inv-1")
    suggestions.dismiss(sid, offered, by="ana")
    assert _versions(sid) == before and suggestions.state(offered) == "dismissed"


def test_a_change_to_its_subject_makes_it_stale(clean):
    sid = _built()
    offered = suggestions.offer(sid, FIFTY, heard=False, invocation_id="inv-1")
    _change(sid, DecisionChange(kind="measurement", subject="read_length", value=100))
    assert suggestions.pending(sid) == []
    with pytest.raises(ValueError, match="MI0201"):
        asyncio.run(suggestions.apply(sid, offered, by="ana"))


def test_the_session_view_lists_what_is_waiting(clean):
    sid = _built()
    suggestions.offer(sid, FIFTY, heard=True, invocation_id="inv-1")
    assert [s["says"] for s in facade.read(sid)["suggestions"]] == ["read length is 50"]


def test_the_route_applies_and_dismisses(clean):
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    client = TestClient(create_app())
    sid = _built()
    keep = suggestions.offer(sid, FIFTY, heard=True, invocation_id="inv-1")
    drop = suggestions.offer(
        sid,
        FIFTY.model_copy(update={"subject": "paired", "value": True}),
        heard=False,
        invocation_id="inv-1",
    )
    base = f"/api/pipeline/authoring/{sid}/suggestions"
    assert client.post(f"{base}/{drop}", json={"decision": "dismiss"}).status_code == 200
    applied = client.post(f"{base}/{keep}", json={"decision": "apply"})
    assert applied.status_code == 200, applied.text
    assert applied.json()["phase"] == "building"
    view = client.get(f"/api/pipeline/authoring/{sid}").json()
    assert view["suggestions"] == []


def test_applying_queues_the_jobs_its_change_asks_for(clean, monkeypatch):
    """Review I1: applied through `perform`, the jobs a change asks for (the next question's
    phrasing, a card's read-back) came back unqueued and were dropped."""
    import asyncio

    from mendel_api.services import session as session_service
    from mendel_api_tests.gathering import _gathering, _pending_for

    queued = []

    async def enqueue(job):
        queued.append(job.name)
        return True

    monkeypatch.setattr(session_service, "_enqueue", enqueue)
    monkeypatch.setenv("COMENI_AI_MODEL", "fake/test")  # a model configured: questions are phrased
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "paired")
    offered = suggestions.offer(
        sid,
        DecisionChange(kind="measurement", subject="paired", value=True, actor="model"),
        heard=False,
        invocation_id=None,
    )
    queued.clear()
    asyncio.run(suggestions.apply(sid, offered, by="ana"))
    assert queued, "the change asked for jobs, and none was queued"
