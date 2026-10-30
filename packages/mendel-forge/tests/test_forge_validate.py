"""A reply is checked against the registry and the module before anything is stored (§3)."""

from pathlib import Path

import pytest
import yaml
from comeni_core.declared.contract import ModuleContract
from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.validate import check_items, known, pending_used
from mendel_forge.forging.values import items_of
from mendel_resolver import layers
from support.paths import REGISTRY

STAR_NF = Path(__file__).parent / "fixtures" / "nf-core" / "star" / "align" / "main.nf"


@pytest.fixture(scope="module")
def stack():
    return layers.load(REGISTRY)


@pytest.fixture(scope="module")
def star_items():
    data = yaml.safe_load((REGISTRY / "tools/nf-core/star/align/contract.yml").read_text())
    data.pop("declares")
    return items_of(ModuleContract(**data))


def _codes(problems) -> list[str]:
    return [p.code for p in problems]


def test_star_aligns_registry_items_pass(stack, star_items):
    assert check_items(star_items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_an_unknown_type_is_MF0507(stack, star_items):
    items = {**star_items, "contract:input:reads": {**star_items["contract:input:reads"],
                                                    "type_id": "nothing.here"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]


def test_a_type_proposed_in_this_adaptation_is_known(stack, star_items):
    items = {**star_items,
             "contract:input:reads": {**star_items["contract:input:reads"], "type_id": "new.type"},
             "vocabulary:type:new.type": {"id": "new.type", "states": []}}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_a_type_in_another_adaptations_unassembled_draft_is_unknown(stack, star_items):
    """Review Focus 3: only assembled drafts are pending; anything else is simply unknown."""
    items = {**star_items, "contract:input:reads": {**star_items["contract:input:reads"],
                                                    "type_id": "draft.only"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]


def test_a_pending_type_is_accepted_and_flagged(stack, star_items):
    items = {**star_items, "contract:input:reads": {**star_items["contract:input:reads"],
                                                    "type_id": "genome.index.bwa"}}
    seen = known(stack, pending=frozenset({"genome.index.bwa"}))
    assert check_items(items, seen, ModuleSpec.parse(STAR_NF)) == []
    assert pending_used(items, seen) == {"genome.index.bwa"}


def test_a_port_main_nf_lacks_is_MF0508(stack, star_items):
    items = {**star_items, "contract:input:ghost": {"position": 9, "name": "ghost",
                                                    "type_id": "fastq.reads"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0508"]


def test_a_param_routed_nowhere_is_MF0509(stack, star_items):
    items = {**star_items, "parameters:param:loose": {"position": 9, "name": "loose",
                                                      "via": "ext", "default": 1}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0509"]
