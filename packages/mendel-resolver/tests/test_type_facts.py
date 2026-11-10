"""Routing with the type connected to a port (#464).

salmon quant is the case: FASTQ reads are mapped against an index; BAM reads are quantified in
alignment mode against the transcripts, and the index is forbidden. The rows say so on
`type.reads`, so which inputs a step needs depends on what routing connected.
"""

import pathlib

from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.goal.asked import InputState
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from mendel_resolver.router import route
from mendel_resolver.rules import RuleTable
from support.paths import ROOT

SALMON = (ROOT / "packages/comeni-core/tests/fixtures/constraints/salmon_quant.yml").read_text()
SALMON_ID = "nf-core/salmon/quant@1.10.3"

TYPES = {
    "fastq.reads": "scope: sample\n",
    "alignment.bam": "scope: sample\n",
    "salmon.index": "scope: run\n",
    "annotation.gtf": "scope: run\n",
    "transcripts.fasta": "scope: run\n",
    "salmon.quant": "scope: sample\n",
}


def _world(tmp_path: pathlib.Path) -> tuple[Registry, Vocabulary]:
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    for type_id, extra in TYPES.items():
        (vocab_dir / f"{type_id}.yml").write_text(
            f"declares: vocabulary\nid: {type_id}\nstates: []\n" + extra)
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()
    (contract_dir / "salmon.yml").write_text("declares: contract\n" + SALMON)
    vocabulary = Vocabulary.load(tmp_path)
    return Registry.load(tmp_path, vocabulary), vocabulary


def _states(plan) -> dict[str, InputState]:
    step = next(s for s in plan.steps if s.contract_id == SALMON_ID)
    return {r.port: r.state for r in step.inputs}


def _goal(*have: str) -> Goal:
    return Goal(have=[GoalInput(type_id=t) for t in have], want=["salmon.quant"])


def test_bam_reads_switch_on_salmons_transcript_fasta(tmp_path):
    registry, vocabulary = _world(tmp_path)
    goal = _goal("alignment.bam", "transcripts.fasta")
    states = _states(route(goal, registry))
    assert states["transcript_fasta"] is InputState.REQUIRED
    assert states["index"] is InputState.OFF
    ir = resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)
    node = next(n for n in ir.nodes if n.contract_id == SALMON_ID)
    assert {r.port: r.state for r in node.inputs}["transcript_fasta"] is InputState.REQUIRED


def test_fastq_reads_need_salmons_index(tmp_path):
    registry, vocabulary = _world(tmp_path)
    goal = _goal("fastq.reads", "salmon.index")
    states = _states(route(goal, registry))
    assert states["index"] is InputState.REQUIRED
    assert states["transcript_fasta"] is InputState.OFF
    resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)


def test_an_index_with_bam_reads_is_refused_with_the_reason(tmp_path):
    """Alignment mode forbids the index: a person switching it on is told why at build."""
    import pytest
    from comeni_core.goal.asked import Constraints, InputChoice
    from mendel_resolver.router import ConstraintViolation

    registry, vocabulary = _world(tmp_path)
    goal = Goal(have=[GoalInput(type_id=t) for t in ("alignment.bam", "transcripts.fasta",
                                                     "salmon.index")],
                want=["salmon.quant"],
                constraints=Constraints(inputs=[InputChoice(contract=SALMON_ID, port="index",
                                                            state=InputState.REQUIRED)]))
    with pytest.raises(ConstraintViolation, match="MD0610.*index.*alignment.bam"):
        resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)
