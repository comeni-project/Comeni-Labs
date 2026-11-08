"""A module's optional emits, and a contract that claims they are always written (#460).

The fixture is nf-core/quast's own main.nf (MIT, nf-core/modules), whose transcriptome,
misassemblies and unaligned reports are `optional: true`.
"""

from pathlib import Path

from comeni_core import yaml_strict
from comeni_core.declared.contract import ModuleContract
from mendel_compiler.conformance import against
from mendel_compiler.modulespec import ModuleSpec

HERE = Path(__file__).parent
MAIN_NF = HERE / "fixtures/quast/main.nf"
QUAST = HERE.parents[1] / "comeni-core/tests/fixtures/constraints/quast.yml"


def _quast(**changes) -> ModuleContract:
    data = yaml_strict.load(QUAST)
    data.update(changes)
    return ModuleContract.model_validate(data)


def test_modulespec_reads_optional_emits():
    spec = ModuleSpec.parse(MAIN_NF)
    assert spec.optional_emits == ["transcriptome", "misassemblies", "unaligned"]


def test_an_optional_emit_declared_always_is_md0611():
    contract = _quast()
    produces = [p.model_dump() for p in contract.produces]
    for port in produces:
        if port["name"] == "unaligned":
            port["produced_when"] = None
    found = against(_quast(produces=produces), ModuleSpec.parse(MAIN_NF), MAIN_NF)
    codes = [(d.code, d.summary) for d in found if d.code == "MD0611"]
    assert len(codes) == 1 and "unaligned" in codes[0][1]


def test_the_quast_fixture_contract_conforms_on_optional_emits():
    found = against(_quast(), ModuleSpec.parse(MAIN_NF), MAIN_NF)
    assert not [d for d in found if d.code == "MD0611"]
