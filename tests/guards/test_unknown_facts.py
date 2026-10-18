"""Whatever a chosen tool reads comes from somewhere, or is tier 4 (#338, #340).

featureCounts reads `meta.strandedness`; with the fact unknown the label was absent and the
module counted unstranded (`-s 0`) with nothing flagged. This holds for every label-carried
fact the example goal states, removed one at a time."""

import pytest
from comeni_core import yaml_strict
from mendel_compiler import conformance, orchestrate
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from mendel_resolver.ports import FlagOnlyResolver
from support.paths import ROOT

LOADED = layers.load(ROOT / "registry")
READ = conformance.facts_read(LOADED.registry, LOADED.modules, LOADED.measurements)
EXAMPLE = yaml_strict.load(ROOT / "tests" / "fixtures" / "goal-v6" / "rnaseq-goal.yml")
CARRIED = sorted(
    m for m in LOADED.measurements.ids()
    if LOADED.measurements.get(m).meta_key and m in EXAMPLE["profile"]
)


def test_the_example_states_label_carried_facts():
    assert CARRIED == ["paired", "strandedness"]


@pytest.mark.parametrize("fact", CARRIED)
def test_a_tool_reading_an_unknown_fact_is_flagged(fact):
    goal = Goal.model_validate({**EXAMPLE, "profile": {
        k: v for k, v in EXAMPLE["profile"].items() if k != fact}})
    built = orchestrate.build(goal, registry_root=ROOT / "registry",
                              resolver=FlagOnlyResolver())
    readers = [n for n in built.ir.nodes if fact in (READ.get(n.contract_id) or ())]
    assert readers, f"something on the spine reads {fact}"
    for node in readers:
        assert f"{node.id}.fact.{fact}" in built.ir.needs_review(), node.contract_id
