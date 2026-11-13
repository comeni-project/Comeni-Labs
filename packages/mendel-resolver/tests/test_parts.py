"""A step may run on parts of a sample (#466, stage 6 part A)."""

import pytest
from comeni_core.declared.contract import InputPort, ModuleContract, OutputPort
from comeni_core.plan.tiers import Grain
from mendel_resolver import layers
from support.paths import ROOT

from emit.fixtures.parts import LAYER, layer


def _stack(tmp_path, extra=None, without=()):
    return layers.load([ROOT / "registry", layer(tmp_path, extra, without)])


def test_the_fixture_layer_loads(tmp_path):
    stack = _stack(tmp_path)
    split = stack.registry.get("lab/split_reads@1.0.0")
    assert split.produces[0].fans_out is Grain.PART
    assert stack.registry.get("lab/search@1.0.0").consumes[0].parts is True


def _refused(tmp_path, name, body):
    with pytest.raises(ValueError, match="MD0346"):
        _stack(tmp_path, {name: body})


def test_only_a_splitter_fans_out(tmp_path):
    body = LAYER["split.contract.yml"].replace("roles: [splitting]", "roles: [searching]")
    _refused(tmp_path, "split.contract.yml", body)


def test_a_splitter_fans_out_its_own_type(tmp_path):
    body = LAYER["split.contract.yml"].replace(
        "{name: reads, type_id: fastq.reads, fans_out: part}",
        "{name: reads, type_id: hits.tsv, fans_out: part}")
    _refused(tmp_path, "split.contract.yml", body)


@pytest.mark.parametrize("extra", ["many: true, grain: sample", "grain: study",
                                   "select: {paired: true}"])
def test_a_port_on_parts_reads_one_sample(tmp_path, extra):
    body = LAYER["search.contract.yml"].replace("parts: true}", f"parts: true, {extra}}}")
    _refused(tmp_path, "search.contract.yml", body)


def test_only_part_fans_out():
    with pytest.raises(ValueError):
        OutputPort(name="x", type_id="fastq.reads", fans_out=Grain.SAMPLE)


def test_a_contract_without_parts_serialises_as_before():
    stack = layers.load([ROOT / "registry"])
    contract = stack.registry.get("nf-core/star/align@2.7.11b")
    dumped = contract.model_dump(mode="json")
    assert all("parts" not in p for p in dumped["consumes"])
    assert all("fans_out" not in p for p in dumped["produces"])
    again = ModuleContract.model_validate(dumped)
    assert again == contract
    port = InputPort(name="reads", type_id="fastq.reads", parts=True)
    assert InputPort.model_validate(port.model_dump(mode="json")).parts is True


def test_no_type_is_a_part(tmp_path):
    with pytest.raises(ValueError):
        _stack(tmp_path, {"hits.tsv.yml": "declares: vocabulary\nid: hits.tsv\nstates: []\n"
                                          "grain: part\n"})

