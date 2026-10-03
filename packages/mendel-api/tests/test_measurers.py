"""Who measures what: inspector pieces on this server, profilers in the lab's pipeline."""

from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services import measurers, registry


def test_read_length_is_measured_by_an_inspector_and_a_profiler():
    found = [m for m in measurers.index(registry.stack()) if m.measurement == "read_length"]
    kinds = {(m.kind, m.runs) for m in found}
    assert ("inspector", "server") in kinds and ("profiler", "lab") in kinds
    inspector = next(m for m in found if m.kind == "inspector")
    assert inspector.by == "fastq@1.1.0 + read_length@1.0.0" and inspector.trusted


def test_a_piece_from_an_untrusted_layer_is_listed_and_not_usable(monkeypatch):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "trusted_layers", [])
    stack = registry.stack()
    inspectors = [m for m in measurers.index(stack) if m.kind == "inspector"]
    assert inspectors and all(not m.trusted for m in inspectors)
    usable = measurers.usable_pieces(stack)
    assert usable.formats == {} and usable.codecs == {} and usable.measures == {}


def test_the_index_is_in_a_stable_order():
    found = measurers.index(registry.stack())
    assert found == sorted(found, key=lambda m: (m.measurement, m.kind, m.by))


def test_the_vocabulary_serves_the_index():
    body = TestClient(create_app()).get("/api/pipeline/authoring/vocabulary").json()
    assert any(m["measurement"] == "paired" and m["kind"] == "inspector" for m in body["measurers"])
