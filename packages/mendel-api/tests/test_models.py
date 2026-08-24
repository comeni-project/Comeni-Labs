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

    **This test is also the only structural guard on §8, and that was an accident worth
    claiming.** §8 names the failure mode for run management as *building it inside `mendel-api`
    because that is where the worker already is* — and run state needs somewhere to live, so a
    `run` table here is the first move in that mistake. It fails this assertion. That is a
    stronger position than the prose alone, and it is narrow: run state in Redis, in a JSON
    column, or on `gate_run` itself would all pass. `test_a_gate_run_carries_no_input_and_no_
    credential` closes the third of those.
    """
    import mendel_api.models as m

    tables = {v.__tablename__ for v in vars(m).values() if hasattr(v, "__tablename__")}
    assert tables == {"source_check", "queue_visit", "pipeline_draft", "gate_run"}, (
        f"the tables moved: {sorted(tables)}. Each of the four argued for itself in this "
        "docstring, and a fifth needs the same argument written down. Two rejections in "
        "particular: a table of contracts, types or roles reverses issue #43 (declared data is "
        "files); a table of RUNS is Wiener's, and building it here because the worker is here "
        "is the exact failure docs/design/execution-boundary.md §8 names."
    )


def test_a_gate_run_carries_no_input_and_no_credential():
    """`GateRun`'s docstring says the day a row here carries a samplesheet, the boundary has
    moved without anybody deciding to move it. This is that sentence as a test.

    **The table set above is the guard against a new *table*; this is the guard against a new
    *column*, and a column is the cheaper mistake.** Wiener's first slice
    (`docs/design/execution-boundary.md` §8) needs an input path, an executor, a `workDir` and a
    credential to do its job, and the shortest route to all four is to widen the table that
    already remembers a Nextflow invocation. That is precisely §8's named failure mode — run
    state entangled with the deterministic half because the worker was already here — and it
    arrives as one plausible line in a model, not as a decision anybody announces.

    A run has its own home, in Wiener, behind Wiener's own boundary. If a field below is genuinely
    needed for a *gate*, add it here with a sentence saying why it is not a run.
    """
    from mendel_api.models import GateRun

    columns = {c.name for c in GateRun.__table__.columns}
    assert columns == {
        "id",
        "draft_id",
        "who",
        "gate",
        "state",
        "output",
        "queued_at",
        "finished_at",
    }, (
        f"gate_run's columns moved: {sorted(columns)}. A gate runs Mendel's own artifact on data "
        "somebody else published and takes no samplesheet, no executor, no workDir and no "
        "credential — docs/design/execution-boundary.md §3. A column for any of those makes this "
        "run history, which is Wiener's, and moves the boundary without anybody deciding to."
    )
