"""A contract's rule may read a per-sample fact (`fact.<measurement>`, #466): it is then
settled per sample, in the run, unless every sample's value is known to break it."""

from comeni_core import yaml_strict
from comeni_core.declared.constraints import Setup, evaluate
from comeni_core.declared.contract import ModuleContract
from support.paths import ROOT

FIXTURES = ROOT / "packages/comeni-core/tests/fixtures/constraints"
SAYS = "`save_merged` is not given when paired is false (merging needs both reads)"


def _fastp() -> ModuleContract:
    data = yaml_strict.load(FIXTURES / "fastp_like.yml")
    data.pop("declares", None)
    return ModuleContract.model_validate(data)


def test_a_rule_broken_by_some_samples_is_per_sample():
    verdict = evaluate(_fastp(), Setup(given=frozenset({"reads"}),
                                       params={"save_merged": True},
                                       unknown_facts={"paired": [True, False, None]}))
    assert verdict.per_sample and verdict.forbidden == []
    assert verdict.holds_at_run_time == []


def test_a_rule_broken_by_every_sample_is_refused():
    verdict = evaluate(_fastp(), Setup(given=frozenset({"reads"}),
                                       params={"save_merged": True},
                                       facts={"paired": False}))
    assert verdict.forbidden == ["save_merged"] and verdict.per_sample == []


def test_a_rule_no_sample_breaks_is_silent():
    verdict = evaluate(_fastp(), Setup(given=frozenset({"reads"}),
                                       params={"save_merged": True}, facts={"paired": True}))
    assert verdict.forbidden == [] and verdict.per_sample == []


def test_a_fact_rule_is_said_in_words():
    verdict = evaluate(_fastp(), Setup(given=frozenset({"reads"}),
                                       params={"save_merged": True},
                                       unknown_facts={"paired": [True, False, None]}))
    assert verdict.per_sample == [verdict.sentences[0]]
