"""Routing a tool's optional inputs: off unless switched on, and why either way (#460).

QUAST is the case. Its reference (`fasta`) and `gff` are optional; three of its reports exist
only with a reference. A goal that only has assemblies must route QUAST without them.
"""

import pathlib

from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.goal.asked import InputState
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.router import route
from support.paths import ROOT

QUAST = (ROOT / "packages/comeni-core/tests/fixtures/constraints/quast.yml").read_text()

TYPES = {
    "assembly.fasta": "scope: sample\n",
    "genome.fasta": "scope: run\n",
    "annotation.gff": "scope: run\n",
    "qc.report": "",
}


def _world(tmp_path: pathlib.Path, contracts: dict[str, str]) -> tuple[Registry, Vocabulary]:
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    for type_id, extra in TYPES.items():
        (vocab_dir / f"{type_id}.yml").write_text(
            f"declares: vocabulary\nid: {type_id}\nstates: []\n{extra}")
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()
    for name, body in contracts.items():
        (contract_dir / name).write_text("declares: contract\n" + body)
    vocabulary = Vocabulary.load(tmp_path)
    return Registry.load(tmp_path, vocabulary), vocabulary


def _assemblies_only() -> Goal:
    return Goal(have=[GoalInput(type_id="assembly.fasta")], want=["qc.report"])


def test_quast_with_only_assemblies_leaves_its_optional_inputs_off(tmp_path):
    registry, _ = _world(tmp_path, {"quast.yml": QUAST})
    plan = route(_assemblies_only(), registry)
    step = next(s for s in plan.steps if s.contract_id == "nf-core/quast@5.3.0")
    assert [(r.port, r.state, r.by) for r in step.inputs] == [
        ("fasta", InputState.OFF, "router"), ("gff", InputState.OFF, "router")]
    assert all(r.reason == "off: not switched on" for r in step.inputs)
