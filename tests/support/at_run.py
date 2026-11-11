"""The overlay the run-time decision tests build with. The shipped registry holds the demo itself:
STAR's index size ruled from the genome's length (#461), samtools faidx and the `.fai` parser
that measures it in the run (#217, #465). The overlay holds only what a test varies: a copy of
the rule for a test to edit, a genome_length declared otherwise, or no usable measurer."""

import pathlib

ROOT = pathlib.Path(__file__).parents[2]
STAR = ROOT / "registry/tools/nf-core/star/genomegenerate"
STAR_ID = "nf-core/star/genomegenerate@2.7.11b"
FAIDX_ID = "nf-core/samtools/faidx@1.24"

PARAM = """params:
  - name: sa_index_nbases
    via: ext
    key: args
    template: "--genomeSAindexNbases {value}"
    domain: {kind: integer, minimum: 4, maximum: 14}
    tier_hint: 4
"""

RULE = """declares: rule
version: 1
derives:
  - fact: star_sa_index_nbases
    kind: integer
    source: genome_length
    transform:
      - {op: log2}
      - {op: divide, by: 2}
      - {op: subtract, by: 1}
      - {op: at_most, by: 14}
      - {op: round}
    because: "the suffix-array index scales with the genome"
    cite: "STAR manual 2.7.11b, section 2.2.5"
decisions:
  - decides: {effect: param, of: index_building, name: sa_index_nbases,
              when_implementation: [nf-core/star/genomegenerate@2.7.11b]}
    rows:
      - when: {}
        then: {fact: star_sa_index_nbases}
        because: "STAR's own formula, as nf-core's module computes it"
        cite: "STAR manual 2.7.11b, section 2.2.5"
"""

GENOME_LENGTH = """declares: measurement
id: genome_length
kind: integer
minimum: 1
unit: bp
description: "Total length of the reference genome"
cite: "Ensembl 112 assembly reports"
describes: genome.fasta
"""

FAI_TYPE = """declares: vocabulary
id: genome.fai
states: []
scope: run
"""

FAIDX = f"""declares: contract
id: {FAIDX_ID}
roles: [fasta_indexing]
nf_process: SAMTOOLS_FAIDX
nf_include: modules/nf-core/samtools/faidx/main
consumes: [{{name: fasta, type_id: genome.fasta}}]
produces: [{{name: fai, type_id: genome.fai}}]
params: []
nf_inputs: [{{ports: [fasta]}}]
container: quay.io/biocontainers/samtools:1.21--h50ea8bc_0
provenance: {{source: hand, drafted_by: hand, approved_by: test, approved_at: "2026-11-10"}}
"""

ROLE = """declares: role
roles:
  - id: fasta_indexing
    explain: Indexes a reference sequence so its lengths and regions can be read quickly.
"""

MEASURER = f"""declares: measurer
id: genome_length_fai
version: 1.0.0
measures: genome_length
by: tool
uses: {FAIDX_ID}
output: fai
entry: piece/fai.py
runs: [pipeline]
"""

PARSER = '''"""genome length: the sum of a `.fai`'s second column."""

from comeni_inspect.outcome import Undetermined, Value


def parse(stream, decided):
    total = lines = 0
    for line in stream:
        fields = line.rstrip(b"\\\\n").split(b"\\\\t")
        if len(fields) < 2 or not fields[1].isdigit():
            return Undetermined(reason=f"line {lines + 1} is not a .fai line", evidence={})
        total += int(fields[1])
        lines += 1
    if not lines:
        return Undetermined(reason="no sequences", evidence={})
    return Value(value=total, evidence={"sequences": lines})
'''


UNUSABLE = """declares: measurer
id: genome_length_fai
version: 1.0.0
measures: genome_length
by: tool
uses: nf-core/samtools/faidx@0.0.0
output: fai
entry: piece/fai.py
runs: [pipeline]
"""
"""Replaces the shipped measurer with one whose tool no layer declares: dropped at load
(MD0327), so the stack has no pipeline measurer for genome_length."""


def overlay(root: pathlib.Path, *, with_measurer: bool = True,
            genome_length: str = GENOME_LENGTH) -> pathlib.Path:
    layer = root / "overlay"
    files = {
        "rules/star_index.yml": RULE,
        "vocabulary/measurements/genome_length.yml": genome_length,
    }
    if not with_measurer:
        files["measurers/measures/genome_length_fai/measurer.yml"] = UNUSABLE
        files["measurers/measures/genome_length_fai/piece/fai.py"] = PARSER
    for name, text in files.items():
        path = layer / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return layer
