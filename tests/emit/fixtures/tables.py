"""Fixture contracts for a second table (#466, stage 6 part B): no shipped tool profiles samples
against a table of databases yet, so they are proven with these, under Nextflow."""

from pathlib import Path

PROVENANCE = ('provenance: {source: test, drafted_by: test, approved_by: test, '
              'approved_at: "2026-11-13"}\n')

LAYER = {
    "database.family.yml": "declares: family\nid: database\ndescription: Reference databases\n",
    "database.index.yml": "declares: vocabulary\nid: database.index\nstates: []\ngrain: study\n",
    "profile.family.yml": "declares: family\nid: profile\ndescription: Taxonomic profiles\n",
    "profile.tsv.yml": "declares: vocabulary\nid: profile.tsv\nstates: []\ngrain: sample\n",
    "profiling.role.yml": "declares: role\nroles:\n"
                          "  - {id: profiling, explain: Profiles reads against a database.}\n",
    "db_type.measurement.yml": """declares: measurement
id: db_type
kind: enum
values: [short, long]
description: "the reads a database is built for, a fixture"
cite: "a test fixture"
describes: database.index
""",
    "profile.contract.yml": """declares: contract
id: lab/profile@1.0.0
nf_process: PROFILE
nf_include: modules/lab/profile/main
roles: [profiling]
consumes:
  - {name: reads, type_id: fastq.reads}
  - {name: db, type_id: database.index}
produces: [{name: profile, type_id: profile.tsv, format: [tsv]}]
nf_inputs: [{ports: [reads]}, {ports: [db]}]
""" + PROVENANCE,
}

PROFILE = """process PROFILE {
    tag "${meta.id}"
    container 'python:3.12-slim'
    input:
    tuple val(meta), path(reads)
    tuple val(meta2), path(db)
    output:
    tuple val(meta), path("*.tsv"), emit: profile
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    "echo ${meta.id} ${meta.database.id} ${meta2.id} > ${prefix}.tsv"
    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    "echo ${meta.id} ${meta.database.id} ${meta2.id} > ${prefix}.tsv"
}
"""

MODULES = {"modules/lab/profile/main": PROFILE}

# The database port reads only short-read databases.
SHORT_ONLY = LAYER["profile.contract.yml"].replace(
    "{name: db, type_id: database.index}", "{name: db, type_id: database.index, "
    "select: {db_type: short}}")


def layer(tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    root = tmp_path / "tables"
    root.mkdir(parents=True, exist_ok=True)
    for name, body in {**LAYER, **(extra or {})}.items():
        (root / name).write_text(body)
    return root


def modules(out: Path) -> None:
    for include, source in MODULES.items():
        path = out / f"{include}.nf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
