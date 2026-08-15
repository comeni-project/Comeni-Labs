"""Routing and wiring over a port that accepts more than one shape."""

import pathlib

import pytest
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from mendel_resolver.router import UnroutableError, route
from mendel_resolver.rules import RuleTable

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `contracts/nf-core/fastqc.yml` sits two levels down from the directory that names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body

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
    (vocab_dir / "alignment.bam.yml").write_text(
        _declared(vocab_dir / "alignment.bam.yml", "states: [coordinate_sorted]\n")
    )
    (vocab_dir / "alignment.cram.yml").write_text(
        _declared(vocab_dir / "alignment.cram.yml", "states: [coordinate_sorted]\n")
    )
    (vocab_dir / "variants.vcf.yml").write_text(
        _declared(vocab_dir / "variants.vcf.yml", "states: []\n")
    )
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()
    for name, body in contracts.items():
        (contract_dir / name).write_text(_declared(contract_dir / name, body))
    vocabulary = Vocabulary.load(tmp_path)
    return Registry.load(tmp_path, vocabulary), vocabulary


def _goal():
    return Goal(have=[GoalInput(type_id="alignment.bam")], want=["variants.vcf"])


def test_the_first_alternative_wins_when_both_can_be_routed(tmp_path):
    """Declaration order is the author saying which input they would rather have."""
    registry, vocabulary = _world(
        tmp_path, {"c.yml": CALLER, "cram.yml": CRAM_MAKER, "sort.yml": SORT}
    )
    steps = [s.contract_id for s in route(_goal(), registry).steps]
    assert "lab/sort@1.0.0" in steps
    assert "lab/cram@1.0.0" not in steps


def test_the_second_alternative_routes_when_the_first_cannot(tmp_path):
    registry, vocabulary = _world(tmp_path, {"c.yml": CALLER, "cram.yml": CRAM_MAKER})
    steps = [s.contract_id for s in route(_goal(), registry).steps]
    assert "lab/cram@1.0.0" in steps


def test_a_port_no_alternative_satisfies_says_so(tmp_path):
    registry, vocabulary = _world(tmp_path, {"c.yml": CALLER})
    with pytest.raises(UnroutableError, match="no alternative for port 'reads'"):
        route(_goal(), registry)


def test_the_edge_records_the_alternative_that_actually_matched(tmp_path):
    """`IREdge.type_id` used to be copied off the port, which an `accepts` port lacks."""
    registry, vocabulary = _world(tmp_path, {"c.yml": CALLER, "cram.yml": CRAM_MAKER})
    ir = resolve(_goal(), registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)
    edge = next(e for e in ir.edges if e.to_node == "caller")
    assert edge.type_id == "alignment.cram"
    assert edge.states == frozenset({"coordinate_sorted"})


def test_prefer_breaks_a_tie_within_one_alternative(tmp_path):
    """`prefer` never promotes a later alternative — it only ranks sources inside one."""
    deduped = SORT.replace("lab/sort@1.0.0", "lab/dedup@1.0.0").replace(
        "nf_process: SORT", "nf_process: DEDUP"
    )
    registry, vocabulary = _world(
        tmp_path, {"c.yml": CALLER, "sort.yml": SORT, "dedup.yml": deduped}
    )
    ir = resolve(_goal(), registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)
    # Two identical producers of a coordinate-sorted BAM: a genuine tie, so it is recorded
    # rather than taken silently.
    assert any(d.subject == "producer:alignment.bam" for d in ir.decisions)
