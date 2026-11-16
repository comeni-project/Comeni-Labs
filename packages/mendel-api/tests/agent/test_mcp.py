"""The engine's tools over MCP, behind a token (#463)."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from mendel_api.agent import mcp as served
from mendel_api.agent.tools import TOOLS
from mendel_api.db import session_scope
from mendel_api.decision_models import PipelineProducerRevision
from mendel_api.main import create_app
from mendel_api.services import decisions
from mendel_api.settings import settings
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from sqlalchemy import select

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

HISAT2 = "nf-core/hisat2/align@2.2.2"
HELLO = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {},
    "clientInfo": {"name": "test-client", "version": "1"}}}
HEADERS = {"Accept": "application/json, text/event-stream"}


def _post(token: str | None):
    with TestClient(create_app()) as client:
        headers = dict(HEADERS, **({"Authorization": f"Bearer {token}"} if token else {}))
        return client.post("/api/mcp/", json=HELLO, headers=headers)


def test_without_the_token_nothing_runs(monkeypatch):
    monkeypatch.setattr(settings, "mcp_token", "the-token")
    assert _post(None).status_code == 401


def test_a_wrong_token_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "mcp_token", "the-token")
    assert _post("another").status_code == 401


def test_with_no_token_configured_mcp_is_off(monkeypatch):
    monkeypatch.setattr(settings, "mcp_token", "")
    refused = _post("anything")
    assert refused.status_code == 401 and "MENDEL_MCP_TOKEN" in refused.text


def test_the_right_token_reaches_the_server(monkeypatch):
    monkeypatch.setattr(settings, "mcp_token", "the-token")
    assert _post("the-token").status_code == 200


def test_mcp_lists_the_same_tools_as_the_agent():
    listed = {tool.name for tool in asyncio.run(served.server.list_tools())}
    assert listed == set(TOOLS) | {"open_draft"}


def test_an_mcp_write_is_recorded_as_the_clients(clean):
    opened = asyncio.run(served.server.call_tool("open_draft", {"name": "from another agent"}))
    draft = served.draft_of(opened)
    asyncio.run(served.server.call_tool("choose_tool", {
        "draft_id": draft, "revision": decisions.revision(draft), "type_id": "alignment.bam",
        "contract": HISAT2, "because": "less memory"}))
    [pin] = decisions.read(draft).producers
    assert (pin.contract, pin.by) == (HISAT2, "model")
    with session_scope() as db:
        who = db.scalars(select(PipelineProducerRevision.who)
                         .where(PipelineProducerRevision.draft_id == draft)).all()
    assert who and all(w.startswith("mcp:") for w in who)


def _result(raw) -> dict:
    """A tool's result as the client reads it, however the SDK wraps it."""
    import json

    if hasattr(raw, "structured_content") and raw.structured_content:
        return raw.structured_content
    parts = raw[0] if isinstance(raw, tuple) else getattr(raw, "content", raw)
    for part in parts if isinstance(parts, list) else [parts]:
        if isinstance(part, dict):
            return part
        if getattr(part, "text", None):
            return json.loads(part.text)
    raise LookupError(raw)


def test_an_mcp_write_after_the_persons_change_is_refused(clean):
    """#463 review: the client states the revision it read; a change made since stands."""
    from mendel_api.services import changes
    from mendel_authoring.payloads import DecisionChange

    draft = served.draft_of(asyncio.run(served.server.call_tool("open_draft", {})))
    read = decisions.revision(draft)
    changes.apply(draft, DecisionChange(kind="parameter", subject="min_mqs", value=10), who="ana")
    stale = _result(asyncio.run(served.server.call_tool("set_value", {
        "draft_id": draft, "revision": read, "name": "min_mqs", "value": 20, "because": "x"})))
    assert stale["ok"] is False and stale["refusal"].startswith("MI0201")
    fresh = _result(asyncio.run(served.server.call_tool("set_value", {
        "draft_id": draft, "revision": stale["revision"], "name": "min_mqs", "value": 20,
        "because": "x"})))
    assert fresh["ok"] is True and fresh["revision"] > stale["revision"]


def test_a_malformed_authorization_header_is_a_clean_refusal(monkeypatch):
    monkeypatch.setattr(settings, "mcp_token", "the-token")
    with TestClient(create_app()) as client:
        refused = client.post("/api/mcp/", json=HELLO,
                              headers=dict(HEADERS, Authorization=b"Bearer \xff\xfe-token"))
    assert refused.status_code == 401
