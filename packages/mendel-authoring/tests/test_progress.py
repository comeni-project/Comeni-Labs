"""Where the walk is: the offered step's place in the pipeline as it stands now, and how many of
its steps have a review that still holds. Never a count of proposals made over the session."""

import pytest
from mendel_authoring.progress import OfferProgress, Upcoming, WalkProgress, progress_of
from pydantic import ValidationError

ORDER = ["index", "align", "counts"]


def test_the_first_offer_is_step_one_of_the_plan():
    got = progress_of(ORDER, frozenset(), frozenset(), "index")
    assert got == WalkProgress(reviewed=0, total=3,
                               active=OfferProgress(position=1, total=3, again=False),
                               upcoming=(Upcoming(node="align", position=2),
                                         Upcoming(node="counts", position=3)))


def test_re_review_uses_current_position_not_lifetime_proposals():
    got = progress_of(["index", "align", "counts"], frozenset({"index"}),
                      frozenset({"index", "align", "old_index"}), "align")
    assert got.reviewed == 1 and got.total == 3
    assert got.active == OfferProgress(position=2, total=3, again=True)


def test_a_swap_inserts_a_step_and_moves_the_offer_with_it():
    swapped = ["index", "trim", "align", "counts"]
    got = progress_of(swapped, frozenset({"index"}), frozenset({"index"}), "trim")
    assert got.active == OfferProgress(position=2, total=4, again=False)
    assert got.reviewed == 1 and got.total == 4


def test_reviews_of_removed_steps_do_not_count():
    got = progress_of(ORDER, frozenset({"index", "old_trim"}), frozenset({"index", "old_trim"}),
                      "align")
    assert got.reviewed == 1


def test_a_step_reviewed_twice_counts_once():
    got = progress_of(ORDER, frozenset({"index"}), frozenset({"index"}), "align")
    assert got.reviewed == 1 and got.active.position == 2


def test_a_complete_walk_has_no_active_offer():
    got = progress_of(ORDER, frozenset(ORDER), frozenset(ORDER), None)
    assert got == WalkProgress(reviewed=3, total=3, active=None)


def test_an_empty_plan_is_zero_of_zero():
    assert progress_of([], frozenset(), frozenset(), None) == WalkProgress(reviewed=0, total=0)


def test_an_offer_outside_the_plan_is_refused_not_clamped():
    with pytest.raises(ValueError, match="not in the plan"):
        progress_of(ORDER, frozenset(), frozenset(), "ghost")


def test_a_plan_naming_a_step_twice_is_refused():
    with pytest.raises(ValueError, match="twice"):
        progress_of(["index", "index"], frozenset(), frozenset(), None)


def test_positions_and_counts_are_bounded():
    with pytest.raises(ValidationError):
        OfferProgress(position=4, total=3)
    with pytest.raises(ValidationError):
        OfferProgress(position=0, total=3)
    with pytest.raises(ValidationError):
        WalkProgress(reviewed=4, total=3)


def test_the_steps_after_the_offer_are_named_in_plan_order():
    got = progress_of(["index", "align", "sort", "counts"], frozenset({"index"}), frozenset({"index"}), "align")
    assert got.upcoming == (Upcoming(node="sort", position=3), Upcoming(node="counts", position=4))


def test_nothing_is_upcoming_when_the_offer_is_the_last_step():
    assert progress_of(ORDER, frozenset(), frozenset(), ORDER[-1]).upcoming == ()


def test_nothing_is_upcoming_when_nothing_is_offered():
    """Without an offer there is no "after": a finished or paused walk names no future steps."""
    assert progress_of(ORDER, frozenset({"index"}), frozenset({"index"}), None).upcoming == ()


def test_a_step_still_reviewed_is_not_upcoming_even_when_the_plan_puts_it_later():
    """A swap can insert a step before one already reviewed; the walk will not offer that one
    again, so it is not ahead of the person."""
    got = progress_of(["hisat2_build", "trimgalore", "hisat2_align"], frozenset({"trimgalore"}),
                      frozenset({"trimgalore", "star_genomegenerate"}), "hisat2_build")
    assert got.upcoming == (Upcoming(node="hisat2_align", position=3),)
