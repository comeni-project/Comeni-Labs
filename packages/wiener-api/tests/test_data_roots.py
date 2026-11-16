"""A run reads only from the data roots (#508, #511), and samples sent as `stage` are linked into
the run's own folder so exactly they are read."""

import os

from wiener_api.services.launcher import _materialise_tables, paths_outside


def files(tmp_path, *names):
    out = []
    for name in names:
        path = tmp_path / name
        path.write_text("x")
        out.append(str(path))
    return out


def test_staged_pairs_become_links_and_one_pattern(tmp_path):
    data, work = tmp_path / "data", tmp_path / "work"
    data.mkdir()
    work.mkdir()
    y1 = files(data, "Y1_R1.fastq.gz", "Y1_R2.fastq.gz")
    y4 = files(data, "Y4_R1.fastq.gz", "Y4_2.fq.gz")
    written = _materialise_tables({"input": {"stage": [{"sample": "Y1", "files": y1},
                                                       {"sample": "Y4", "files": y4}]}}, work)
    staged = work / "input"
    assert written["input"] == f"{staged}/*_R{{1,2}}.*"
    assert sorted(os.listdir(staged)) == ["Y1_R1.fastq.gz", "Y1_R2.fastq.gz",
                                          "Y4_R1.fastq.gz", "Y4_R2.fq.gz"]
    assert os.readlink(staged / "Y4_R2.fq.gz") == y4[1]


def test_staged_single_files_become_one_pattern_each(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    a, b = files(tmp_path, "a.fasta", "b.fasta")
    written = _materialise_tables({"assemblies": {"stage": [{"sample": "a", "files": [a]},
                                                            {"sample": "b", "files": [b]}]}}, work)
    assert written["assemblies"] == f"{work / 'assemblies'}/*"
    assert sorted(os.listdir(work / "assemblies")) == ["a.fasta", "b.fasta"]


def test_a_path_inside_the_data_roots_is_accepted(tmp_path):
    (tmp_path / "data").mkdir()
    ref = files(tmp_path / "data", "genome.fasta")[0]
    assert paths_outside({"fasta": ref}, [tmp_path / "data"]) == []


def test_a_path_outside_the_data_roots_is_refused(tmp_path):
    (tmp_path / "data").mkdir()
    assert paths_outside({"fasta": "/etc/passwd"}, [tmp_path / "data"]) == ["/etc/passwd"]


def test_samplesheet_and_staged_paths_are_checked_too(tmp_path):
    (tmp_path / "data").mkdir()
    rows = [{"sample": "a", "reads_1": "/etc/a.fq"}]
    stage = {"stage": [{"sample": "b", "files": ["/root/b.fq"]}]}
    assert paths_outside({"input": rows, "other": stage}, [tmp_path / "data"]) == [
        "/etc/a.fq", "/root/b.fq"]


def test_a_link_inside_a_root_pointing_outside_is_refused(tmp_path):
    (tmp_path / "data").mkdir()
    os.symlink("/etc/passwd", tmp_path / "data" / "x.fq")
    assert paths_outside({"x": str(tmp_path / "data" / "x.fq")}, [tmp_path / "data"]) != []


def test_words_that_are_not_paths_are_left_alone(tmp_path):
    assert paths_outside({"mode": "fast", "n": ""}, [tmp_path]) == []


def _bundle_with(holes: list[str]) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.nf", "workflow {}\n")
        archive.writestr("nextflow.config", "params {\n"
                         + "".join(f"  {h} = null\n" for h in holes) + "}\n")
    return buffer.getvalue()


def test_submit_refuses_an_input_outside_the_data_roots(client, tmp_path, monkeypatch):
    from wiener_api.settings import settings

    (tmp_path / "data").mkdir()
    monkeypatch.setattr(settings, "data_roots", [tmp_path / "data"])
    stored = client.post("/api/artifacts", files={"bundle": ("run.zip", _bundle_with(["fasta"]))})
    artifact_id = stored.json()["artifact_id"]
    assert stored.json()["declared"] == ["fasta"], stored.text
    refused = client.post("/api/runs", json={"artifact_id": artifact_id,
                                             "params": {"fasta": "/etc/passwd"}})
    assert refused.status_code == 422 and "MW0103" in refused.text
    inside = files(tmp_path / "data", "genome.fasta")[0]
    accepted = client.post("/api/runs", json={"artifact_id": artifact_id,
                                              "params": {"fasta": inside}})
    assert accepted.status_code == 202, accepted.text


def test_submit_takes_staged_samples(client, tmp_path, monkeypatch):
    from wiener_api.settings import settings

    (tmp_path / "data").mkdir()
    monkeypatch.setattr(settings, "data_roots", [tmp_path / "data"])
    stored = client.post("/api/artifacts", files={"bundle": ("run.zip", _bundle_with(["input"]))})
    y1 = files(tmp_path / "data", "Y1_R1.fq", "Y1_R2.fq")
    accepted = client.post("/api/runs", json={
        "artifact_id": stored.json()["artifact_id"],
        "params": {"input": {"stage": [{"sample": "Y1", "files": y1}]}}})
    assert accepted.status_code == 202, accepted.text


def test_a_list_of_paths_is_checked(tmp_path):
    """Checkpoint B, I1: `fastq.reads` reads a List param directly."""
    (tmp_path / "data").mkdir()
    assert paths_outside({"reads": ["/etc/passwd"]}, [tmp_path / "data"]) == ["/etc/passwd"]


def test_a_relative_path_is_refused(tmp_path):
    (tmp_path / "data").mkdir()
    bad = "../../../../etc/passwd"
    assert paths_outside({"x": bad, "y": [{"sample": "a", "r": bad}]}, [tmp_path / "data"]) == [
        bad, bad]


def test_a_url_is_refused_and_a_file_url_is_checked(tmp_path):
    (tmp_path / "data").mkdir()
    inside = files(tmp_path / "data", "a.fq")[0]
    got = paths_outside({"x": "file:///etc/passwd", "y": "s3://bucket/a.fq",
                         "z": f"file://{inside}"}, [tmp_path / "data"])
    assert got == ["file:///etc/passwd", "s3://bucket/a.fq"]


def test_a_relative_staged_file_is_refused(tmp_path):
    (tmp_path / "data").mkdir()
    stage = {"stage": [{"sample": "a", "files": ["data/a.fq"]}]}
    assert paths_outside({"input": stage}, [tmp_path / "data"]) == ["data/a.fq"]


def test_the_csv_header_is_every_rows_columns_in_first_seen_order(tmp_path):
    """Checkpoint B, I9: a short first row drops no column for the rest."""
    written = _materialise_tables({"input": [{"sample": "a", "reads_1": "/d/a.fq"},
                                             {"sample": "b", "reads_1": "/d/b1.fq",
                                              "reads_2": "/d/b2.fq"}]}, tmp_path)
    lines = (tmp_path / "input.csv").read_text().splitlines()
    assert written["input"] == str(tmp_path / "input.csv")
    assert lines == ["sample,reads_1,reads_2", "a,/d/a.fq,", "b,/d/b1.fq,/d/b2.fq"]
