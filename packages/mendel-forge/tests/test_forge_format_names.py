"""One name for a format, and a mention kept apart from a declaration."""

from mendel_forge.model import Channel
from mendel_forge.topics import canonical, mentioned


def test_a_formats_other_spellings_fold_into_one():
    assert canonical(["fa", "fna", "fasta"]) == ["fasta"]
    assert canonical(["fq"]) == ["fastq"]
    assert canonical(["sam", "bam"]) == ["bam"]
    assert canonical(["gff3", "gtf"]) == ["gff"]
    assert canonical(["bcf"]) == ["vcf"]
    assert canonical(["csv", "tsv"]) == ["table"]
    assert canonical(["html", "pdf"]) == ["report"]


def test_a_format_with_no_other_name_stays_itself_and_the_result_is_sorted():
    assert canonical(["log", "cram", "h5ad"]) == ["cram", "h5ad", "log"]


def test_a_description_can_mention_a_format_nobody_declared():
    reads = Channel(name="reads", description="List of input FastQ files of size 1 and 2.")
    assert mentioned([reads], declared=[]) == ["fastq"]


def test_a_declared_format_is_not_also_a_mention():
    reads = Channel(name="reads", description="Input FastQ files.")
    assert mentioned([reads], declared=["fastq"]) == []


def test_a_word_inside_another_word_is_not_a_mention():
    channel = Channel(name="x", description="Embedded fragments of a sample bedrock.")
    assert mentioned([channel], declared=[]) == []
