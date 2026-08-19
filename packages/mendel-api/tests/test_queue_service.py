"""Reading the queue, without HTTP.

Each control is tested for the thing it must not do: a filter that changes the total, a
grouping that loses which draft asked, a sort that quietly falls back to alphabet.
"""

from datetime import UTC, datetime, timedelta

import pytest
from mendel_api import questions
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


@pytest.fixture
def _drifted(monkeypatch, broken_registry_copy):
    """The real check, over a real registry with a real break in it.

    Not a stubbed `CheckResult`: the thing most likely to be wrong is the projection from a
    `Drift` to a row, and a hand-built fixture would agree with whatever the projection
    assumed. `two_drafts` still stands in for the workspace, which is a different half.
    """
    from mendel_api.services import checked
    from mendel_api.settings import settings

    def _point_at(*breaks):
        registry = None
        for relative, was, now in breaks:
            registry = broken_registry_copy(relative, was, now)
        monkeypatch.setattr(settings, "registry_root", registry)
        checked._run.cache_clear()
        return registry

    yield _point_at
    checked._run.cache_clear()


FASTQC = "tools/nf-core/fastqc/fastqc.contract.yml"
MULTIQC = "tools/nf-core/multiqc/multiqc.contract.yml"


def test_a_drifted_contract_is_the_first_row_in_the_queue(two_drafts, _drifted):
    _drifted((FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))

    rows = queue.read().questions
    assert rows, "the queue is empty — the fixture did not take"
    assert rows[0].kind is questions.RowKind.DRIFT
    assert rows[0].band is Band.DRIFT
    assert rows[0].about == "nf-core/fastqc@0.12.1"
    assert "WRONG" in rows[0].why_open and "FASTQC" in rows[0].why_open


def test_a_drift_row_is_not_collapsed_with_another_contracts(two_drafts, _drifted):
    """Two contracts drifting on one field are two pieces of work with two values, and one
    accept cannot settle both. `aggregate()` collapses on subject, so a drift row's subject
    carries the contract id — and drift rows do not go through `aggregate()` at all."""
    _drifted(
        (FASTQC, "nf_process: FASTQC", "nf_process: WRONG"),
        (MULTIQC, "nf_process: MULTIQC", "nf_process: ALSOWRONG"),
    )

    drift_rows = [r for r in queue.read().questions if r.kind is questions.RowKind.DRIFT]
    assert len({r.about for r in drift_rows}) == 2
    assert all(r.candidates == [] for r in drift_rows)


def test_a_question_row_is_not_about_a_contract(two_drafts):
    rows = [r for r in queue.read().questions if r.kind is questions.RowKind.QUESTION]
    assert rows, "no question rows — the workspace fixture is empty"
    assert all(r.about is None for r in rows)


def test_drift_survives_the_since_last_visit_filter(two_drafts, _drifted, monkeypatch):
    """Nothing records when a source moved, so a drift row has no `changed_at` — and
    *changed since my last visit* is the maintenance filter, which is exactly the case drift
    is. Filtering rung 1 out of the maintenance view would hide the wrong half.

    `visits.last` is stubbed rather than reached: it needs Postgres, and CI has none — which
    phase 1's audit found the hard way. The baseline is *now*, so every question is older
    than it and only the exemption can put a row in this list.
    """
    from mendel_api.services import visits

    monkeypatch.setattr(visits, "last", lambda who: datetime.now(UTC))
    _drifted((FASTQC, "nf_process: FASTQC", "nf_process: WRONG"))

    rows = queue.read(since_last_visit=True, who="whoever").questions
    # Two rows, not one: `nf_process` is checked by BOTH checkers, so one edit is a value
    # drift and MD0101 — the overlap spec §3.1 declares rather than merges away.
    assert rows and all(r.kind is questions.RowKind.DRIFT for r in rows)


def test_one_field_drifting_is_one_row_even_when_both_checkers_see_it(two_drafts, _drifted):
    """**Found by running it, not by a test.** `container` and `nf_process` are checked by
    both checkers, so one edit produced two queue rows with the same subject leading to the
    same screen — the same work twice, which is what the queue's collapsing exists to stop.

    The drift SCREEN still shows both, in its two sections: one is what the source says the
    value is, the other is the diagnostic that refuses. That is the coverage spec §3.1
    declares. A queue row is a piece of work, and this is one piece of work.
    """
    _drifted((FASTQC, "container: quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0",
              "container: quay.io/biocontainers/fastqc:0.0.0--stale"))

    rows = [r for r in queue.read().questions if r.kind is questions.RowKind.DRIFT]
    assert len(rows) == 1
    # The value row wins, because it is the one that can be accepted.
    assert "0.0.0--stale" in rows[0].why_open
