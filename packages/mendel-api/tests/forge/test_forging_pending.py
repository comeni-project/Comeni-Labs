"""Pending vocabulary: an assembled adaptation's new types are usable by later ones (spec §5)."""

import shutil

import pytest
import sqlalchemy as sa
from mendel_api.db import session_scope
from mendel_api.services import catalogue, forging
from mendel_api.settings import settings
from mendel_api_tests.catalogue import FIXTURES, FakeSource
from mendel_api_tests.database import reachable
from mendel_forge.forging.model import Move
from support.paths import REGISTRY

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")
NEW = "genome.index.forged"


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    with session_scope() as db:
        for table in ("forge_review", "forge_pull_request", "forge_test_run", "forge_step",
                      "forge_message", "forge_revision",
                      "forge_item",
                      "forge_adaptation",
                      "catalogue_module", "catalogue_sync"):
            db.execute(sa.text(f"DELETE FROM {table}"))
    root = tmp_path / "forge"
    shutil.copytree(REGISTRY / "tools/nf-core/star/align/module",
                    root / "nf-core-modules/modules/nf-core/star/align")
    shutil.copytree(FIXTURES / "bwa" / "mem", root / "nf-core-modules/modules/nf-core/bwa/mem")
    monkeypatch.setattr(settings, "forge_cache", root)
    catalogue.run_sync(FakeSource(["star/align", "bwa/mem"]))


def _do(adaptation_id, move, key, value=None):
    item = forging.load(adaptation_id).items.get(key)
    forging.act(adaptation_id, forging.person(move, key, expected=item.current.n if item else None,
                                              value=value, because=None))


def _earlier(assembled: bool = True) -> str:
    """star/align re-forged, proposing a new type, approved and (by default) assembled."""
    a = forging.start("nf-core", "star/align", "rafael", reforge="nf-core/star/align@2.7.11b").id
    _do(a, Move.ANSWER, "questions:role", {"choice": "alignment"})
    for key, item in forging.load(a).items.items():
        if item.status == "proposed":
            _do(a, Move.APPROVE, key)
    _do(a, Move.WRITE, f"vocabulary:type:{NEW}", {"id": NEW, "states": []})
    _do(a, Move.WRITE, "rules:none", {"because": "nothing new"})
    _do(a, Move.WRITE, "tests:test:small", {
        "inputs": {"reads": ["genomics/a.fq"], "index": ["genomics/star"],
                   "gtf": ["genomics/a.gtf"]},
        "expect": [{"port": "bam", "pattern": "*.bam"}]})
    _do(a, Move.WRITE, "measurers:none", {"because": "nothing to measure"})
    if assembled:
        proof = forging.assemble(a)
        assert proof.loaded and proof.conforms, proof.problems
    return a


def _later() -> str:
    b = forging.start("nf-core", "bwa/mem", "rafael").id
    _do(b, Move.ANSWER, "questions:role", {"choice": "alignment"})
    return b


def test_a_later_adaptation_sees_an_assembled_one_tagged_pending():
    a = _earlier()
    b = _later()
    assert NEW in forging.pending_ids(b)
    _do(b, Move.WRITE, "contract:input:index", {"position": 1, "name": "index", "type_id": NEW})
    assert forging.read(b).depends_on == [a]


def test_an_unassembled_adaptation_is_invisible():
    _earlier(assembled=False)
    b = _later()
    assert NEW not in forging.pending_ids(b)
    with pytest.raises(Exception, match="MF0507"):
        _do(b, Move.WRITE, "contract:input:index", {"position": 1, "name": "index",
                                                    "type_id": NEW})


def test_abandoning_the_earlier_marks_and_reopens_the_later():
    """Review Focus 4: the dependant is marked and re-opened, and nothing of it is deleted."""
    a = _earlier()
    b = _later()
    _do(b, Move.WRITE, "contract:input:index", {"position": 1, "name": "index", "type_id": NEW})
    forging.abandon(a)
    item = forging.load(b).items["contract:input:index"]
    assert item.status == "reopened" and item.value["type_id"] == NEW
    assert "MF0513" in forging.read(b).messages[-1].content


def test_an_assembled_dependant_of_an_abandoned_draft_goes_back_to_review():
    """Review I6: it stops lending its own vocabulary, and its dependants hear of it."""
    a = _earlier()
    b = _later()
    _do(b, Move.WRITE, "contract:input:index", {"position": 1, "name": "index", "type_id": NEW})
    forging.set_phase(b, "assembled")
    forging.abandon(a)
    assert forging.read(b).phase == "reviewing"


def test_a_new_type_can_depend_on_a_pending_family_and_reopens_when_it_changes():
    a = _earlier(assembled=False)
    _do(a, Move.WRITE, "vocabulary:family:assembly", {
        "id": "assembly", "description": "Assembled sequences and assembly products."})
    _do(a, Move.WRITE, "vocabulary:type:assembly.fasta", {"id": "assembly.fasta", "states": []})
    proof = forging.assemble(a)
    assert proof.loaded and proof.conforms, proof.problems
    b = _later()
    _do(b, Move.WRITE, "contract:process", {
        "nf_process": "BWA_MEM", "nf_include": "modules/nf-core/bwa/mem/main",
        "roles": ["alignment"]})
    _do(b, Move.WRITE, "contract:input:reads", {
        "position": 0, "name": "reads", "type_id": "fastq.reads"})
    _do(b, Move.WRITE, "contract:output:bam", {
        "position": 0, "name": "bam", "type_id": "alignment.bam"})
    _do(b, Move.WRITE, "contract:nf_inputs", [
        {"ports": ["reads"]}, {"literal": [], "because": "Only family loading is tested"},
        {"literal": [], "because": "Only family loading is tested"},
        {"literal": False, "because": "Use the default output format"}])
    _do(b, Move.WRITE, "parameters:none", {"because": "Defaults"})
    assert "assembly" in forging.pending_families(b)
    assert "assembly" not in forging.pending_ids(b)
    key = "vocabulary:type:assembly.graph"
    _do(b, Move.WRITE, key, {"id": "assembly.graph", "states": []})
    assert forging.read(b).depends_on == [a]
    _do(b, Move.WRITE, "rules:none", {"because": "No new selection rule"})
    _do(b, Move.WRITE, "tests:test:small", {
        "inputs": {"reads": ["genomics/a.fq"]},
        "expect": [{"port": "bam", "pattern": "*.bam"}]})
    _do(b, Move.WRITE, "measurers:none", {"because": "nothing to measure"})
    proof = forging.assemble(b)
    assert proof.loaded and proof.conforms, proof.problems
    forging.abandon(a)
    assert forging.read(b).phase == "reviewing"
    item = forging.load(b).items[key]
    assert item.status == "reopened" and item.value["id"] == "assembly.graph"


def test_family_key_and_declared_id_must_agree():
    b = _later()
    with pytest.raises(Exception, match="family ID must match"):
        _do(b, Move.WRITE, "vocabulary:family:assembly", {
            "id": "other", "description": "Assembled sequences."})
