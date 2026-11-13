"""The forge drafts a measurer end to end (#487): `samtools faidx`'s genome-length parser, drafted
by a fake model, approved, assembled, proven by a fake Wiener that reports the fact, and placed in
a registry checkout that does not have it yet. Fakes only: no model, Wiener or GitHub."""

import json
import shutil

import pytest
import sqlalchemy as sa
from comeni_ai import ModelAccess
from mendel_api.db import session_scope
from mendel_api.services import catalogue, forge_publish, forge_tests, forging, forging_ai
from mendel_api.settings import settings
from mendel_api_tests.catalogue import FakeSource
from mendel_api_tests.database import reachable
from mendel_forge.forging.model import Move, Piece
from mendel_forge.publishing import PullRequest, PullRequestState
from support.forge_measurer import FAIDX, KEY, measurer
from support.paths import REGISTRY

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

OURS = "measurers/measures/genome_length_fai"


class Model:
    """Replies with the faidx parser, as a model would draft it."""

    access = ModelAccess(model="fake/forge", base_url="http://local")
    last_prompt = last_response = last_refusal = last_usage = None

    def respond(self, prompt, shape, choices=None):
        self.last_prompt = prompt
        self.last_response = json.dumps({"items": {KEY: measurer()},
                                         "because": {KEY: "the .fai lists each length"}})
        return shape.model_validate_json(self.last_response)


class Wiener:
    def submit(self, bundle, name, params):
        return "run1"

    def state(self, run_id):
        return "succeeded"

    def results(self, run_id):
        return ["samtools_faidx/genome.fasta.fai"]

    def measured(self, run_id):
        return [{"measurement": "genome_length", "value": 29903, "undetermined": None}]


class GitHub:
    def __init__(self, root):
        self.root, self.opened = root, []

    def checkout(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.copytree(REGISTRY, self.root, ignore=shutil.ignore_patterns(".git"))
        shutil.rmtree(self.root / OURS)  # the registry before this measurer existed
        return self.root

    def open_pull_request(self, change):
        self.opened.append(change)
        return PullRequest(number=1, url="https://github.com/x/y/pull/1", branch=change.branch)

    def state(self, number):
        return PullRequestState(state="open", head="abc", checks="pending", says="")


@pytest.fixture
def github(tmp_path, monkeypatch):
    with session_scope() as db:
        for table in ("forge_review", "forge_pull_request", "forge_test_run", "forge_step",
                      "forge_message", "forge_revision", "forge_item", "forge_adaptation",
                      "catalogue_module", "catalogue_sync"):
            db.execute(sa.text(f"DELETE FROM {table}"))
        db.execute(sa.text("DELETE FROM ai_invocation WHERE agent = 'forge'"))
    root = tmp_path / "forge"
    shutil.copytree(REGISTRY / "tools/nf-core/samtools/faidx/module",
                    root / "nf-core-modules/modules/nf-core/samtools/faidx")
    monkeypatch.setattr(settings, "forge_cache", root)
    monkeypatch.setattr(settings, "wiener_url", "http://wiener:8001")
    monkeypatch.setenv("COMENI_FORGE_GITHUB_TOKEN_SET", "set")
    catalogue.run_sync(FakeSource(["samtools/faidx"]))
    publisher = GitHub(tmp_path / "checkout")
    monkeypatch.setattr(forge_tests, "runner", lambda: Wiener())
    monkeypatch.setattr(forge_publish, "publisher", lambda: publisher)

    async def queued(*args, **kwargs):
        return True

    monkeypatch.setattr(forge_tests.jobs, "enqueue", queued)
    return publisher


def _do(adaptation_id, move, key, value=None):
    item = forging.load(adaptation_id).items.get(key)
    forging.act(adaptation_id, forging.person(move, key, expected=item.current.n if item else None,
                                              value=value, because=None))


@pytest.mark.asyncio
async def test_faidx_measurer_from_draft_to_pull_request(github):
    a = forging.start("nf-core", "samtools/faidx", "rafael", reforge=FAIDX).id
    _do(a, Move.ANSWER, "questions:role", {"choice": "fasta_indexing"})
    for key, item in forging.load(a).items.items():
        if item.status == "proposed":
            _do(a, Move.APPROVE, key)
    for key in ("vocabulary:none", "rules:none"):
        _do(a, Move.WRITE, key, {"because": "nothing new"})
    _do(a, Move.WRITE, "tests:test:small", {"inputs": {"fasta": ["genomics/genome.fasta"]},
                                            "expect": [{"port": "fai", "pattern": "*.fai"}]})

    forging_ai.draft_piece(a, Piece.MEASURERS, Model())
    drafted = forging.load(a).items[KEY]
    assert drafted.status == "proposed" and drafted.current.actor == "ai"
    _do(a, Move.APPROVE, KEY)

    proof = forging.assemble(a)
    assert proof.loaded and proof.conforms, proof.problems
    await forge_tests.start(a)
    forge_tests.submit_all(a)
    forge_tests.poll()
    assert forging.read(a).phase == "tested", forging.read(a).messages[-1].content

    await forge_publish.start(a)
    forge_publish.publish(a)
    assert forging.read(a).phase == "in_review", forging.read(a).messages[-1].content
    placed = github.root / OURS / "piece" / "genome_length_fai.py"
    assert placed.read_text() == measurer()["code"]
    (change,) = github.opened
    assert f"| `{KEY}` | ai | " in change.body, "drafted by the AI, decided by a person"
