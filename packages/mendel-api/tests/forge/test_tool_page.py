"""An imported tool's page, filled from the registry and only from it (forge part 1 spec, §7)."""

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.services import catalogue
from mendel_api_tests.catalogue import FakeSource
from mendel_api_tests.database import reachable

STAR = "/api/registry/tools/nf-core/star/align@2.7.11b"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_star_align_page_carries_the_registry(client):
    answer = client.get(STAR)
    assert answer.status_code == 200, answer.text
    page = answer.json()
    assert page["id"] == "nf-core/star/align@2.7.11b"
    assert page["name"] == "STAR"
    assert page["description"].startswith("An aligner that maps sequencing reads")
    params = {p["name"]: p for p in page["params"]}
    assert params["star_ignore_sjdbgtf"]["because"].startswith("Align *with* the annotation")
    assert params["star_ignore_sjdbgtf"]["default"] is False
    assert params["seq_platform"]["asks_person"] is True
    reads = next(port for port in page["consumes"] if port["name"] == "reads")
    assert reads["states_conventional"] == ["trimmed"]
    assert reads["conventional_because"]
    assert page["ext_args"] == "--readFilesCommand zcat"
    assert page["ext_args_because"]
    assert page["priority"] == 10 and page["priority_because"]
    assert page["approved_by"] == "rafael" and page["approved_at"] == "2026-08-03"
    assert page["licence"] == "MIT"
    assert page["upstream"]["path"] == "modules/nf-core/star/align"
    rules = [rule for rule in page["rules"] if rule["role"] == "alignment"]
    assert rules, "the alignment rule is shown"
    assert rules[0]["rows"][0]["then"] == "nf-core/star/align@2.7.11b"
    assert rules[0]["rows"][0]["when"] == {"read_length": ">= 70"}
    assert page["registry_at"]


def test_unknown_tool_is_MF0504(client):
    answer = client.get("/api/registry/tools/nf-core/nothing@1.0")
    assert answer.status_code == 404
    assert answer.json()["detail"].startswith("MF0504")


@pytest.mark.skipif(not reachable(), reason="no database")
def test_page_has_catalogue_when_synced(client):
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM catalogue_module"))
        db.execute(sa.text("DELETE FROM catalogue_sync"))
    assert client.get(STAR).json()["catalogue"] is None
    catalogue.run_sync(FakeSource(["star/align"]))
    page = client.get(STAR).json()
    assert page["catalogue"]["row"]["state"] == "imported"
    assert page["catalogue"]["module"]["tool_version"] == "2.7.11b"
