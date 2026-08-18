"""Declining a question, through the API's vocabulary."""

import pytest
from mendel_api.services.answers import propose_one


class _Propose:
    def __init__(self):
        self.seen = None

    def __call__(self, req):
        self.seen = req
        from mendel_forge.ops import ProposeResult

        return ProposeResult(name=req.name, field=req.field, remaining=[req.field])


def test_it_records_the_proposal_and_says_the_hole_is_still_open(monkeypatch):
    """A proposal is not a fill. If this ever returns `still_open=False`, the UI will show a
    declined question as settled and a draft that cannot land will look ready."""
    p = _Propose()
    monkeypatch.setattr("mendel_api.services.answers.ops.propose", p)

    got = propose_one(draft="fastqc", subject="produces[0].type_id", id="qc.report.html",
                      description="an HTML QC report", why="nothing declared fits", by="rafael")

    assert got.still_open is True
    assert p.seen.id == "qc.report.html"
    assert p.seen.by == "rafael"


def test_a_reason_is_required(monkeypatch):
    monkeypatch.setattr("mendel_api.services.answers.ops.propose", _Propose())
    with pytest.raises(ValueError, match="reason"):
        propose_one(draft="fastqc", subject="roles", id="x", description="y", why=" ",
                    by="rafael")


def test_a_description_is_required(monkeypatch):
    """A proposal with no description is a name nobody can review, and the reviewer in phase 3
    has only this text to judge by."""
    monkeypatch.setattr("mendel_api.services.answers.ops.propose", _Propose())
    with pytest.raises(ValueError, match="description"):
        propose_one(draft="fastqc", subject="roles", id="x", description="  ", why="w",
                    by="rafael")


def test_an_absent_author_falls_back(monkeypatch):
    p = _Propose()
    monkeypatch.setattr("mendel_api.services.answers.ops.propose", p)
    monkeypatch.setattr("mendel_api.services.answers.default_author", lambda: "rafael")
    propose_one(draft="fastqc", subject="roles", id="x", description="y", why="w", by=None)
    assert p.seen.by == "rafael"
