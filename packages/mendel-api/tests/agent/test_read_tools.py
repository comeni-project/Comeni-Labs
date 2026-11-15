"""The builder agent's read tools (#463): typed views, names in words, refusals as results."""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.agent.tools import TOOLS, ToolContext, call, spec_of
from mendel_api.services import decisions, drafts
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from mendel_resolver.goal import Goal
from support.example import example_mapping

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


def _rnaseq() -> ToolContext:
    draft = drafts.create(DraftGraph(), "rnaseq", "ana")
    decisions.import_goal(draft, Goal.model_validate(example_mapping()), who="ana")
    return ToolContext(draft_id=draft, session_id=None, who="builder-agent",
                       expected_revision=decisions.revision(draft))


def test_every_tool_has_a_schema_the_model_can_read():
    assert TOOLS
    names = [spec_of(t).name for t in TOOLS.values()]
    assert len(names) == len(set(names))
    for tool in TOOLS.values():
        schema = spec_of(tool).parameters
        assert schema["type"] == "object", tool.name


def test_read_step_says_what_decided_each_setting(clean):
    result = call(_rnaseq(), "read_step", {"node": "star_align"})
    assert result.ok, result.refusal
    step = result.view
    assert step.contract.startswith("nf-core/star/align@")
    ignored = next(s for s in step.settings if s.name == "star_ignore_sjdbgtf")
    assert ignored.tier == 2 and ignored.reason


def test_a_refused_argument_is_a_result_not_an_exception(clean):
    result = call(_rnaseq(), "read_step", {"node": "no_such_step"})
    assert not result.ok
    assert "no_such_step" in result.refusal
    malformed = call(_rnaseq(), "read_step", {"step": 3})
    assert not malformed.ok and malformed.refusal


def test_reads_name_types_in_words(clean):
    result = call(_rnaseq(), "read_pipeline", {})
    assert result.ok, result.refusal
    named = {i.type_id: i.name for i in result.view.inputs}
    assert named["annotation.gtf"] == "gene annotation (GTF)"


def test_find_tools_names_who_makes_and_reads_a_type(clean):
    result = call(_rnaseq(), "find_tools", {"type_id": "alignment.bam"})
    assert result.ok, result.refusal
    assert any(t.contract.startswith("nf-core/star/align@") for t in result.view.makes)
    assert any(t.contract.startswith("nf-core/samtools/sort@") for t in result.view.reads)


def test_read_rules_gives_conditions_and_citations(clean):
    result = call(_rnaseq(), "read_rules", {"role": "alignment"})
    assert result.ok, result.refusal
    assert result.view.rules and all(r.rows for r in result.view.rules)


def test_what_is_needed_lists_the_open_questions(clean):
    result = call(_rnaseq(), "what_is_needed", {})
    assert result.ok, result.refusal
    assert isinstance(result.view.needs, list)


def test_the_registry_vocabulary_names_every_type_and_measurement(clean):
    """Walk 2026-11-15: the agent guessed `reads.fastq` and `paired_end`, and was refused four
    times. It can read every type and measurement the registry declares, by its exact id."""
    from mendel_api.services import registry

    seen = call(_rnaseq(), "list_vocabulary", {})
    assert seen.ok, seen.refusal
    stack = registry.stack()
    assert {t.type_id for t in seen.view.types} == set(stack.vocabulary.types)
    assert {m.measurement for m in seen.view.measurements} == set(stack.measurements.ids())
    length = next(m for m in seen.view.measurements if m.measurement == "read_length")
    assert length.kind == "integer" and length.name and length.describes == "fastq.reads"


def test_the_goal_says_the_analysis_name_so_the_agent_can_name_it(clean):
    """Walk 2026-11-15: the agent could not tell the analysis was still untitled."""
    ctx = _rnaseq()
    goal = call(ctx, "read_goal", {})
    assert goal.ok and goal.view.name == "rnaseq"
