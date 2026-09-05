"""Paging, the overview's counts, and what approval refuses.

**Against a real database**, because every claim here is about SQL: whether a keyset cursor is
stable under insertion, whether a count describes the unfiltered world, and whether a
compare-and-swap excludes a stale approval. None of the three can be answered by a fake.
"""

from datetime import UTC, datetime, timedelta

import pytest
from mendel_api.db import session_scope
from mendel_api.models import ForgeAdaptation, ForgeCatalogueItem, ForgeSourceSnapshot
from mendel_api.services import forge_adaptations, forge_overview, forge_review, forge_state
from mendel_forge.workflow import AdaptationState, EventKind, MessageState, RevisionState
from sqlalchemy import text


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


@pytest.fixture
def items(clean_forge) -> list[str]:
    """Three catalogue items across two sources, stored the way a sync stores them."""
    from mendel_forge.catalogue import CatalogueItem

    now = datetime.now(UTC)
    made = []
    with session_scope() as session:
        session.add(
            ForgeSourceSnapshot(
                id="s" * 32, source="nf-core", started_at=now, finished_at=now, ok=True
            )
        )
        session.flush()
        for n, (source, ref) in enumerate(
            [("nf-core", "samtools/sort"), ("nf-core", "fastqc"), ("pegi3s", "clustalw")], 1
        ):
            domain = CatalogueItem(
                id=f"{n:064d}",
                source=source,
                ref=ref,
                display_name=ref,
                content_digest=f"{n:064d}",
            )
            session.add(
                ForgeCatalogueItem(
                    id=domain.id,
                    snapshot_id="s" * 32,
                    source=source,
                    ref=ref,
                    display_name=ref,
                    metadata_json=domain.model_dump(mode="json"),
                    content_digest=domain.content_digest,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )
            made.append(domain.id)
    return made


# ── cursor paging ─────────────────────────────────────────────────────────────────────


def test_a_page_hands_back_a_cursor_only_when_there_is_more(items):
    """`next_cursor` is `None` on the last page, so *is there more* is answered by the response
    rather than by the caller counting rows against the limit it asked for."""
    for item in items:
        forge_adaptations.begin(item, who="rafael")

    first = forge_adaptations.listing(limit=2)
    assert len(first.items) == 2 and first.next_cursor

    second = forge_adaptations.listing(limit=2, cursor=first.next_cursor)
    assert len(second.items) == 1 and second.next_cursor is None


def test_paging_visits_every_row_exactly_once(items):
    """The property offset paging loses. Walked rather than asserted on one page, because a
    cursor that skipped or repeated would still produce two plausible-looking pages."""
    for item in items:
        forge_adaptations.begin(item, who="rafael")

    seen, cursor = [], None
    while True:
        page = forge_adaptations.listing(limit=1, cursor=cursor)
        seen += [row.id for row in page.items]
        cursor = page.next_cursor
        if cursor is None:
            break
    assert len(seen) == 3
    assert len(set(seen)) == 3, "a row was returned twice"


def test_a_cursor_is_stable_when_rows_are_inserted_behind_it(items, clean_forge):
    """**Why §7 asks for cursors.** A sync that inserts while somebody is on page three shifts
    every offset page by however many landed before their offset — so they see duplicates and
    miss rows with nothing looking wrong. A keyset names a position in the order instead.
    """
    started = [forge_adaptations.begin(item, who="rafael").id for item in items]
    first = forge_adaptations.listing(limit=1)

    # Something older arrives after the first page was read. Under offset paging this shifts
    # the window; under a keyset it cannot, because the cursor is a position and not a count.
    with session_scope() as session:
        old = datetime.now(UTC) - timedelta(days=1)
        row = session.get(ForgeAdaptation, started[0])
        row.updated_at = old

    rest, cursor = [], first.next_cursor
    while cursor:
        page = forge_adaptations.listing(limit=1, cursor=cursor)
        rest += [row.id for row in page.items]
        cursor = page.next_cursor
    assert first.items[0].id not in rest, "the first page's row came back on a later one"


def test_a_forged_cursor_is_refused(items):
    """`MI0111`. A cursor a caller can construct is a cursor a caller will construct, and the
    ordering then becomes a public contract that cannot change."""
    with pytest.raises(ValueError, match="MI0111"):
        forge_adaptations.listing(cursor="not-a-cursor")


def test_a_state_filter_is_applied_in_sql(items):
    """Server-side — §7. Filtering in the browser means sending sixteen hundred rows to show
    three, which is the same argument `forge_catalogue.search` already makes."""
    first = forge_adaptations.begin(items[0], who="rafael").id
    forge_adaptations.begin(items[1], who="rafael")
    forge_state.move(
        first,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="w",
        kind=EventKind.QUEUED,
    )
    page = forge_adaptations.listing(state=AdaptationState.QUEUED)
    assert [row.id for row in page.items] == [first]


def test_a_page_never_exceeds_the_maximum(items):
    """A caller that can ask for everything will."""
    page = forge_adaptations.listing(limit=10_000)
    assert len(page.items) <= forge_adaptations.MAX_LIMIT


# ── the overview ──────────────────────────────────────────────────────────────────────


def test_the_stages_are_the_seven_the_plan_names():
    """§7 lists them, in the order a tool passes through. Written out rather than derived
    because the *order* matters and a set has none."""
    assert [state.value for state in forge_overview._STAGES] == [
        "scaffolding",
        "queued",
        "generating",
        "validating",
        "review",
        "changes_requested",
        "failed",
    ]
    assert set(forge_overview.Stages.model_fields) == {s.value for s in forge_overview._STAGES}


def test_the_only_unfinished_state_that_is_not_a_stage_is_publishing():
    """**This is what fails when a state is added to the workflow and not to `_STAGES`** — the
    arrangement `HINTS` uses for `HoleKind`, and the reason the omission is named rather than
    left as a difference somebody has to notice.

    `publishing` is absent on purpose: it is a moment, not a stage. It lasts one job and either
    reaches `published` or returns to `review`, so a band counting it would flicker between 0
    and 1 and mean nothing when a person looked. §7's list agrees.
    """
    from mendel_forge.workflow import ACTIVE, AdaptationState

    assert set(ACTIVE) - set(forge_overview._STAGES) == {AdaptationState.PUBLISHING}


def test_the_overview_counts_and_never_lists(items):
    """`docs/design/forge-review.md` §3 records an Overview page designed and cut for answering
    the same question as the queue. The moment a tool ref or an adaptation id appears here, it
    has become that page."""
    for item in items:
        forge_adaptations.begin(item, who="rafael")
    rendered = forge_overview.overview().model_dump_json()
    for identifier in items:
        assert identifier not in rendered, "an id reached the overview"
    assert "samtools/sort" not in rendered, "a tool ref reached the overview"


def test_the_stage_counts_describe_every_adaptation(items):
    for item in items:
        forge_adaptations.begin(item, who="rafael")
    assert forge_overview.overview().stages.scaffolding == 3


def test_a_failed_sync_shows_on_its_source_and_carries_a_code(clean_forge):
    """The row says *this source's last look at upstream did not work*, with the code and never
    upstream's message — `MI0104`, and the reason is on that entry."""
    from mendel_api.services import forge_catalogue

    forge_catalogue.record_failure(
        "nf-core",
        error="MI0104: the nf-core catalogue could not be read",
        started_at=datetime.now(UTC),
    )
    (row,) = forge_overview.overview().sources
    assert row.source == "nf-core"
    assert "MI0104" in row.sync_error
    assert forge_overview.overview().attention.failed_syncs == 1


def test_only_the_most_recent_snapshot_counts_as_a_failed_sync(clean_forge):
    """**Most recent, not any.** Counting every failed snapshot ever would make a source that
    broke once in March permanently red, and the number would only ever grow."""
    from mendel_api.services import forge_catalogue
    from mendel_forge.catalogue import SourceSnapshot

    forge_catalogue.record_failure("nf-core", error="MI0104", started_at=datetime.now(UTC))
    assert forge_overview.overview().attention.failed_syncs == 1

    forge_catalogue.record(
        SourceSnapshot(
            source="nf-core", source_revision="abc", synced_at=datetime.now(UTC), items=()
        )
    )
    assert forge_overview.overview().attention.failed_syncs == 0


# ── approval ──────────────────────────────────────────────────────────────────────────


def _in_review(item: str, *, green: bool, digest: str = "d" * 64) -> tuple[str, int]:
    adaptation = forge_state.begin(item, who="rafael")
    forge_state.move(
        adaptation,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="w",
        kind=EventKind.QUEUED,
    )
    forge_state.claim(adaptation, row_version=2, worker="w")
    revision = forge_state.add_revision(
        adaptation, state=RevisionState.VALIDATED, manifest={}
    )
    forge_state.move(
        adaptation,
        AdaptationState.VALIDATING,
        expect=AdaptationState.GENERATING,
        row_version=3,
        actor="w",
        kind=EventKind.GENERATED,
        revision_id=revision,
    )
    forge_state.move(
        adaptation,
        AdaptationState.REVIEW,
        expect=AdaptationState.VALIDATING,
        row_version=4,
        actor="w",
        kind=EventKind.VALIDATED,
        revision_id=revision,
    )
    with session_scope() as session:
        session.get(ForgeAdaptation, adaptation).registry_digest = digest
        row = session.get(type(session.get(ForgeAdaptation, adaptation)), adaptation)
        assert row is not None
        from mendel_api.models import ForgeRevision

        session.get(ForgeRevision, revision).green = green
    return adaptation, 5


def test_approve_refuses_a_candidate_nothing_validated(items):
    """`green` is false, so approval is impossible — the whole reason `_record_verdict` refuses
    to write `True` for a candidate no ladder has run over."""
    adaptation, version = _in_review(items[0], green=False)
    with pytest.raises(ValueError, match="valid"):
        forge_adaptations.approve(
            adaptation, who="rafael", reason="looks right", registry_digest_now="d" * 64
        )


def test_approve_refuses_when_the_registry_moved_under_it(items):
    """A green verdict describes the layer that was read at the time, and that layer can be
    gone. `mendel upgrade` rests on the same argument for a pipeline."""
    adaptation, _ = _in_review(items[0], green=True, digest="d" * 64)
    with pytest.raises(ValueError):
        forge_adaptations.approve(
            adaptation, who="rafael", reason="looks right", registry_digest_now="e" * 64
        )


def test_approve_refuses_an_adaptation_that_is_still_running(items):
    """The page that shows *Approve* on a generating row is the page that will eventually be
    clicked, and a service that accepted the click would approve a candidate that does not
    exist yet. `MF0300`."""
    adaptation = forge_state.begin(items[0], who="rafael")
    forge_state.move(
        adaptation,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="w",
        kind=EventKind.QUEUED,
    )
    forge_state.claim(adaptation, row_version=2, worker="w")
    with pytest.raises(ValueError):
        forge_adaptations.approve(
            adaptation, who="rafael", reason="looks right", registry_digest_now="d" * 64
        )


def test_approve_reports_every_unmet_condition_rather_than_the_first(items):
    """Six presses to learn six facts the server knew at the first one. `approval_refusals`
    returns them all, and this is what stops a caller here from collapsing that."""
    adaptation, _ = _in_review(items[0], green=False)
    with pytest.raises(ValueError) as refusal:
        forge_adaptations.approve(
            adaptation, who="rafael", reason="", registry_digest_now="e" * 64
        )
    assert len(str(refusal.value).strip().splitlines()) > 1


# ── the review conversation ───────────────────────────────────────────────────────────


def test_a_question_is_stored_pending_and_visible_immediately(items):
    """§7: *the pending message is visible immediately*. A curator who sees nothing until a
    model answers cannot tell *sent* from *lost*, and at 227 seconds they retype it."""
    adaptation = forge_state.begin(items[0], who="rafael")
    turn = forge_review.ask(adaptation, message="why is this fastq.reads?")
    assert turn.state is MessageState.PENDING
    assert [t.id for t in forge_review.conversation(adaptation)] == [turn.id]


def test_a_question_is_grounded_at_the_moment_it_is_asked(items):
    """Not at the moment it is answered. A revision landing while the question sits in the
    queue would otherwise re-ground it, and the answer would be about a candidate the curator
    never saw."""
    adaptation, _ = _in_review(items[0], green=True)
    with session_scope() as session:
        current = session.get(ForgeAdaptation, adaptation).current_revision_id
    turn = forge_review.ask(adaptation, message="why this type?")
    assert turn.revision_id == current
