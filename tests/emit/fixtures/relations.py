"""Fixture contracts for relations between samples (#466, stage 5 part B): no shipped tool has
them yet, so they are proven with these, under Nextflow."""

from pathlib import Path

MEASUREMENT = """declares: measurement
id: {id}
kind: {kind}
description: "{id}, a fixture key"
cite: "a test fixture"
describes: fastq.reads
"""

LAYER = {
    "assembly.family.yml": "declares: family\nid: assembly\n"
                           "description: Genomes assembled from reads\n",
    "assembly.fasta.yml": "declares: vocabulary\nid: assembly.fasta\nstates: []\ngrain: sample\n",
    "assembly.role.yml": "declares: role\nroles:\n  - {id: assembly, explain: Assembles reads.}\n",
    "group.measurement.yml": MEASUREMENT.format(id="group", kind="key"),
    "coassemble.contract.yml": """declares: contract
id: lab/coassemble@1.0.0
nf_process: COASSEMBLE
nf_include: modules/lab/coassemble/main
roles: [assembly]
consumes: [{name: reads, type_id: fastq.reads, many: true, by: group}]
produces: [{name: assembly, type_id: assembly.fasta, format: [fa]}]
nf_inputs: [{ports: [reads]}]
provenance: {source: test, drafted_by: test, approved_by: test, approved_at: "2026-11-12"}
""",
}

COASSEMBLE = """process COASSEMBLE {
    tag "${meta.id}"
    container 'python:3.12-slim'
    input:
    tuple val(meta), path(reads)
    output:
    tuple val(meta), path("*.fa"), emit: assembly
    script:
    "echo ${reads.size()} > ${meta.id}.fa"
    stub:
    "echo ${reads.size()} > ${meta.id}.fa"
}
"""


def layer(tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    root = tmp_path / "relations"
    root.mkdir(exist_ok=True)
    for name, body in {**LAYER, **(extra or {})}.items():
        (root / name).write_text(body)
    return root


def module(out: Path, include: str, source: str) -> None:
    """A fixture module written into a built pipeline: the layer declares no module source."""
    path = out / f"{include}.nf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
