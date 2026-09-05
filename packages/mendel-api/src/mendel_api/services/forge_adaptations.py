"""Reading and moving adaptations, for the HTTP surface.

**Every mutation here is a thin call onto `forge_state`, which is the only module that moves an
adaptation.** This one turns a request into that call and its refusal into something a page can
render; it holds no rule about what may follow what, because a second copy of the transition
table is the thing `workflow.py`'s docstring exists to prevent.

**Cursor paging, not offset.** §7 asks for it and the reason is concurrency: a sync that inserts
sixteen hundred rows while somebody is on page three shifts every subsequent page by however
many landed before their offset, so they see duplicates and miss rows without anything looking
wrong. A keyset cursor is stable under insertion because it names a *position in the order*
rather than a distance from the start.
"""

import base64
import binascii
import json
from datetime import UTC, datetime

from comeni_core.diagnostics import coded
from mendel_forge.workflow import AdaptationState
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, tuple_

from mendel_api.db import session_scope
from mendel_api.models import ForgeAdaptation, ForgeCatalogueItem, ForgeEvent, ForgeRevision
from mendel_api.services import forge_state

_FROZEN = ConfigDict(extra="forbid", frozen=True)

MAX_LIMIT = 200
"""The largest page anybody may ask for.

Not a performance number — a *shape* one. A caller that can ask for everything will, and the
page that does becomes the page nobody notices is slow until the catalogue is sixteen hundred
rows deep. `MF0202`'s failure mode, arriving through the front end.
"""


class Cursor(BaseModel):
    """Where a page left off, as the ordering key rather than as a count.

    Opaque to the client on purpose. A cursor a caller can construct is a cursor a caller will
    construct, and then the ordering is a public contract that cannot change — `routes/build.py`
    records the same argument for why a draft id is opaque.
    """

    model_config = _FROZEN

    updated_at: datetime
    id: str

    def encode(self) -> str:
        return base64.urlsafe_b64encode(
            json.dumps({"u": self.updated_at.isoformat(), "i": self.id}).encode()
        ).decode()

    @classmethod
    def decode(cls, raw: str) -> "Cursor":
        try:
            payload = json.loads(base64.urlsafe_b64decode(raw.encode()))
            return cls(updated_at=datetime.fromisoformat(payload["u"]), id=payload["i"])
        except (ValueError, KeyError, binascii.Error) as bad:
            raise ValueError(
                coded("MI0111", "that page cursor is not one this endpoint issued")
                + "\n  cursors are opaque; ask for the first page and follow `next_cursor`"
            ) from bad


class AdaptationRow(BaseModel):
    """One adaptation, as a list renders it. **No candidate text and no holes** — those are the
    detail endpoint's, and a list that carried them would be a list nobody can page."""

    model_config = _FROZEN

    id: str
    catalogue_item_id: str
    source: str
    ref: str
    display_name: str
    state: AdaptationState
    row_version: int
    who: str
    failed_stage: AdaptationState | None = None
    current_revision_id: str | None = None
    created_at: datetime
    updated_at: datetime


class Page(BaseModel):
    """A slice, and how to ask for the next one. **No total.**

    A keyset page cannot cheaply say how many rows are behind it, and a count that needed a
    second full scan on every page would be the cost this paging exists to avoid. The overview
    is where totals live, and they are counted once over the unfiltered world.
    """

    model_config = _FROZEN

    items: tuple[AdaptationRow, ...] = ()
    next_cursor: str | None = None


class Event(BaseModel):
    model_config = _FROZEN

    kind: str
    from_state: AdaptationState | None = None
    detail: str
    actor: str
    at: datetime


class Revision(BaseModel):
    model_config = _FROZEN

    id: str
    ordinal: int
    state: str
    green: bool
    unresolved_required: int
    validation: dict
    created_at: datetime


class Adaptation(BaseModel):
    """One adaptation in full: where it is, what it produced, and what happened to it."""

    model_config = _FROZEN

    adaptation: AdaptationRow
    revisions: tuple[Revision, ...] = ()
    events: tuple[Event, ...] = ()


