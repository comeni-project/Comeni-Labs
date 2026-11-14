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


PAIRS = {
    "calls.family.yml": "declares: family\nid: calls\ndescription: Variant calls\n",
    "calls.vcf.yml": "declares: vocabulary\nid: calls.vcf\nstates: []\ngrain: sample\n",
    "calling.role.yml": "declares: role\nroles:\n  - {id: calling, explain: Calls variants.}\n",
    "patient.measurement.yml": MEASUREMENT.format(id="patient", kind="key"),
    "status.measurement.yml": MEASUREMENT.format(id="status", kind="enum")
    + "values: [tumor, normal]\n",
    "pair.contract.yml": """declares: contract
id: lab/pair_call@1.0.0
nf_process: PAIR_CALL
nf_include: modules/lab/pair_call/main
roles: [calling]
consumes:
  - {name: tumour, type_id: fastq.reads, select: {status: tumor}}
  - {name: normal, type_id: fastq.reads, select: {status: normal}}
produces: [{name: calls, type_id: calls.vcf, format: [vcf]}]
nf_inputs: [{ports: [tumour, normal], join: by_key, key: patient}]
provenance: {source: test, drafted_by: test, approved_by: test, approved_at: "2026-11-12"}
""",
}

PAIR_CALL = """process PAIR_CALL {
    tag "${meta.patient}"
    container 'python:3.12-slim'
    input:
    tuple val(meta), path(tumour), path(normal)
    output:
    tuple val(meta), path("*.vcf"), emit: calls
    script:
    "touch ${meta.patient}.vcf"
    stub:
    "touch ${meta.patient}.vcf"
}
"""

CHIP = {
    "peaks.family.yml": "declares: family\nid: peaks\ndescription: Peaks called on reads\n",
    "peaks.bed.yml": "declares: vocabulary\nid: peaks.bed\nstates: []\ngrain: sample\n",
    "peaks.role.yml": "declares: role\nroles:\n  - {id: peak_calling, explain: Calls peaks.}\n",
    "control.measurement.yml": MEASUREMENT.format(id="control", kind="sample_ref"),
    "peaks.contract.yml": """declares: contract
id: lab/peaks@1.0.0
nf_process: PEAKS
nf_include: modules/lab/peaks/main
roles: [peak_calling]
consumes:
  - {name: chip, type_id: fastq.reads, select: {control: present}}
  - {name: control, type_id: fastq.reads}
produces: [{name: peaks, type_id: peaks.bed, format: [bed]}]
nf_inputs: [{ports: [chip, control], join: by_ref, key: control}]
provenance: {source: test, drafted_by: test, approved_by: test, approved_at: "2026-11-12"}
""",
}

PEAKS = """process PEAKS {
    tag "${meta.id}"
    container 'python:3.12-slim'
    input:
    tuple val(meta), path(chip), path(control, stageAs: 'control/*')
    output:
    tuple val(meta), path("*.bed"), emit: peaks
    script:
    "touch ${meta.id}.bed"
    stub:
    "touch ${meta.id}.bed"
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
