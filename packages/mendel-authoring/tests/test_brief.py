"""A step's card: four fields, each from declared data or the resolver's record, as written."""

from mendel_authoring.brief import OPEN_STEP, Source, brief_of, tool_of


def _step(blueprint, node):
    return blueprint.step(node)


def test_the_tool_is_the_contract_ids_first_two_segments():
    assert tool_of("nf-core/star/align@1.11.0") == "nf-core/star"
    assert tool_of("nf-core/fastqc@0.12.1") == "nf-core/fastqc"


def test_does_is_the_tools_own_description(rnaseq, declared):
    brief = brief_of(_step(rnaseq(150), "star_align"), declared)
    assert brief.does is not None
    assert brief.does.text == "STAR aligns RNA-seq reads to a genome, splice-aware."
    assert brief.does.source is Source.CURATED


def test_a_tool_with_no_description_gets_no_does(rnaseq, declared):
    assert brief_of(_step(rnaseq(150), "multiqc"), declared).does is None


def test_why_is_the_resolvers_reason_then_the_rule_behind_it(rnaseq, declared):
    why = brief_of(_step(rnaseq(150), "star_align"), declared).why
    assert [w.text for w in why] == [
        "read length 150 ≥ 100: STAR",
        "read length decides which aligner is appropriate (Dobin et al. 2013)",
    ]
    assert {w.source for w in why} == {Source.ENGINE}


def test_why_without_a_rule_is_the_reason_alone(rnaseq, declared):
    why = brief_of(_step(rnaseq(150), "fastqc"), declared).why
    assert [w.text for w in why] == ["the only contract producing qc.report"]


def test_makes_names_each_family_once(rnaseq, declared):
    """STAR makes alignment.bam and alignment.bai: one family, said once."""
    makes = brief_of(_step(rnaseq(150), "star_align"), declared).makes
    assert [m.text for m in makes] == ["reads placed on a reference"]
    assert makes[0].source is Source.CURATED


def test_tier_three_checks_the_measured_premise(rnaseq, declared):
    check = brief_of(_step(rnaseq(150), "star_align"), declared).check
    assert [c.text for c in check] == [
        "read_length is 150, measured by fastq@1.1.0 + read_length@1.0.0"
    ]


def test_tier_four_checks_the_open_question(rnaseq, declared):
    check = brief_of(_step(rnaseq(None), "star_align"), declared).check
    assert [c.text for c in check] == [OPEN_STEP]


def test_a_tier_four_setting_is_checked_by_name(rnaseq, declared):
    check = brief_of(_step(rnaseq(150, strandedness_open=True), "featurecounts"), declared).check
    assert [c.text for c in check] == ["no rule decided strandedness"]


def test_tiers_one_and_two_have_nothing_to_check(rnaseq, declared):
    assert brief_of(_step(rnaseq(150), "fastqc"), declared).check == []
    assert brief_of(_step(rnaseq(150), "featurecounts"), declared).check == []
