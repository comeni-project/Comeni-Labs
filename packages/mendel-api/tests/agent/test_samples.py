"""Every sample in one upload, each kept with the session under its name and with its
measurements (#466, #218; operator, 11-12: no cap)."""

import pytest
from fastapi.testclient import TestClient
from mendel_api import jobs
from mendel_api.agent.samples import _agreed, _sample_name
from mendel_api.authoring.types import UploadedSample
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import inspect, registry
from mendel_api.services.sample_upload import samples_of
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from support.paths import ROOT

PAIR = sorted((ROOT / "registry/measurers/formats/fastq/piece/fixtures/pair_150").glob("*.gz"))
needs_db = pytest.mark.skipif(not reachable(), reason="no database")


def test_mates_pair_and_the_rest_stand_alone():
    files = [(n, b"x") for n in ("a_R1.fq.gz", "a_R2.fq.gz", "b_1.fq", "b_2.fq", "c_R1.fq")]
    grouped = samples_of(files, ())
    assert [(s.name, [f for f, _ in s.files]) for s in grouped] == [
        ("a", ["a_R1.fq.gz", "a_R2.fq.gz"]), ("b", ["b_1.fq", "b_2.fq"]), ("c_R1", ["c_R1.fq"])]


def test_sizes_follow_their_files():
    files = [("b_1.fq", b"1"), ("a.fq", b"2"), ("b_2.fq", b"3")]
    grouped = samples_of(files, (10, 20, 30))
    assert [(s.name, s.sizes) for s in grouped] == [("b", (10, 30)), ("a", (20,))]


def test_a_repeated_name_is_numbered():
    grouped = samples_of([("a.fq", b"1"), ("a.fq", b"2"), ("a.fq", b"3")], ())
    assert [s.name for s in grouped] == ["a", "a#2", "a#3"]


@pytest.mark.parametrize("names", [
    ("S1_L001_R1_001.fastq.gz", "S1_L001_R2_001.fastq.gz"),
    ("a_r1.fq", "a_r2.fq"),
    ("a_R1", "a_R2"),
    ("a_R1.fq.gz", "a_R2.fq"),
    ("a.R1.fq", "a.R2.fq"),
])
def test_real_world_mates_pair(names):
    """bcl2fastq's own names, lowercase, no extension, mixed compression."""
    (one,) = samples_of([(n, b"x") for n in names], ())
    assert [f for f, _ in one.files] == sorted(names)


def test_two_files_that_do_not_look_like_mates_are_still_one_sample():
    (one,) = samples_of([("left.fq", b"x"), ("right.fq", b"y")], ())
    assert [f for f, _ in one.files] == ["left.fq", "right.fq"]


def test_a_sample_name_too_long_for_the_record_is_shortened_not_logged():
    name = _sample_name("x" * 400)
    assert len(name) <= 256
    UploadedSample(name=name, outcome="measured")


def test_a_fact_is_recorded_only_when_every_sample_decided_it():
    """One FASTQ pair and a BAM nothing reads: the pair's facts are not the study's."""
    (r1, r2) = PAIR
    grouped = samples_of([("a_R1.fq.gz", r1.read_bytes()), ("a_R2.fq.gz", r2.read_bytes()),
                          ("b.bam", b"not a fastq")], ())
    found = [inspect.inspect_sample(list(s.files), registry.stack(), None) for s in grouped]
    assert _agreed(found).facts == []


@needs_db
def test_many_pairs_in_one_upload_are_each_kept_with_their_facts(clean, monkeypatch):
    async def enqueue(name, *args, job_id=None, queue=jobs.DEFAULT_QUEUE, expires=None):
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    client = TestClient(create_app())
    sid = client.post("/api/pipeline/authoring", json={"prompt": "gene counts"}).json()[
        "session"]["id"]
    (r1, r2) = PAIR
    files = []
    for n in range(40):
        files += [("files", (f"s{n:03}_R1.fq.gz", r1.read_bytes())),
                  ("files", (f"s{n:03}_R2.fq.gz", r2.read_bytes()))]
    got = client.post(f"/api/pipeline/authoring/{sid}/samples", files=files)
    assert got.status_code == 200, got.text
    assert got.json()["samples"] == 40
    with session_scope() as db:
        kept = db.get(PipelineAuthoringSession, sid).samples
    assert len(kept) == 40 and kept[0]["name"] == "s000"
    assert kept[0]["files"] == ["s000_R1.fq.gz", "s000_R2.fq.gz"]
    facts = {f["measurement"]: f["value"] for f in kept[0]["facts"]}
    assert facts["paired"] is True and facts["read_length"] == 150
