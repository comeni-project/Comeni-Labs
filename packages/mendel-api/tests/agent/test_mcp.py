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
        "draft_id": draft, "type_id": "alignment.bam", "contract": HISAT2,
        "because": "less memory"}))
    [pin] = decisions.read(draft).producers
    assert (pin.contract, pin.by) == (HISAT2, "model")
    with session_scope() as db:
        who = db.scalars(select(PipelineProducerRevision.who)
                         .where(PipelineProducerRevision.draft_id == draft)).all()
    assert who and all(w.startswith("mcp:") for w in who)
