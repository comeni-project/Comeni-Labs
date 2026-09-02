from pathlib import Path

from mendel_forge.candidates import for_field
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]


def _stack():
    return layers.load(ROOT / "registry")


def test_a_type_id_hole_offers_every_declared_type():
    found = [c.value for c in for_field("produces[0].type_id", _stack())]
    assert "qc.report" in found
    assert "alignment.bam" in found
    assert found == sorted(found), "candidates must be sorted; output is compared byte-for-byte"


def test_a_roles_hole_offers_every_declared_role():
    found = [c.value for c in for_field("roles", _stack())]
    assert "qc_per_sample" in found


def test_a_state_hole_offers_only_the_states_of_its_own_type():
    """`state` is meaningless without the type it qualifies, and offering every state in
    the vocabulary would invite `coordinate_sorted` on a FASTQ."""
    found = [c.value for c in for_field("produces[0].state", _stack(), type_id="alignment.bam")]
    assert "coordinate_sorted" in found
    assert "trimmed" not in found


def test_a_prose_field_has_no_candidates():
    assert for_field("priority_because", _stack()) == []


def test_an_unknown_field_has_no_candidates_rather_than_raising():
    """A hole for a field nobody anticipated is free text, not a crash. The forge must keep
    working when a contract gains a field before this file knows about it."""
    assert for_field("some_future_field", _stack()) == []


def test_every_candidate_says_where_it_is_declared():
    candidates = for_field("roles", _stack())
    assert candidates, "the stack offered no role candidates — nothing below is exercised"
    for candidate in candidates:
        assert candidate.note, f"{candidate.value} has no note saying where it comes from"
