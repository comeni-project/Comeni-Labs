"""Forge home's *Your registry can't yet* (#534): what analyses want that nothing in the
registry makes, derived from their current wants at every read, never recorded apart."""

import pytest
from comeni_core.plan.draft import DraftGraph
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services import decisions, drafts
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


def _wanting(*type_ids: str) -> str:
    draft = drafts.create(DraftGraph(), "an analysis", "ana")
    for type_id in type_ids:
        decisions.set_want(draft, type_id, who="ana")
    return draft


def _read(client) -> list[dict]:
    response = client.get("/api/forge/unreachable")
    assert response.status_code == 200, response.text
    return response.json()["wants"]


def test_a_want_nothing_makes_is_counted_per_analysis(clean):
    _wanting("assembly.fasta", "counts.matrix")
    _wanting("assembly.fasta")
    rows = _read(TestClient(create_app()))
    assert [(r["type_id"], r["builds"]) for r in rows] == [("assembly.fasta", 2)]
    assert rows[0]["name"], "the vocabulary's name for it"


def test_a_want_the_registry_makes_is_not_listed(clean):
    _wanting("counts.matrix")
    assert _read(TestClient(create_app())) == []


def test_a_want_taken_back_is_not_counted(clean):
    draft = _wanting("assembly.fasta")
    decisions.retract_want(draft, "assembly.fasta", who="ana")
    assert _read(TestClient(create_app())) == []
