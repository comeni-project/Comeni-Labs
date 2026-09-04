"""Moving an adaptation, against a real database.

**The rules are checked in `mendel-forge`; what is here is the storage.** `test_visits.py`
records why the split exists — CI has no Postgres, and a rule only a developer machine can
check is a rule nobody checks — so the transition table lives in `mendel_forge.workflow` with a
suite that always runs, and these tests cover what only a database can answer: whether a
compare-and-swap actually excludes the second writer, whether the partial index actually
refuses a second active adaptation, and whether a `RESTRICT` foreign key actually keeps history.

Run them with a database on hand:

    DB_HOST_PORT=55432 docker compose up -d postgres
    export MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@localhost:55432/mendel
    cd packages/mendel-api && uv run alembic upgrade head

`DB_HOST_PORT` rather than the default 5432, because a developer machine running any other
project's Postgres already has that port, and `docker compose up` fails on the bind rather than
on anything to do with this repository.
"""

from datetime import UTC, datetime, timedelta

import pytest
from mendel_api.db import session_scope
from mendel_api.models import ForgeAdaptation, ForgeCatalogueItem, ForgeEvent, ForgeSourceSnapshot
from mendel_api.services import forge_state
from mendel_forge.workflow import AdaptationState, EventKind, RevisionState
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
def item(clean_forge) -> str:
    """One catalogue item to adapt, and the snapshot it came from.

    Built through the models rather than through `forge_catalogue.record`: these tests are
    about transitions, and routing them through the sync service would make every one of them
    fail when the sync breaks, for a reason that has nothing to do with what they claim.
    """
    now = datetime.now(UTC)
    with session_scope() as session:
        session.add(
            ForgeSourceSnapshot(
                id="s" * 32, source="nf-core", started_at=now, finished_at=now, ok=True
            )
        )
        session.flush()
        session.add(
            ForgeCatalogueItem(
                id="i" * 64,
                snapshot_id="s" * 32,
                source="nf-core",
                ref="samtools/sort",
                display_name="samtools sort",
                metadata_json={},
                content_digest="d" * 64,
                first_seen_at=now,
                last_seen_at=now,
            )
        )
    return "i" * 64


def _state(adaptation_id: str) -> tuple[AdaptationState, int]:
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        return AdaptationState(row.state), row.row_version


def _events(adaptation_id: str) -> list[str]:
    with session_scope() as session:
        return [
            row.kind
            for row in session.query(ForgeEvent)
            .filter(ForgeEvent.adaptation_id == adaptation_id)
            .order_by(ForgeEvent.id)
        ]


def test_starting_an_adaptation_records_who_and_leaves_it_scaffolding(item):
    adaptation = forge_state.begin(item, who="rafael")
    assert _state(adaptation) == (AdaptationState.SCAFFOLDING, 1)
    assert _events(adaptation) == [EventKind.CREATED]


def test_a_second_adaptation_of_the_same_tool_is_refused_with_the_first_one_named(item):
    """Rule 2, through the service half.

    The refusal names the adaptation already in flight, because *this tool is already being
    adapted* leaves a person hunting for it — and the one they find may be somebody else's.
    """
    first = forge_state.begin(item, who="rafael")
    with pytest.raises(ValueError, match="MI0101") as refusal:
        forge_state.begin(item, who="someone-else")
    assert first in str(refusal.value)
    assert "scaffolding" in str(refusal.value)


def test_a_finished_adaptation_frees_the_tool_for_another(item):
    """The other half of rule 2, and the half that would make a bug invisible: if *active* were
    read as *exists*, a published tool could never be re-adapted, and a version bump upstream
    is exactly when it must be.
    """
    first = forge_state.begin(item, who="rafael")
    with session_scope() as session:
        session.get(ForgeAdaptation, first).state = AdaptationState.PUBLISHED.value
    second = forge_state.begin(item, who="rafael")
    assert second != first


def test_the_partial_index_refuses_a_second_active_row_even_without_the_service(item):
    """The index, checked on its own — with the service's refusal bypassed entirely.

    Two mechanisms enforce one active adaptation, and `models.py` claims they are not the
    redundancy `SourceSnapshot.classified` was. This is what makes that claim checkable: the
    service is not involved, so what refuses here can only be the database.
    """
    forge_state.begin(item, who="rafael")
    now = datetime.now(UTC)
    with (
        pytest.raises(Exception, match="ix_forge_adaptation_one_active"),
        session_scope() as session,
    ):
        session.add(
            ForgeAdaptation(
                id="x" * 32,
                catalogue_item_id=item,
                state=AdaptationState.QUEUED.value,
                row_version=1,
                who="racing",
                created_at=now,
                updated_at=now,
            )
        )


