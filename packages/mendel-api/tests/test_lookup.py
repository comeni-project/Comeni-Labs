"""What a type is, and who already uses it.

The lookup panel is a DECISION AID rather than a dictionary: "7 contracts consume this"
answers "is this the normal choice" in a way a description cannot. That is the same argument
`CLAUDE.md` makes for why there is no vector store — exact retrieval, versioned and diffable.
"""

import pytest
from mendel_api.services import lookup


def test_it_reports_a_type_s_states_in_a_stable_order():
    """`vocabulary.types[id]` is a FROZENSET, which has no stable order. This repo has
    shipped that bug before — `IREdge.states` carries a serialiser for it — so the payload
    is a sorted list and a test says so."""
    card = lookup.type_("alignment.bam")
    assert card.states == sorted(card.states)
    assert "coordinate_sorted" in card.states


def test_it_names_who_produces_and_who_consumes():
    card = lookup.type_("alignment.bam")
    assert card.produced_by, "something must produce a BAM in this registry"
    assert card.produced_by == sorted(card.produced_by)


def test_a_type_nobody_declared_is_refused_rather_than_empty():
    """An empty card for an unknown id is indistinguishable from a declared type nobody
    uses, and those are different problems."""
    with pytest.raises(ValueError, match="MD0001|not declared|unknown"):
        lookup.type_("nonsense.type")
