"""What slice 1 persists, and what it deliberately does not.

A drift check is a fact about a moment — it ran, it looked at N contracts, M disagreed.
Nothing else in the system remembers that, which is why it is the one table.
"""

from datetime import UTC, datetime

from mendel_api.models import SourceCheck


def test_a_source_check_records_when_and_what():
    c = SourceCheck(ran_at=datetime.now(UTC), checked=58, drifted=4, skipped=0)
    assert c.checked == 58
    assert c.drifted == 4


def test_the_registry_is_not_in_the_database():
    """Issue #43 decided declared data is files. A table holding contracts, types or
    roles would be that decision quietly reversed.

    `pipeline_draft` is the third table and is not that reversal: a draft is not declared data.
    The five properties #43 argued for — diff, blame, review, signature, merge — are what a
    *cited registry* sells, and a half-drawn graph needs none of them until it is landed.
    `POST /drafts/{id}/keep` is landing, and it writes a file.

    `gate_run` is the fourth and is not that reversal either. A gate's verdict lives in the
    artifact — `Pipeline.gate`, stamped by `pipeline_file.stamp` — and this row holds what the
    artifact cannot: that somebody asked, when, and what Nextflow printed while failing.

    **It is not run history.** `docs/design/execution-boundary.md` §2 puts run management in
    Wiener; this remembers *gates*, which are Mendel's own artifact checking itself on public
    data. The day a row here carries a samplesheet, this table has become Wiener's and the
    boundary has moved without anyone deciding to move it.
    """
    import mendel_api.models as m

    tables = {v.__tablename__ for v in vars(m).values() if hasattr(v, "__tablename__")}
    assert tables == {"source_check", "queue_visit", "pipeline_draft", "gate_run"}, (
        f"unexpected: {tables}"
    )
