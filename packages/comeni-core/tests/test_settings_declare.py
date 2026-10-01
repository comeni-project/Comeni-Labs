"""Settings: declarations, and the reasons a setting is greyed out (spec §4, §5)."""

import pytest
from comeni_core.settings.reasons import (
    REASON_KINDS,
    Designed,
    Needs,
    Pinned,
    ReadOnlyHere,
    Reason,
)
from pydantic import TypeAdapter, ValidationError


def test_every_reason_says_something_a_person_can_read():
    reasons = [
        Pinned(env="COMENI_AI_MODEL"),
        Designed(where="arrives with the consultant build"),
        Needs(what="choose a connection first"),
        ReadOnlyHere(why="Wiener reads this from its own .env"),
    ]
    assert reasons, "no reasons were built — this test is measuring nothing"
    for reason in reasons:
        assert len(reason.says) > 20, reason
    assert "COMENI_AI_MODEL" in reasons[0].says


def test_the_list_is_closed():
    """A fifth kind is a change to `reasons.py`, never a string somebody invents."""
    assert REASON_KINDS == ("pinned", "designed", "needs", "read_only_here")
    with pytest.raises(ValidationError):
        TypeAdapter(Reason).validate_python({"kind": "because", "why": "x"})


def test_a_reason_round_trips_through_json():
    adapter = TypeAdapter(Reason)
    reason = Needs(what="set COMENI_SETTINGS_KEY")
    assert adapter.validate_json(adapter.dump_json(reason)) == reason
