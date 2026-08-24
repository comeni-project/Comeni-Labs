"""The CI/CD mapping. Every name here comes from the research note, not from this file."""

import json
from pathlib import Path

import pytest
from comeni_core import yaml_strict
from comeni_core.artifact.pipeline import Pipeline
from wiener_core.events import RunEvent, admit
from wiener_core.spans import SpanKind, pipeline_name, spans
from wiener_core.state import RunPhase, replay

ROOT = Path(__file__).parents[3]
SPINE = ROOT / "tests/fixtures/pipeline/rnaseq-spine.yml"
SPINE_RUN = ROOT / "tests/fixtures/weblog/spine-run.events.jsonl"
RESOURCED = ROOT / "tests/fixtures/weblog/resourced-run.jsonl"
PLAIN = ROOT / "tests/fixtures/weblog/failing-run.jsonl"


@pytest.fixture
def pipeline() -> Pipeline:
    return Pipeline.model_validate(yaml_strict.load(SPINE))


def _spine_state():
    return replay([RunEvent.model_validate(json.loads(line))
                   for line in SPINE_RUN.read_text().splitlines() if line.strip()])


def _state_of(path):
    bodies = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return replay([admit(b, run_id="r1", seq=i) for i, b in enumerate(bodies)])


def test_a_run_is_one_server_span_with_a_child_per_attempt(pipeline):
    made = spans(_spine_state(), pipeline)
    root = made[0]
    assert root.kind is SpanKind.SERVER
    assert root.attributes["cicd.pipeline.action.name"] == "RUN"
    assert all(span.parent == root.span_id for span in made[1:])
    assert all(span.kind is SpanKind.INTERNAL for span in made[1:])
    assert len(made) == 1 + 5, "five processes, one attempt each"


def test_the_enum_mapping_is_the_note_s_table(pipeline):
    """§1.4. A wrong value here is a dashboard that lies, and two of them are arguments rather
    than lookups: `LOST -> timeout` and `CACHED -> skip`."""
    state = _spine_state()
    assert spans(state, pipeline)[0].attributes["cicd.pipeline.result"] == "success"

    lost = state.model_copy(update={"phase": RunPhase.LOST})
    assert spans(lost, pipeline)[0].attributes["cicd.pipeline.result"] == "timeout"

    failed = _state_of(PLAIN)
    root = spans(failed, pipeline)[0]
    assert root.attributes["cicd.pipeline.result"] == "failure"
    assert root.attributes["error.type"], "Conditionally Required when the result is a failure"


def test_a_failed_task_carries_its_exit_code_under_the_standard_name(pipeline):
    """`process.exit.code` exists and is exactly `trace.exit` — reuse beats inventing
    `wiener.task.exit`."""
    failed = next(
        span for span in spans(_state_of(PLAIN), pipeline)
        if span.attributes.get("cicd.pipeline.task.run.result") == "failure"
    )
    assert failed.attributes["process.exit.code"] == 2
    assert failed.attributes["error.type"] == "exit_2"


def test_no_lab_string_becomes_an_attribute(pipeline):
    """§8, and it covers the exporter and §10.2's redactor with one test. `script`, `workdir`,
    `name` and `tag` are exactly the fields a backend would happily index and retain."""
    for state in (_spine_state(), _state_of(PLAIN), _state_of(RESOURCED)):
        for span in spans(state, pipeline, run_url="/runs/x"):
            rendered = " ".join(str(value) for value in span.attributes.values())
            assert "/tmp" not in rendered and "test -f" not in rendered
            assert ".fastq" not in rendered and "work/" not in rendered


def test_the_timestamps_are_the_events_own_and_in_nanoseconds(pipeline):
    """Research §3: a span may be backdated, so the mapping is pure and a three-day run maps in
    milliseconds. If these came from a clock, replay would produce different telemetry."""
    state = _spine_state()
    once, twice = spans(state, pipeline), spans(state, pipeline)
    assert once == twice

    root = once[0]
    assert root.start_ns == state.started_at_ms * 1_000_000
    assert root.start_ns > 1_700_000_000_000_000_000, "nanoseconds, not milliseconds"


def test_the_ids_are_derived_so_replay_is_identical(pipeline):
    """A random span id makes a golden file impossible and replay non-identical."""
    assert spans(_spine_state(), pipeline)[0].span_id == spans(_spine_state(), pipeline)[0].span_id


def test_the_six_without_a_convention_are_present_when_the_trace_had_them(pipeline):
    """§2 of the note: no peak-memory convention exists anywhere, and none pairs a request with
    a use. These are the facts that keep custom names."""
    task = spans(_state_of(RESOURCED), pipeline)[1]
    for name in ("wiener.task.attempt", "wiener.task.cpus_asked", "wiener.task.cpu_used_pct",
                 "wiener.task.memory_peak_bytes", "wiener.task.read_bytes",
                 "wiener.task.write_bytes", "wiener.task.queue_wait_ms"):
        assert name in task.attributes, f"{name} is missing"


def test_a_trace_less_run_omits_them_rather_than_sending_zeros(pipeline):
    """`failing-run.jsonl` was captured without `trace.enabled` — §4.3 finding 6. A zero would
    read as "this task used no memory", which is a lie about a real number, and a dashboard
    cannot tell a real zero from a missing one."""
    task = spans(_state_of(PLAIN), pipeline)[1]
    assert "wiener.task.memory_peak_bytes" not in task.attributes
    assert "wiener.task.cpu_used_pct" not in task.attributes
    assert task.attributes["wiener.task.attempt"] == 1, "the attempt index is never optional"


def test_the_pipeline_name_is_stable_across_a_rebuild(pipeline):
    """A190. Every board groups by `cicd.pipeline.name`, so it is derived from the goal rather
    than from the artifact digest — a digest starts a new series on every change, which makes
    "is the spine getting slower" unanswerable across exactly the change you want to measure."""
    assert pipeline_name(pipeline) == "counts.matrix"
    assert pipeline_name(None) == "unknown"


def test_a_run_that_never_started_has_no_spans(pipeline):
    """A span needs a start, and a queued run has not got one."""
    assert spans(replay([]), pipeline) == []


def test_the_fold_is_where_the_lab_strings_stop():
    """**Stronger than the test above, and found by trying to break it.**

    Sabotaging `spans()` to emit `process.command_line` — a real convention field — failed with
    `TaskState has no attribute 'script'`: the marked fields live on `TaskTrace`, and `fold`
    keeps `process` rather than `name`, so **nothing a span can reach is a lab string**. §8's
    rule is enforced by construction here rather than by vigilance.

    This test is what keeps that true. Adding `script` to `TaskState` — which somebody will want
    for the console one day — reopens the path, and this fails rather than the leak shipping.
    """
    from typing import get_args, get_type_hints

    from wiener_core.events import LabString
    from wiener_core.state import Attempt, RunState, TaskState

    def marked(hint) -> bool:
        if any(isinstance(m, LabString) for m in getattr(hint, "__metadata__", ())):
            return True
        return any(marked(arg) for arg in get_args(hint))

    for model in (RunState, TaskState, Attempt):
        leaks = [n for n, h in get_type_hints(model, include_extras=True).items() if marked(h)]
        assert not leaks, (
            f"{model.__name__} carries {leaks}, which a span can reach — §8 says nothing marked "
            "LAB_STRING becomes a span attribute, and the fold is what has been keeping that "
            "true by not carrying one at all"
        )
