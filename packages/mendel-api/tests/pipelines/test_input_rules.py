"""A step's rules between its inputs, evaluated over how it is set up (#460, #511): what the Step
tab lays its optional inputs out by."""

from types import SimpleNamespace

import yaml
from comeni_core.declared.contract import ModuleContract
from mendel_api.services.build import rules_of
from support.paths import ROOT

QUAST = yaml.safe_load(
    (ROOT / "packages/comeni-core/tests/fixtures/constraints/quast.yml").read_text()
)
QUAST.pop("declares", None)
CONTRACT = ModuleContract.model_validate(QUAST)


def _step(**states: str):
    return SimpleNamespace(
        input_states=[
            SimpleNamespace(port=p, state=SimpleNamespace(value=s)) for p, s in states.items()
        ],
        settings=[],
    )


def _gff_rule(step):
    rules = rules_of(step, CONTRACT)
    assert rules, "QUAST declares rules; none came back"
    return next(r for r in rules if "gff" in r.when)


def test_annotation_without_a_reference_breaks_the_rule():
    rule = _gff_rule(_step(gff="required", fasta="off"))
    assert rule.kind == "requires" and rule.names == ["fasta"]
    assert rule.applies and rule.broken and not rule.at_run


def test_annotation_with_a_reference_keeps_it():
    rule = _gff_rule(_step(gff="required", fasta="required"))
    assert rule.applies and not rule.broken


def test_an_annotation_each_run_may_leave_empty_is_the_runs_to_settle():
    rule = _gff_rule(_step(gff="optional", fasta="off"))
    assert not rule.broken and rule.at_run


def test_no_annotation_and_the_rule_does_not_apply():
    rule = _gff_rule(_step(gff="off", fasta="off"))
    assert not rule.applies and not rule.broken
    assert rule.says and "`" not in rule.says
