"""The reading rule and Check these, end to end (#511): a rule or a fix is kept on the analysis's
data and applied on every scan."""

from mendel_api.services import decisions
from mendel_api.services.data import scan as scanning
from mendel_api_tests.building import clean as clean  # noqa: F401
from mendel_api_tests.data import PAIR, draft, pairs, tick, view


def folder_with_a_stray_mate(root):
    folder = pairs(root / "demo", "Y1", "Y2")
    (folder / "Y4_R1.fastq.gz").write_bytes(PAIR[0].read_bytes())
    (folder / "Y4_2.fq.gz").write_bytes(PAIR[1].read_bytes())
    return folder


def test_the_view_lists_the_rule_its_examples_and_the_checks(clean, client, root):
    d = draft(client)
    tick(client, d, folder_with_a_stray_mate(root))
    scanning.scan(d, who="ana")
    got = view(client, d)
    assert got["rule"]["origin"] == "rule" and got["rule"]["pattern"] is None
    assert got["rule_result"]["samples"] == 4 and got["rule_result"]["unfit"] == 0
    assert got["rule_result"]["examples"][0] == ["Y1_R1.fq.gz", "Y1", "1"]
    [check] = got["checks"]
    assert check["kind"] == "missing_mate" and check["sample"] == "Y4_R1"


def test_a_persons_rule_is_tagged_you_and_unconfirmed_until_confirm(clean, client, root):
    d = draft(client)
    tick(client, d, folder_with_a_stray_mate(root))
    got = client.put(f"/api/data/{d}/rule", json={"pattern": "{sample}_R{read}.fq.gz"})
    assert got.status_code == 200, got.text
    assert got.json()["rule"] == {
        "pattern": "{sample}_R{read}.fq.gz",
        "origin": "you",
        "confirmed": False,
        "reason": None,
    }
    scanning.scan(d, who="ana")
    after = view(client, d)
    assert [s["name"] for s in after["samples"]] == ["Y1", "Y2"]
    assert after["rule_result"]["unfit"] == 2
    confirmed = client.post(f"/api/data/{d}/rule/confirm").json()
    assert confirmed["rule"]["confirmed"] is True


