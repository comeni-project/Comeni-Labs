"""An analysis's data, scanned where it is (#511): the folders a person ticks, every file in
them, the samples they pair into and what was measured on each. Paths stay here; never in a
pipeline."""

import json

import pytest
from fastapi.testclient import TestClient
from mendel_api import jobs
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import AnalysisData, PipelineDraft
from mendel_api.services import decisions, inspect
from mendel_api.services.data import scan as scanning
from mendel_api.settings import settings
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from mendel_resolver.goal import Goal
from support.example import example_mapping
from support.paths import ROOT

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

PAIR = sorted((ROOT / "registry/measurers/formats/fastq/piece/fixtures/pair_150").glob("*.gz"))


@pytest.fixture
def root(tmp_path, monkeypatch):
    base = tmp_path / "data"
    base.mkdir()
    monkeypatch.setattr(settings, "data_roots", [base])
    return base


@pytest.fixture
def client(monkeypatch):
    queued = []

    async def enqueue(name, *args, job_id=None, queue=jobs.DEFAULT_QUEUE, expires=None):
        queued.append((name, args, job_id))
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    app = TestClient(create_app())
    app.queued = queued
    return app


def draft(client) -> str:
    made = client.post("/api/pipeline/drafts", json={"graph": {"nodes": [], "edges": []}})
    return made.json()["id"]


def pairs(folder, *stems):
    folder.mkdir(parents=True, exist_ok=True)
    r1, r2 = PAIR
    for stem in stems:
        (folder / f"{stem}_R1.fq.gz").write_bytes(r1.read_bytes())
        (folder / f"{stem}_R2.fq.gz").write_bytes(r2.read_bytes())
    return folder


def tick(client, draft_id, *folders):
    return client.put(f"/api/data/{draft_id}/folders", json={"folders": [str(f) for f in folders]})


def view(client, draft_id):
    return client.get(f"/api/data/{draft_id}").json()


def test_ticking_a_folder_outside_the_roots_is_refused(clean, client, root, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    refused = tick(client, draft(client), outside)
    assert refused.status_code in (400, 422) and "MI0221" in refused.text


def test_ticking_queues_one_scan_and_says_it_is_scanning(clean, client, root):
    d = draft(client)
    got = tick(client, d, pairs(root / "liver", "L01"))
    assert got.status_code == 200, got.text
    assert got.json()["scan"]["state"] == "scanning"
    [(name, args, job_id)] = client.queued
    assert name == "scan_analysis_data" and args[0] == d and job_id.startswith(f"scan:{d}:")


def test_scan_pairs_r1_r2_into_samples_and_keeps_every_file(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "liver", "L01", "L02"))
    scanning.scan(d, who="ana")
    got = view(client, d)
    assert got["scan"]["state"] == "done" and got["scan"]["done"] == 4 == got["scan"]["total"]
    assert [s["name"] for s in got["samples"]] == ["L01", "L02"]
    first = got["samples"][0]
    assert [p.rsplit("/", 1)[1] for p in first["files"]] == ["L01_R1.fq.gz", "L01_R2.fq.gz"]
    facts = {f["measurement"]: f["value"] for f in got["samples"][0]["facts"]}
    assert facts["paired"] is True and facts["read_length"] == 150
    assert got["files"] == 4
    files = client.get(f"/api/data/{d}/files").json()
    assert [f["name"] for f in files["files"]] == [
        "L01_R1.fq.gz", "L01_R2.fq.gz", "L02_R1.fq.gz", "L02_R2.fq.gz"]
    assert files["files"][0]["sample"] == "L01" and files["files"][0]["recognised"]


def test_a_lone_r1_is_a_sample_of_its_own(clean, client, root):
    d = draft(client)
    folder = pairs(root / "liver", "L01")
    (folder / "L17_R1.fq.gz").write_bytes(PAIR[0].read_bytes())
    tick(client, d, folder)
    scanning.scan(d, who="ana")
    got = [(s["name"], len(s["files"])) for s in view(client, d)["samples"]]
    assert got == [("L01", 2), ("L17_R1", 1)]


def test_same_sample_name_in_two_folders_is_numbered(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "a", "S1"), pairs(root / "b", "S1"))
    scanning.scan(d, who="ana")
    assert [s["name"] for s in view(client, d)["samples"]] == ["S1", "S1#2"]


def test_scan_reads_at_most_head_bytes_per_file(clean, client, root, monkeypatch):
    d = draft(client)
    folder = root / "big"
    folder.mkdir()
    (folder / "huge.fq").write_bytes(b"@r\nACGT\n+\nIIII\n" * 10_000)
    monkeypatch.setattr(inspect, "HEAD_BYTES", 64)
    read = []
    real = scanning._head

    def spy(path, size):
        out = real(path, size)
        read.append(len(out))
        return out

    monkeypatch.setattr(scanning, "_head", spy)
    tick(client, d, folder)
    scanning.scan(d, who="ana")
    assert read == [64]


