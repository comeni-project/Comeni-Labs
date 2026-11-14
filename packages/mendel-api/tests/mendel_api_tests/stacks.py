"""Layer stacks for tests that need a tool the curated registry does not have."""

from mendel_resolver import layers
from support.paths import ROOT

QUAST = (ROOT / "packages/comeni-core/tests/fixtures/constraints/quast.yml").read_text()
ASSEMBLY_OVERLAY = {
    "assembly.family.yml": "declares: family\nid: assembly\ndescription: Assembled genomes\n",
    "assembly.fasta.yml": "declares: vocabulary\nid: assembly.fasta\nstates: []\ngrain: sample\n",
    "annotation.gff.yml": "declares: vocabulary\nid: annotation.gff\nstates: []\ngrain: study\n",
    "qc.report.yml": "declares: vocabulary\nid: qc.report\nstates: [aggregated, assembly]\n",
    "quast.contract.yml": "declares: contract\n" + QUAST.replace(
        "type_id: qc.report", "type_id: qc.report::assembly"),
}


def with_quast(tmp_path):
    """The curated registry plus QUAST, whose reports compete with FastQC's `qc.report`."""
    layer = tmp_path / "overlay"
    layer.mkdir()
    for name, body in ASSEMBLY_OVERLAY.items():
        (layer / name).write_text(body)
    return layers.load([ROOT / "registry", layer])
