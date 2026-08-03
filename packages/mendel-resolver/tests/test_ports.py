import pytest
from comeni_core.decision import Ambiguity
from mendel_resolver.ports import FlagOnlyResolver, NoCandidatesError


def test_picks_first_candidate_deterministically():
    ambiguity = Ambiguity(
        node_id="star", subject="seq_platform", candidates=["illumina", "nanopore"]
    )
    resolution = FlagOnlyResolver().resolve(ambiguity)
    assert resolution.chosen == "illumina"
    assert resolution.resolved_by == "flag-only"
    assert resolution.confidence == 0.0


def test_reason_names_the_subject_so_the_user_knows_what_to_check():
    ambiguity = Ambiguity(node_id="star", subject="seq_platform", candidates=["illumina"])
    assert "seq_platform" in FlagOnlyResolver().resolve(ambiguity).reason


def test_raises_when_there_is_nothing_to_choose_from():
    with pytest.raises(NoCandidatesError, match="star.seq_platform"):
        FlagOnlyResolver().resolve(
            Ambiguity(node_id="star", subject="seq_platform", candidates=[])
        )


def test_is_deterministic_across_calls():
    ambiguity = Ambiguity(node_id="n", subject="s", candidates=["b", "a", "c"])
    resolver = FlagOnlyResolver()
    assert resolver.resolve(ambiguity).chosen == resolver.resolve(ambiguity).chosen == "b"
