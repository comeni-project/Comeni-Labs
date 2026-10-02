"""`POST /api/pipeline/authoring/{session_id}/samples`: one file or a pair, only the head read,
nothing written to disk, the protection level asked first (14.7.6.4)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services import authoring, inspect
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
        inspect, "inspect_sample",
        lambda files, stack: seen.extend(len(b) for _, b in files) or real(files, stack),
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
