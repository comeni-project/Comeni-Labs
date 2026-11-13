"""A step may run on parts of a sample (#466, stage 6 part A)."""

import pytest
from comeni_core.declared.contract import InputPort, ModuleContract, OutputPort
from comeni_core.plan.tiers import Grain
from emit.fixtures.parts import LAYER, layer
from mendel_resolver import layers
from support.paths import ROOT


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



SEARCH = "lab/search@1.0.0"


def _goal(stack, *, have=("fastq.reads", "genome.fasta"), constraints=None):
    from mendel_resolver.goal import Goal

    return Goal.model_validate({
        "have": [{"type_id": t} for t in have], "want": ["hits.tsv"],
        "constraints": constraints or {},
        "profile": stack.measurements.profile({}).model_dump(mode="json")})


def _resolved(stack, goal):
    from mendel_resolver.resolve import resolve

    return resolve(goal, stack.routing, stack.rules, stack.measurements,
                   vocabulary=stack.vocabulary)


def test_a_step_on_parts_is_split_and_merged(tmp_path):
    stack = _stack(tmp_path)
    ir = _resolved(stack, _goal(stack))
    order = [n.id for n in ir.nodes]
    assert order.index("split_search") < order.index("search") < order.index("merge_search_hits")
    nodes = {n.id: n for n in ir.nodes}
    assert nodes["split_search"].contract_id == "lab/split_reads@1.0.0"
    assert nodes["merge_search_hits"].contract_id == "lab/merge_hits@1.0.0"
    parts = nodes["search"].parts
    assert parts.on and parts.splitter == "lab/split_reads@1.0.0"
    assert [(m.port, m.contract) for m in parts.mergers] == [("hits", "lab/merge_hits@1.0.0")]
    assert "lab/search@1.0.0 can run on parts of fastq.reads" in parts.because
    edges = {(e.from_node, e.from_port, e.to_node, e.to_port) for e in ir.edges}
    assert ("split_search", "reads", "search", "reads") in edges
    assert ("search", "hits", "merge_search_hits", "hits") in edges
    assert not [e for e in ir.edges if e.to_node == "split_search"]  # reads from the input
    assert all(order.index(e.from_node) < order.index(e.to_node) for e in ir.edges)
    # A merger is placed, never routed: it would gather the study into one (Task 2 check).
    assert order == ["split_search", "search", "merge_search_hits"]


def test_a_step_kept_whole_is_todays_pipeline(tmp_path):
    """Review Focus 3: no split, no merge, only the record that a split was possible."""
    stack = _stack(tmp_path)
    whole = _resolved(stack, _goal(stack, constraints={"whole": [SEARCH]}))
    bare = _stack(tmp_path / "x", without=("split.contract.yml",))
    plain = _resolved(bare, _goal(bare))
    nodes = {n.id: n for n in whole.nodes}
    assert not nodes["search"].parts.on
    assert [n.id for n in whole.nodes] == [n.id for n in plain.nodes]
    assert whole.edges == plain.edges
    assert plain.nodes[[n.id for n in plain.nodes].index("search")].parts is None


def test_no_merger_means_no_split(tmp_path):
    stack = _stack(tmp_path, without=("merge.contract.yml",))
    ir = _resolved(stack, _goal(stack))
    assert "split_search" not in {n.id for n in ir.nodes}
    assert next(n for n in ir.nodes if n.id == "search").parts is None


def test_a_second_per_sample_input_means_no_split(tmp_path):
    body = LAYER["search.contract.yml"].replace(
        "  - {name: genome, type_id: genome.fasta}",
        "  - {name: genome, type_id: genome.fasta}\n  - {name: extra, type_id: alignment.bam}")
    body = body.replace("{ports: [genome]}]", "{ports: [genome]}, {ports: [extra]}]")
    stack = _stack(tmp_path, {"search.contract.yml": body})
    ir = _resolved(stack, _goal(stack, have=("fastq.reads", "genome.fasta", "alignment.bam")))
    assert "split_search" not in {n.id for n in ir.nodes}


def test_parts_are_deterministic(tmp_path):
    stack = _stack(tmp_path)
    assert _resolved(stack, _goal(stack)).model_dump_json() \
        == _resolved(stack, _goal(stack)).model_dump_json()


def test_the_shipped_rnaseq_goal_is_unchanged(tmp_path):
    """No shipped tool runs on parts; the splitting role changes nothing."""
    from mendel_resolver.goal import Goal

    stack = layers.load([ROOT / "registry"])
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in ("fastq.reads", "genome.fasta", "annotation.gtf")],
        "want": ["counts.matrix"],
        "profile": stack.measurements.profile({"read_length": 150}).model_dump(mode="json")})
    ir = _resolved(stack, goal)
    assert not [n for n in ir.nodes if n.parts is not None or n.id.startswith("split_")]
