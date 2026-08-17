"""Ingest every vendored nf-core module and compare against the contract we ship.

Real ground truth, and the only test here with any. A disagreement is a finding either
way: the ingester is wrong, or a shipped contract is. Do not weaken an assertion to make
this pass — bring the disagreement to the checkpoint.

The count is derived from the tree rather than written down. Two numbers in CLAUDE.md
were stale for three plans because nothing counted them (A71, A72).
"""

from pathlib import Path

import pytest
from mendel_forge.assemble import scaffold_for
from mendel_forge.sources import ToolRef
from mendel_forge.sources.nfcore import NfCoreSource
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]
STACK = layers.load(ROOT / "registry")
PAIRS = [
    (contract, ToolRef(source="nf-core", ident=contract.id.split("@")[0].removeprefix("nf-core/")))
    for contract in STACK.registry.all()
    if contract.id.startswith("nf-core/")
    and (ROOT / "vendor" / f"{contract.nf_include}.nf").exists()
]


def _scaffold(contract, ref):
    obs = NfCoreSource().ingest(ref, ROOT / "vendor")
    return scaffold_for(
        obs, STACK, ident=contract.id.split("@")[0], version=contract.id.split("@")[1]
    )


def test_there_are_pairs_to_compare():
    assert len(PAIRS) >= 5, f"only {len(PAIRS)} pairs; this test is not testing"


@pytest.mark.parametrize("contract,ref", PAIRS, ids=lambda x: getattr(x, "id", str(x)))
def test_the_derived_fields_match_what_we_ship(contract, ref):
    scaffold = _scaffold(contract, ref)
    assert scaffold.filled["nf_process"].value == contract.nf_process
    assert scaffold.filled["nf_include"].value == contract.nf_include
    if contract.container:
        assert scaffold.filled["container"].value == contract.container


@pytest.mark.parametrize("contract,ref", PAIRS, ids=lambda x: getattr(x, "id", str(x)))
def test_every_shipped_output_port_appears_as_a_derived_name(contract, ref):
    scaffold = _scaffold(contract, ref)
    derived = {v.value for k, v in scaffold.filled.items() if k.endswith("].name")}
    for port in contract.produces:
        assert port.name in derived, f"{contract.id}: {port.name} was not derived"
