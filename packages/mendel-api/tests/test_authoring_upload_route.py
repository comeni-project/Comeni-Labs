"""`POST /api/pipeline/authoring/{session_id}/samples`: one file or a pair, only the head read,
nothing written to disk, the protection level asked first (14.7.6.4)."""

import gzip
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mendel_api.authoring.types import CharacteriseReply
from mendel_api.main import create_app
from mendel_api.services import authoring, authoring_jobs, characterise, inspect
from test_authoring_samples import (  # noqa: F401
    _database_is_reachable,
    _gathering,
    _pending_for,
    clean,
)

ROOT = Path(__file__).resolve().parents[3]
PAIR = ROOT / "registry/inspectors/formats/fastq/piece/fixtures/pair_150"
needs_db = pytest.mark.skipif(not _database_is_reachable(), reason="no database")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _at(subject: str) -> tuple[str, str]:
    sid = _gathering(["counts.matrix"])
    return sid, _pending_for(sid, subject)


def _post(client, sid, pid, files):
    return client.post(
        f"/api/pipeline/authoring/{sid}/samples", data={"proposal_id": pid}, files=files
    )


@needs_db
def test_an_upload_is_inspected_and_answers_the_gap(client, clean):  # noqa: F811
    sid, pid = _at("paired")
    files = [("files", (p.name, p.read_bytes())) for p in sorted(PAIR.glob("*.gz"))]
    got = _post(client, sid, pid, files)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["outcome"] == "measured" and {"paired", "read_length"} <= set(body["recorded"])
    assert body["steps"][0] == "read the first 4 MB of 2 file(s)"
    assert body["session"]["pending_proposal"]["id"] != pid


@needs_db
@pytest.mark.parametrize("count", [0, 3])
def test_any_count_but_one_or_two_is_refused(client, clean, count):  # noqa: F811
    """Review focus 1."""
    sid, pid = _at("read_length")
    files = [("files", (f"f{i}.fq", b"@r\nA\n+\nI\n")) for i in range(count)]
    got = _post(client, sid, pid, files)
    assert got.status_code == 422 and "MI0214" in got.text
    assert authoring.pending_id(sid) == pid


@needs_db
def test_above_level_0_the_upload_is_refused(client, clean, monkeypatch):  # noqa: F811
    from mendel_api.services import protection

    monkeypatch.setattr(protection, "level", lambda: "sealed")
    sid, pid = _at("read_length")
    got = _post(client, sid, pid, [("files", ("a.fq", b"@r\nA\n+\nI\n"))])
    assert got.status_code == 403 and "MI0213" in got.text


@needs_db
def test_only_the_head_is_kept_and_nothing_is_spooled_to_disk(client, clean, monkeypatch):  # noqa: F811
    """Review focus 2: a large file is read through, never held, never written."""
    import tempfile

    import starlette.formparsers

    def no_disk(*args, **kwargs):
        raise AssertionError("an upload was written to disk")

    # Starlette imports the class by name, so its own reference is patched too; patching only
    # `tempfile` left this test passing against `request.form()`, which spools to disk.
    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", no_disk)
    monkeypatch.setattr(tempfile, "SpooledTemporaryFile", no_disk)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", no_disk)
    seen = []
    real = inspect.inspect_sample
    monkeypatch.setattr(
        inspect,
        "inspect_sample",
        lambda files, stack, claimed=None: (
            seen.extend(len(b) for _, b in files) or real(files, stack, claimed)
        ),
    )
    sid, pid = _at("read_length")
    big = b"@r\n" + b"A" * (10 * 2**20)
    got = _post(client, sid, pid, [("files", ("big.fq", big))])
    assert got.status_code == 200, got.text
    assert seen == [inspect.HEAD_BYTES]


@needs_db
def test_a_sample_on_a_settled_gap_is_refused(client, clean):  # noqa: F811
    sid, pid = _at("paired")
    files = [("files", (p.name, p.read_bytes())) for p in sorted(PAIR.glob("*.gz"))]
    assert _post(client, sid, pid, files).status_code == 200
    again = _post(client, sid, pid, files)
    assert again.status_code == 422 and "MI0203" in again.text


def _multipart(parts: list[tuple[str, str | None, bytes]], *, close: bool = True) -> bytes:
    boundary = b"b0undary"
    body = b""
    for name, filename, data in parts:
        disposition = f'form-data; name="{name}"' + (
            f'; filename="{filename}"' if filename is not None else ""
        )
        body += b"--" + boundary + b"\r\nContent-Disposition: " + disposition.encode()
        body += b"\r\n\r\n" + data + b"\r\n"
    return body + (b"--" + boundary + b"--\r\n" if close else b"")


