"""A run's inputs come from the analysis's data (#508, #511): each channel the kept pipeline
declares is answered from the samples and references by type, and anything not answered says
why, so no path is typed."""

from pathlib import Path

from comeni_core import yaml_strict
from comeni_core.artifact.pipeline import InputForm, Pipeline
from mendel_api.services.data.bindings import bind
from mendel_api_tests.building import clean as clean  # noqa: F401
from mendel_api_tests.data import draft, pairs, tick
from support.paths import ROOT

RNASEQ = Pipeline.model_validate(
    yaml_strict.load(ROOT / "tests/fixtures/pipeline-v9/pipeline.yml"))


def files(tmp_path, *names):
    out = []
    for name in names:
        path = tmp_path / name
        path.write_text("x")
        out.append(str(path))
    return out


def sample(name, paths, type_id="fastq.reads", left_out=False, **facts):
    return {"name": name, "files": paths, "outcome": "measured", "type_id": type_id,
            "left_out": left_out,
            "facts": [{"measurement": k, "value": v} for k, v in facts.items()]}


def reference(path, type_id):
    return {"path": path, "name": Path(path).name, "type_id": type_id, "origin": "you"}


def test_a_direct_pipeline_stages_its_kept_samples_and_names_its_references(tmp_path):
    y1 = files(tmp_path, "Y1_R1.fq.gz", "Y1_R2.fq.gz")
    y2 = files(tmp_path, "Y2_R1.fq.gz", "Y2_R2.fq.gz")
    gtf, fasta = files(tmp_path, "genes.gtf", "genome.fasta")
    got = bind(RNASEQ, [sample("Y1", y1), sample("Y2", y2)],
               [reference(gtf, "annotation.gtf"), reference(fasta, "genome.fasta")])
    assert got.missing == []
    assert got.params == {"input": {"stage": [{"sample": "Y1", "files": y1},
                                              {"sample": "Y2", "files": y2}]},
                          "gtf": gtf, "fasta": fasta}
    assert got.summary == "2 samples, 2 references"


def test_left_out_sample_is_not_bound(tmp_path):
    y1 = files(tmp_path, "Y1_R1.fq", "Y1_R2.fq")
    y3 = files(tmp_path, "Y3_R1.fq", "Y3_R2.fq")
    gtf, fasta = files(tmp_path, "genes.gtf", "genome.fasta")
    got = bind(RNASEQ, [sample("Y1", y1), sample("Y3", y3, left_out=True)],
               [reference(gtf, "annotation.gtf"), reference(fasta, "genome.fasta")])
    assert [s["sample"] for s in got.params["input"]["stage"]] == ["Y1"]


def test_unanswered_channel_is_missing_with_its_type(tmp_path):
    got = bind(RNASEQ, [sample("Y1", files(tmp_path, "a_R1.fq", "a_R2.fq"))], [])
    assert {(m.channel, m.type_id) for m in got.missing} == {
        ("gtf", "annotation.gtf"), ("fasta", "genome.fasta")}
    assert all(m.why for m in got.missing) and "gtf" not in got.params


def test_deleted_file_after_scan_is_missing_not_sent(tmp_path):
    y1 = files(tmp_path, "Y1_R1.fq", "Y1_R2.fq")
    Path(y1[1]).unlink()
    got = bind(RNASEQ, [sample("Y1", y1)], [])
    [gone] = [m for m in got.missing if m.channel == "reads"]
    assert "Y1_R2.fq" in gone.why and "input" not in got.params


def test_samplesheet_rows_come_from_kept_samples_in_artifact_column_order(tmp_path):
    sheet = RNASEQ.model_copy(update={"input_form": InputForm.SAMPLESHEET})
    y1 = files(tmp_path, "Y1_R1.fq", "Y1_R2.fq")
    gtf, fasta = files(tmp_path, "genes.gtf", "genome.fasta")
    got = bind(sheet, [sample("Y1", y1)],
               [reference(gtf, "annotation.gtf"), reference(fasta, "genome.fasta")])
    assert got.params["input"] == [{"sample": "Y1", "reads_1": y1[0], "reads_2": y1[1]}]


def test_no_kept_pipeline_says_keep_it_first():
    got = bind(None, [], [])
    assert got.params == {} and got.missing[0].why.startswith("keep the pipeline")


def test_the_route_binds_the_kept_pipeline_to_the_scanned_data(clean, client, root, monkeypatch):
    from mendel_api.services import drafts as draft_service
    from mendel_api.services.data import scan as scanning

    d = draft(client)
    tick(client, d, pairs(root / "reads", "Y1"))
    scanning.scan(d, who="ana")
    monkeypatch.setattr(draft_service, "artifact_path",
                        lambda _: ROOT / "tests/fixtures/pipeline-v9/pipeline.yml")
    got = client.get(f"/api/data/{d}/bindings").json()
    assert {m["channel"] for m in got["missing"]} == {"gtf", "fasta"}
    assert got["params"] == {} and got["summary"] == "1 sample"


def test_bindings_are_never_written_to_the_draft(clean, client, root, monkeypatch):
    import json

    from mendel_api.db import session_scope
    from mendel_api.models import PipelineDraft
    from mendel_api.services import drafts as draft_service

    d = draft(client)
    monkeypatch.setattr(draft_service, "artifact_path",
                        lambda _: ROOT / "tests/fixtures/pipeline-v9/pipeline.yml")
    client.get(f"/api/data/{d}/bindings")
    with session_scope() as db:
        row = db.get(PipelineDraft, d)
        assert "stage" not in json.dumps(row.graph or {})
