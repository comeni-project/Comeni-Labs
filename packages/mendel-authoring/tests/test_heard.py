"""Whether the person said it: a quote of their own words, checked against what they typed
(Part I.0 spec §5.3)."""

from mendel_authoring import heard

TURNS = [(1, "Gene counts from my  Paired-End Illumina reads, 150 bp"), (3, "use HISAT2")]


def test_a_quote_in_a_turn_is_heard_case_and_spacing_folded():
    assert heard.find("paired-end illumina", TURNS) == 1
    assert heard.find("Use hisat2", TURNS) == 3


def test_a_quote_nobody_typed_is_not_heard():
    assert heard.find("single-end", TURNS) is None


def test_a_quote_too_short_to_prove_anything_is_not_heard():
    assert heard.find("15", TURNS) is None
    assert heard.find(None, TURNS) is None
    assert heard.find("   ", TURNS) is None


def test_a_quote_cannot_join_two_turns():
    assert heard.find("150 bp use HISAT2", TURNS) is None


def test_no_turns_hears_nothing():
    assert heard.find("paired-end", []) is None
