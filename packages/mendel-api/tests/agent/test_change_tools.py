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


def test_a_build_overtaken_by_the_persons_change_is_not_drawn_as_current(clean, monkeypatch):
    """#463 review: the person changes a decision while the agent's build is resolving. The
    build from the older decisions must not land over it marked current: it is refused, and
    the pipeline stays outdated until it is built from the person's change."""
    from mendel_api.db import session_scope
    from mendel_api.models import PipelineDraft
    from mendel_api.services import blueprint as bp

    ctx = _rnaseq()
    real = bp.resolve

    def overtaken(goal, *args, **kwargs):
        built = real(goal, *args, **kwargs)
        changes.apply(ctx.draft_id, DecisionChange(kind="parameter", subject="min_mqs", value=10),
                      who="ana")
        return built

    monkeypatch.setattr(bp, "resolve", overtaken)
    resolved = call(ctx, "resolve", {})
    assert not resolved.ok and resolved.refusal.startswith("MI0201"), resolved
    with session_scope() as db:
        assert db.get(PipelineDraft, ctx.draft_id).projection_current is False
    monkeypatch.setattr(bp, "resolve", real)
    ctx.expected_revision = decisions.revision(ctx.draft_id)
    assert call(ctx, "resolve", {}).ok


def test_what_the_agent_withdraws_is_recorded_as_the_ais(clean):
    """#463 review: a retract is a decision too. The agent switching a role back on must not
    read in the history as the person's act."""
    ctx = _rnaseq()
    off = call(ctx, "switch_role", {"role": "trimming", "on": False, "because": "reads are clean"})
    assert off.ok, off.refusal
    on = call(ctx, "switch_role", {"role": "trimming", "on": True, "because": "keep it after all"})
    assert on.ok, on.refusal
    history = decisions.intent_history(ctx.draft_id, "role", "trimming")
    assert [(h["action"], str(h["actor_kind"])) for h in history][-1] == ("retract", "model")


def test_a_change_landing_between_the_check_and_the_write_is_refused(clean, monkeypatch):
    """#463 review: the stale check and the write are one step. A person's change landing after
    the check passed still refuses the agent's write, and the person's value stands."""
    from mendel_api.agent import change as change_tools

    ctx = _rnaseq()
    real = changes.apply

    def raced(draft_id, change, *, who):
        with decisions.expecting(None):
            real(draft_id, DecisionChange(kind="parameter", subject="min_mqs", value=10),
                 who="ana")
        return real(draft_id, change, who=who)

    monkeypatch.setattr(change_tools.changes, "apply", raced)
    refused = call(ctx, "set_value", {"name": "min_mqs", "value": 20, "because": "stricter"})
    assert not refused.ok and refused.refusal.startswith("MI0201"), refused
    [value] = [p for p in decisions.read(ctx.draft_id).parameters if p.name == "min_mqs"]
    assert (value.value, value.by) == (10, "person")


def test_a_tool_that_half_wrote_does_not_make_the_next_write_stale(clean):
    ctx = _rnaseq()
    half = call(ctx, "want", {"type_id": "qc.report", "states": ["no_such_state"],
                              "because": "gene counts"})
    assert not half.ok and "no_such_state" in half.refusal
    after = call(ctx, "set_value", {"name": "min_mqs", "value": 20, "because": "stricter"})
    assert after.ok, after.refusal


def test_the_agent_gives_the_analysis_a_working_name(clean):
    """Walk 2026-11-15: the analysis stayed "Untitled analysis". The agent names it; the person
    can rename it. A name is not a decision, so it moves no decision revision."""
    from mendel_api.db import session_scope
    from mendel_api.models import PipelineDraft

    ctx = _rnaseq()
    before = decisions.revision(ctx.draft_id)
    named = call(ctx, "name_pipeline", {"name": "Mouse liver RNA-seq counts"})
    assert named.ok, named.refusal
    with session_scope() as db:
        assert db.get(PipelineDraft, ctx.draft_id).name == "Mouse liver RNA-seq counts"
    assert decisions.revision(ctx.draft_id) == before
    assert not call(ctx, "name_pipeline", {"name": ""}).ok


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
