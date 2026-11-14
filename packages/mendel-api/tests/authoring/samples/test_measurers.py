"""Who measures what, and where each measurer runs: the server, the pipeline, or both (#465)."""

from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services import measurers, registry


def test_read_length_runs_on_the_server_and_in_the_pipeline():
    found = [m for m in measurers.index(registry.stack()) if m.measurement == "read_length"]
    assert len(found) == 1
    (measurer,) = found
    assert measurer.by == "fastq@1.1.0 + read_length@1.0.0" and measurer.trusted
    assert measurer.runs == ["server", "pipeline"]
    assert "kind" not in measurer.model_dump()


def _overlay(tmp_path, name: str, body: str):
    folder = tmp_path / "measurers" / "measures" / name
    (folder / "piece").mkdir(parents=True)
    (folder / "piece" / f"{name}.py").write_text("x = 1\n")
    (folder / "measurer.yml").write_text(body)
    from mendel_resolver import layers

    return layers.load([registry.stack().paths[0], tmp_path])


def test_a_pipeline_only_code_measurer_is_not_offered_for_an_upload(tmp_path):
    """Listed with where it runs, and never among what this server may run (Task 2 review)."""
    stack = _overlay(tmp_path, "read_length", (
        "declares: measurer\nid: read_length\nversion: 2.0.0\nmeasures: read_length\n"
        "by: code\nrecord: sequence\nentry: piece/read_length.py\nruns: [pipeline]\n"))
    (measurer,) = [m for m in measurers.index(stack) if m.measurement == "read_length"]
    assert measurer.runs == ["pipeline"]
    assert "read_length" not in measurers.usable_pieces(stack).measurers


def test_a_tool_measurer_is_listed_with_its_tool(tmp_path):
    stack = _overlay(tmp_path, "genome_length_star", (
        "declares: measurer\nid: genome_length_star\nversion: 1.0.0\nmeasures: genome_length\n"
        "by: tool\nuses: nf-core/star/genomegenerate@2.7.11b\noutput: index\n"
        "entry: piece/genome_length_star.py\nruns: [pipeline]\n"))
    # Beside the shipped samtools faidx measurer of the same fact.
    (measurer,) = [m for m in measurers.index(stack) if m.by.startswith("genome_length_star@")]
    assert measurer.by == "genome_length_star@1.0.0 (nf-core/star/genomegenerate@2.7.11b)"
    assert measurer.runs == ["pipeline"]


def test_a_piece_from_an_untrusted_layer_is_listed_and_not_usable(monkeypatch):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "trusted_layers", [])
    stack = registry.stack()
    listed = measurers.index(stack)
    assert listed and all(not m.trusted for m in listed)
    usable = measurers.usable_pieces(stack)
    assert usable.formats == {} and usable.codecs == {} and usable.measurers == {}


def test_the_index_is_in_a_stable_order():
    found = measurers.index(registry.stack())
    assert found == sorted(found, key=lambda m: (m.measurement, m.by))


def test_the_vocabulary_serves_the_index():
    body = TestClient(create_app()).get("/api/pipeline/authoring/vocabulary").json()
    assert any(m["measurement"] == "paired" and "server" in m["runs"] for m in body["measurers"])
