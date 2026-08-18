"""Reading the queue, without HTTP.

Each control is tested for the thing it must not do: a filter that changes the total, a
grouping that loses which draft asked, a sort that quietly falls back to alphabet.
"""

from datetime import UTC, datetime, timedelta

import pytest
from mendel_api.questions import Band
from mendel_api.services import queue


class _Draft:
    """A workspace of two drafts, standing in for ops.list_ and ops.show."""

    def __init__(self, holes: dict[str, list[str]], changed: dict[str, datetime]):
        self.holes, self.changed = holes, changed

    def list_(self, req):
        from mendel_forge.ops import ListResult

        return ListResult(names=sorted(self.holes))

    def show(self, req):
        from mendel_forge.ops import ShowResult
        from mendel_forge.scaffold import Hole

        return ShowResult(
            name=req.name, target="t", filled={},
            changed_at=self.changed[req.name],
            holes=[
                Hole(subject=s, what="", why_open="", candidates=[], closed=True, evidence=[])
                for s in self.holes[req.name]
            ],
        )


@pytest.fixture
def two_drafts(monkeypatch):
    now = datetime.now(UTC)
    fake = _Draft(
        holes={"fastqc": ["roles", "consumes[0].name"], "samtools": ["roles"]},
        changed={"fastqc": now, "samtools": now - timedelta(days=7)},
    )
    monkeypatch.setattr("mendel_api.services.queue.ops.list_", fake.list_)
    monkeypatch.setattr("mendel_api.services.queue.ops.show", fake.show)
    return fake


def test_it_collapses_identical_work_by_default(two_drafts):
    """Both drafts ask `roles`; that is one row asked by two. The design's throughput move."""
    got = queue.read()
    roles = [q for q in got.questions if q.subject == "roles"]
    assert len(roles) == 1
    assert roles[0].asked_by == ["fastqc", "samtools"]


def test_grouping_by_module_does_not_collapse(two_drafts):
    """`group=module` is not the same rows rearranged — it is the un-aggregated set. A
    client cannot derive it from the collapsed one, because collapsing threw away which
    draft asked."""
    got = queue.read(group=queue.Grouping.MODULE)
    roles = [q for q in got.questions if q.subject == "roles"]
    assert [q.asked_by for q in roles] == [["fastqc"], ["samtools"]]


def test_a_band_filter_narrows_the_rows_but_not_the_total(two_drafts):
    """`total` counts the open questions in the workspace. A filter that changed it would
    make the queue understate how much work exists — which is what `total` is for."""
    everything = queue.read()
    only_routing = queue.read(band=Band.ROUTING)
    assert all(q.band is Band.ROUTING for q in only_routing.questions)
    assert only_routing.total == everything.total


def test_sorting_by_recency_puts_the_newest_draft_first(two_drafts):
    got = queue.read(sort=queue.Ordering.RECENT, group=queue.Grouping.MODULE)
    assert got.questions[0].asked_by == ["fastqc"]


def test_the_default_sort_is_consequence(two_drafts):
    got = queue.read()
    assert [q.subject for q in got.questions] == ["roles", "consumes[0].name"]


def test_since_last_visit_hides_what_has_not_moved(two_drafts, monkeypatch):
    monkeypatch.setattr(
        "mendel_api.services.queue.visits.last",
        lambda who: datetime.now(UTC) - timedelta(days=1),
    )
    got = queue.read(since_last_visit=True, group=queue.Grouping.MODULE)
    assert {tuple(q.asked_by) for q in got.questions} == {("fastqc",)}


def test_a_first_visit_shows_everything_rather_than_nothing(two_drafts, monkeypatch):
    """`last()` is None for someone who has never been here. Reading that as "nothing is
    newer than never" empties the queue for exactly the person least able to tell that it
    is wrong."""
    monkeypatch.setattr("mendel_api.services.queue.visits.last", lambda who: None)
    got = queue.read(since_last_visit=True)
    assert len(got.questions) > 0
