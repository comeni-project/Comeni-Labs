"""What a step needs from the person: nothing, a fact a rule lacks, or a choice no rule settles."""

from comeni_core.plan.decision import ProducerDecision
from mendel_authoring.needs import NeedKind, need_of

# Spelled here rather than imported from `conftest`: a `conftest` import resolves to whichever
# package's conftest was collected first, so it broke the moment this ran beside another suite.
STAR = "nf-core/star/align@1.11.0"
HISAT2 = "nf-core/hisat2/align@2.2.2"


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


def test_a_tool_a_person_chose_is_not_asked_again(rnaseq, declared):
    """Review Focus 1, on the shape the router writes: a replayed person's answer is `chosen`
    plus the step's `why.source = human`; the router never sets `human_override` on a producer
    record. Found by the final review: the first fix keyed on `human_override` alone."""
    from comeni_core.artifact.pipeline import ModuleRef
    from comeni_core.plan.tiers import ValueSource

    blueprint = rnaseq(None)
    star = blueprint.step("star_align")
    chosen = star.model_copy(
        update={
            "module": ModuleRef(contract_id=HISAT2, digest=star.module.digest),
            "why": star.why.model_copy(update={"source": ValueSource.HUMAN}),
        }
    )
    record = blueprint.pipeline.decisions[0].model_copy(update={"chosen": HISAT2})
    assert record.human_override is None and record.unknown == ["read_length"]
    assert need_of(chosen, [record], declared).kind is NeedKind.NOTHING


def test_a_setting_a_person_answered_is_not_asked_again(rnaseq, declared):
    from comeni_core.plan.tiers import ValueSource

    blueprint = rnaseq(150, strandedness_open=True)
    counts = blueprint.step("featurecounts")
    answered = counts.model_copy(
        update={
            "settings": [
                s.model_copy(
                    update={
                        "value": 2,
                        "why": s.why.model_copy(update={"source": ValueSource.HUMAN}),
                    }
                )
                for s in counts.settings
            ]
        }
    )
    assert answered.settings
    assert need_of(answered, blueprint.pipeline.decisions, declared).kind is NeedKind.NOTHING


def test_a_setting_with_no_declared_domain_is_not_a_choice(rnaseq, declared):
    """Issue 252: no list to choose from; it is a registry gap, and left to the run."""
    from comeni_core.plan.decision import ParamDecision

    blueprint = rnaseq(150)
    record = ParamDecision(
        key="star_align.seq_platform", subject="seq_platform", candidates=[None],
        chosen=None, reason="flag-only", resolved_by="flag-only",
    )
    need = need_of(blueprint.step("star_align"), [record], declared)
    assert need.kind is NeedKind.NOTHING
