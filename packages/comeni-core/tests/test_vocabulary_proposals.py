"""A vocabulary plus the types a draft is proposing to add.

**Derived, never mutated.** `with_measurements` is the same shape and the same argument: the
loaded vocabulary is what the registry says, and a caller asking "what if I added these"
must not be able to change that for everybody else.
"""

from comeni_core.declared.vocabulary import Vocabulary


def _base() -> Vocabulary:
    return Vocabulary(types={"alignment.bam": frozenset({"indexed"})})


def test_it_adds_a_type_with_no_states():
    """States are a separate judgement. Inventing them at approval time would be the
    reviewer guessing at a second thing while judging the first."""
    got = _base().with_proposals(["qc.index_stats"])
    assert got.types["qc.index_stats"] == frozenset()


def test_it_leaves_the_original_alone():
    base = _base()
    base.with_proposals(["qc.index_stats"])
    assert "qc.index_stats" not in base.types


def test_a_proposal_never_overwrites_a_declared_type():
    """If the registry already declares it, the registry wins — its states are real and a
    proposal's emptiness is not. A proposal for a declared type is a mistake upstream, and
    silently emptying that type's states would be a very quiet way to break routing."""
    got = _base().with_proposals(["alignment.bam"])
    assert got.types["alignment.bam"] == frozenset({"indexed"})


def test_no_proposals_is_the_same_vocabulary():
    assert _base().with_proposals([]).types == _base().types
