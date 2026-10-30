"""Assembling over HTTP: an approved adaptation becomes a draft layer, or re-opens a piece (§4)."""

import shutil

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.services import catalogue, forging
from mendel_api.settings import settings
from mendel_api_tests.catalogue import FakeSource
from mendel_api_tests.database import reachable
from mendel_forge.forging.model import Move
from support.paths import REGISTRY

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")
STAR = "nf-core/star/align@2.7.11b"


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    with session_scope() as db:
        for table in ("forge_message", "forge_revision", "forge_item", "forge_adaptation",
                      "catalogue_module", "catalogue_sync"):
            db.execute(sa.text(f"DELETE FROM {table}"))
    cache = tmp_path / "forge"
    shutil.copytree(REGISTRY / "tools/nf-core/star/align/module",
                    cache / "nf-core-modules/modules/nf-core/star/align")
    monkeypatch.setattr(settings, "forge_cache", cache)
    catalogue.run_sync(FakeSource(["star/align"]))
    return TestClient(create_app())


def _approved_reforge() -> str:
    adaptation_id = forging.start("nf-core", "star/align", "rafael", reforge=STAR).id
    forging.act(adaptation_id, forging.person(Move.ANSWER, "questions:role", expected=None,
                                              value={"choice": "alignment"}, because=None))
    for key, item in forging.load(adaptation_id).items.items():
        if item.status == "proposed":
            forging.act(adaptation_id, forging.person(Move.APPROVE, key, expected=item.current.n,
                                                      value=None, because=None))
    for key in ("vocabulary:none", "rules:none"):
        forging.act(adaptation_id, forging.person(Move.WRITE, key, expected=None,
                                                  value={"because": "nothing new"}, because=None))
    return adaptation_id


def test_an_approved_adaptation_assembles_and_loads(client):
    adaptation_id = _approved_reforge()
    answer = client.post(f"/api/forge/adaptations/{adaptation_id}/assemble")
    assert answer.status_code == 200, answer.text
    proof = answer.json()
    assert proof["loaded"] and proof["conforms"], proof["problems"]
    assert "tools/nf-core/star/align/contract.yml" in proof["files"]
    assert forging.read(adaptation_id).phase == "assembled"


def _approve_reopened(adaptation_id: str) -> None:
    for key, item in forging.load(adaptation_id).items.items():
        if item.status == "reopened":
            forging.act(adaptation_id, forging.person(Move.APPROVE, key, expected=item.current.n,
                                                      value=None, because=None))


def test_assembly_reopens_the_blamed_piece(client):
    """A process name main.nf does not declare passes the item checks and fails conformance."""
    adaptation_id = _approved_reforge()
    process = forging.load(adaptation_id).items["contract:process"]
    forging.act(adaptation_id, forging.person(
        Move.CHANGE, "contract:process", expected=process.current.n,
        value={**process.value, "nf_process": "STAR_ALIGNED"}, because="testing"))
    _approve_reopened(adaptation_id)
    proof = client.post(f"/api/forge/adaptations/{adaptation_id}/assemble").json()
    assert not proof["conforms"] and proof["blames"] == "contract"
    assert forging.load(adaptation_id).items["contract:process"].status == "reopened"
    assert forging.read(adaptation_id).phase == "reviewing"
    assert "MF0512" in forging.read(adaptation_id).messages[-1].content


def test_assembling_before_all_is_approved_is_refused(client):
    adaptation_id = forging.start("nf-core", "star/align", "rafael").id
    answer = client.post(f"/api/forge/adaptations/{adaptation_id}/assemble")
    assert answer.status_code == 422 and answer.json()["detail"].startswith("MF0506")


def test_a_person_value_is_checked_like_the_ais(client):
    adaptation_id = forging.start("nf-core", "star/align", "rafael").id
    forging.act(adaptation_id, forging.person(Move.ANSWER, "questions:role", expected=None,
                                              value={"choice": "alignment"}, because=None))
    answer = client.post(f"/api/forge/adaptations/{adaptation_id}/commands", json={
        "move": "write", "item": "contract:input:reads",
        "value": {"position": 0, "name": "reads", "type_id": "nothing.here"}})
    assert answer.status_code == 422 and answer.json()["detail"].startswith("MF0507")


def test_a_missing_licence_reopens_nothing_and_says_it_once(client, tmp_path, monkeypatch):
    """Review I9: the fault is the registry's, not the adaptation's."""
    adaptation_id = _approved_reforge()
    base = tmp_path / "base"
    shutil.copytree(REGISTRY, base, ignore=shutil.ignore_patterns(".git", "LICENSES"))
    monkeypatch.setattr(settings, "registry_root", base)
    proof = forging.assemble(adaptation_id)
    assert not proof.loaded and proof.blames is None
    assert proof.problems[0].says.count("MF0511") == 0, "the code is the problem's, once"
    assert all(i.status in ("approved", "removed")
               for i in forging.load(adaptation_id).items.values())
    assert forging.read(adaptation_id).phase == "reviewing"


def test_an_assembly_that_breaks_never_leaves_the_phase_assembling(client):
    """Review I2: whatever fails, the adaptation goes back to review, and the route says why."""
    adaptation_id = _approved_reforge()
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM catalogue_module"))
    answer = client.post(f"/api/forge/adaptations/{adaptation_id}/assemble")
    assert answer.status_code == 200, answer.text
    assert not answer.json()["loaded"]
    assert forging.read(adaptation_id).phase == "reviewing"


def test_a_command_during_assembly_demotes_it(client):
    """Review I10: a change landing while assembling must not end as assembled."""
    adaptation_id = _approved_reforge()
    forging.set_phase(adaptation_id, "assembling")
    process = forging.load(adaptation_id).items["contract:process"]
    forging.act(adaptation_id, forging.person(Move.CHANGE, "contract:process",
                                              expected=process.current.n,
                                              value=process.value, because="again"))
    assert forging.read(adaptation_id).phase == "reviewing"