def _raw(client, sid, body: bytes):
    return client.post(
        f"/api/pipeline/authoring/{sid}/samples",
        content=body,
        headers={"content-type": "multipart/form-data; boundary=b0undary"},
    )


@needs_db
def test_many_form_fields_are_refused_not_held(client, clean):  # noqa: F811
    """Review of #134: every distinct field name was kept, so 100,000 of them held 200 MB."""
    sid, pid = _at("read_length")
    parts = [("proposal_id", None, pid.encode())]
    parts += [(f"f{i}", None, b"x" * 200) for i in range(50)]
    parts += [("files", "a.fq", b"@r\nA\n+\nI\n")]
    got = _raw(client, sid, _multipart(parts))
    assert got.status_code == 422 and "MI0214" in got.text


@needs_db
def test_a_body_cut_before_its_end_is_refused(client, clean):  # noqa: F811
    """Review of #134: a truncated body read as one empty file and answered *nothing reads this
    type yet*, which is not what happened."""
    sid, pid = _at("read_length")
    body = _multipart(
        [("proposal_id", None, pid.encode()), ("files", "a.fq", b"@r\nA\n")], close=False
    )
    got = _raw(client, sid, body)  # no closing boundary: the file part never ends
    assert got.status_code == 422 and "MI0214" in got.text


@needs_db
def test_an_empty_file_input_is_not_a_file(client, clean, monkeypatch):  # noqa: F811
    """Issue 226: a browser form's empty second file input (`filename=""`, no bytes) counted
    as a file named *sample*."""
    seen = []
    monkeypatch.setattr(
        inspect,
        "inspect_sample",
        lambda files, stack, claimed=None: seen.append(files) or _nothing(),
    )
    sid, pid = _at("read_length")
    body = _multipart([("proposal_id", None, pid.encode()), ("files", "a.fq", b"@r\nA\n+\nI\n"),
                       ("files", "", b"")])
    got = _raw(client, sid, body)
    assert got.status_code == 200, got.text
    assert [name for name, _ in seen[0]] == ["a.fq"]


@needs_db
def test_a_file_under_another_field_name_is_refused(client, clean):  # noqa: F811
    sid, pid = _at("read_length")
    body = _multipart([("proposal_id", None, pid.encode()), ("other", "a.fq", b"@r\nA\n+\nI\n")])
    got = _raw(client, sid, body)
    assert got.status_code == 422 and "MI0214" in got.text and "other" in got.text


@needs_db
def test_a_refused_second_upload_is_never_inspected(client, clean, monkeypatch):  # noqa: F811
    """Issue 226 (from 14.7.6.5's review): the gap was asked about only after inspecting."""
    sid, pid = _at("paired")
    files = [("files", (p.name, p.read_bytes())) for p in sorted(PAIR.glob("*.gz"))]
    assert _post(client, sid, pid, files).status_code == 200
    monkeypatch.setattr(
        inspect, "inspect_sample", lambda *a: pytest.fail("a settled gap's sample was inspected")
    )
    again = _post(client, sid, pid, files)
    assert again.status_code == 422 and "MI0203" in again.text


def _nothing():
    return inspect.Inspection(outcome="no_inspector", reason="nothing reads this type yet",
                              steps=[])


@needs_db
def test_the_upload_does_its_database_work_off_the_event_loop(client, clean, monkeypatch):  # noqa: F811
    """Issue 226: `answer_with_sample` and the session view ran on the event loop, holding every
    other request while the database answered."""
    import asyncio

    on_loop = []

    def where(real):
        def wrapped(*args, **kwargs):
            try:
                asyncio.get_running_loop()
                on_loop.append(real.__name__)
            except RuntimeError:
                pass
            return real(*args, **kwargs)

        return wrapped

    monkeypatch.setattr(authoring, "answer_with_sample", where(authoring.answer_with_sample))
    monkeypatch.setattr(authoring, "read", where(authoring.read))
    sid, pid = _at("paired")
    files = [("files", (p.name, p.read_bytes())) for p in sorted(PAIR.glob("*.gz"))]
    assert _post(client, sid, pid, files).status_code == 200
    assert on_loop == []


@pytest.fixture
def readable(monkeypatch):
    monkeypatch.setattr(characterise, "available", lambda: True)
    queued = []

    async def enqueue(session_id, proposal_id, attempt, excerpt):
        queued.append((session_id, proposal_id, attempt, excerpt))
        return True

    monkeypatch.setattr(authoring_jobs, "enqueue_characterise", enqueue)
    return queued


def _bam():
    header = "@HD\tVN:1.6\tSO:coordinate\n" + "@SQ\tSN:chr1\tLN:1000\n" * 20
    return gzip.compress(b"BAM\x01" + struct.pack("<i", len(header)) + header.encode())