def test_a_transition_bumps_the_row_version(item):
    adaptation = forge_state.begin(item, who="rafael")
    moved = forge_state.move(
        adaptation,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="rafael",
        kind=EventKind.QUEUED,
    )
    assert moved.row_version == 2
    assert _state(adaptation) == (AdaptationState.QUEUED, 2)


def test_a_stale_row_version_loses_and_is_told_what_it_is_now(item):
    """Two browser tabs. The second one is refused rather than overwriting the first.

    **The refusal reports the current state and version**, because the recovery is to re-read,
    and a refusal that does not say what changed makes the caller poll to find out.
    """
    adaptation = forge_state.begin(item, who="rafael")
    forge_state.move(
        adaptation,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="tab-one",
        kind=EventKind.QUEUED,
    )
    with pytest.raises(ValueError, match="MI0100") as refusal:
        forge_state.move(
            adaptation,
            AdaptationState.QUEUED,
            expect=AdaptationState.SCAFFOLDING,
            row_version=1,
            actor="tab-two",
            kind=EventKind.QUEUED,
        )
    assert "queued at version 2" in str(refusal.value)


def test_a_tab_that_left_review_and_came_back_to_it_still_loses(item):
    """**The only test in this file that the row-version compare is load-bearing for**, and it
    exists because deleting that compare left all sixteen others green.

    Every other stale case also has a mismatched *state*, so `expect` alone catches it and the
    version looks like belt and braces. The case it actually covers is a state moved through
    and back: a reviewer opens the candidate, someone else requests changes, the model produces
    a new revision, and the adaptation returns to `review`. The first tab is still holding
    `review` — the right state, the wrong candidate — and pressing *Approve* there approves work
    it has never seen.

    That is `SourceSnapshot.classified` again in a new place: two mechanisms presented as
    defence in depth where only one was carrying the claim. Found by deleting the compare and
    watching nothing fail.
    """
    adaptation = forge_state.begin(item, who="rafael")
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation)
        row.state, row.row_version = AdaptationState.REVIEW.value, 7
    stale_tab = 7

    forge_state.request_changes(adaptation, row_version=7, who="someone-else", reason="wrong type")
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation)
        row.state = AdaptationState.REVIEW.value  # a new revision came back for review

    with session_scope() as session:
        assert session.get(ForgeAdaptation, adaptation).state == AdaptationState.REVIEW.value

    with pytest.raises(ValueError, match="MI0100"):
        forge_state.move(
            adaptation,
            AdaptationState.PUBLISHING,
            expect=AdaptationState.REVIEW,
            row_version=stale_tab,
            actor="rafael",
            kind=EventKind.APPROVED,
        )


def test_a_duplicate_claim_of_one_job_is_refused(item):
    """ARQ delivers at least once, so this is the ordinary case on a redeploy rather than a
    pathological one. The second worker must not start a second model call."""
    adaptation = forge_state.begin(item, who="rafael")
    forge_state.move(
        adaptation,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="rafael",
        kind=EventKind.QUEUED,
    )
    claimed = forge_state.claim(adaptation, row_version=2, worker="ai-worker-1")
    assert claimed.state is AdaptationState.GENERATING
    with pytest.raises(ValueError, match="MI0100"):
        forge_state.claim(adaptation, row_version=2, worker="ai-worker-2")
    assert _events(adaptation).count(EventKind.CLAIMED) == 1


def test_an_illegal_transition_is_refused_before_the_database_is_touched(item):
    """`MF0300` rather than `MI0100`: the caller's expectation is right and the *request* is
    wrong, which is a different finding and deserves a different code. And nothing is written —
    an event recording an attempt that never happened would be an audit of nothing."""
    adaptation = forge_state.begin(item, who="rafael")
    with pytest.raises(ValueError, match="MF0300"):
        forge_state.move(
            adaptation,
            AdaptationState.PUBLISHING,
            expect=AdaptationState.SCAFFOLDING,
            row_version=1,
            actor="rafael",
            kind=EventKind.APPROVED,
        )
    assert _events(adaptation) == [EventKind.CREATED]


def test_a_scaffold_failure_retries_as_a_scaffold(item):
    """Rule 9 through the storage: `failed_stage` is written on the way in and read on the way
    out, and a retry that ignored it would queue a model against a bundle that does not exist.
    """
    adaptation = forge_state.begin(item, who="rafael")
    forge_state.fail(
        adaptation,
        stage=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="worker",
        detail="MF0201 the source did not answer",
    )
    assert _state(adaptation)[0] is AdaptationState.FAILED
    resumed = forge_state.retry(adaptation, row_version=2, actor="rafael")
    assert resumed.state is AdaptationState.SCAFFOLDING


