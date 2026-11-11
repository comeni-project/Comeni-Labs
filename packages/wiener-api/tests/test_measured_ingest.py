"""What a completed run measured enters its record, closed, and the run says how it compares
with what its pipeline was built on (#465, Review Focus 5)."""

import json
import pathlib
import shutil

from wiener_api.services import launcher, projection
from wiener_api.settings import settings
from wiener_core.events import EventKind

HERE = pathlib.Path(__file__).parent
PIPELINE = HERE / "fixtures/measuring_pipeline.yml"


def _artifact(tmp_path, run) -> None:
    settings.artifact_root = tmp_path / "artifacts"
    folder = settings.artifact_root / run.artifact_id
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(PIPELINE, folder / "pipeline.yml")


def _report(run_id: str, sample: str, value, process="measure_fastq", name=None, extra=None):
    folder = launcher.results_dir(run_id) / process
    folder.mkdir(parents=True, exist_ok=True)
    facts = {"read_length": {"by": ["fastq@1.1.0", "read_length@1.0.0"], "coverage": "all",
                             "evidence": {"rows": 1000}, "value": value}, **(extra or {})}
    (folder / (name or f"{sample}.measured.json")).write_text(json.dumps({"facts": facts}))


def _complete(session, run_id: str) -> None:
    projection.record(session, settings.lab_id, run_id, {
        "event": "completed", "utcTime": "2026-11-10T10:00:00Z", "runId": run_id,
        "metadata": {"workflow": {"success": True}}})


def test_an_estimate_the_run_bears_out_and_one_it_does_not(client, a_run, session, tmp_path):
    _artifact(tmp_path, a_run)
    _report(a_run.id, "s1", 150)
    _report(a_run.id, "s2", 100)
    _complete(session, a_run.id)
    session.commit()
    body = client.get(f"/api/runs/{a_run.id}/measured").json()
    views = {f["sample"]: f for f in body["facts"]}
    assert views["s1"]["status"] == "confirmed"
    assert views["s2"]["status"] == "disagrees"
    assert views["s2"]["used_by"] == ["selection:star_align"] and views["s2"]["estimate"] == 150


def test_only_what_the_pipeline_declares_is_read(client, a_run, session, tmp_path):
    _artifact(tmp_path, a_run)
    _report(a_run.id, "s1", 150, extra={"strandedness": {"value": "forward"}})
    _report(a_run.id, "s1", 150, process="someone_else")
    big = launcher.results_dir(a_run.id) / "measure_fastq" / "huge.measured.json"
    big.write_text(json.dumps({"facts": {"read_length": {"value": 1}}, "pad": "x" * 100_000}))
    _report(a_run.id, "bad", "not json", name="broken.measured.json")
    (launcher.results_dir(a_run.id) / "measure_fastq" / "broken.measured.json").write_text("{")
    _complete(session, a_run.id)
    session.commit()
    facts = client.get(f"/api/runs/{a_run.id}/measured").json()["facts"]
    assert [(f["measurement"], f["sample"]) for f in facts] == [("read_length", "s1")]


def test_a_redelivered_completion_reads_nothing_twice(client, a_run, session, tmp_path):
    _artifact(tmp_path, a_run)
    _report(a_run.id, "s1", 150)
    _complete(session, a_run.id)
    _complete(session, a_run.id)
    session.commit()
    from wiener_api import repository

    kinds = [row.kind for row in repository.events(session, settings.lab_id, a_run.id)]
    assert kinds.count(EventKind.MEASURED) == 1


def test_a_run_that_measured_nothing_says_so(client, a_run):
    assert client.get(f"/api/runs/{a_run.id}/measured").json() == {"facts": [], "decided": []}


def test_a_malformed_report_never_loses_the_completed_event(client, a_run, session, tmp_path):
    """A file a step wrote cannot speak for the run, nor stop it being recorded (Task 9
    review)."""
    _artifact(tmp_path, a_run)
    folder = launcher.results_dir(a_run.id) / "measure_fastq"
    folder.mkdir(parents=True)
    (folder / "list.measured.json").write_text(json.dumps({"facts": [1]}))
    (folder / "deep.measured.json").write_text("[" * 100_000 + "]" * 100_000)
    (folder / "string.measured.json").write_text(json.dumps({"facts": "x"}))
    _report(a_run.id, "s1", 150)
    _complete(session, a_run.id)
    session.commit()
    from wiener_api import repository

    kinds = [row.kind for row in repository.events(session, settings.lab_id, a_run.id)]
    assert EventKind.COMPLETED in kinds
    facts = client.get(f"/api/runs/{a_run.id}/measured").json()["facts"]
    assert [f["sample"] for f in facts] == ["s1"]


def test_the_values_run_time_settings_took_are_read(client, a_run, session, tmp_path):
    import yaml

    _artifact(tmp_path, a_run)
    path = settings.artifact_root / a_run.artifact_id / "pipeline.yml"
    data = yaml.safe_load(path.read_text())
    step = next(s for s in data["steps"] if s["id"] == "star_genomegenerate")
    step["settings"] = [{
        "name": "sa_index_nbases", "value": None, "via": "ext", "key": "args",
        "template": "--genomeSAindexNbases {value}",
        "why": {"tier": 3, "source": "resolver", "reason": "decided at run time"},
        "at_run": {"facts": [{"measurement": "genome_length", "meta_key": "genome_length",
                              "source": "measured",
                              "measured_by": "comeni/measure/genome_length_fai@1.0.0"}],
                   "rule": "param:index_building:sa_index_nbases",
                   "rows": [{"takes": "genome_length"}], "fallback": None,
                   "fallback_reason": "asked"}}]
    path.write_text(yaml.safe_dump(data))
    decided = launcher.results_dir(a_run.id) / "decided"
    decided.mkdir(parents=True)
    (decided / "star_genomegenerate.sa_index_nbases.tsv").write_text("g\t6\nbad line\n")
    (decided / "../escape.tsv").write_text("x\t1\n")
    _complete(session, a_run.id)
    session.commit()
    body = client.get(f"/api/runs/{a_run.id}/measured").json()
    assert body["decided"] == [{"step": "star_genomegenerate", "setting": "sa_index_nbases",
                                "sample": "g", "value": "6"}]


def test_a_symlinked_results_folder_is_not_followed(client, a_run, session, tmp_path):
    _artifact(tmp_path, a_run)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "s9.measured.json").write_text(json.dumps(
        {"facts": {"read_length": {"value": 1}}}))
    results = launcher.results_dir(a_run.id)
    results.mkdir(parents=True)
    (results / "measure_fastq").symlink_to(elsewhere, target_is_directory=True)
    _complete(session, a_run.id)
    session.commit()
    assert client.get(f"/api/runs/{a_run.id}/measured").json()["facts"] == []
