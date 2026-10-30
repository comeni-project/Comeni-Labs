"""Running a tool's tests: green only for what ran, and never stuck (spec §4). A fake runner."""

import shutil
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from comeni_flow.interpret import Refused
from mendel_api.db import session_scope
from mendel_api.models import ForgeTestRun
from mendel_api.services import catalogue, forge_tests, forging
from mendel_api.settings import settings
from mendel_api_tests.catalogue import FakeSource
from mendel_api_tests.database import reachable
from mendel_forge.forging.model import Move
from mendel_forge.runner import RunnerUnavailable
from support.paths import REGISTRY

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

STAR = "nf-core/star/align@2.7.11b"
TEST = {"inputs": {"reads": ["genomics/a.fq"], "index": ["genomics/star"],
                   "gtf": ["genomics/a.gtf"]},
        "params": {"seq_platform": "ILLUMINA"},
        "expect": [{"port": "bam", "pattern": "*.bam"}]}


class FakeRunner:
    def __init__(self, phase="running", files=("star_align/s.bam",)):
        self.phase, self.files = phase, list(files)
        self.submitted: list[dict] = []
        self.refuse_submit = self.refuse_state = False

    def submit(self, bundle, name, params):
        if self.refuse_submit:
            raise RunnerUnavailable("Wiener refused POST /api/runs: 401")
        self.submitted.append(params)
        return f"run{len(self.submitted)}"

    def state(self, run_id):
        if self.refuse_state:
            raise RunnerUnavailable("Wiener could not be reached: ConnectError")
        return self.phase

    def results(self, run_id):
        return self.files


@pytest.fixture
def fake(tmp_path, monkeypatch):
    with session_scope() as db:
        for table in ("forge_test_run", "forge_message", "forge_revision", "forge_item",
                      "forge_adaptation", "catalogue_module", "catalogue_sync"):
            db.execute(sa.text(f"DELETE FROM {table}"))
    root = tmp_path / "forge"
    shutil.copytree(REGISTRY / "tools/nf-core/star/align/module",
                    root / "nf-core-modules/modules/nf-core/star/align")
    monkeypatch.setattr(settings, "forge_cache", root)
    monkeypatch.setattr(settings, "wiener_url", "http://wiener:8001")
    catalogue.run_sync(FakeSource(["star/align"]))
    runner = FakeRunner()
    monkeypatch.setattr(forge_tests, "runner", lambda: runner)

    async def queued(*args, **kwargs):
        return True

    monkeypatch.setattr(forge_tests.jobs, "enqueue", queued)
    return runner


def _do(adaptation_id, move, key, value=None):
    item = forging.load(adaptation_id).items.get(key)
    forging.act(adaptation_id, forging.person(move, key, expected=item.current.n if item else None,
                                              value=value, because=None))


def _assembled() -> str:
    a = forging.start("nf-core", "star/align", "rafael", reforge=STAR).id
    _do(a, Move.ANSWER, "questions:role", {"choice": "alignment"})
    for key, item in forging.load(a).items.items():
        if item.status == "proposed":
            _do(a, Move.APPROVE, key)
    for key in ("vocabulary:none", "rules:none"):
        _do(a, Move.WRITE, key, {"because": "nothing new"})
    _do(a, Move.WRITE, "tests:test:small", TEST)
    proof = forging.assemble(a)
    assert proof.loaded and proof.conforms, proof.problems
    return a


async def _started(adaptation_id: str) -> None:
    await forge_tests.start(adaptation_id)
    forge_tests.submit_all(adaptation_id)


def _says(adaptation_id: str) -> str:
    return "\n".join(m.content for m in forging.read(adaptation_id).messages)


@pytest.mark.asyncio
async def test_running_submits_each_test_with_public_urls_and_enters_testing(fake):
    a = _assembled()
    await _started(a)
    assert forging.read(a).phase == "testing"
    assert len(fake.submitted) == 1
    urls = [v for v in fake.submitted[0].values() if isinstance(v, str)]
    assert urls and all(u.startswith("https://raw.githubusercontent.com/nf-core/test-datasets/")
                        for u in urls)
    assert [r.state for r in forging.read(a).tests] == ["running"]


@pytest.mark.asyncio
async def test_every_expectation_met_is_green_and_tested(fake):
    a = _assembled()
    await _started(a)
    fake.phase = "succeeded"
    assert forge_tests.poll() == 1
    view = forging.read(a)
    assert view.phase == "tested" and [r.state for r in view.tests] == ["passed"]
    assert forge_tests.proven(a)


