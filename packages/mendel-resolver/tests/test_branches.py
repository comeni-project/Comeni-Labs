"""A tool chosen from a fact that differs between samples is chosen per sample (#466, stage 4)."""

from comeni_core.plan.at_run import AtRunSource, AtRunTest
from mendel_resolver import at_run, layers
from mendel_resolver.goal import Goal
from mendel_resolver.premises import build_premises
from support.paths import ROOT

STAR = "nf-core/star/align@2.7.11b"
HISAT2 = "nf-core/hisat2/align@2.2.2"


def _stack():
    return layers.load([ROOT / "registry"])


def _goal(stack, *, varies=(), profile=None) -> Goal:
    return Goal.model_validate({
        "have": [{"type_id": t} for t in ("fastq.reads", "genome.fasta", "annotation.gtf")],
        "want": ["counts.matrix"], "constraints": {"varies": list(varies)},
        "profile": stack.measurements.profile(profile or {}).model_dump(mode="json")})


def _points(stack, goal):
    premises = build_premises(goal=goal, derivations=stack.rules.derivations,
                              measurements=stack.measurements)
    return at_run.branch_points(stack.routing, stack.rules, premises, stack.measurements, goal)


def test_a_tool_chosen_from_a_varying_fact_is_a_branch_point():
    stack = _stack()
    (point,) = _points(stack, _goal(stack, varies=["read_length"]))
    assert point.decision.key() == "implementation:alignment"
    assert point.facts == ("read_length",)
    assert point.sources == (AtRunSource.CELL_OR_MEASURED,)
    assert point.outcomes == (STAR, HISAT2)
    star, hisat2 = point.rows
    assert (star.then, star.when[0].test, star.when[0].operand) == (STAR, AtRunTest.GE, [70])
    assert (hisat2.then, hisat2.when[0].test) == (HISAT2, AtRunTest.LT)


def test_a_stated_fact_is_no_branch_point():
    """Every sample stated to one side: today's pipeline exactly (Review Focus 2)."""
    stack = _stack()
    assert _points(stack, _goal(stack, profile={"read_length": 150})) == []


def test_an_unknown_fact_nobody_said_varies_is_no_branch_point():
    """It stays the question it is today: nobody said the samples differ."""
    stack = _stack()
    assert _points(stack, _goal(stack)) == []


def test_rows_that_reach_one_tool_are_no_branch_point(tmp_path):
    layer = tmp_path / "one"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules/alignment.yml").write_text("""declares: rule
version: 1
decisions:
  - decides: {effect: implementation, of: alignment}
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@2.7.11b, because: a fixture}
      - {when: {read_length: "< 70"}, then: nf-core/star/align@2.7.11b, because: a fixture}
""")
    stack = layers.load([ROOT / "registry", layer])
    assert _points(stack, _goal(stack, varies=["read_length"])) == []
