"""The engine's findings on type questions (#452): advice for the person, never a decision."""

from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.checks import arrival, channel_formats, findings, type_format
from mendel_forge.model import Channel

QUAST = ModuleSpec.of("""
process QUAST {
    input:
    tuple val(meta) , path(consensus)
    tuple val(meta2), path(fasta)
    tuple val(meta3), path(gff)

    output:
    tuple val(meta), path("${prefix}.tsv"), emit: results

    script:
    ""
}
""")
SCOPES = {"genome.fasta": "run", "annotation.gtf": "run"}


def _asked(**suggested: str) -> dict[str, dict]:
    return {f"questions:input_type:{name}": {"asks": "?", "suggested": type_id,
                                             "options": [{"id": type_id}]}
            for name, type_id in suggested.items()}


def test_the_meta_name_says_how_an_input_arrives():
    assert arrival(QUAST, "consensus") == "sample"
    assert arrival(QUAST, "fasta") == arrival(QUAST, "gff") == "run"
    assert arrival(ModuleSpec.of("process P {\n    input:\n    path(x)\n\n    output:\n"
                                 "    path('y'), emit: y\n\n    script:\n    ''\n}"), "x") is None


def test_quasts_walk_suggestions_are_each_flagged():
    """The GPU walk (#412): genome.fasta for both, annotation.gtf for a gff input."""
    asked = _asked(consensus="genome.fasta", fasta="genome.fasta", gff="annotation.gtf")
    found = findings({}, SCOPES, QUAST, {}, asked)
    codes = {key.rsplit(":", 1)[1]: sorted(f.code for f in fs) for key, fs in found.items()}
    assert codes == {"consensus": ["MF0520", "MF0521"], "fasta": ["MF0521"], "gff": ["MF0522"]}
    assert "one per sample" in found["questions:input_type:consensus"][0].says


def test_the_right_answers_draw_no_finding():
    asked = _asked(consensus="assembly.fasta", fasta="genome.fasta", gff="annotation.gff")
    assert findings({}, SCOPES, QUAST, {}, asked) == {}


def test_an_answer_counts_over_the_suggestion():
    asked = _asked(consensus="genome.fasta", fasta="genome.fasta")
    items = {"questions:input_type:consensus": {"choice": "assembly.fasta"}}
    assert findings(items, SCOPES, QUAST, {}, asked) == {}


def test_a_pattern_names_the_format_before_the_name_does():
    assert channel_formats(Channel(name="gff", pattern="*.{gtf,gtf.gz}"), "gff") == {"gtf"}
    assert channel_formats(None, "gff") == {"gff"}
    assert channel_formats(None, "consensus") == set()
    assert type_format("fastq.reads") == "fastq" and type_format("qc.report") is None
