"""References, a person's columns and the Overview (#511)."""

from mendel_api.services import decisions
from mendel_api.services.data import scan as scanning
from mendel_api.services.data.summary import summary
from mendel_api_tests.building import clean as clean  # noqa: F401
from test_scan import client as client  # noqa: F401
from test_scan import draft, pairs, tick, view  # noqa: F401
from test_scan import root as root


def a_reference(root):
    ref = root / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    (ref / "genome.fasta").write_text(">chrI\nACGTACGT\n")
    return ref / "genome.fasta"


def test_reference_from_a_file_is_kept_with_its_type(clean, client, root):
    d = draft(client)
    got = client.post(f"/api/data/{d}/references",
                      json={"path": str(a_reference(root)), "type_id": "genome.fasta"})
    assert got.status_code == 200, got.text
    [ref] = got.json()["references"]
    assert (ref["name"], ref["type_id"], ref["origin"]) == ("genome.fasta", "genome.fasta", "you")
    assert [i.type_id for i in decisions.read(d).inputs] == ["genome.fasta"]
    assert client.delete(f"/api/data/{d}/references/0").json()["references"] == []


def test_reference_outside_roots_is_refused(clean, client, root, tmp_path):
    outside = tmp_path / "x.fasta"
    outside.write_text(">a\nA\n")
    refused = client.post(f"/api/data/{draft(client)}/references",
                          json={"path": str(outside), "type_id": "genome.fasta"})
    assert refused.status_code in (400, 422) and "MI0221" in refused.text


def test_a_reference_of_an_undeclared_type_is_refused(clean, client, root):
    refused = client.post(f"/api/data/{draft(client)}/references",
                          json={"path": str(a_reference(root)), "type_id": "no.such"})
    assert refused.status_code in (400, 422)


def sample(name, files, type_id="fastq.reads", **facts):
    return {"name": name, "files": files, "outcome": "measured", "type_id": type_id,
            "left_out": False, "facts": [{"measurement": k, "value": v} for k, v in facts.items()]}


def file(path, size):
    return {"path": path, "name": path, "size": size}


def test_tiles_for_reads_and_for_assemblies_use_the_same_four_labels():
    reads = summary([sample("a", ["a1", "a2"], read_length=101)], [file("a1", 10), file("a2", 10)])
    assemblies = summary([sample("x", ["x.fa"], type_id=None)], [file("x.fa", 5)])
    assert [t.label for t in reads.tiles] == [t.label for t in assemblies.tiles] == [
        "Samples", "Kinds of data", "Size on disk", "Files"]
    assert [t.value for t in reads.tiles] == ["1", "1", "20 B", "2"]


def test_compare_by_lists_only_numeric_facts_every_sample_has():
    got = summary([sample("a", [], read_length=101, paired=True, n50=10),
                   sample("b", [], read_length=50, paired=True)], [])
    [read_length] = got.compare_by
    assert read_length.measurement == "read_length" and read_length.label == "Read length"
    assert [(v.sample, v.value) for v in read_length.values] == [("a", 101), ("b", 50)]
    assert read_length.median == 75.5


def test_compare_by_is_empty_when_nothing_numeric_was_measured():
    assert summary([sample("a", [], paired=True)], []).compare_by == []


def test_what_was_measured_says_measured_or_varies():
    got = summary([sample("a", [], read_length=101, paired=True),
                   sample("b", [], read_length=50, paired=True)], [])
    assert [(m.measurement, m.value, m.origin) for m in got.measured] == [
        ("paired", True, "measured"), ("read_length", None, "varies")]


def test_a_column_is_kept_per_sample(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1", "Y2"))
    scanning.scan(d, who="ana")
    got = client.put(f"/api/data/{d}/columns",
                     json={"name": "condition", "values": {"Y1": "treated", "Y2": "control"}})
    assert got.status_code == 200, got.text
    assert got.json()["columns"] == {"condition": {"Y1": "treated", "Y2": "control"}}


def test_a_column_cannot_shadow_a_measured_fact(clean, client, root):
    refused = client.put(f"/api/data/{draft(client)}/columns",
                         json={"name": "read_length", "values": {}})
    assert refused.status_code in (400, 422) and "MI0224" in refused.text


def test_the_view_carries_the_summary(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1", "Y2"))
    scanning.scan(d, who="ana")
    got = view(client, d)["summary"]
    assert got["tiles"][0] == {"label": "Samples", "value": "2", "hint": None}
    assert [c["measurement"] for c in got["compare_by"]] == ["read_length"]
