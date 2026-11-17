"""A step says what it does (#511): its job's short label, from the role vocabulary."""

from pathlib import Path

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
    # The lab names the job its own way: a layer above replaces the role, label and all.
    "qc.role.yml": "declares: role\nroles:\n  - id: qc_per_sample\n    label: Check each assembly\n"
                   "    explain: Measure one sample and report on it.\n",
}


def _view(tmp_path: Path):
    layer = tmp_path / "overlay"
    layer.mkdir()
    for name, body in OVERLAY.items():
        (layer / name).write_text(body)
    goal = Goal(have=[GoalInput(type_id="assembly.fasta")], want=["assembly.qc"])
    built = orchestrate.build(goal, registry_roots=[ROOT / "registry", layer])
    [view] = [v for v in step_views(built.pipeline, built.layers) if v.contract_id == QUAST_ID]
    return view


def test_a_step_says_what_it_does_from_its_role(tmp_path):
    assert _view(tmp_path).does == "Check each assembly"


def test_a_measuring_step_is_drawn_under_the_step_it_reads():
    """#517: the canvas's layout hangs a step whose job is measurement under its source."""
    from types import SimpleNamespace as N

    from mendel_api.services.authoring_canvas import _placed

    port = lambda name, side: N(name=name, side=side)  # noqa: E731
    steps = [N(id="faidx", tier=1, measures=False, ports=[port("fasta", "in"), port("fai", "out")]),
             N(id="measure", tier=1, measures=True,
               ports=[port("data", "in"), port("genome_length", "out")])]
    graph = N(edges=[N(from_node="faidx", from_port="fai", to_node="measure", to_port="data")])
    at = _placed(graph, steps)
    assert at["measure"]["x"] == at["faidx"]["x"] and at["measure"]["y"] > at["faidx"]["y"]


def test_a_step_view_says_whether_it_measures(tmp_path):
    assert _view(tmp_path).measures is False