def test_scan_of_many_samples_holds_one_samples_heads_at_a_time(clean, client, root, monkeypatch):
    """Heads read and not yet measured: counted up when read, down when their sample has been
    inspected. A scan that read every head first would peak at 60 (Checkpoint A, finding 7)."""
    d = draft(client)
    pairs(root / "many", *[f"s{n:03}" for n in range(30)])
    held, peak = [0], [0]
    read, inspected = scanning._head, inspect.inspect_sample

    def reading(path, size):
        held[0] += 1
        peak[0] = max(peak[0], held[0])
        return read(path, size)

    def inspecting(files, stack, claimed=None, sizes=()):
        try:
            return inspected(files, stack, claimed, sizes=sizes)
        finally:
            held[0] -= len(files)

    monkeypatch.setattr(scanning, "_head", reading)
    monkeypatch.setattr(inspect, "inspect_sample", inspecting)
    tick(client, d, root / "many")
    scanning.scan(d, who="ana")
    assert len(view(client, d)["samples"]) == 30
    assert peak[0] == 2


def test_a_failed_scan_says_so_and_does_not_raise(clean, client, root, monkeypatch):
    d = draft(client)
    tick(client, d, pairs(root / "liver", "L01"))

    def broken(*_args, **_kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(inspect, "inspect_sample", broken)
    scanning.scan(d, who="ana")
    got = view(client, d)["scan"]
    assert got["state"] == "failed" and "disk on fire" in got["error"]


def test_paths_never_reach_the_draft(clean, client, root):
    d = draft(client)
    folder = pairs(root / "liver", "L01")
    tick(client, d, folder)
    scanning.scan(d, who="ana")
    with session_scope() as db:
        row = db.get(PipelineDraft, d)
        stored = json.dumps({"graph": row.graph, "name": row.name}, default=str)
    assert str(root) not in stored
    facts = json.dumps([f.model_dump(mode="json") for f in decisions.read(d).facts])
    assert str(root) not in facts and "L01" not in facts


def test_read_facts_lists_samples_from_the_data_table(clean, client, root):
    from mendel_api.agent import loop
    from mendel_api.agent.read import Nothing, read_facts
    from mendel_api.agent.tools import ToolContext

    d = draft(client)
    tick(client, d, pairs(root / "liver", "L01", "L02"))
    scanning.scan(d, who="ana")
    session = loop.start_session(d, who="ana")
    context = ToolContext(draft_id=d, session_id=session, who="ana", expected_revision=0)
    got = read_facts(context, Nothing())
    assert got.samples == ["L01", "L02"]


def test_the_upload_route_is_gone(clean, client):
    started = client.post("/api/pipeline/authoring", json={"prompt": "gene counts"})
    session = started.json()["session"]
    gone = client.post(f"/api/pipeline/authoring/{session['id']}/samples",
                       files=[("files", ("a.fq", b"@"))])
    assert gone.status_code in (404, 405)


def test_deleting_the_draft_deletes_its_data(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "liver", "L01"))
    assert client.delete(f"/api/pipeline/drafts/{d}").status_code == 204
    with session_scope() as db:
        assert db.get(AnalysisData, d) is None


def test_a_symlinked_file_pointing_outside_is_not_read(clean, client, root, tmp_path, monkeypatch):
    """Checkpoint A, finding 1: a link inside a ticked folder must not reach the rest of the
    machine. The file is skipped, and nothing outside the root is opened."""
    import os

    secret = tmp_path / "outside" / "secret.txt"
    secret.parent.mkdir()
    secret.write_text("TOKEN=abc\n")
    d = draft(client)
    folder = pairs(root / "liver", "L01")
    os.symlink(secret, folder / "L09_R1.fq")
    opened = []
    real = scanning._head

    def spy(path, size):
        opened.append(str(path))
        return real(path, size)

    monkeypatch.setattr(scanning, "_head", spy)
    tick(client, d, folder)
    scanning.scan(d, who="ana")
    got = view(client, d)
    assert got["scan"]["state"] == "done"
    assert [s["name"] for s in got["samples"]] == ["L01"]
    assert not any("L09" in p or "secret" in p for p in opened)


def test_a_fifo_in_a_folder_does_not_hang_the_scan(clean, client, root):
    import os

    d = draft(client)
    folder = pairs(root / "liver", "L01")
    os.mkfifo(folder / "pipe_R1.fq")
    tick(client, d, folder)
    scanning.scan(d, who="ana")
    assert [s["name"] for s in view(client, d)["samples"]] == ["L01"]


def test_a_stale_scan_does_not_overwrite_a_newer_one(clean, client, root):
    """Checkpoint A, finding 3: the person ticks A, then A and B; the first scan finishing last
    must not write A's samples over A and B's."""
    d = draft(client)
    a, b = pairs(root / "a", "SA"), pairs(root / "b", "SB")
    tick(client, d, a)
    first = view(client, d)["revision"]
    tick(client, d, a, b)
    scanning.scan(d, who="ana")
    assert [s["name"] for s in view(client, d)["samples"]] == ["SA", "SB"]
    scanning.scan(d, who="ana", revision=first)
    got = view(client, d)
    assert [s["name"] for s in got["samples"]] == ["SA", "SB"] and got["scan"]["state"] == "done"


