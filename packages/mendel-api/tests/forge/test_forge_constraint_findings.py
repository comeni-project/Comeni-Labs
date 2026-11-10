"""The forge shows the contract's constraint findings on its process item (#460, #464)."""

from comeni_core import yaml_strict
from comeni_core.declared.contract import ModuleContract
from mendel_api.services.forge_checks import _with_constraint_checks
from mendel_forge.forging.values import items_of
from support.paths import ROOT

FIXTURES = ROOT / "packages/comeni-core/tests/fixtures/constraints"


def _items(name: str, **rows) -> dict:
    data = yaml_strict.load(FIXTURES / f"{name}.yml")
    data.update(rows)
    return items_of(ModuleContract.model_validate(data))


def test_a_clean_draft_has_no_constraint_findings():
    assert _with_constraint_checks({}, _items("salmon_quant")) == {}


def test_forge_checks_report_a_type_gap():
    """salmon with FASTQ reads that need and refuse an index: the draft says so (MD0612)."""
    data = yaml_strict.load(FIXTURES / "salmon_quant.yml")
    data["constraints"][1] = {"when": {"type.reads": "fastq.reads"}, "requires": ["index"],
                              "forbids": ["index"], "because": "contradicts itself for FASTQ"}
    found = _with_constraint_checks({}, items_of(ModuleContract.model_validate(data)))
    codes = [f.code for f in found["contract:process"]]
    assert "MD0612" in codes


def test_forge_checks_report_a_table_gap():
    """#461: a drafted rule over two facts that leaves a case uncovered says so on its item."""
    from mendel_api.services.forge_checks import _with_rule_checks

    items = {"rules:rule:alignment": {
        "decides": {"effect": "implementation", "of": "alignment"},
        "rows": [{"when": {"read_length": ">= 70", "strandedness": "reverse"},
                  "then": "nf-core/star/align@2.7.11b", "cite": "a"}]}}
    found = _with_rule_checks({}, items)
    assert [f.code for f in found["rules:rule:alignment"]] == ["MD0311"]