def test_a_bad_rule_is_refused(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1"))
    refused = client.put(f"/api/data/{d}/rule", json={"pattern": "{read}.fq"})
    assert refused.status_code in (400, 422) and "MI0223" in refused.text


def test_use_file_fix_pairs_the_mate_and_survives_a_rescan(clean, client, root):
    d = draft(client)
    tick(client, d, folder_with_a_stray_mate(root))
    scanning.scan(d, who="ana")
    got = client.post(
        f"/api/data/{d}/fixes", json={"kind": "use_file", "sample": "Y4_R1", "file": "Y4_2.fq.gz"}
    )
    assert got.status_code == 200, got.text
    scanning.scan(d, who="ana")
    after = view(client, d)
    assert ("Y4", 2) in [(s["name"], len(s["files"])) for s in after["samples"]]
    assert after["checks"] == []
    scanning.scan(d, who="ana")
    assert ("Y4", 2) in [(s["name"], len(s["files"])) for s in view(client, d)["samples"]]


def test_leave_out_keeps_the_sample_listed_but_out_of_the_facts(clean, client, root):
    d = draft(client)
    tick(client, d, folder_with_a_stray_mate(root))
    scanning.scan(d, who="ana")
    client.post(f"/api/data/{d}/fixes", json={"kind": "leave_out", "sample": "Y4_R1"})
    client.post(f"/api/data/{d}/fixes", json={"kind": "leave_out", "sample": "Y4_2"})
    scanning.scan(d, who="ana")
    after = view(client, d)
    out = {s["name"]: s["left_out"] for s in after["samples"]}
    assert out["Y4_R1"] is True and out["Y1"] is False
    facts = {f.subject: f for f in decisions.read(d).facts}
    assert facts["paired"].value is True, "the lone halves no longer split the facts"


def test_a_fix_uses_saved_measurements_without_queueing_or_reading_files(
    clean, client, root, monkeypatch
):
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1"))
    scanning.scan(d, who="ana")
    client.queued.clear()
    from mendel_api.services.data import edits

    def unexpected(*args):
        raise AssertionError("a sample choice must not read files")

    monkeypatch.setattr(edits, "_head", unexpected)
    before = view(client, d)
    for _ in range(5):
        got = client.post(f"/api/data/{d}/fixes", json={"kind": "leave_out", "sample": "Y1"})
        assert got.status_code == 200, got.text
    after = got.json()
    assert after["scan"] == before["scan"]
    assert after["samples"][0]["left_out"] is True
    assert len(after["fixes"]) == 1 and after["revision"] == before["revision"] + 1
    assert client.queued == []
    undone = client.delete(f"/api/data/{d}/fixes/0").json()
    assert undone["samples"][0]["left_out"] is False and undone["fixes"] == []


def test_pairing_and_undo_read_only_the_affected_sample(clean, client, root, monkeypatch):
    from mendel_api.services.data import edits

    d = stray(client, root)
    read = []
    original = edits._head
    monkeypatch.setattr(
        edits, "_head", lambda path, size: (read.append(path.name), original(path, size))[1]
    )
    client.queued.clear()
    before = view(client, d)
    got = client.post(
        f"/api/data/{d}/fixes", json={"kind": "use_file", "sample": "Y4_R1", "file": "Y4_2.fq.gz"}
    )
    assert got.status_code == 200, got.text
    assert set(read) == {"Y4_R1.fastq.gz", "Y4_2.fq.gz"} and len(read) == 2
    assert got.json()["scan"]["finished_at"] == before["scan"]["finished_at"]
    assert any(s["name"] == "Y4" and len(s["files"]) == 2 for s in got.json()["samples"])
    # A retry still names the original singleton, which no longer exists, and is a no-op.
    repeat = client.post(
        f"/api/data/{d}/fixes", json={"kind": "use_file", "sample": "Y4_R1", "file": "Y4_2.fq.gz"}
    )
    assert repeat.status_code == 200 and len(repeat.json()["fixes"]) == 1 and len(read) == 2
    read.clear()
    undone = client.delete(f"/api/data/{d}/fixes/0")
    assert undone.status_code == 200, undone.text
    assert len(read) == 2 and set(read) == {"Y4_R1.fastq.gz", "Y4_2.fq.gz"}
    assert client.queued == []


def test_a_fix_can_be_undone(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1", "Y2"))
    scanning.scan(d, who="ana")
    client.post(f"/api/data/{d}/fixes", json={"kind": "leave_out", "sample": "Y1"})
    scanning.scan(d, who="ana")
    assert [s["left_out"] for s in view(client, d)["samples"]] == [True, False]
    undone = client.delete(f"/api/data/{d}/fixes/0")
    assert undone.status_code == 200, undone.text and undone.json()["fixes"] == []
    scanning.scan(d, who="ana")
    assert [s["left_out"] for s in view(client, d)["samples"]] == [False, False]


def test_a_file_named_as_a_reference_is_not_a_sample(clean, client, root):
    d = draft(client)
    folder = pairs(root / "a", "Y1")
    (folder / "genome.fasta").write_text(">chrI\nACGT\n")
    tick(client, d, folder)
    scanning.scan(d, who="ana")
    assert "genome" in [s["name"] for s in view(client, d)["samples"]]
    client.post(
        f"/api/data/{d}/references",
        json={"path": str(folder / "genome.fasta"), "type_id": "genome.fasta"},
    )
    scanning.scan(d, who="ana")
    after = view(client, d)
    assert [s["name"] for s in after["samples"]] == ["Y1"]
    files = {f["name"]: f for f in client.get(f"/api/data/{d}/files").json()["files"]}
    assert files["genome.fasta"]["used_as"] == "reference"


def stray(client, root):
    d = draft(client)
    tick(client, d, folder_with_a_stray_mate(root))
    scanning.scan(d, who="ana")
    return d


def test_an_ai_fix_is_kept_by_the_person(clean, client, root):
    """Checkpoint C, 1: the AI's change is the person's once they keep it."""
    from mendel_api.agent.data import ApplyFixArgs, apply_fix
    from mendel_api.agent.tools import ToolContext

    d = stray(client, root)
    apply_fix(
        ToolContext(draft_id=d, session_id=None, who="ana", expected_revision=0),
        ApplyFixArgs(kind="use_file", sample="Y4_R1", file="Y4_2.fq.gz", because="same stem"),
    )
    assert view(client, d)["fixes"][0]["by"] == "ai"
    kept = client.post(f"/api/data/{d}/fixes/0/keep").json()
    assert kept["fixes"][0]["by"] == "you" and kept["fixes"][0]["reason"] == "same stem"


def test_a_fix_for_a_sample_that_is_not_there_is_refused(clean, client, root):
    """Checkpoint C, 3: a fix that would do nothing is refused at the boundary."""
    d = stray(client, root)
    refused = client.post(f"/api/data/{d}/fixes", json={"kind": "leave_out", "sample": "nope"})
    assert refused.status_code in (400, 422) and "MI0226" in refused.text
    wrong_file = client.post(
        f"/api/data/{d}/fixes", json={"kind": "use_file", "sample": "Y4_R1", "file": "Y1_R1.fq.gz"}
    )
    assert wrong_file.status_code in (400, 422) and "MI0226" in wrong_file.text


def test_the_route_records_every_fix_as_the_persons(clean, client, root):
    d = stray(client, root)
    got = client.post(
        f"/api/data/{d}/fixes",
        json={"kind": "leave_out", "sample": "Y1", "by": "ai", "reason": "forged"},
    )
    assert got.json()["fixes"][0]["by"] == "you" and got.json()["fixes"][0]["reason"] is None


def test_keeping_an_odd_value_dismisses_its_check(clean, client, root):
    """Checkpoint C, 9: 'Keep it' — the person decided the value is fine."""
    from mendel_api.services.data.rule import Fix, checks

    samples = [
        {
            "name": n,
            "files": ["a", "b"],
            "type_id": "fastq.reads",
            "left_out": False,
            "facts": [{"measurement": "read_length", "value": v}],
        }
        for n, v in (("Y1", 101), ("Y2", 101), ("Y3", 50))
    ]
    assert [c.sample for c in checks(samples, [])] == ["Y3"]
    keep = Fix(kind="keep", sample="Y3", measurement="read_length")
    assert checks(samples, [], [keep]) == []


def test_a_cell_is_set_on_its_own(clean, client, root):
    """Checkpoint C, 5: two cells edited one after the other keep both."""
    d = stray(client, root)
    client.put(f"/api/data/{d}/columns", json={"name": "condition", "values": {}})
    client.put(f"/api/data/{d}/columns/condition/Y1", json={"value": "treated"})
    got = client.put(f"/api/data/{d}/columns/condition/Y2", json={"value": "control"}).json()
    assert got["columns"] == {"condition": {"Y1": "treated", "Y2": "control"}}


def test_read_again_rescans_and_a_scan_says_when(clean, client, root):
    """Checkpoint C, 10."""
    d = stray(client, root)
    assert view(client, d)["scan"]["finished_at"]
    client.queued.clear()
    got = client.post(f"/api/data/{d}/rescan").json()
    assert got["scan"]["state"] == "scanning" and client.queued[0][0] == "scan_analysis_data"