def test_a_generation_failure_retries_as_a_queued_job(item):
    adaptation = forge_state.begin(item, who="rafael")
    forge_state.move(
        adaptation,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="rafael",
        kind=EventKind.QUEUED,
    )
    forge_state.claim(adaptation, row_version=2, worker="w")
    forge_state.fail(
        adaptation,
        stage=AdaptationState.GENERATING,
        row_version=3,
        actor="w",
        detail="provider timed out",
    )
    assert forge_state.retry(adaptation, row_version=4, actor="rafael").state is (
        AdaptationState.QUEUED
    )


def test_a_recovered_adaptation_no_longer_carries_the_stage_it_failed_at(item):
    """A stale `failed_stage` sends the *next* retry to the wrong place — rule 9 inverted, and
    a defect that only shows up on the second failure of one adaptation, which is exactly the
    path nobody walks by hand."""
    adaptation = forge_state.begin(item, who="rafael")
    forge_state.fail(
        adaptation, stage=AdaptationState.SCAFFOLDING, row_version=1, actor="w", detail="x"
    )
    forge_state.retry(adaptation, row_version=2, actor="rafael")
    with session_scope() as session:
        assert session.get(ForgeAdaptation, adaptation).failed_stage is None


def test_requesting_changes_needs_a_reason(item):
    adaptation = forge_state.begin(item, who="rafael")
    with pytest.raises(ValueError, match="MF0301"):
        forge_state.request_changes(adaptation, row_version=1, who="rafael", reason="  ")


def test_a_revision_is_numbered_from_what_is_stored_and_becomes_current(item):
    """Ordinals a person reads. Derived from the table rather than passed in, so two callers
    cannot both decide they are number 2."""
    adaptation = forge_state.begin(item, who="rafael")
    first = forge_state.add_revision(
        adaptation, state=RevisionState.SCAFFOLDED, manifest={"scaffold": "scaffold/"}
    )
    second = forge_state.add_revision(
        adaptation,
        state=RevisionState.SCAFFOLDED,
        manifest={"scaffold": "scaffold/"},
        parent_revision_id=first,
    )
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation)
        assert row.current_revision_id == second
    assert first != second


def test_the_current_revision_belongs_to_its_adaptation(item):
    """`ForgeAdaptation.current_revision_id` carries no foreign key — the pair of real
    constraints would be a cycle — so `models.py` says a test holds the other half. This is it.

    **What it rules out is a revision of somebody else's adaptation becoming current**, which a
    database with the FK would refuse and this one cannot. `add_revision` is the only writer,
    and it writes a revision it created for that adaptation in the same transaction.
    """
    first = forge_state.begin(item, who="rafael")
    with session_scope() as session:
        session.get(ForgeAdaptation, first).state = AdaptationState.ARCHIVED.value
    second = forge_state.begin(item, who="rafael")

    revision = forge_state.add_revision(
        second, state=RevisionState.SCAFFOLDED, manifest={"scaffold": "scaffold/"}
    )
    with session_scope() as session:
        assert session.get(ForgeAdaptation, first).current_revision_id is None
        assert session.get(ForgeAdaptation, second).current_revision_id == revision


def test_deleting_a_catalogue_item_is_refused_while_an_adaptation_points_at_it(item):
    """`models.py` says archiving never deletes history, and that the rule holds because there
    is no cascade to break it with. A `RESTRICT` foreign key is only a claim until somebody
    tries the delete — so this tries it."""
    forge_state.begin(item, who="rafael")
    with pytest.raises(Exception, match="forge_adaptation"), session_scope() as session:
        session.delete(session.get(ForgeCatalogueItem, item))


def test_a_worker_that_never_came_back_is_reportable(item):
    """Rule 7. The sweep reports rather than acts, because *the worker died* and *the model is
    slow* look identical from the row, and only the caller knows which timeout applies."""
    adaptation = forge_state.begin(item, who="rafael")
    forge_state.move(
        adaptation,
        AdaptationState.QUEUED,
        expect=AdaptationState.SCAFFOLDING,
        row_version=1,
        actor="rafael",
        kind=EventKind.QUEUED,
    )
    forge_state.claim(adaptation, row_version=2, worker="w")
    assert forge_state.stale(datetime.now(UTC) - timedelta(hours=1)) == []
    assert forge_state.stale(datetime.now(UTC) + timedelta(hours=1)) == [adaptation]


def test_a_scaffolding_adaptation_is_not_reported_as_a_lost_job(item):
    """Only states a *worker* holds. A row sitting in `scaffolding` because nobody pressed the
    next button is not a lost job, and reclaiming it would restart work nobody asked for."""
    forge_state.begin(item, who="rafael")
    assert forge_state.stale(datetime.now(UTC) + timedelta(hours=1)) == []
