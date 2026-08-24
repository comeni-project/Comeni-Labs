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


def test_a_run_is_one_trace_through_the_real_sdk(finished, pipeline, monkeypatch):
    """**The test that would have caught it, and did not exist.**

    Every test above stubs `_emit`, so they assert what Wiener *intends* rather than what the
    SDK produces — and the SDK invents a random trace id for a span with no parent context. The
    run span landed in a trace of its own while the five task spans shared the derived one, and
    their parent pointed at a span that did not exist: one lone `RUN` and five orphans.

    Found by querying ClickHouse at Checkpoint 3. This runs the real TracerProvider into an
    in-memory exporter, which is the same path minus the socket.
    """
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from wiener_api.services import telemetry

    collected = InMemorySpanExporter()
    # **`build_provider`, not a provider of its own** — the first version of this test built one
    # with `_ids` attached, so it passed whether or not the real one wired the generator.
    provider = telemetry.build_provider(Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(collected))
    monkeypatch.setattr(telemetry, "_tracer", provider.get_tracer("test"))
    monkeypatch.setattr(telemetry, "configure", lambda: True)
    histogram = type("H", (), {"record": lambda *a: None})()
    monkeypatch.setitem(telemetry._metrics, "duration", histogram)
    monkeypatch.setitem(telemetry._metrics, "errors", type("C", (), {"add": lambda *a: None})())

    telemetry.export(finished, pipeline)
    sent = collected.get_finished_spans()

    assert len({span.context.trace_id for span in sent}) == 1, "a run must be ONE trace"
    root = next(span for span in sent if span.parent is None)
    assert len([s for s in sent if s.parent is None]) == 1, "exactly one root"
    for child in (s for s in sent if s.parent is not None):
        assert child.parent.span_id == root.context.span_id, (
            "a task span's parent must be the run span that exists, not an id nothing emitted"
        )