@pytest.mark.asyncio
async def test_a_run_that_publishes_nothing_matching_is_not_green(fake):
    a = _assembled()
    await _started(a)
    fake.phase, fake.files = "succeeded", ["star_align/s.log", "other/x.bam"]
    forge_tests.poll()
    view = forging.read(a)
    assert view.phase == "assembled" and view.tests[0].state == "failed"
    assert "*.bam" in view.tests[0].says and "MF0515" in _says(a)
    assert not forge_tests.proven(a)


@pytest.mark.asyncio
async def test_a_failed_run_returns_to_assembled_with_its_reason(fake):
    a = _assembled()
    await _started(a)
    fake.phase = "failed"
    forge_tests.poll()
    view = forging.read(a)
    assert view.phase == "assembled" and "failed" in view.tests[0].says


@pytest.mark.asyncio
async def test_wiener_refusing_at_submit_does_not_strand_testing(fake):
    a = _assembled()
    fake.refuse_submit = True
    await _started(a)
    view = forging.read(a)
    assert view.phase == "assembled" and "401" in view.tests[0].says


@pytest.mark.asyncio
async def test_wiener_unreachable_while_polling_retries_then_fails_after_an_hour(fake):
    a = _assembled()
    await _started(a)
    fake.refuse_state = True
    forge_tests.poll()
    assert forging.read(a).phase == "testing", "one failed poll is not a failed test"
    with session_scope() as db:
        db.execute(sa.update(ForgeTestRun).values(
            heard_at=datetime.now(UTC) - timedelta(hours=2)))
    forge_tests.poll()
    view = forging.read(a)
    assert view.phase == "assembled" and "no answer" in view.tests[0].says


@pytest.mark.asyncio
async def test_a_command_during_testing_never_becomes_tested(fake):
    a = _assembled()
    await _started(a)
    process = forging.load(a).items["contract:process"]
    _do(a, Move.CHANGE, "contract:process", process.value)
    assert forging.read(a).phase == "reviewing"
    fake.phase = "succeeded"
    forge_tests.poll()
    assert forging.read(a).phase == "reviewing"
    assert not forge_tests.proven(a)


@pytest.mark.asyncio
async def test_two_starts_make_one_set_of_runs(fake):
    a = _assembled()
    await forge_tests.start(a)
    with pytest.raises(Refused, match="MF0506"):
        await forge_tests.start(a)
    assert forging.read(a).phase == "testing"


@pytest.mark.asyncio
async def test_green_counts_only_for_its_digest(fake):
    a = _assembled()
    await _started(a)
    fake.phase = "succeeded"
    forge_tests.poll()
    assert forge_tests.proven(a)
    (forging.draft_dir(a) / "registry.yml").write_text("name: changed\nrequires_format: 2\n")
    assert not forge_tests.proven(a)


@pytest.mark.asyncio
async def test_running_again_after_a_failure_counts_only_the_new_attempt(fake):
    a = _assembled()
    await _started(a)
    fake.phase = "failed"
    forge_tests.poll()
    await _started(a)
    fake.phase = "succeeded"
    forge_tests.poll()
    assert forging.read(a).phase == "tested" and forge_tests.proven(a)
    assert len(forging.read(a).tests) == 1


@pytest.mark.asyncio
async def test_no_wiener_is_MF0514_and_the_page_says_why(fake, monkeypatch):
    a = _assembled()
    monkeypatch.setattr(settings, "wiener_url", "")
    with pytest.raises(Refused, match="MF0514"):
        await forge_tests.start(a)
    assert "MF0514" in (forging.read(a).tests_unavailable or "")


@pytest.mark.asyncio
async def test_tests_not_assembled_are_refused(fake):
    a = forging.start("nf-core", "star/align", "rafael", reforge=STAR).id
    with pytest.raises(Refused, match="MF0506"):
        await forge_tests.start(a)


@pytest.mark.asyncio
async def test_a_tested_adaptation_stays_pending_vocabulary(fake):
    a = _assembled()
    await _started(a)
    fake.phase = "succeeded"
    forge_tests.poll()
    assert forging.read(a).phase == "tested"
    assert a not in forging.pending_ids(a)
    assert forging.visible_phases() >= {"assembled", "testing", "tested"}
