"""Publishing and approving: nothing unproven goes out, nothing unchecked merges. A fake GitHub."""

import shutil

import pytest
import sqlalchemy as sa
from comeni_flow.interpret import Refused
from mendel_api.db import session_scope
from mendel_api.models import ForgePullRequest
from mendel_api.services import catalogue, forge_publish, forge_tests, forging
from mendel_api.settings import settings
from mendel_api_tests.catalogue import FakeSource
from mendel_api_tests.database import reachable
from mendel_forge.forging.model import Move
from mendel_forge.publishing import PublishUnavailable, PullRequest, PullRequestState
from support.paths import REGISTRY

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

STAR = "nf-core/star/align@2.7.11b"
TEST = {"inputs": {"reads": ["genomics/a.fq"], "index": ["genomics/star"],
                   "gtf": ["genomics/a.gtf"]},
        "params": {"seq_platform": "ILLUMINA"},
        "expect": [{"port": "bam", "pattern": "*.bam"}]}


class FakeRunner:
    def submit(self, bundle, name, params):
        return "run1"

    def state(self, run_id):
        return "succeeded"

    def results(self, run_id):
        return ["star_align/s.bam"]


class FakePublisher:
    def __init__(self, root):
        self.root = root
        self.opened, self.merged, self.closed = [], [], []
        self.refuse_open = self.refuse_merge = False
        self.now = PullRequestState(state="open", head="abc", checks="pending", says="not started")

    def checkout(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.copytree(REGISTRY, self.root, ignore=shutil.ignore_patterns(".git"))
        return self.root

    def open_pull_request(self, change):
        if self.refuse_open:
            raise PublishUnavailable("GitHub refused POST: 403")
        self.opened.append(change)
        number = len(self.opened)
        return PullRequest(number=number, url=f"https://github.com/x/y/pull/{number}",
                           branch=change.branch)

    def state(self, number):
        return self.now

    def merge(self, number, head):
        if self.refuse_merge:
            raise PublishUnavailable("GitHub refused PUT: 405")
        self.merged.append((number, head))

    def close(self, number):
        self.closed.append(number)


@pytest.fixture
def fake(tmp_path, monkeypatch):
    with session_scope() as db:
        for table in ("forge_pull_request", "forge_test_run", "forge_message", "forge_revision",
                      "forge_item", "forge_adaptation", "catalogue_module", "catalogue_sync"):
            db.execute(sa.text(f"DELETE FROM {table}"))
    root = tmp_path / "forge"
    for path in ("star/align", "star/genomegenerate"):
        shutil.copytree(REGISTRY / "tools/nf-core" / path / "module",
                        root / "nf-core-modules/modules/nf-core" / path)
    monkeypatch.setattr(settings, "forge_cache", root)
    monkeypatch.setattr(settings, "wiener_url", "http://wiener:8001")
    monkeypatch.setenv("COMENI_FORGE_GITHUB_TOKEN_SET", "set")
    catalogue.run_sync(FakeSource(["star/align", "star/genomegenerate"]))
    publisher = FakePublisher(tmp_path / "checkout")
    monkeypatch.setattr(forge_tests, "runner", lambda: FakeRunner())
    monkeypatch.setattr(forge_publish, "publisher", lambda: publisher)

    async def queued(*args, **kwargs):
        return True

    monkeypatch.setattr(forge_tests.jobs, "enqueue", queued)
    return publisher


def _do(adaptation_id, move, key, value=None):
    item = forging.load(adaptation_id).items.get(key)
    forging.act(adaptation_id, forging.person(move, key, expected=item.current.n if item else None,
                                              value=value, because=None))


async def _tested(contract=STAR, path="star/align", test=TEST) -> str:
    a = forging.start("nf-core", path, "rafael", reforge=contract).id
    _do(a, Move.ANSWER, "questions:role", {"choice": "alignment"})
    for key, item in forging.load(a).items.items():
        if item.status == "proposed":
            _do(a, Move.APPROVE, key)
    for key in ("vocabulary:none", "rules:none"):
        _do(a, Move.WRITE, key, {"because": "nothing new"})
    _do(a, Move.WRITE, "tests:test:small", test)
    proof = forging.assemble(a)
    assert proof.loaded and proof.conforms, proof.problems
    await forge_tests.start(a)
    forge_tests.submit_all(a)
    forge_tests.poll()
    assert forging.read(a).phase == "tested"
    return a


async def _in_review() -> str:
    a = await _tested()
    await forge_publish.start(a)
    forge_publish.publish(a)
    assert forging.read(a).phase == "in_review", forging.read(a).messages[-1].content
    return a


def _says(adaptation_id: str) -> str:
    return "\n".join(m.content for m in forging.read(adaptation_id).messages)


def _green(fake) -> None:
    fake.now = PullRequestState(state="open", head="abc", checks="green")
    forge_publish.poll()


@pytest.mark.asyncio
async def test_opening_needs_a_proven_draft(fake):
    a = forging.start("nf-core", "star/align", "rafael", reforge=STAR).id
    with pytest.raises(Refused, match="MF0506"):
        await forge_publish.start(a)


@pytest.mark.asyncio
async def test_a_draft_edited_after_its_tests_is_not_published(fake):
    a = await _tested()
    await forge_publish.start(a)
    (forging.draft_dir(a) / "registry.yml").write_text("name: changed\nrequires_format: 2\n")
    forge_publish.publish(a)
    assert not fake.opened and forging.read(a).phase == "tested"
    assert "MF0517" in _says(a)


@pytest.mark.asyncio
async def test_opening_records_the_pull_request_and_enters_review(fake):
    a = await _in_review()
    view = forging.read(a)
    assert view.pull_request.number == 1 and view.pull_request.checks == "pending"
    change = fake.opened[0]
    assert change.branch == "forge/nf-core-star-align-2.7.11b"
    assert "contract:process" in change.body and "run1" in change.body
    assert (fake.root / "changelog.d/nf-core-star-align.md").is_file()


@pytest.mark.asyncio
async def test_a_second_adaptation_cannot_open_while_one_is_open(fake):
    await _in_review()
    b = await _tested()
    with pytest.raises(Refused, match="MF0506.*open"):
        await forge_publish.start(b)
    assert forging.read(b).phase == "tested"


def test_the_database_holds_one_open_pull_request_at_most(fake):
    a = forging.start("nf-core", "star/align", "rafael", reforge=STAR).id
    b = forging.start("nf-core", "star/align", "rafael", reforge=STAR).id
    row = dict(number=1, url="u", branch="x", state="open", checks="pending", head="", digest="d",
               opened_by="r", opened_at=sa.func.now())
    with session_scope() as db:
        db.add(ForgePullRequest(adaptation=a, **row))
    with pytest.raises(sa.exc.IntegrityError), session_scope() as db:
        db.add(ForgePullRequest(adaptation=b, **row))


@pytest.mark.asyncio
async def test_the_registrys_checks_failing_pushes_nothing(fake, monkeypatch):
    a = await _tested()
    await forge_publish.start(a)
    monkeypatch.setattr(forge_publish, "check", lambda checkout: ["MD0013 somewhere: misfiled"])
    forge_publish.publish(a)
    assert not fake.opened and forging.read(a).phase == "tested"
    assert "MF0517" in _says(a) and "misfiled" in _says(a)


@pytest.mark.asyncio
async def test_github_refusing_at_open_returns_to_tested(fake):
    a = await _tested()
    fake.refuse_open = True
    await forge_publish.start(a)
    forge_publish.publish(a)
    assert forging.read(a).phase == "tested" and "403" in _says(a)


@pytest.mark.asyncio
@pytest.mark.parametrize("checks", ["pending", "red"])
async def test_approve_refuses_unless_green(fake, checks):
    a = await _in_review()
    fake.now = PullRequestState(state="open", head="abc", checks=checks, says="why not")
    forge_publish.poll()
    with pytest.raises(Refused, match="MF0518"):
        await forge_publish.approve(a, "rafael")
    assert not fake.merged


@pytest.mark.asyncio
async def test_a_check_gone_red_refuses_at_the_merge(fake):
    a = await _in_review()
    _green(fake)
    await forge_publish.approve(a, "rafael")
    fake.now = PullRequestState(state="open", head="abc", checks="red", says="failed: lint")
    forge_publish.merge(a, "rafael")
    assert not fake.merged and forging.read(a).phase == "in_review"
    assert "MF0518" in _says(a)
    assert forging.read(a).pull_request.merging is False


@pytest.mark.asyncio
async def test_approve_merges_the_head_and_records_who(fake):
    a = await _in_review()
    _green(fake)
    await forge_publish.approve(a, "rafael")
    assert forging.read(a).pull_request.merging is True
    forge_publish.merge(a, "rafael")
    assert fake.merged == [(1, "abc")]
    view = forging.read(a)
    assert view.phase == "merged" and view.pull_request.state == "merged"
    with session_scope() as db:
        assert db.scalar(sa.select(ForgePullRequest.approved_by)) == "rafael"


@pytest.mark.asyncio
async def test_github_refusing_the_merge_stays_in_review_and_says_so(fake):
    a = await _in_review()
    _green(fake)
    fake.refuse_merge = True
    await forge_publish.approve(a, "rafael")
    forge_publish.merge(a, "rafael")
    assert forging.read(a).phase == "in_review" and "405" in _says(a)


@pytest.mark.asyncio
async def test_a_pull_request_merged_by_hand_is_noticed(fake):
    a = await _in_review()
    fake.now = PullRequestState(state="merged", head="abc", checks="green")
    forge_publish.poll()
    assert forging.read(a).phase == "merged"


@pytest.mark.asyncio
async def test_one_closed_by_hand_returns_to_tested(fake):
    a = await _in_review()
    fake.now = PullRequestState(state="closed", head="abc", checks="pending")
    forge_publish.poll()
    assert forging.read(a).phase == "tested"
    await forge_publish.start(a)
    forge_publish.publish(a)
    assert forging.read(a).pull_request.number == 2


@pytest.mark.asyncio
async def test_a_merged_adaptation_refuses_commands(fake):
    a = await _in_review()
    fake.now = PullRequestState(state="merged", head="abc", checks="green")
    forge_publish.poll()
    item = forging.load(a).items["contract:process"]
    with pytest.raises(Refused, match="MF0506"):
        forging.act(a, forging.person(Move.CHANGE, "contract:process", expected=item.current.n,
                                      value=item.value, because=None))


@pytest.mark.asyncio
async def test_a_change_in_review_demotes_and_the_next_open_closes_the_old_one(fake):
    a = await _in_review()
    process = forging.load(a).items["contract:process"]
    _do(a, Move.CHANGE, "contract:process", process.value)
    assert forging.read(a).phase == "reviewing"
    for key, item in forging.load(a).items.items():
        if item.status == "reopened":
            _do(a, Move.APPROVE, key)
    forging.assemble(a)
    await forge_tests.start(a)
    forge_tests.submit_all(a)
    forge_tests.poll()
    await forge_publish.start(a)
    forge_publish.publish(a)
    assert fake.closed == [1] and forging.read(a).pull_request.number == 2


@pytest.mark.asyncio
async def test_the_catalogue_shows_in_review_and_merged_not_released(fake):
    await _in_review()
    assert catalogue.read_module("nf-core", "star/align").row.state == "in_review"
    fake.now = PullRequestState(state="merged", head="abc", checks="green")
    forge_publish.poll()
    assert catalogue.read_module("nf-core", "star/align").row.state == "imported", \
        "the registry in use already holds this version"
    with session_scope() as db:
        db.execute(sa.text("UPDATE forge_adaptation SET version = '9.9'"))
    assert catalogue.read_module("nf-core", "star/align").row.state == "merged_not_released"


@pytest.mark.asyncio
async def test_no_token_is_MF0516_and_the_page_says_why(fake, monkeypatch):
    a = await _tested()
    monkeypatch.delenv("COMENI_FORGE_GITHUB_TOKEN_SET")
    with pytest.raises(Refused, match="MF0516"):
        await forge_publish.start(a)
    assert "MF0516" in (forging.read(a).publish_unavailable or "")
