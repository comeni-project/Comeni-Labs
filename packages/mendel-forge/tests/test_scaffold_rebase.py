"""The forge's types are the shared ones now, and the container still owns the blocking.

Plan 2.5. `Hole` and `FilledValue` were the forge's own vocabulary for a question and an
answer; the build path had a second one. These assert the seam is where the spec put it —
shared shape, unshared behaviour.
"""

from comeni_core.review import Answer, Question, ValueSource
from mendel_forge.scaffold import FilledValue, Hole


def test_a_hole_is_a_question():
    assert issubclass(Hole, Question)


def test_a_filled_value_is_an_answer():
    assert issubclass(FilledValue, Answer)


def test_a_hole_keeps_what_is_genuinely_its_own():
    """`after` orders holes whose candidates depend on another's answer; the resolver ladder
    handles that itself. `channels` is nf-core vocabulary. Neither belongs on the base."""
    own = set(Hole.model_fields) - set(Question.model_fields)
    assert own == {"after", "channels"}


def test_a_filled_value_adds_nothing_to_the_answer():
    """A signal that the base is drawn at about the right place — spec §4.2."""
    assert set(FilledValue.model_fields) == set(Answer.model_fields)


def test_the_scaffold_still_owns_the_blocking(incomplete_scaffold):
    """Spec §3.1: the guarantee is that the container refuses, not that the hole knows.

    A `blocks` field or a `blocks()` method on the type would trade a structural property
    for a runtime check, which is the mistake CLAUDE.md records about invariant 1.
    """
    assert not incomplete_scaffold.is_complete()
    assert not hasattr(Hole, "blocks")


def test_filler_is_gone():
    import mendel_forge.scaffold as scaffold

    assert not hasattr(scaffold, "Filler")


def test_a_hand_fill_is_recorded_as_human(incomplete_scaffold):
    """`HAND` folded into `HUMAN`. Same fact, one name."""
    hole = incomplete_scaffold.holes[0]
    filled = incomplete_scaffold.fill(
        hole.subject, ["qc_per_sample"], ValueSource.HUMAN, by="rafael", why="because"
    )
    assert filled.filled[hole.subject].how is ValueSource.HUMAN
