"""The build plan: every step in the blueprint's order, its card and its need, and the wrap-up."""

import os
from pathlib import Path

import pytest
from mendel_authoring.blueprint import Blueprint
from mendel_authoring.needs import NeedKind
from mendel_authoring.pacing import Pacing, waits
from mendel_authoring.plan import plan_of

GOLDEN = Path(__file__).parent / "golden"


def _golden(name: str, plan) -> None:
    """Compare against the stored plan. `COMENI_WRITE_GOLDEN=1` writes it — then read the diff."""
    path = GOLDEN / name
    rendered = plan.model_dump_json(indent=2) + "\n"
    if os.environ.get("COMENI_WRITE_GOLDEN") == "1":
        path.parent.mkdir(exist_ok=True)
        path.write_text(rendered)
    assert path.exists(), f"{name} missing: run once with COMENI_WRITE_GOLDEN=1 and review it"
    assert rendered == path.read_text()


def test_the_plan_follows_the_blueprints_order(rnaseq, declared):
    plan = plan_of(rnaseq(150), declared)
    assert [s.node for s in plan.steps] == ["fastqc", "star_align", "featurecounts", "multiqc"]


def test_without_a_read_length_only_the_aligner_needs_the_person(rnaseq, declared):
    plan = plan_of(rnaseq(None), declared)
    assert [(s.node, s.need.kind) for s in plan.needing()] == [("star_align", NeedKind.FACT)]


def test_with_a_read_length_nothing_needs_the_person(rnaseq, declared):
    assert plan_of(rnaseq(150), declared).needing() == []


def test_golden_without_a_read_length(rnaseq, declared):
    _golden("plan-without-read-length.json", plan_of(rnaseq(None), declared))


def test_golden_with_a_read_length(rnaseq, declared):
    _golden("plan-with-read-length.json", plan_of(rnaseq(150), declared))


def test_the_same_blueprint_gives_the_same_plan(rnaseq, declared):
    blueprint = rnaseq(None, strandedness_open=True)
    first = plan_of(blueprint, declared).model_dump_json()
    assert first == plan_of(blueprint, declared).model_dump_json()


def test_an_empty_blueprint_is_an_empty_plan(rnaseq, declared):
    """Review Focus 5."""
    full = rnaseq(150)
    empty = Blueprint(
        registry=full.registry,
        order=[],
        pipeline=full.pipeline.model_copy(update={"steps": [], "decisions": []}),
    )
    plan = plan_of(empty, declared)
    assert plan.steps == [] and plan.needing() == []
    assert plan.wrap_up.gets  # the goal still says what it wants


def test_together_waits_at_every_step(rnaseq, declared):
    plan = plan_of(rnaseq(None), declared)
    assert waits(plan, Pacing.TOGETHER) == ["fastqc", "star_align", "featurecounts", "multiqc"]


def test_stop_where_needed_waits_only_where_the_person_is_needed(rnaseq, declared):
    plan = plan_of(rnaseq(None, strandedness_open=True), declared)
    assert waits(plan, Pacing.STOP_WHERE_NEEDED) == ["star_align", "featurecounts"]


def test_ask_is_a_question_not_a_pacing():
    """Review Focus 4: the setting's third option is resolved by the shell before `waits`."""
    with pytest.raises(ValueError):
        Pacing("ask")