def test_a_failed_scan_does_not_keep_another_selections_samples(clean, client, root, monkeypatch):
    d = draft(client)
    tick(client, d, pairs(root / "a", "SA"))
    scanning.scan(d, who="ana")
    tick(client, d, pairs(root / "b", "SB"))
    def broken(*_args, **_kwargs):
        raise OSError("x")

    monkeypatch.setattr(inspect, "inspect_sample", broken)
    scanning.scan(d, who="ana")
    got = view(client, d)
    assert got["scan"]["state"] == "failed" and got["samples"] == []


def test_a_draft_deleted_mid_scan_ends_the_scan_quietly(clean, client, root, monkeypatch):
    d = draft(client)
    tick(client, d, pairs(root / "a", "SA"))
    real = inspect.inspect_sample

    def delete_then_inspect(*args, **kwargs):
        client.delete(f"/api/pipeline/drafts/{d}")
        return real(*args, **kwargs)

    monkeypatch.setattr(inspect, "inspect_sample", delete_then_inspect)
    scanning.scan(d, who="ana")  # does not raise


def test_ticking_a_file_is_refused(clean, client, root):
    folder = pairs(root / "a", "SA")
    refused = tick(client, draft(client), folder / "SA_R1.fq.gz")
    assert refused.status_code in (400, 422) and "MI0221" in refused.text


def _asks_for_data(d: str) -> str:
    """A session whose agent's last turn asked for data, as the agent does with shape `data`."""
    from mendel_api.agent import loop
    from mendel_api.authoring.types import TurnState
    from mendel_api.models import PipelineAuthoringTurn
    from sqlalchemy import select

    session = loop.start_session(d, who="ana")
    seq = loop.add_person_turn(session, "count genes")
    with session_scope() as db:
        turn = db.scalar(select(PipelineAuthoringTurn).where(
            PipelineAuthoringTurn.session_id == session, PipelineAuthoringTurn.seq == seq))
        turn.state = TurnState.ANSWERED.value
        turn.blocks = [{"kind": "ask", "id": "b1", "question_id": "q1", "shape": "data",
                        "question": "Which reads?", "options": [], "unit": ""}]
    return session


def test_a_finished_scan_answers_the_agents_data_question(clean, client, root, monkeypatch):
    """Checkpoint A, finding 5: the person follows "Open Data" and ticks; the agent hears what
    was found, as the person's answer, once."""
    import asyncio

    from mendel_api.agent import chat

    said = []

    async def say(session_id, text):
        said.append((session_id, text))
        return 0, True

    monkeypatch.setattr(chat, "say", say)
    d = draft(client)
    session = _asks_for_data(d)
    tick(client, d, pairs(root / "liver", "L01", "L02"))
    scanning.scan(d, who="ana")
    asyncio.run(chat.data_scanned(d))
    [(to, text)] = said
    assert to == session and "2 samples" in text and "paired" in text
    assert "/" not in text, "no path in the agent's words"


def test_a_scan_with_no_open_data_question_says_nothing(clean, client, root, monkeypatch):
    import asyncio

    from mendel_api.agent import chat, loop

    said = []

    async def say(session_id, text):
        said.append(text)
        return 0, True

    monkeypatch.setattr(chat, "say", say)
    d = draft(client)
    loop.start_session(d, who="ana")
    tick(client, d, pairs(root / "liver", "L01"))
    scanning.scan(d, who="ana")
    asyncio.run(chat.data_scanned(d))
    assert said == []


def test_a_scan_that_cannot_be_queued_says_so_rather_than_scanning_forever(clean, client, root,
                                                                            monkeypatch):
    async def down(*_args, **_kwargs):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(jobs, "enqueue", down)
    d = draft(client)
    got = tick(client, d, pairs(root / "a", "SA")).json()
    assert got["scan"]["state"] == "failed" and "could not start" in got["scan"]["error"]


def test_changing_the_folders_changes_the_facts(clean, client, root):
    """Checkpoint A, finding 4: facts measured on data no longer ticked do not stay."""
    d = draft(client)
    tick(client, d, pairs(root / "reads", "L01"))
    scanning.scan(d, who="ana")
    assert {f.subject for f in decisions.read(d).facts} >= {"paired", "read_length"}
    assert [i.type_id for i in decisions.read(d).inputs] == ["fastq.reads"]
    empty = root / "empty"
    empty.mkdir()
    tick(client, d, empty)
    scanning.scan(d, who="ana")
    assert decisions.read(d).facts == [] and decisions.read(d).inputs == []


def test_the_persons_word_stands_over_what_the_data_measured(clean, client, root):
    d = draft(client)
    decisions.import_goal(d, Goal.model_validate(example_mapping()), who="ana")
    tick(client, d, pairs(root / "reads", "L01"))
    scanning.scan(d, who="ana")
    facts = {f.subject: f for f in decisions.read(d).facts}
    assert facts["read_length"].origin.value == "person_said"
    assert facts["quality_encoding"].origin.value == "measured"
