import pytest
from comeni_core.plan.decision import ParamAsked
from mendel_resolver.ports import FlagOnlyResolver, NoCandidatesError


def test_picks_first_candidate_deterministically():
    ambiguity = ParamAsked(
        node_id="star", subject="seq_platform", candidates=["illumina", "nanopore"]
    )
    resolution = FlagOnlyResolver().resolve(ambiguity)
    assert resolution.value == "illumina"
    assert resolution.by == "flag-only"
    assert resolution.confidence == 0.0


def test_reason_names_the_subject_so_the_user_knows_what_to_check():
    ambiguity = ParamAsked(node_id="star", subject="seq_platform", candidates=["illumina"])
    assert "seq_platform" in FlagOnlyResolver().resolve(ambiguity).why


def test_reason_is_true_whether_a_rule_was_absent_or_could_not_apply():
    """Issue 178: *no rule covered* read false beside *a rule that could not apply* (#174),
    where a rule exists and its premise is unknown. The flag-only resolver cannot tell which
    happened, so it says only what it knows."""
    ambiguity = ParamAsked(node_id="star", subject="seq_platform", candidates=["illumina"])
    why = FlagOnlyResolver().resolve(ambiguity).why
    assert "no rule covered" not in why
    assert why.startswith("nothing decided 'seq_platform'")
    assert "without judgement — please review" in why


def test_raises_when_there_is_nothing_to_choose_from():
    with pytest.raises(NoCandidatesError, match="star.seq_platform"):
        FlagOnlyResolver().resolve(
            ParamAsked(node_id="star", subject="seq_platform", candidates=[])
        )


def test_is_deterministic_across_calls():
    ambiguity = ParamAsked(node_id="n", subject="s", candidates=["b", "a", "c"])
    resolver = FlagOnlyResolver()
    assert resolver.resolve(ambiguity).value == resolver.resolve(ambiguity).value == "b"
