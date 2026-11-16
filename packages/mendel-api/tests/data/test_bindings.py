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


def _sheet_with_paired_varying():
    """The RNA-seq pipeline as a samplesheet where `paired` varies: its fact is the second file
    cell, read from the row (`from_row`)."""
    from comeni_core.artifact.pipeline import RowFact, SheetFact

    paired = SheetFact.model_construct(
        measurement="paired", column="reads_2", kind="boolean", values=[], required=False,
        from_row=RowFact.SECOND_FILE_PRESENT, auto=False, describes="fastq.reads", meta=[])
    return RNASEQ.model_copy(update={"input_form": InputForm.SAMPLESHEET, "sheet_facts": [paired]})


def test_a_fact_the_row_states_does_not_overwrite_the_file_cell(tmp_path):
    """Checkpoint B, C1: `paired` is read from whether the second file is there."""
    pe = files(tmp_path, "P_R1.fq", "P_R2.fq")
    se = files(tmp_path, "S.fq")
    gtf, fasta = files(tmp_path, "genes.gtf", "genome.fasta")
    got = bind(_sheet_with_paired_varying(), [sample("P", pe, paired=True),
                                              sample("S", se, paired=False)],
               [reference(gtf, "annotation.gtf"), reference(fasta, "genome.fasta")])
    assert got.missing == []
    assert got.params["input"] == [{"sample": "P", "reads_1": pe[0], "reads_2": pe[1]},
                                   {"sample": "S", "reads_1": se[0], "reads_2": ""}]


def test_every_row_has_every_column_so_a_short_first_row_drops_nothing(tmp_path):
    """Checkpoint B, I9: the CSV's columns are the first row's keys."""
    se = files(tmp_path, "A.fq")
    pe = files(tmp_path, "B_R1.fq", "B_R2.fq")
    gtf, fasta = files(tmp_path, "genes.gtf", "genome.fasta")
    got = bind(_sheet_with_paired_varying(), [sample("A", se, paired=False),
                                              sample("B", pe, paired=True)],
               [reference(gtf, "annotation.gtf"), reference(fasta, "genome.fasta")])
    assert [list(row) for row in got.params["input"]] == [["sample", "reads_1", "reads_2"]] * 2


def test_a_direct_pairs_channel_refuses_single_end_samples(tmp_path):
    """Checkpoint B, I2: `fromFilePairs` drops a lone file; say so rather than lose a sample."""
    pe = files(tmp_path, "P_R1.fq", "P_R2.fq")
    se = files(tmp_path, "S.fq")
    gtf, fasta = files(tmp_path, "genes.gtf", "genome.fasta")
    got = bind(RNASEQ, [sample("P", pe), sample("S", se)],
               [reference(gtf, "annotation.gtf"), reference(fasta, "genome.fasta")])
    [refused] = got.missing
    assert refused.channel == "reads" and "S" in refused.why and got.params == {}


def test_a_fact_nothing_measured_comes_from_the_persons_column(tmp_path):
    """Checkpoint B, I8: strandedness differs and only the person knows it."""
    from comeni_core.artifact.pipeline import SheetFact

    strand = SheetFact.model_construct(
        measurement="strandedness", column="strandedness", kind="choice",
        values=["forward", "reverse", "unstranded"], required=True, from_row=None, auto=False,
        describes="fastq.reads", meta=[])
    sheet = RNASEQ.model_copy(update={"input_form": InputForm.SAMPLESHEET,
                                      "sheet_facts": [strand]})
    a, b = files(tmp_path, "A_R1.fq", "A_R2.fq"), files(tmp_path, "B_R1.fq", "B_R2.fq")
    gtf, fasta = files(tmp_path, "genes.gtf", "genome.fasta")
    refs = [reference(gtf, "annotation.gtf"), reference(fasta, "genome.fasta")]
    unanswered = bind(sheet, [sample("A", a), sample("B", b)], refs)
    assert {m.channel for m in unanswered.missing} == {"strandedness"}
    got = bind(sheet, [sample("A", a), sample("B", b)], refs,
               {"strandedness": {"A": "reverse", "B": "forward"}})
    assert got.missing == []
    assert [r["strandedness"] for r in got.params["input"]] == ["reverse", "forward"]
