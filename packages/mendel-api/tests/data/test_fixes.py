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
    assert got.json()["rule"] == {"pattern": "{sample}_R{read}.fq.gz", "origin": "you",
                                  "confirmed": False, "reason": None}
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
    got = client.post(f"/api/data/{d}/fixes",
                      json={"kind": "use_file", "sample": "Y4_R1", "file": "Y4_2.fq.gz"})
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


def test_a_fix_queues_a_scan(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1"))
    client.queued.clear()
    client.post(f"/api/data/{d}/fixes", json={"kind": "leave_out", "sample": "Y1"})
    assert [name for name, _, _ in client.queued] == ["scan_analysis_data"]


def test_a_fix_can_be_undone(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1", "Y2"))
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
    client.post(f"/api/data/{d}/references",
                json={"path": str(folder / "genome.fasta"), "type_id": "genome.fasta"})
    scanning.scan(d, who="ana")
    after = view(client, d)
    assert [s["name"] for s in after["samples"]] == ["Y1"]
    files = {f["name"]: f for f in client.get(f"/api/data/{d}/files").json()["files"]}
    assert files["genome.fasta"]["used_as"] == "reference"
