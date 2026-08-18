"""Answering one question, without HTTP.

The logic is here rather than in the route so it can be tested directly — that separation is
what the no-logic-in-handlers rule buys, and it is why these tests are fast and specific.
"""

import pytest
from mendel_api.services.answers import answer_one


class _Fill:
    """Stands in for ops.fill, and records exactly what it was handed."""

    def __init__(self, remaining=()):
        self.seen = None
        self._remaining = list(remaining)

    def __call__(self, req):
        self.seen = req
        from mendel_forge.ops import FillResult

        return FillResult(name=req.name, field=req.field, remaining=self._remaining)


def test_it_answers_and_reports_what_is_left(monkeypatch):
    fill = _Fill(remaining=["roles"])
    monkeypatch.setattr("mendel_api.services.answers.ops.fill", fill)

    got = answer_one(draft="fastqc", subject="consumes[0].type_id",
                     value="fastq.reads", why="it reads FASTQs", by="rafael")

    assert got.draft == "fastqc"
    assert got.remaining == ["roles"]


def test_the_question_s_subject_becomes_the_forge_s_field(monkeypatch):
    """`OpenQuestion.subject` and `FillRequest.field` are the same thing under two names.
    The service is where they meet; letting `subject` leak into the forge, or `field` leak
    into the API, would make one of the two vocabularies wrong everywhere."""
    fill = _Fill()
    monkeypatch.setattr("mendel_api.services.answers.ops.fill", fill)

    answer_one(draft="fastqc", subject="roles", value=["qc_per_sample"],
               why="it QCs a sample", by="rafael")

    assert fill.seen.field == "roles"
    assert fill.seen.value == ["qc_per_sample"]


def test_an_absent_author_falls_back_rather_than_writing_an_empty_name(monkeypatch):
    fill = _Fill()
    monkeypatch.setattr("mendel_api.services.answers.ops.fill", fill)
    monkeypatch.setattr("mendel_api.services.answers.default_author", lambda: "rafael")

    answer_one(draft="fastqc", subject="roles", value=["x"], why="w", by=None)

    assert fill.seen.by == "rafael"


def test_a_reason_is_required(monkeypatch):
    """Every value carries a reason a reader can act on — that is the product claim, and an
    answer with a blank `why` is the one way the UI could quietly break it."""
    monkeypatch.setattr("mendel_api.services.answers.ops.fill", _Fill())

    with pytest.raises(ValueError, match="reason"):
        answer_one(draft="fastqc", subject="roles", value=["x"], why="   ", by="rafael")


def test_a_refusal_from_the_forge_is_not_swallowed(monkeypatch):
    """MF0003 means the value is not legal for that hole. The service must let it through:
    the API turns a ValueError into a 422 carrying the code, and the UI shows it."""
    def refuse(req):
        raise ValueError("MF0003: 'nonsense' is not legal for roles")

    monkeypatch.setattr("mendel_api.services.answers.ops.fill", refuse)

    with pytest.raises(ValueError, match="MF0003"):
        answer_one(draft="fastqc", subject="roles", value="nonsense", why="w", by="rafael")
