"""What a step needs from the person: nothing, a fact a rule lacks, or a choice no rule settles."""

from comeni_core.plan.decision import ProducerDecision
from conftest import HISAT2, STAR
from mendel_authoring.needs import NeedKind, need_of


def _need(blueprint, node, declared):
    return need_of(blueprint.step(node), blueprint.pipeline.decisions, declared)


def test_a_settled_step_needs_nothing(rnaseq, declared):
    assert _need(rnaseq(150), "star_align", declared).kind is NeedKind.NOTHING


def test_a_rule_missing_its_fact_asks_for_the_fact(rnaseq, declared):
    need = _need(rnaseq(None), "star_align", declared)
    assert need.kind is NeedKind.FACT
    assert need.facts == ["read_length"]


def test_a_fact_still_carries_the_tools_so_the_person_can_choose_instead(rnaseq, declared):
    need = _need(rnaseq(None), "star_align", declared)
    assert len(need.choices) == 1
    offered = need.choices[0].candidates
    assert [c.value for c in offered] == [STAR, HISAT2]
    assert offered[1].does == "HISAT2 aligns reads to a genome with a small memory footprint."


def test_a_tier_four_setting_is_a_choice(rnaseq, declared):
    need = _need(rnaseq(150, strandedness_open=True), "featurecounts", declared)
    assert need.kind is NeedKind.CHOICE
    assert need.facts == []
    assert [c.value for c in need.choices[0].candidates] == [0, 1, 2]
    assert need.choices[0].candidates[0].does is None


def test_a_tie_with_no_missing_fact_is_a_choice(rnaseq, declared):
    blueprint = rnaseq(None)
    tie = blueprint.pipeline.decisions[0].model_copy(update={"unknown": []})
    pipeline = blueprint.pipeline.model_copy(update={"decisions": [tie]})
    need = need_of(blueprint.step("star_align"), pipeline.decisions, declared)
    assert need.kind is NeedKind.CHOICE


def test_a_question_a_person_already_answered_needs_nothing(rnaseq, declared):
    """Review Focus 1: the walk must not re-ask a settled question."""
    blueprint = rnaseq(None)
    answered = blueprint.pipeline.decisions[0].model_copy(update={"human_override": HISAT2})
    assert isinstance(answered, ProducerDecision)
    need = need_of(blueprint.step("star_align"), [answered], declared)
    assert need.kind is NeedKind.NOTHING


def test_another_steps_decision_is_not_this_steps_need(rnaseq, declared):
    assert _need(rnaseq(None), "fastqc", declared).kind is NeedKind.NOTHING
