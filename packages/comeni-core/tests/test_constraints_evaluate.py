"""What a contract allows for one setup: missing, forbidden, produced, and why (#460)."""

from comeni_core import yaml_strict
from comeni_core.declared.constraints import Setup, evaluate, rows_of, sentence
from comeni_core.declared.contract import ModuleContract
from support.paths import ROOT

FIXTURES = ROOT / "packages/comeni-core/tests/fixtures/constraints"


def _contract(name: str) -> ModuleContract:
    data = yaml_strict.load(FIXTURES / f"{name}.yml")
    return ModuleContract.model_validate(data)


GFF_ROW = "`gff` is used only with `fasta` (QUAST reads --features only against a reference (-r))"


def test_quast_with_only_assemblies_produces_the_basic_reports():
    verdict = evaluate(_contract("quast"), Setup(given=frozenset({"consensus"})))
    assert verdict.produced == ["results", "tsv"]
    assert verdict.missing == [] and verdict.forbidden == []


def test_quast_with_a_reference_produces_its_reports():
    verdict = evaluate(_contract("quast"), Setup(given=frozenset({"consensus", "fasta"})))
    assert verdict.produced == ["results", "tsv", "transcriptome", "misassemblies", "unaligned"]


def test_gff_without_fasta_is_missing_fasta_with_its_sentence():
    verdict = evaluate(_contract("quast"), Setup(given=frozenset({"consensus", "gff"})))
    assert verdict.missing == ["fasta"]
    assert verdict.sentences == [GFF_ROW]


def test_a_required_input_left_out_is_missing():
    verdict = evaluate(_contract("quast"), Setup(given=frozenset()))
    assert verdict.missing == ["consensus"]


def test_gatk_dbsnp_without_its_index_is_missing_the_index():
    verdict = evaluate(_contract("gatk4_haplotypecaller"),
                       Setup(given=frozenset({"input", "dbsnp"})))
    assert verdict.missing == ["dbsnp_tbi"]
    both = evaluate(_contract("gatk4_haplotypecaller"),
                    Setup(given=frozenset({"input", "dbsnp", "dbsnp_tbi"})))
    assert both.missing == []


def test_kraken2_fastqs_only_with_the_flag():
    contract = _contract("kraken2")
    given = frozenset({"reads", "db"})
    on = evaluate(contract, Setup(given=given, params={"save_output_fastqs": True}))
    off = evaluate(contract, Setup(given=given, params={"save_output_fastqs": False}))
    assert "classified_reads_fastq" in on.produced
    assert "classified_reads_fastq" not in off.produced


def test_an_unknown_reference_puts_the_gff_rule_at_run_time():
    verdict = evaluate(_contract("quast"), Setup(given=frozenset({"consensus", "gff"}),
                                                 unknown=frozenset({"fasta"})))
    assert verdict.missing == []
    assert verdict.holds_at_run_time == [GFF_ROW]


def test_one_of_forbids_both_and_requires_one():
    contract = ModuleContract.model_validate({
        "id": "nf-core/star/align@2.7.11b", "nf_process": "STAR_ALIGN",
        "nf_include": "modules/nf-core/star/align/main", "roles": ["alignment"],
        "consumes": [{"name": "reads", "type_id": "fastq.reads"},
                     {"name": "index", "type_id": "genome.index.star", "required": False},
                     {"name": "fasta", "type_id": "genome.fasta", "required": False}],
        "nf_inputs": [{"ports": ["reads"]}, {"ports": ["index"], "absent": 2},
                      {"ports": ["fasta"], "absent": 2}],
        "groups": [{"kind": "one_of", "members": ["index", "fasta"],
                    "because": "STAR maps against a prebuilt index or builds one"}],
        "provenance": {"source": "t", "drafted_by": "t", "approved_by": "t",
                       "approved_at": "2026-11-06"},
    })
    both = evaluate(contract, Setup(given=frozenset({"reads", "index", "fasta"})))
    assert both.forbidden == ["fasta"]
    neither = evaluate(contract, Setup(given=frozenset({"reads"})))
    assert neither.missing == ["one of index, fasta"]


def test_rows_and_sentences_are_in_declaration_order():
    rows = rows_of(_contract("gatk4_haplotypecaller"))
    assert [r.requires for r in rows] == [["dbsnp_tbi"], ["dbsnp"]]
    assert sentence(rows[0]) == ("`dbsnp` is used only with `dbsnp_tbi` "
                                 "(the tabix index is read with the VCF it indexes)")


def test_each_group_kind_reads_as_a_sentence():
    from comeni_core.declared.constraints import group_sentence
    from comeni_core.declared.contract import Group

    def of(kind: str) -> str:
        return group_sentence(Group(kind=kind, members=["a", "b"], because="why"))

    assert of("one_of") == "exactly one of `a`, `b` (why)"
    assert of("any_of") == "at least one of `a`, `b` (why)"
    assert of("all_or_none") == "`a` and `b` together, or none of them (why)"


def _salmon_setup(given: set[str], reads: str) -> Setup:
    return Setup(given=frozenset(given), types={"reads": reads})


def test_bam_reads_require_the_transcript_fasta():
    """salmon's alignment mode (#464): the type connected to `reads` decides the inputs."""
    salmon = _contract("salmon_quant")
    assert evaluate(salmon, _salmon_setup({"reads"}, "alignment.bam")).missing == [
        "transcript_fasta"]
    assert evaluate(salmon, _salmon_setup({"reads", "transcript_fasta", "index"},
                                          "alignment.bam")).forbidden == ["index"]
    fastq = evaluate(salmon, _salmon_setup({"reads", "index"}, "fastq.reads"))
    assert fastq.missing == [] and fastq.forbidden == []


def test_a_type_condition_decides_which_output_is_written():
    picard = _contract("picard_markduplicates")
    cram = evaluate(picard, Setup(given=frozenset({"reads", "fasta", "fai"}),
                                  types={"reads": "alignment.cram"}))
    assert cram.produced == ["cram", "metrics"]
    assert cram.missing == []
    bam = evaluate(picard, Setup(given=frozenset({"reads"}), types={"reads": "alignment.bam"}))
    assert bam.produced == ["bam", "metrics"]