def _row(row: ForgeAdaptation, item: ForgeCatalogueItem | None) -> AdaptationRow:
    return AdaptationRow(
        id=row.id,
        catalogue_item_id=row.catalogue_item_id,
        source=item.source if item else "",
        ref=item.ref if item else "",
        display_name=item.display_name if item else "",
        state=AdaptationState(row.state),
        row_version=row.row_version,
        who=row.who,
        failed_stage=AdaptationState(row.failed_stage) if row.failed_stage else None,
        current_revision_id=row.current_revision_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def listing(
    *,
    state: AdaptationState | None = None,
    source: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> Page:
    """A page of adaptations, newest first, filtered server-side.

    **Ordered by `(updated_at desc, id desc)` and paged on that pair.** `updated_at` alone is not
    unique — a sync moves many rows in one transaction — and a cursor on a non-unique key either
    skips rows or repeats them at every tie. The id breaks it, and it is the primary key, so the
    order is total.
    """
    limit = max(1, min(limit, MAX_LIMIT))
    where = []
    if state is not None:
        where.append(ForgeAdaptation.state == state.value)
    if cursor:
        after = Cursor.decode(cursor)
        where.append(
            tuple_(ForgeAdaptation.updated_at, ForgeAdaptation.id)
            < tuple_(after.updated_at, after.id)
        )

    with session_scope() as session:
        query = (
            select(ForgeAdaptation, ForgeCatalogueItem)
            .join(
                ForgeCatalogueItem,
                ForgeAdaptation.catalogue_item_id == ForgeCatalogueItem.id,
                isouter=True,
            )
            .where(*where)
        )
        if source:
            query = query.where(ForgeCatalogueItem.source == source)
        rows = session.execute(
            query.order_by(ForgeAdaptation.updated_at.desc(), ForgeAdaptation.id.desc())
            # One more than asked for, so *is there another page* is answered by the rows
            # themselves rather than by a second count that can disagree with them.
            .limit(limit + 1)
        ).all()
        items = [_row(row, item) for row, item in rows[:limit]]

    following = None
    if len(rows) > limit and items:
        following = Cursor(updated_at=items[-1].updated_at, id=items[-1].id).encode()
    return Page(items=tuple(items), next_cursor=following)


def detail(adaptation_id: str) -> Adaptation:
    """One adaptation, its revisions and its history, in one read.

    One session for the three, because a page renders them together: a revision list from one
    moment beside an event list from another shows an event about a revision that is not there.
    """
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        if row is None:
            raise KeyError(adaptation_id)
        item = session.get(ForgeCatalogueItem, row.catalogue_item_id)
        revisions = session.scalars(
            select(ForgeRevision)
            .where(ForgeRevision.adaptation_id == adaptation_id)
            .order_by(ForgeRevision.ordinal)
        ).all()
        events = session.scalars(
            select(ForgeEvent)
            .where(ForgeEvent.adaptation_id == adaptation_id)
            .order_by(ForgeEvent.id)
        ).all()
        return Adaptation(
            adaptation=_row(row, item),
            revisions=tuple(
                Revision(
                    id=revision.id,
                    ordinal=revision.ordinal,
                    state=revision.state,
                    green=revision.green,
                    unresolved_required=revision.unresolved_required,
                    validation=revision.validation,
                    created_at=revision.created_at,
                )
                for revision in revisions
            ),
            events=tuple(
                Event(
                    kind=event.kind,
                    from_state=(
                        AdaptationState(event.from_state) if event.from_state else None
                    ),
                    detail=event.detail,
                    actor=event.actor,
                    at=event.at,
                )
                for event in events
            ),
        )


def revision(adaptation_id: str, revision_id: str) -> Revision:
    """One revision — **and only if it belongs to this adaptation.**

    A revision fetched by id alone is a revision anybody can read by guessing, and the
    adaptation in the path would then be decoration. `forge_state.add_revision` makes the same
    check from the other direction.
    """
    with session_scope() as session:
        row = session.get(ForgeRevision, revision_id)
        if row is None or row.adaptation_id != adaptation_id:
            raise KeyError(revision_id)
        return Revision(
            id=row.id,
            ordinal=row.ordinal,
            state=row.state,
            green=row.green,
            unresolved_required=row.unresolved_required,
            validation=row.validation,
            created_at=row.created_at,
        )


def _current(adaptation_id: str) -> tuple[AdaptationState, int]:
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        if row is None:
            raise KeyError(adaptation_id)
        return AdaptationState(row.state), row.row_version


def retry(adaptation_id: str, *, who: str) -> AdaptationRow:
    _, version = _current(adaptation_id)
    forge_state.retry(adaptation_id, row_version=version, actor=who)
    return detail(adaptation_id).adaptation


def request_changes(adaptation_id: str, *, who: str, reason: str) -> AdaptationRow:
    _, version = _current(adaptation_id)
    forge_state.request_changes(adaptation_id, row_version=version, who=who, reason=reason)
    return detail(adaptation_id).adaptation


def approve(
    adaptation_id: str, *, who: str, reason: str, registry_digest_now: str
) -> AdaptationRow:
    """**Every approval condition is `approval_refusals`', not this function's.**

    `forge_state.approve` reports all six unmet conditions together rather than the first, and
    re-deciding any of them here would be a second answer that agrees today.
    """
    _, version = _current(adaptation_id)
    forge_state.approve(
        adaptation_id,
        row_version=version,
        who=who,
        reason=reason,
        registry_digest_now=registry_digest_now,
    )
    return detail(adaptation_id).adaptation


def archive(adaptation_id: str, *, who: str, reason: str) -> AdaptationRow:
    """Close an adaptation nobody is working on.

    `expect` is read here rather than passed in by the caller, because the browser has one and
    the state machine has the truth — and `ALLOWED` refuses a running state anyway, so a stale
    read becomes `MF0300` rather than an archive of something in flight.
    """
    state, version = _current(adaptation_id)
    forge_state.archive(
        adaptation_id, expect=state, row_version=version, who=who, reason=reason
    )
    return detail(adaptation_id).adaptation


def begin(catalogue_item_id: str, *, who: str) -> AdaptationRow:
    """Create the durable state. **Enqueueing the scaffold is the route's job, not this one.**

    Splitting them is what lets a test walk the state machine without a queue, and it is the
    same split `services/gates.py` makes: the row is a fact, the job is a side effect, and a
    caller that cannot reach Redis should still be able to create the fact.
    """
    adaptation_id = forge_state.begin(catalogue_item_id, who=who)
    return detail(adaptation_id).adaptation


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
