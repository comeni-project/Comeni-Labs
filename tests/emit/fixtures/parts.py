"""Fixture contracts for parts (#466, stage 6 part A): no shipped tool splits a sample or merges
its parts yet, so they are proven with these, under Nextflow."""

from pathlib import Path

PROVENANCE = 'provenance: {source: test, drafted_by: test, approved_by: test, approved_at: "2026-11-13"}\n'

LAYER = {
    "hits.family.yml": "declares: family\nid: hits\ndescription: Hits of reads in a genome\n",
    "hits.tsv.yml": "declares: vocabulary\nid: hits.tsv\nstates: []\ngrain: sample\n",
    "parts.role.yml": "declares: role\nroles:\n"
                      "  - {id: splitting, explain: Splits an item into parts.}\n"
                      "  - {id: searching, explain: Searches reads in a genome.}\n",
    "split.contract.yml": """declares: contract
id: lab/split_reads@1.0.0
nf_process: SPLIT_READS
nf_include: modules/lab/split_reads/main
roles: [splitting]
consumes: [{name: reads, type_id: fastq.reads}]
produces: [{name: reads, type_id: fastq.reads, fans_out: part}]
nf_inputs: [{ports: [reads]}]
""" + PROVENANCE,
    "search.contract.yml": """declares: contract
id: lab/search@1.0.0
nf_process: SEARCH
nf_include: modules/lab/search/main
roles: [searching]
consumes:
  - {name: reads, type_id: fastq.reads, parts: true}
  - {name: genome, type_id: genome.fasta}
produces: [{name: hits, type_id: hits.tsv, format: [tsv]}]
nf_inputs: [{ports: [reads]}, {ports: [genome]}]
""" + PROVENANCE,
    "merge.contract.yml": """declares: contract
id: lab/merge_hits@1.0.0
nf_process: MERGE_HITS
nf_include: modules/lab/merge_hits/main
roles: [merging]
consumes: [{name: hits, type_id: hits.tsv, many: true, grain: sample}]
produces: [{name: hits, type_id: hits.tsv, format: [tsv]}]
nf_inputs: [{ports: [hits]}]
""" + PROVENANCE,
}

# The splitter makes one part of a sample whose name ends in `_one`, and three of any other.
SPLIT_READS = """process SPLIT_READS {
    tag "${meta.id}"
    container 'python:3.12-slim'
    input:
    tuple val(meta), path(reads)
    output:
    tuple val(meta), path("part_*.fq"), emit: reads
    script:
    def n = meta.id.endsWith('_one') ? 1 : 3
    "for i in \\$(seq 1 ${n}); do echo ${meta.id}.\\$i > part_\\$i.fq; done"
    stub:
    def n = meta.id.endsWith('_one') ? 1 : 3
    "for i in \\$(seq 1 ${n}); do echo ${meta.id}.\\$i > part_\\$i.fq; done"
}
"""

SEARCH = """process SEARCH {
    tag "${meta.id}"
    container 'python:3.12-slim'
    input:
    tuple val(meta), path(reads)
    path genome
    output:
    tuple val(meta), path("*.tsv"), emit: hits
    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    "cat ${reads} > ${prefix}.tsv"
    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    "cat ${reads} > ${prefix}.tsv"
}
"""

MERGE_HITS = """process MERGE_HITS {
    tag "${meta.id}"
    container 'python:3.12-slim'
    input:
    tuple val(meta), path(hits, stageAs: '?/*')
    output:
    tuple val(meta), path("*.merged.tsv"), emit: hits
    script:
    "cat ${hits} | sort > ${meta.id}.merged.tsv"
    stub:
    "cat ${hits} | sort > ${meta.id}.merged.tsv"
}
"""

MODULES = {"modules/lab/split_reads/main": SPLIT_READS, "modules/lab/search/main": SEARCH,
           "modules/lab/merge_hits/main": MERGE_HITS}


def layer(tmp_path: Path, extra: dict[str, str] | None = None,
          without: tuple[str, ...] = ()) -> Path:
    root = tmp_path / "parts"
    root.mkdir(parents=True, exist_ok=True)
    for name, body in {**LAYER, **(extra or {})}.items():
        if name not in without:
            (root / name).write_text(body)
    return root


def modules(out: Path) -> None:
    """The fixture modules written into a built pipeline: the layer declares no module source."""
    for include, source in MODULES.items():
        path = out / f"{include}.nf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
