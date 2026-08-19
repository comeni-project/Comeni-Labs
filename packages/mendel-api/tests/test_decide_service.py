"""Deciding a proposal through the API's vocabulary."""

import pytest
from mendel_api.services.answers import decide_proposal
from mendel_forge.scaffold import Decision


class _Decide:
    def __init__(self, value: str | None = "qc.index_stats"):
        self.seen = None
        self.value = value

    def __call__(self, req):
        self.seen = req
        from mendel_forge.ops import DecideResult

        return DecideResult(
            name=req.name, field=req.field, decision=req.decision,
            value=self.value, remaining=["roles"],
        )


def test_approving_reports_what_was_written(monkeypatch):
    d = _Decide()
    monkeypatch.setattr("mendel_api.services.answers.ops.decide", d)

    got = decide_proposal(draft="fastqc", subject="produces[0].type_id",
                          decision=Decision.APPROVED, id=None, why="real output", by="reviewer")

    assert got.value == "qc.index_stats"
    assert got.still_open is False


def test_rejecting_says_the_hole_is_open_again(monkeypatch):
    """The UI must not remove the row. `still_open` is the payload saying so, the same field
    `propose_one` returns and for the same reason."""
    d = _Decide(value=None)
    monkeypatch.setattr("mendel_api.services.answers.ops.decide", d)

    got = decide_proposal(draft="fastqc", subject="produces[0].type_id",
                          decision=Decision.REJECTED, id=None, why="a measurement", by="r")

    assert got.value is None
    assert got.still_open is True


def test_a_reason_is_required(monkeypatch):
    """A rejection with no reason is the one that wastes the next reviewer's time."""
    monkeypatch.setattr("mendel_api.services.answers.ops.decide", _Decide())
    with pytest.raises(ValueError, match="reason"):
        decide_proposal(draft="fastqc", subject="roles", decision=Decision.REJECTED,
                        id=None, why="  ", by="r")


def test_an_absent_author_falls_back(monkeypatch):
    d = _Decide()
    monkeypatch.setattr("mendel_api.services.answers.ops.decide", d)
    monkeypatch.setattr("mendel_api.services.answers.default_author", lambda: "rafael")
    decide_proposal(draft="fastqc", subject="roles", decision=Decision.APPROVED,
                    id=None, why="w", by=None)
    assert d.seen.by == "rafael"
