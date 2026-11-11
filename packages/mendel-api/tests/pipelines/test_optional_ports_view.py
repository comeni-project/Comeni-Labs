"""A step's optional inputs on the canvas (#460): each says it is optional, what state it is in
and why, and what it adds; a conditional output says when it is written."""

from pathlib import Path

from comeni_core.goal.asked import Constraints, InputChoice, InputState
from mendel_api.services.build import step_views
from mendel_compiler import orchestrate
from mendel_resolver.goal import Goal, GoalInput
from support.paths import ROOT

QUAST = (ROOT / "packages/comeni-core/tests/fixtures/constraints/quast.yml").read_text()
QUAST_ID = "nf-core/quast@5.3.0"
OVERLAY = {
    "assembly.family.yml": "declares: family\nid: assembly\ndescription: assemblies\n",
    "assembly.fasta.yml": "declares: vocabulary\nid: assembly.fasta\nstates: []\ngrain: sample\n",
    "assembly.qc.yml": "declares: vocabulary\nid: assembly.qc\nstates: []\ngrain: sample\n",
    "annotation.gff.yml": "declares: vocabulary\nid: annotation.gff\nstates: []\ngrain: study\n",
    "quast.contract.yml": "declares: contract\n" + QUAST.replace("type_id: qc.report",
                                                                 "type_id: assembly.qc"),
}


def _ports(tmp_path: Path, *choices: tuple[str, InputState]) -> dict:
    layer = tmp_path / "overlay"
    layer.mkdir()
    for name, body in OVERLAY.items():
        (layer / name).write_text(body)
    have = ["assembly.fasta"] + (["genome.fasta"] if choices else [])
    goal = Goal(have=[GoalInput(type_id=t) for t in have], want=["assembly.qc"],
                constraints=Constraints(inputs=[InputChoice(contract=QUAST_ID, port=p, state=s)
                                                for p, s in choices]))
    built = orchestrate.build(goal, registry_roots=[ROOT / "registry", layer])
    [view] = [v for v in step_views(built.pipeline, built.layers)
              if v.contract_id == QUAST_ID]
    return {(p.side, p.name): p for p in view.ports}


def test_an_off_optional_input_says_so_and_what_it_adds(tmp_path):
    fasta = _ports(tmp_path)[("in", "fasta")]
    assert (fasta.optional, fasta.state, fasta.reason) == (True, "off", "off: not switched on")
    assert fasta.adds == ["transcriptome", "misassemblies", "unaligned"]


def test_a_switched_on_input_carries_its_state(tmp_path):
    ports = _ports(tmp_path, ("fasta", InputState.OPTIONAL))
    assert ports[("in", "fasta")].state == "optional"
    assert ports[("in", "consensus")].optional is False
    assert ports[("out", "misassemblies")].only == "only with fasta"
    assert ports[("out", "results")].only is None
