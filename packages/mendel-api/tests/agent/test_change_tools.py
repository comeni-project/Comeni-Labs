"""The builder agent's change, build, compile and ask tools (#463)."""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.agent.tools import ToolContext, call
from mendel_api.services import changes, decisions, drafts
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from mendel_authoring.payloads import DecisionChange
from mendel_resolver.goal import Goal
from support.example import example_mapping

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

HISAT2 = "nf-core/hisat2/align@2.2.2"


def _rnaseq() -> ToolContext:
    draft = drafts.create(DraftGraph(), "rnaseq", "ana")
    decisions.import_goal(draft, Goal.model_validate(example_mapping()), who="ana")
    return ToolContext(draft_id=draft, session_id=None, who="builder-agent",
                       expected_revision=decisions.revision(draft))


def test_a_tool_choice_is_written_as_the_ais(clean):
    ctx = _rnaseq()
    chose = call(ctx, "choose_tool", {"type_id": "alignment.bam", "contract": HISAT2,
                                      "because": "the lab's machines have little memory"})
    assert chose.ok, chose.refusal
    [pin] = decisions.read(ctx.draft_id).producers
    assert (pin.contract, pin.by) == (HISAT2, "model")
    resolved = call(ctx, "resolve", {})
    assert resolved.ok, resolved.refusal
    aligner = next(s for s in resolved.view.steps if s.contract == HISAT2)
    assert aligner.chosen_by == "model"


def test_a_stale_write_is_refused_and_the_persons_edit_stands(clean):
    ctx = _rnaseq()
    assert call(ctx, "read_goal", {}).ok
    changes.apply(ctx.draft_id, DecisionChange(kind="parameter", subject="min_mqs", value=10),
                  who="ana")
    stale = call(ctx, "set_value", {"name": "min_mqs", "value": 20, "because": "stricter"})
    assert not stale.ok and stale.refusal.startswith("MI0201")
    [value] = [p for p in decisions.read(ctx.draft_id).parameters if p.name == "min_mqs"]
    assert (value.value, value.by) == (10, "person")
    assert call(ctx, "read_goal", {}).ok
    again = call(ctx, "set_value", {"name": "min_mqs", "value": 20, "because": "stricter"})
    assert again.ok, again.refusal


def test_resolve_reports_the_rules_that_fired(clean):
    resolved = call(_rnaseq(), "resolve", {})
    assert resolved.ok, resolved.refusal
    assert any("alignment" in r.decides for r in resolved.view.rules), resolved.view.rules
    assert all(r.reason for r in resolved.view.rules)


def test_compile_returns_the_nextflow(clean):
    ctx = _rnaseq()
    assert call(ctx, "resolve", {}).ok
    compiled = call(ctx, "compile", {})
    assert compiled.ok, compiled.refusal
    assert "workflow {" in compiled.view.main_nf


def test_an_undeclared_type_is_refused_with_its_code(clean):
    result = call(_rnaseq(), "want", {"type_id": "no.such.type", "because": "testing"})
    assert not result.ok and "MI0204" in result.refusal


def test_asking_returns_the_question_and_writes_nothing(clean):
    ctx = _rnaseq()
    before = decisions.revision(ctx.draft_id)
    asked = call(ctx, "ask", {"question": "Do you have a GTF?", "shape": "yes_no"})
    assert asked.ok, asked.refusal
    assert asked.view.question == "Do you have a GTF?" and asked.view.id
    assert decisions.revision(ctx.draft_id) == before
