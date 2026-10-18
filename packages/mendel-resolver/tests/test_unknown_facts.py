"""The resolver's half: unknown facts a chosen tool reads become tier-4 records (#338)."""

from comeni_core import yaml_strict
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from mendel_resolver.resolve import resolve
from support.paths import ROOT

LOADED = layers.load(ROOT / "registry")
EXAMPLE = yaml_strict.load(ROOT / "tests" / "fixtures" / "goal-v6" / "rnaseq-goal.yml")
WITHOUT = {k: v for k, v in EXAMPLE["profile"].items() if k != "strandedness"}


def _resolve(profile, facts_read):
    goal = Goal.model_validate({**EXAMPLE, "profile": profile})
    return resolve(goal, LOADED.registry, LOADED.rules, LOADED.measurements,
                   vocabulary=LOADED.vocabulary, facts_read=facts_read)


def _facts(ir):
    return [d for d in ir.decisions if getattr(d, "kind", "") == "fact"]


def test_an_unknown_fact_is_a_record_with_the_declared_values():
    ir = _resolve(WITHOUT, {c.id: frozenset({"strandedness"}) for c in LOADED.registry.all()
                            if "featurecounts" in c.id})
    [record] = _facts(ir)
    assert record.unknown == ["strandedness"]
    assert record.candidates == ["forward", "reverse", "unstranded"]


def test_a_known_fact_or_no_mapping_changes_nothing():
    stated = _resolve(EXAMPLE["profile"], {c.id: frozenset({"strandedness"})
                                           for c in LOADED.registry.all()})
    assert _facts(stated) == []
    assert _facts(_resolve(WITHOUT, None)) == []


def test_an_unreadable_tool_records_nothing():
    assert _facts(_resolve(WITHOUT, {c.id: None for c in LOADED.registry.all()})) == []


def test_an_unknown_yes_or_no_fact_offers_both():
    """Review Focus 4: pairing travels as a yes/no on the label."""
    without = {k: v for k, v in EXAMPLE["profile"].items() if k != "paired"}
    ir = _resolve(without, {c.id: frozenset({"paired"}) for c in LOADED.registry.all()
                            if "star/align" in c.id})
    [record] = _facts(ir)
    assert record.candidates == [True, False]
