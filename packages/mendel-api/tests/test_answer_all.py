"""Answering one question across every draft asking it.

The throughput move the design rests on: "answering once settles all three". Its hard part is
not the loop, it is what happens when the third draft refuses.
"""

import pytest
from mendel_api.services.answers import answer_all


class _Forge:
    """Two drafts that accept and one that refuses, standing in for ops."""

    def __init__(self, refuses: set[str] = frozenset()):
        self.refuses = set(refuses)
        self.filled: list[tuple[str, str, object, str, str]] = []

    def list_(self, req):
        from mendel_forge.ops import ListResult

        return ListResult(names=["samtools-faidx", "samtools-index", "samtools-sort"])

    def show(self, req):
        from mendel_forge.ops import ShowResult
        from mendel_forge.scaffold import Hole

        # Every draft here asks the same question; the "does not ask" case overrides `show`.
        subject = "consumes[0].type_id"
        return ShowResult(
            name=req.name, target="t", filled={},
            holes=[Hole(subject=subject)],
        )

    def fill(self, req):
        from mendel_forge.ops import FillResult

        if req.name in self.refuses:
            raise ValueError(f"MF0003: {req.value!r} is not legal for {req.field}")
        self.filled.append((req.name, req.field, req.value, req.by, req.why))
        return FillResult(name=req.name, field=req.field, remaining=[])


@pytest.fixture
def forge(monkeypatch):
    def install(f: _Forge) -> _Forge:
        monkeypatch.setattr("mendel_api.services.answers.ops.list_", f.list_)
        monkeypatch.setattr("mendel_api.services.answers.ops.show", f.show)
        monkeypatch.setattr("mendel_api.services.answers.ops.fill", f.fill)
        return f

    return install


def test_it_settles_every_draft_that_asks(forge):
    forge(_Forge())
    got = answer_all(subject="consumes[0].type_id", value="alignment.bam",
                     why="it takes a BAM", by="rafael")
    assert got.settled == ["samtools-faidx", "samtools-index", "samtools-sort"]
    assert got.refused == []


def test_one_refusal_does_not_stop_the_others(forge):
    """**The decision this test exists for** — spec §3.1. The design's own worked example is
    a batch with one wrong member; all-or-nothing would block the other two exactly when the
    throughput move is most useful."""
    forge(_Forge(refuses={"samtools-faidx"}))
    got = answer_all(subject="consumes[0].type_id", value="alignment.bam",
                     why="it takes a BAM", by="rafael")

    assert got.settled == ["samtools-index", "samtools-sort"]
    assert [r.draft for r in got.refused] == ["samtools-faidx"]
    assert "MF0003" in got.refused[0].detail


def test_every_settled_draft_carries_the_same_provenance(forge):
    """The batch path must not be the one that loses the reasons — spec §5 of the interface
    spec. Each value is written with the same `by` and the same `why`, individually."""
    f = forge(_Forge())
    answer_all(subject="consumes[0].type_id", value="alignment.bam",
               why="it takes a BAM", by="rafael")

    assert {(by, why) for _, _, _, by, why in f.filled} == {("rafael", "it takes a BAM")}


def test_a_draft_that_does_not_ask_is_left_alone(forge):
    """Answering "consumes[0].type_id" must not touch a draft whose holes do not include it.
    A batch that writes to every draft in the workspace is a batch nobody can trust."""
    f = _Forge()
    f.show = lambda req: __import__(
        "mendel_forge.ops", fromlist=["ShowResult"]
    ).ShowResult(name=req.name, target="t", filled={}, holes=[])
    forge(f)

    got = answer_all(subject="consumes[0].type_id", value="x", why="w", by="rafael")
    assert got.settled == []
    assert f.filled == []


def test_a_reason_is_required(forge):
    forge(_Forge())
    with pytest.raises(ValueError, match="reason"):
        answer_all(subject="roles", value="x", why="  ", by="rafael")
