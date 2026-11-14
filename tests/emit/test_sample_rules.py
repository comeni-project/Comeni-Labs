"""A tool's rule over a per-sample fact, settled per sample in the run (#466).

The fixture is fastp-like: merging (`save_merged`) needs both reads, so a single-end sample may
not merge. Where the value came from a default or a rule, it is left unset for those samples;
where a person set it, a single-end sample stops the run, naming itself and the rule.
"""

import pytest
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.at_run import AtRunTest
from comeni_core.plan.draft import DraftGraph, DraftNode, DraftParam
from mendel_compiler.emit import emit, emit_config
from mendel_resolver import layers
from mendel_resolver.materialise import goal_of, ir_of
from support.paths import ROOT

FIXTURE = ROOT / "packages/comeni-core/tests/fixtures/constraints/fastp_like.yml"
SAYS = "merging needs both reads"


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    layer = tmp_path_factory.mktemp("fastp")
    (layer / "tools/test/fastp_like").mkdir(parents=True)
    (layer / "tools/test/fastp_like/contract.yml").write_text(FIXTURE.read_text())
    return layers.load([ROOT / "registry", layer])


def _pipeline(stack, params=()) -> Pipeline:
    graph = DraftGraph(nodes=[DraftNode(id="trim", contract_id="test/fastp_like@1.0",
                                        params=list(params))], edges=[])
    ir = ir_of(graph, stack)
    goal = goal_of(graph, stack)
    goal = goal.model_copy(update={"constraints": goal.constraints.model_copy(
        update={"varies": ["paired"]})})
    return Pipeline.of(ir, stack.registry, stack.vocabulary, stack.measurements, stack.paths,
                       goal=goal)


def test_a_default_is_left_unset_for_the_samples_the_rule_forbids(stack):
    pipeline = _pipeline(stack)
    step = next(s for s in pipeline.steps if s.id == "trim")
    setting = next(s for s in step.settings if s.name == "save_merged")
    assert setting.at_run is not None and setting.at_run.fallback is True
    (row,) = setting.at_run.rows
    (condition,) = row.when
    assert (condition.fact, condition.test, condition.operand, row.then) == (
        "paired", AtRunTest.EQ, [False], None)
    assert step.sample_rules == []
    assert "meta.paired" in emit_config(pipeline)


def test_a_persons_value_stops_a_sample_the_rule_forbids(stack):
    pipeline = _pipeline(stack, [DraftParam(name="save_merged", value=True)])
    step = next(s for s in pipeline.steps if s.id == "trim")
    (rule,) = step.sample_rules
    assert SAYS in rule.says
    assert [(c.fact, c.operand) for c in rule.when] == [("paired", [False])]
    text = emit(pipeline)
    assert "error(\"sample ${meta.id}: \" + '" in text and SAYS in text


def test_a_rule_every_sample_breaks_unsets_a_default_and_refuses_a_persons_value(stack):
    """Every sample known single-end: the default is not passed at all, and a person's value is
    refused at build, never shipped (Task 7 review, Critical)."""
    def built(params=()):
        graph = DraftGraph(nodes=[DraftNode(id="trim", contract_id="test/fastp_like@1.0",
                                            params=list(params))], edges=[])
        ir = ir_of(graph, stack)
        goal = goal_of(graph, stack)
        ir.profile = stack.measurements.profile({"paired": False})
        return Pipeline.of(ir, stack.registry, stack.vocabulary, stack.measurements,
                           stack.paths, goal=goal)

    setting = next(s for s in built().steps[0].settings if s.name == "save_merged")
    assert setting.value is None and setting.at_run is None
    with pytest.raises(ValueError, match="MD0337"):
        built([DraftParam(name="save_merged", value=True)])
