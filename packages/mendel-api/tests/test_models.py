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

    **Seven tables arrived at once with the forge's workflow**, and the argument for each is in
    its own class docstring rather than here — this assertion is the list, and `models.py` is
    where a table says why it exists. What did not change is the line: *accepted* declarations
    are files, and everything before a human approves one is workflow state. A `forge_revision`
    holds a candidate, which is a draft in the same sense `pipeline_draft` is.

    **The test of which side a row is on is whether deleting the table changes a build.** For
    all fourteen, it does not. `forge_catalogue_item` is the one worth naming: it holds tool
    metadata, which sounds exactly like registry data, and is a cache of what somebody else
    publishes — read over the network, replaced on every sync, read by no build.

    **Three authoring tables arrived on 2026-09-09** and pass that test in the direction that
    matters: delete every session, turn and proposal and `pipeline_draft` still opens, still
    validates and still keeps. What is lost is the *account* of how the graph came to look that
    way, which is the workflow-state side of issue #43's line — the same side a `forge_revision`
    is on.

    They are also the closest thing yet to the §8 mistake this test guards, and the distinction
    is worth stating: a `pipeline_authoring_*` row is about **authoring an artifact**, and a run
    row would be about **executing one**. A samplesheet, an input path or a task record here
    would mean this table has become Wiener's.
    """
    import mendel_api.models as m

    tables = {v.__tablename__ for v in vars(m).values() if hasattr(v, "__tablename__")}
    assert tables == {
        "source_check",
        "queue_visit",
        "pipeline_draft",
        "gate_run",
        "forge_source_snapshot",
        "forge_catalogue_item",
        "forge_adaptation",
        "forge_revision",
        "forge_event",
        "forge_message",
        "ai_invocation",
        "pipeline_authoring_session",
        "pipeline_authoring_turn",
        "pipeline_authoring_proposal",
    }, (
        f"the tables moved: {sorted(tables)}. Each argued for itself in its own class "
        "docstring, and a fifteenth needs the same argument written down. Two rejections in "
        "particular: a table of contracts, types or roles that a BUILD reads reverses issue "
        "#43 (declared data is files); a table of RUNS is Wiener's, and building it here "
        "because the worker is here is the exact failure docs/design/execution-boundary.md "
        "§8 names."
    )


def test_no_forge_table_holds_a_credential():
    """`AiInvocation`'s docstring says no table in that block holds a provider key. This is
    that sentence as a test, and it is the cheapest guard in the file.

    **A key column is one plausible line away at every point in this plan.** `ai_invocation`
    already carries `provider` and `model`; adding `api_key` beside them so a worker "does not
    have to read the environment twice" is a five-second edit that puts a secret in every
    database dump, every backup and every row a debugging endpoint renders. The credential
    reaches `comeni_ai.access` from the environment and reaches nothing else.

    Named parts rather than exact column sets: the forge tables are going to grow columns
    through the rest of this plan, and a guard that has to be edited on every legitimate
    addition is a guard people learn to update without reading.
    """
    import mendel_api.models as m

    forbidden = (
        "key",
        "secret",
        "password",
        "credential",
        "authorization",
        "bearer",
        "api_token",
        "auth_token",
        "access_token",
    )
    # **Not a bare `token`**, and finding that out cost one run of this test: `input_tokens` and
    # `output_tokens` are how many a provider counted, which is the opposite of a secret. The
    # compound forms are what actually name a credential, and a guard that fires on the columns
    # it exists to permit is one somebody edits without reading.
    offenders = []
    for value in vars(m).values():
        table = getattr(value, "__table__", None)
        if table is None or not (table.name.startswith("forge_") or table.name == "ai_invocation"):
            continue
        for column in table.columns:
            if any(word in column.name.lower() for word in forbidden):
                offenders.append(f"{table.name}.{column.name}")
    assert offenders == [], (
        f"these look like credentials: {offenders}. A provider key lives in the environment and "
        "reaches comeni_ai.access; a column puts it in every dump, backup and debug response. "
        "If one of these is genuinely not a secret, rename it — the guard reads names because "
        "a name is what a reviewer reads too."
    )


def test_the_partial_index_names_exactly_the_terminal_states():
    """`ForgeAdaptation`'s docstring says the index's SQL is `workflow.TERMINAL` spelled out.

    A comment claiming a guard exists is worse than no comment — `geometry.ts` said its
    constants were held to `layout.py`'s by a named test, no such test existed, and by the time
    anybody looked the two had drifted by 60 pixels. This is that named test.

    **What drifts here is not the index; it is the enum.** Adding a terminal state to
    `AdaptationState` without editing the SQL leaves the partial index treating it as active,
    so a finished adaptation would block its catalogue item forever and the refusal would name
    a state nobody can act on.
    """
    from mendel_api.models import ForgeAdaptation
    from mendel_forge.workflow import TERMINAL

    index = next(
        i for i in ForgeAdaptation.__table__.indexes if i.name == "ix_forge_adaptation_one_active"
    )
    clause = str(index.dialect_options["postgresql"]["where"])
    named = {word.strip("'") for word in clause.split("(")[-1].rstrip(")").split(", ")}
    assert named == {state.value for state in TERMINAL}, (
        f"the index excludes {sorted(named)} and workflow.TERMINAL is "
        f"{sorted(s.value for s in TERMINAL)}. One active adaptation per catalogue item is the "
        "rule; the index is the half that holds when two requests arrive together."
    )
    assert index.unique


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


def test_the_pending_proposal_index_names_the_pending_state():
    """`PipelineAuthoringProposal`'s docstring says the index's SQL is `ProposalState.PENDING`
    spelled out. This is the named test that claim refers to.

    Same failure mode as `test_the_partial_index_names_exactly_the_terminal_states` one table
    over: what drifts is not the index, it is the enum. Renaming the member without editing the
    SQL leaves the index enforcing uniqueness over a state nothing ever writes — so the rule
    reads as enforced and enforces nothing, which is A14's failure mode in a constraint.
    """
    from mendel_api.authoring.types import ProposalState
    from mendel_api.models import PipelineAuthoringProposal

    index = next(
        i
        for i in PipelineAuthoringProposal.__table__.indexes
        if i.name == "ix_pipeline_authoring_proposal_one_pending"
    )
    assert index.unique, "one-pending is not unique, so it enforces nothing"
    clause = str(index.dialect_options["postgresql"]["where"])
    assert ProposalState.PENDING.value in clause, (
        f"the index says {clause!r}, which does not name ProposalState.PENDING"
    )


def test_an_authoring_row_carries_no_sample_no_path_and_no_credential():
    """The §8 line, asked of the three tables closest to crossing it.

    `test_the_registry_is_not_in_the_database` argues these are workflow state rather than run
    state. This is the structural half: a column that could hold a samplesheet, an input path or
    a provider key would move the boundary without anybody deciding to.

    Named columns rather than a substring sweep would be a blocklist. This asks the opposite —
    every column is one somebody wrote down here — so a column added later fails until it is
    named, which is `_leaf_problems`' shape applied to a table.
    """
    from mendel_api import models as m

    declared = {
        "pipeline_authoring_session": {
            "id", "draft_id", "mode", "phase", "failed_from", "goal", "blueprint",
            "registry_digest", "cursor", "row_version", "who", "created_at", "updated_at",
        },
        "pipeline_authoring_turn": {
            "id", "session_id", "seq", "role", "state", "blocks", "text", "base_revision",
            "ai_invocation_id", "at",
        },
        "pipeline_authoring_proposal": {
            "id", "session_id", "turn_id", "kind", "payload", "state", "chosen_option",
            "by", "draft_revision", "created_at", "settled_at",
        },
    }
    tables = {t.__tablename__: t for t in vars(m).values() if hasattr(t, "__tablename__")}
    assert set(declared) <= set(tables), "the authoring tables moved"

    for name, expected in declared.items():
        actual = {c.name for c in tables[name].__table__.columns}
        assert actual == expected, (
            f"{name}'s columns are {sorted(actual)}. A new one needs an argument: nothing here "
            "may hold a sample identifier, a filename, a path, a provider's own error text, or "
            "a credential — the first three are invariant 15 and the last two are why "
            "ai_invocation carries a diagnostic code instead."
        )
