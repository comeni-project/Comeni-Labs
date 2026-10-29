"""Topics come from nf-core's own keywords and EDAM terms; formats from its file patterns."""

from pathlib import Path

from mendel_forge.model import Channel
from mendel_forge.nfcore.parse import parse_module
from mendel_forge.topics import formats_of, topics_of

FIXTURES = Path(__file__).parent / "fixtures" / "nf-core"


def test_alignment_keyword_gives_alignment():
    assert "alignment" in topics_of(["align", "reference"], [])


def test_an_edam_operation_gives_its_topic():
    assert topics_of([], ["http://edamontology.org/operation_0310"]) == ["assembly"]


def test_no_match_gives_no_topic():
    assert topics_of(["frobnicate"], []) == []


def test_brace_patterns_expand_and_drop_compression():
    assert formats_of([Channel(name="reads", pattern="*.{fastq,fq}.gz")]) == ["fastq", "fq"]


def test_a_pattern_without_an_extension_gives_no_format():
    assert formats_of([Channel(name="index", pattern="star"), Channel(name="x")]) == []


def test_star_align_has_topics_and_formats():
    module = parse_module(FIXTURES / "star" / "align", "star/align")
    assert "alignment" in module.topics
    assert "bam" in module.formats_out
    assert "gtf" in module.formats_in
