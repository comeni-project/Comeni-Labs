"""Every sample in one upload, each kept with the session under its name and with its
measurements (#466, #218; operator, 11-12: no cap)."""

import pytest
from fastapi.testclient import TestClient
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services.sample_upload import samples_of
from mendel_api_tests.database import reachable
from mendel_api_tests.samples import _gathering, _pending_for
from mendel_api_tests.samples import clean as clean  # noqa: F401
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
    grouped = samples_of([("a.fq", b"1"), ("a.fq", b"2")], ())
    assert [s.name for s in grouped] == ["a", "a#2"]


@needs_db
def test_many_pairs_in_one_upload_are_each_kept_with_their_facts(clean):  # noqa: F811
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")
    (r1, r2) = PAIR
    files = []
    for n in range(40):
        files += [("files", (f"s{n:03}_R1.fq.gz", r1.read_bytes())),
                  ("files", (f"s{n:03}_R2.fq.gz", r2.read_bytes()))]
    got = TestClient(create_app()).post(f"/api/pipeline/authoring/{sid}/samples",
                                        data={"proposal_id": pid}, files=files)
    assert got.status_code == 200, got.text
    with session_scope() as db:
        kept = db.get(PipelineAuthoringSession, sid).samples
    assert len(kept) == 40 and kept[0]["name"] == "s000"
    assert kept[0]["files"] == ["s000_R1.fq.gz", "s000_R2.fq.gz"]
    facts = {f["measurement"]: f["value"] for f in kept[0]["facts"]}
    assert facts["paired"] is True and facts["read_length"] == 150


def test_the_spread_counts_each_value_most_common_first():
    from mendel_api.stages.samples import spread

    kept = ([{"facts": [{"measurement": "read_length", "value": 150}]}] * 480
            + [{"facts": [{"measurement": "read_length", "value": 75}]}] * 20
            + [{"facts": []}])
    assert spread(kept, "read_length") == [(150, 480), (75, 20)]


def test_the_spread_is_said_in_words():
    from mendel_api.stages.samples import spread_words

    assert spread_words([(150, 480), (75, 20)]) == "150 in 480 samples, 75 in 20"
    assert spread_words([(True, 3), (False, 1)]) == "yes in 3 samples, no in 1"


@needs_db
def test_samples_that_differ_on_pairing_propose_it_varies(clean):  # noqa: F811
    """Paired and single-end uploads record no pairing and propose *it differs*, waiting for
    the click (operator, 11-11)."""
    from mendel_api.services import session as facade
    from mendel_api_tests.samples import _payload

    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")
    (r1, r2) = PAIR
    files = [("files", ("a_R1.fq.gz", r1.read_bytes())), ("files", ("a_R2.fq.gz", r2.read_bytes())),
             ("files", ("b.fq.gz", r1.read_bytes()))]
    got = TestClient(create_app()).post(f"/api/pipeline/authoring/{sid}/samples",
                                        data={"proposal_id": pid}, files=files)
    assert got.status_code == 200, got.text
    pending = _payload(facade.pending_id(sid))
    assert pending["subject"] == "paired"
    block = pending["block"]
    assert "yes in 1 samples, no in 1" in block["why_open"]
    (recommended,) = [o for o in block["options"] if o.get("recommended")]
    assert recommended["id"] == "varies"


@needs_db
def test_the_models_memory_has_the_spread_and_no_name(clean):  # noqa: F811
    from mendel_api.services import known

    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")
    (r1, r2) = PAIR
    files = [("files", ("patient07_R1.fq.gz", r1.read_bytes())),
             ("files", ("patient07_R2.fq.gz", r2.read_bytes())),
             ("files", ("patient08.fq.gz", r1.read_bytes()))]
    TestClient(create_app()).post(f"/api/pipeline/authoring/{sid}/samples",
                                  data={"proposal_id": pid}, files=files)
    text = known.text(sid)
    assert "paired: yes in 1 samples, no in 1" in text
    assert "patient07" not in text and "patient08" not in text
