"""Routing and wiring over a port that accepts more than one shape."""

import pytest
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from mendel_resolver.router import UnroutableError, route
from mendel_resolver.rules import RuleTable

CALLER = """
id: lab/caller@1.0.0
nf_process: CALLER
nf_include: modules/lab/caller/main
consumes:
  - name: reads
    accepts:
      - {type_id: alignment.bam, states: [coordinate_sorted]}
      - {type_id: alignment.cram, states: [coordinate_sorted]}
produces: [{name: vcf, type_id: variants.vcf, state: []}]
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-03"}
"""

CRAM_MAKER = """
id: lab/cram@1.0.0
nf_process: CRAM
nf_include: modules/lab/cram/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: cram, type_id: alignment.cram, state: [coordinate_sorted]}]
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-03"}
"""

SORT = """
id: lab/sort@1.0.0
nf_process: SORT
nf_include: modules/lab/sort/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-03"}
"""


def _world(tmp_path, contracts: dict[str, str]):
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    (vocab_dir / "alignment.cram.yml").write_text("states: [coordinate_sorted]\n")
    (vocab_dir / "variants.vcf.yml").write_text("states: []\n")
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()
    for name, body in contracts.items():
        (contract_dir / name).write_text(body)
    vocabulary = Vocabulary.load(vocab_dir)
    return Registry.load(contract_dir, vocabulary)


def _goal():
    return Goal(have=[GoalInput(type_id="alignment.bam")], want=["variants.vcf"])


def test_the_first_alternative_wins_when_both_can_be_routed(tmp_path):
    """Declaration order is the author saying which input they would rather have."""
    registry = _world(tmp_path, {"c.yml": CALLER, "cram.yml": CRAM_MAKER, "sort.yml": SORT})
    steps = [s.contract_id for s in route(_goal(), registry).steps]
    assert "lab/sort@1.0.0" in steps
    assert "lab/cram@1.0.0" not in steps


def test_the_second_alternative_routes_when_the_first_cannot(tmp_path):
    registry = _world(tmp_path, {"c.yml": CALLER, "cram.yml": CRAM_MAKER})
    steps = [s.contract_id for s in route(_goal(), registry).steps]
    assert "lab/cram@1.0.0" in steps


def test_a_port_no_alternative_satisfies_says_so(tmp_path):
    registry = _world(tmp_path, {"c.yml": CALLER})
    with pytest.raises(UnroutableError, match="no alternative for port 'reads'"):
        route(_goal(), registry)


def test_the_edge_records_the_alternative_that_actually_matched(tmp_path):
    """`IREdge.type_id` used to be copied off the port, which an `accepts` port lacks."""
    registry = _world(tmp_path, {"c.yml": CALLER, "cram.yml": CRAM_MAKER})
    ir = resolve(_goal(), registry, RuleTable(), MeasurementRegistry())
    edge = next(e for e in ir.edges if e.to_node == "caller")
    assert edge.type_id == "alignment.cram"
    assert edge.states == frozenset({"coordinate_sorted"})


def test_prefer_breaks_a_tie_within_one_alternative(tmp_path):
    """`prefer` never promotes a later alternative — it only ranks sources inside one."""
    deduped = SORT.replace("lab/sort@1.0.0", "lab/dedup@1.0.0").replace(
        "nf_process: SORT", "nf_process: DEDUP"
    )
    registry = _world(tmp_path, {"c.yml": CALLER, "sort.yml": SORT, "dedup.yml": deduped})
    ir = resolve(_goal(), registry, RuleTable(), MeasurementRegistry())
    # Two identical producers of a coordinate-sorted BAM: a genuine tie, so it is recorded
    # rather than taken silently.
    assert any(d.subject == "producer:alignment.bam" for d in ir.decisions)
