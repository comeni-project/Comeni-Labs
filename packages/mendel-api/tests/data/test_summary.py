"""References, a person's columns and the Overview (#511)."""

from mendel_api.services import decisions
from mendel_api.services.data import scan as scanning
from mendel_api.services.data.summary import summary
from mendel_api_tests.building import clean as clean  # noqa: F401
from mendel_api_tests.data import draft, pairs, tick, view


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
    reads = summary([sample("a", ["a1", "a2"], read_length=101)], 2, 20)
    assemblies = summary([sample("x", ["x.fa"], type_id=None)], 1, 5)
    assert [t.label for t in reads.tiles] == [t.label for t in assemblies.tiles] == [
        "Samples", "Kinds of data", "Size on disk", "Files"]
    assert [t.value for t in reads.tiles] == ["1", "1", "20 B", "2"]


def test_compare_by_lists_only_numeric_facts_every_sample_has():
    got = summary([sample("a", [], read_length=101, paired=True, n50=10),
                   sample("b", [], read_length=50, paired=True)], 0, 0)
    [read_length] = got.compare_by
    assert read_length.measurement == "read_length" and read_length.label == "Read length"
    assert [(v.sample, v.value) for v in read_length.values] == [("a", 101), ("b", 50)]
    assert read_length.median == 75.5


def test_compare_by_is_empty_when_nothing_numeric_was_measured():
    assert summary([sample("a", [], paired=True)], 0, 0).compare_by == []


def test_what_was_measured_says_measured_or_varies():
    got = summary([sample("a", [], read_length=101, paired=True),
                   sample("b", [], read_length=50, paired=True)], 0, 0)
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
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1"))
    scanning.scan(d, who="ana")
    refused = client.put(f"/api/data/{d}/columns", json={"name": "read_length", "values": {}})
    assert refused.status_code in (400, 422) and "MI0225" in refused.text


def test_a_column_may_give_a_fact_nothing_measured(clean, client, root):
    """Checkpoint B, I8: strandedness is the person's to give, per sample."""
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1"))
    scanning.scan(d, who="ana")
    got = client.put(f"/api/data/{d}/columns",
                     json={"name": "strandedness", "values": {"Y1": "reverse"}})
    assert got.status_code == 200, got.text


def test_the_view_carries_the_summary(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1", "Y2"))
    scanning.scan(d, who="ana")
    got = view(client, d)["summary"]
    assert got["tiles"][0] == {"label": "Samples", "value": "2", "hint": None}
    assert [c["measurement"] for c in got["compare_by"]] == ["read_length"]


def _current(d):
    from mendel_api.db import session_scope
    from mendel_api.models import PipelineDraft

    with session_scope() as db:
        return db.get(PipelineDraft, d).projection_current


def _set_current(d):
    from mendel_api.db import session_scope
    from mendel_api.models import PipelineDraft

    with session_scope() as db:
        db.get(PipelineDraft, d).projection_current = True


def test_data_changes_mark_the_drawn_pipeline_outdated(clean, client, root):
    """Checkpoint B, I7: the goal moved, so the picture is not current any more."""
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1"))
    _set_current(d)
    scanning.scan(d, who="ana")
    assert _current(d) is False
    _set_current(d)
    client.post(f"/api/data/{d}/references",
                json={"path": str(a_reference(root)), "type_id": "genome.fasta"})
    assert _current(d) is False
    _set_current(d)
    client.put(f"/api/data/{d}/columns", json={"name": "condition", "values": {"Y1": "x"}})
    assert _current(d) is False


def test_a_units_change_on_the_datas_input_is_the_persons(clean, client, root):
    """Checkpoint B, I6: it is logged as what the person said, never as `measured`."""
    from mendel_api.services import changes
    from mendel_authoring.payloads import DecisionChange

    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1"))
    scanning.scan(d, who="ana")
    changes.apply(d, DecisionChange(kind="units", subject="fastq.reads", value=True), who="ana")
    [reads] = [i for i in decisions.read(d).inputs if i.type_id == "fastq.reads"]
    assert reads.units is True and reads.origin.value == "person_said"


def test_reference_types_are_the_study_wide_ones(clean, client):
    got = client.get("/api/data/reference-types").json()
    assert "genome.fasta" in got and "annotation.gtf" in got and "fastq.reads" not in got
    assert got == sorted(got)


def test_drafts_page_rows_carry_data_summary(clean, client, root):
    d = draft(client)
    tick(client, d, pairs(root / "a", "Y1", "Y2"))
    scanning.scan(d, who="ana")
    rows = {r["id"]: r for r in client.get("/api/pipeline/drafts").json()["drafts"]}
    assert rows[d]["data"] == {"samples": 2, "checks": 0, "scan": "done", "folders": 1}
    other = draft(client)
    rows = {r["id"]: r for r in client.get("/api/pipeline/drafts").json()["drafts"]}
    assert rows[other]["data"] is None


def test_this_machine_says_cpus_memory_and_disk(clean, client, root):
    got = client.get("/api/data/machine").json()
    assert got["cpus"] >= 1 and got["memory_gb"] > 0 and got["disk_free_gb"] >= 0
    assert got["load"] >= 0


def test_the_polled_view_counts_the_files_where_they_are_kept(clean, client, root):
    """#592. The data view, polled every 2 s while a scan runs, loaded every listed file to
    count them and add their sizes. It asks the database for the two numbers."""
    from mendel_api.db import engine
    from sqlalchemy import event

    d = draft(client)
    tick(client, d, pairs(root / "liver", "L01", "L02"))
    scanning.scan(d, who="ana")
    sent = []

    def heard(conn, cursor, statement, *args):
        sent.append(statement)

    event.listen(engine, "before_cursor_execute", heard)
    try:
        got = view(client, d)
    finally:
        event.remove(engine, "before_cursor_execute", heard)
    assert got["files"] == 4
    assert sent, "no statement captured: this would check nothing"
    assert not [s for s in sent if "analysis_data.files" in s], "the file list was loaded"
