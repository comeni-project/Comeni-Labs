"""The end of the build: what you'll get, what you need to run it, who decided what."""

from mendel_authoring.wrapup import Count, wrap_up


def test_what_youll_get_is_the_goals_want_in_its_familys_words(rnaseq, declared):
    gets = wrap_up(rnaseq(150), declared).gets
    assert [(g.id, g.what.text if g.what else None) for g in gets] == [
        ("counts.matrix", "reads counted per feature")
    ]


def test_what_you_need_to_run_it_is_each_input_channel(rnaseq, declared):
    inputs = wrap_up(rnaseq(150), declared).inputs
    assert [(i.id, i.what.text if i.what else None) for i in inputs] == [
        ("params.input", "raw sequencing reads")
    ]


def test_a_setting_with_no_value_is_left_to_the_run(rnaseq, declared):
    assert wrap_up(rnaseq(150), declared).unset == []
    assert wrap_up(rnaseq(150, strandedness_open=True), declared).unset == [
        "featurecounts.strandedness"
    ]


def test_who_decided_what_counts_every_step_and_setting(rnaseq, declared):
    decided = wrap_up(rnaseq(150, strandedness_open=True), declared).decided
    assert decided == [
        Count(tier=1, source="resolver", count=1),
        Count(tier=2, source="resolver", count=2),
        Count(tier=3, source="resolver", count=1),
        Count(tier=4, source="resolver", count=1),
    ]