@needs_db
def test_a_type_nothing_reads_is_queued_for_the_ai(client, clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    got = _post(client, sid, pid, [("files", ("x.bam", _bam()))])
    assert got.status_code == 200, got.text
    assert got.json()["outcome"] == "reading"
    [(q_sid, q_pid, attempt, excerpt)] = readable
    assert (q_sid, q_pid, attempt) == (sid, pid, 1)
    assert excerpt.binary_before and excerpt.text.startswith("@HD")
    block = got.json()["session"]["pending_proposal"]["block"]
    assert block["reading"]["state"] == "pending"


@needs_db
def test_without_the_ai_a_type_nothing_reads_is_as_today(client, clean, monkeypatch):  # noqa: F811
    sid, pid = _at("paired")
    monkeypatch.setattr(characterise, "available", lambda: False)
    got = _post(client, sid, pid, [("files", ("x.bam", _bam()))])
    assert got.json()["outcome"] == "no_inspector"


@needs_db
def test_a_file_with_no_text_is_never_queued(client, clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    got = _post(client, sid, pid, [("files", ("x.bin", bytes(range(256)) * 50))])
    assert got.json()["outcome"] == "no_inspector" and readable == []


@needs_db
def test_a_second_upload_while_reading_is_refused(client, clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    _post(client, sid, pid, [("files", ("x.bam", _bam()))])
    again = _post(client, sid, pid, [("files", ("x.bam", _bam()))])
    assert again.status_code == 422 and "MI0215" in again.text
    assert len(readable) == 1


@needs_db
def test_a_hand_back_is_claimed_by_the_recorded_type_and_measured(client, clean, readable):  # noqa: F811
    sid, pid = _at("paired")
    attempt = authoring.start_reading(pid)
    authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="fastq.reads"), by="ana", handed_back=True
    )
    files = [("files", (p.name.replace(".fq.gz", ".txt.gz"), p.read_bytes()))
             for p in sorted(PAIR.glob("*.gz"))]
    got = _post(client, sid, pid, files)
    assert got.json()["outcome"] == "measured", got.text
    assert "paired" in got.json()["recorded"]


@needs_db
def test_a_browser_cannot_claim_a_type_the_session_did_not_record(client, clean, readable):  # noqa: F811
    sid, pid = _at("paired")
    files = [("files", (p.name.replace(".fq.gz", ".txt.gz"), p.read_bytes()))
             for p in sorted(PAIR.glob("*.gz"))]
    got = client.post(
        f"/api/pipeline/authoring/{sid}/samples",
        data={"proposal_id": pid, "claimed": "fastq.reads"}, files=files,
    )
    # Refused outright (a form field nobody declared), or inspected without the claim.
    assert got.status_code != 200 or got.json()["outcome"] != "measured"


@needs_db
def test_a_hand_back_that_fails_the_content_check_drops_the_type(client, clean, readable):  # noqa: F811
    sid, pid = _at("paired")
    attempt = authoring.start_reading(pid)
    authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="fastq.reads"), by="ana", handed_back=True
    )
    got = _post(client, sid, pid, [("files", ("x.txt", b">not a fastq\nACGT\n" * 50))])
    assert got.json()["outcome"] == "unreadable"
    assert authoring.reading_of(pid) is None


@needs_db
def test_a_reading_never_queued_ends_at_once_and_frees_the_question(client, clean, monkeypatch):  # noqa: F811
    """Issue 241: Redis refused, or the job id was already taken."""
    monkeypatch.setattr(characterise, "available", lambda: True)

    async def refused(*args):
        return False

    monkeypatch.setattr(authoring_jobs, "enqueue_characterise", refused)
    sid, pid = _at("genome.fasta")
    got = _post(client, sid, pid, [("files", ("x.bam", _bam()))])
    assert got.status_code == 200, got.text
    assert got.json()["session"]["pending_proposal"]["block"]["reading"]["state"] == "no_answer"
    authoring.check_sample_question(pid)


@needs_db
def test_a_hand_back_never_starts_another_reading(client, clean, readable):  # noqa: F811
    """Issue 246: a pair whose files disagree is claimed by nothing, even by type; the re-send
    must not start a new reading, or the card re-sends without end."""
    sid, pid = _at("paired")
    attempt = authoring.start_reading(pid)
    authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="fastq.reads"), by="ana", handed_back=True
    )
    r1 = next(iter(sorted(PAIR.glob("*.gz"))))
    files = [("files", ("x_R1.fq.gz", r1.read_bytes())),
             ("files", ("x_R2.txt", gzip.decompress(r1.read_bytes())))]
    got = _post(client, sid, pid, files)
    assert got.status_code == 200, got.text
    assert got.json()["outcome"] != "reading" and readable == []
