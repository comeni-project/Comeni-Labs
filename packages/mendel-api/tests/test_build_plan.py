"""The build plan over the real registry: the resolver's record reaches the person's card.

This is the test that holds Task 1 and the plan together. The pure tests use a hand-written
blueprint that already carries `unknown`; only this one proves the resolver writes it.
"""

from pathlib import Path

from comeni_core import yaml_strict
from comeni_core.goal.asked import ProducerPin, Site
from mendel_api.services import blueprint as bp
from mendel_api.services import declared, registry
from mendel_authoring.amend import ChooseTool
from mendel_authoring.gaps import GapKind
from mendel_authoring.needs import NeedKind
from mendel_authoring.plan import plan_of
from mendel_authoring.wrapup import wrap_up
from mendel_resolver.goal import Goal

ROOT = Path(__file__).resolve().parents[3]
STAR = "nf-core/star/align@1.11.0"
HISAT2 = "nf-core/hisat2/align@2.2.2"


def _rnaseq(**profile_without) -> Goal:
    data = yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml")
    for key in profile_without:
        data["profile"].pop(key)
    return Goal.model_validate(data)


def _aligner(goal: Goal):
    blueprint, _ = bp.resolve(goal)
    plan = plan_of(blueprint, declared.of(registry.stack()))
    assert plan.steps, "the resolver built nothing: the test reads the wrong goal"
    return next(step for step in plan.steps if step.contract == STAR)


def test_with_no_read_length_the_aligner_asks_for_it():
    star = _aligner(_rnaseq(read_length=True))
    assert star.need.kind is NeedKind.FACT
    assert star.need.facts == ["read_length"]


def test_with_a_read_length_the_aligner_checks_its_premise():
    """The tool is settled by the rule; what remains open is not the tool. (The shipped
    registry leaves STAR's `seq_platform` at tier 4, a choice of its own, so the step's need
    is not *nothing* — but it asks for no fact and no tool.)"""
    star = _aligner(_rnaseq())
    assert star.need.facts == []
    assert all(not choice.key.startswith("producer:") for choice in star.need.choices)
    assert any("read_length is 150" in line.text for line in star.brief.check)
    assert star.brief.does is not None


def test_domain_gap_is_not_a_run_requirement():
    """HISAT2's contract declares no values for `seq_platform`: the registry is incomplete, and
    no researcher can provide what it never listed."""
    alternate, _ = bp.resolve(ChooseTool(pin=ProducerPin(
        site=Site(type_id="alignment.bam"), contract=HISAT2)).apply(_rnaseq()))
    wrap = wrap_up(alternate, declared.of(registry.stack()))
    assert "hisat2_align.seq_platform" not in wrap.unset
    assert any(g.kind is GapKind.NO_DOMAIN and g.subject == "seq_platform" for g in wrap.gaps)
