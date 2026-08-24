"""What gets sent, and when. No test here opens a socket."""

import json
from pathlib import Path

import pytest
from comeni_core import yaml_strict
from comeni_core.artifact.pipeline import Pipeline
from wiener_core.events import RunEvent
from wiener_core.state import RunPhase, replay

ROOT = Path(__file__).parents[3]
SPINE = ROOT / "tests/fixtures/pipeline/rnaseq-spine.yml"
SPINE_RUN = ROOT / "tests/fixtures/weblog/spine-run.events.jsonl"


@pytest.fixture
def pipeline() -> Pipeline:
    return Pipeline.model_validate(yaml_strict.load(SPINE))


@pytest.fixture
def finished():
    return replay([RunEvent.model_validate(json.loads(line))
                   for line in SPINE_RUN.read_text().splitlines() if line.strip()])


@pytest.fixture
def sending(monkeypatch):
    """The SDK, stood in for. `configure()` is patched rather than the network, so a test never
    needs a collector — the same reason `jobs.enqueue` is patched rather than Redis."""
    from wiener_api.services import telemetry

    sent: list = []
    monkeypatch.setattr(telemetry, "configure", lambda: True)
    monkeypatch.setattr(telemetry, "_emit", sent.append)
    histogram = type("H", (), {"record": lambda *a: None})()
    monkeypatch.setitem(telemetry._metrics, "duration", histogram)
    monkeypatch.setitem(telemetry._metrics, "errors", type("C", (), {"add": lambda *a: None})())
    return sent


def test_a_finished_run_exports_a_span_per_attempt_plus_the_run(finished, pipeline, sending):
    from wiener_api.services.telemetry import export

    assert export(finished, pipeline) == 6, "one run span and five attempts"
    assert len(sending) == 6


def test_a_run_still_going_exports_nothing(finished, pipeline, sending):
    """**A span that has not ended cannot be sent**, and a run in flight has at least one — so
    telemetry lands once and complete, rather than in fragments a backend has to stitch."""
    from wiener_api.services.telemetry import export

    running = finished.model_copy(update={"phase": RunPhase.RUNNING, "ended_at_ms": None})
    assert export(running, pipeline) == 0
    assert sending == []


def test_nothing_is_constructed_when_no_endpoint_is_set(finished, pipeline, monkeypatch):
    """**Off by default means no exporter exists**, not one that drops quietly — a lens that
    lies about being off is worse than no lens. `CLAUDE.md`'s standing rule for telemetry."""
    from wiener_api.services import telemetry
    from wiener_api.settings import settings

    monkeypatch.setattr(settings, "otlp_endpoint", "")
    monkeypatch.setattr(telemetry, "_tracer", None)
    assert telemetry.configure() is False
    assert telemetry.export(finished, pipeline) == 0


def test_the_ids_are_stable_and_fit_the_wire(finished, pipeline):
    """`wiener-core` names a span `<run>.<task>.<attempt>` because a golden file has to read;
    OpenTelemetry wants eight bytes. Meeting the wire format is this side's job."""
    from wiener_api.services.telemetry import _id_of

    assert _id_of("a.b.c", 8) == _id_of("a.b.c", 8)
    assert 0 < _id_of("a.b.c", 8) < 2**64
    assert 0 < _id_of("a", 16) < 2**128


def test_every_attempt_of_a_run_shares_its_trace(finished, pipeline, sending):
    """A run is one trace — §8. If the children hashed a different root they would scatter into
    five unrelated traces, which is the failure that looks like it works."""
    from wiener_api.services.telemetry import _id_of, export

    export(finished, pipeline)
    root, *children = sending
    assert all(child.parent == root.span_id for child in children)
    assert len({_id_of(child.parent.split(".")[0], 16) for child in children}) == 1
