"""Sending what `wiener_core.spans` described. **The impure half of §8.**

`wiener-core` says which spans a run is; this meets the wire format. That split is not tidiness:
the OpenTelemetry SDK is a network client, and `tests/test_purity.py` refuses it in the pure
package — which was watched failing on 2026-08-24, so §3.1's *"structurally impossible to put the
exporter on the wrong side"* is a demonstrated claim rather than a hopeful one.

**Off unless pointed somewhere.** `settings.otlp_endpoint` empty constructs no exporter at all.
"""

import logging

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from wiener_core.spans import Span, SpanKind, pipeline_name, spans
from wiener_core.state import RunPhase, RunState

from wiener_api.settings import settings

log = logging.getLogger(__name__)

class _DerivedIds(IdGenerator):
    """Ids the SDK would otherwise invent.

    **A run is one trace, and without this it was two.** The SDK generates a random trace id for
    a span with no parent context, so the run span landed in a trace of its own while the five
    task spans shared the derived one — and their `ParentSpanId` pointed at a span that did not
    exist. In a UI that is one lone `RUN` and five orphans, which is the shape of failure that
    looks like it works until somebody opens it.

    Caught by querying ClickHouse at Checkpoint 3, not by a unit test: the test stubbed `_emit`,
    so it asserted what Wiener *intended* rather than what the SDK produced.

    Safe to be stateful because `export()` emits one run's spans in order, in one thread.
    """

    def __init__(self) -> None:
        self.trace_id = 0
        self.span_id = 0

    def generate_trace_id(self) -> int:
        return self.trace_id

    def generate_span_id(self) -> int:
        return self.span_id


_ids = _DerivedIds()
_tracer: trace.Tracer | None = None
_metrics: dict[str, object] = {}

_KIND = {SpanKind.SERVER: trace.SpanKind.SERVER, SpanKind.INTERNAL: trace.SpanKind.INTERNAL}


def _id_of(value: str, width: int) -> int:
    """A stable numeric id from `wiener-core`'s readable one.

    The pure half names a span `<run>.<task>.<attempt>`, which is legible in a golden file and
    is not eight bytes. Meeting the wire format is this side's job — §1.5 of the research note
    makes the same point about `process.command_line`: adopting a convention is not adopting
    every one of its shapes into the place that describes the data.
    """
    import hashlib

    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:width], "big") or 1


def configure() -> bool:
    """Build the exporters, once. Returns whether telemetry is on."""
    global _tracer
    if not settings.otlp_endpoint:
        return False
    if _tracer is not None:
        return True

    resource = Resource.create({"service.name": "wiener"})
    provider = build_provider(resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
        endpoint=settings.otlp_endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    _tracer = provider.get_tracer("wiener")

    meter = MeterProvider(resource=resource, metric_readers=[PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.otlp_endpoint, insecure=True))]).get_meter("wiener")
    _metrics.update({
        # §1.3 of the research note, verbatim. `cicd.worker.count` is deliberately absent:
        # a worker is a node and there is no node until W5 puts something on a cluster.
        "duration": meter.create_histogram(
            "cicd.pipeline.run.duration", unit="s", description="how long a run took"),
        "active": meter.create_up_down_counter(
            "cicd.pipeline.run.active", unit="{run}", description="runs in flight"),
        "errors": meter.create_counter(
            "cicd.pipeline.run.errors", unit="{error}", description="runs that failed"),
    })
    metrics.set_meter_provider(MeterProvider(resource=resource))
    return True


def build_provider(resource: Resource) -> TracerProvider:
    """The provider, built where a test can reach it.

    **Separated because the test that could not see it was vacuous**: it built its own provider
    with `_ids` attached, so removing the generator from the real one changed nothing and the
    test still passed. A guard that constructs its own subject is asserting its own setup.
    """
    return TracerProvider(resource=resource, id_generator=_ids)


def _emit(span: Span) -> None:
    # The run id is the first segment of every span's id — `<run>.<task>.<attempt>` — so one
    # trace id covers the run whether or not the span has a parent.
    _ids.trace_id = _id_of(span.span_id.split(".")[0], 16)
    _ids.span_id = _id_of(span.span_id, 8)

    parent = None
    if span.parent:
        parent = trace.set_span_in_context(NonRecordingSpan(SpanContext(
            trace_id=_id_of(span.parent.split(".")[0], 16),
            span_id=_id_of(span.parent, 8),
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )))

    sent = _tracer.start_span(  # type: ignore[union-attr]
        span.name, context=parent, kind=_KIND[span.kind],
        start_time=span.start_ns, attributes=dict(span.attributes),
    )
    sent.end(end_time=span.end_ns or span.start_ns)


def export(state: RunState, pipeline=None, run_url: str | None = None) -> int:
    """Send a finished run's spans. Returns how many were sent.

    **Only when the run is over.** A span that has not ended cannot be sent, and a run still
    going has at least one — so telemetry lands once, complete, rather than in fragments a
    backend has to stitch.
    """
    if not configure():
        return 0
    if state.phase not in (RunPhase.SUCCEEDED, RunPhase.FAILED, RunPhase.CANCELLED, RunPhase.LOST):
        return 0

    made = spans(state, pipeline, run_url=run_url)
    for span in made:
        _emit(span)

    name = pipeline_name(pipeline)
    if state.started_at_ms and state.ended_at_ms:
        _metrics["duration"].record(  # type: ignore[attr-defined]
            (state.ended_at_ms - state.started_at_ms) / 1000,
            {"cicd.pipeline.name": name, "cicd.pipeline.run.state": "finalizing"},
        )
    if state.phase is not RunPhase.SUCCEEDED:
        _metrics["errors"].add(  # type: ignore[attr-defined]
            1, {"cicd.pipeline.name": name, "error.type": _error_type(state)})
    return len(made)


def _error_type(state: RunState) -> str:
    return "no_events" if state.phase is RunPhase.LOST else "task_failed"


def in_flight(delta: int, pipeline=None) -> None:
    """`cicd.pipeline.run.active` — §2's fleet level, which had no mechanism before."""
    if not configure():
        return
    _metrics["active"].add(  # type: ignore[attr-defined]
        delta, {"cicd.pipeline.name": pipeline_name(pipeline),
                "cicd.pipeline.run.state": "executing"})
