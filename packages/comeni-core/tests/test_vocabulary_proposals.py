"""Derive proposed types without mutating or weakening the loaded vocabulary."""

from comeni_core.declared.vocabulary import Vocabulary


def _base() -> Vocabulary:
    return Vocabulary(types={"alignment.bam": frozenset({"indexed"})})


def test_it_adds_a_type_with_no_states():
    """A proposal introduces an ID but does not invent states."""
    got = _base().with_proposals(["qc.index_stats"])
    assert got.types["qc.index_stats"] == frozenset()


def test_it_leaves_the_original_alone():
    base = _base()
    base.with_proposals(["qc.index_stats"])
    assert "qc.index_stats" not in base.types


def test_a_proposal_never_overwrites_a_declared_type():
    """A proposal cannot replace the states of an existing declaration."""
    got = _base().with_proposals(["alignment.bam"])
    assert got.types["alignment.bam"] == frozenset({"indexed"})


def test_no_proposals_is_the_same_vocabulary():
    assert _base().with_proposals([]).types == _base().types
