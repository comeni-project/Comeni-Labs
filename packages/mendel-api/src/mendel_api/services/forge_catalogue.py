"""What an upstream source last said, stored so a page does not have to ask it again.

**This caches; it does not accept.** The rows here are what nf-core and PEGiS publish right
now, read over the network and replaced on the next sync. Nothing a build reads comes from
this table — `models.ForgeCatalogueItem` states the test: delete it and a build emits the same
bytes. The registry stays files.

**A failed sync never blanks a catalogue.** `record_failure` writes a snapshot row that says
what went wrong and leaves every item where it was, so a page shows *stale, and here is why*
rather than zero tools. That is why `SourceSnapshot` in `mendel-forge` is only ever a success:
the failure has a different shape and lives only here.
"""

import secrets
from collections.abc import Mapping
from datetime import UTC, datetime

from mendel_forge.catalogue import (
    CatalogueItem,
    Freshness,
    LandedSource,
    SourceCounts,
    SourceSnapshot,
)
from mendel_forge.workflow import ACTIVE, TERMINAL, AdaptationState
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from mendel_api.db import session_scope
from mendel_api.models import ForgeAdaptation, ForgeCatalogueItem, ForgeSourceSnapshot


def _now() -> datetime:
    return datetime.now(UTC)


def _last_success(session: Session, source: str) -> str | None:
    return session.scalars(
        select(ForgeSourceSnapshot.id)
        .where(ForgeSourceSnapshot.source == source, ForgeSourceSnapshot.ok.is_(True))
        .order_by(ForgeSourceSnapshot.started_at.desc())
        .limit(1)
    ).first()


def record(snapshot: SourceSnapshot, *, started_at: datetime | None = None) -> str:
    """Store one successful sync and reconcile the source's items against it.

    **Every item seen is stamped with this snapshot's id, and anything left carrying an older
    one is marked absent.** That is one `UPDATE` rather than a `NOT IN` over sixteen hundred
    ids, and it needs no second pass to work out what was missing — the rows say so themselves.

    Absent rather than deleted: a tool that vanished upstream keeps its row, and so does every
    adaptation, revision and event that points at it. Deleting the item would take an approved
    contract's provenance with it, and a foreign key with no cascade is what turns that mistake
    into a refusal.
    """
    snapshot_id = secrets.token_hex(16)
    counts_without_workflow = _counts_from_items(snapshot.items)
    with session_scope() as session:
        session.add(
            ForgeSourceSnapshot(
                id=snapshot_id,
                source=snapshot.source,
                source_revision=snapshot.source_revision,
                etag=snapshot.etag,
                started_at=started_at or snapshot.synced_at,
                finished_at=snapshot.synced_at,
                ok=True,
                error="",
                counts=counts_without_workflow,
                filters=[node.model_dump(mode="json") for node in snapshot.filters],
                warnings=[w.model_dump(mode="json") for w in snapshot.warnings],
                last_successful_sync_id=snapshot_id,
            )
        )
        session.flush()

        seen = _now()
        for item in snapshot.items:
            values = {
                "id": item.id,
                "snapshot_id": snapshot_id,
                "source": item.source,
                "ref": item.ref,
                "display_name": item.display_name,
                "summary": item.summary,
                "metadata": item.model_dump(mode="json"),
                "content_digest": item.content_digest,
                "adaptable": item.adaptable,
                "unsupported_reason": item.unsupported_reason or "",
                "present": True,
                "last_updated_at": item.last_updated_at,
                "first_seen_at": seen,
                "last_seen_at": seen,
            }
            # **Core, against `__table__`, rather than the ORM entity** — and that is a real
            # trap rather than a style choice. `insert(ForgeCatalogueItem).values(metadata=…)`
            # resolves `metadata` as an *attribute*, which on any declarative class is
            # SQLAlchemy's own `MetaData` object, and the failure is
            # `'MetaData' object has no attribute '_bulk_update_tuples'` several frames away
            # from anything that mentions this column. Against the table, the keys are column
            # names and there is no attribute to collide with.
            statement = insert(ForgeCatalogueItem.__table__).values(**values)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["id"],
                    # `first_seen_at` is deliberately absent: it is the one column an upsert
                    # must not touch. Overwriting it would make every tool look newly
                    # discovered on every sync, which is the number the overview page is for.
                    set_={
                        key: statement.excluded[key]
                        for key in values
                        if key not in ("id", "first_seen_at")
                    },
                )
            )

        session.execute(
            update(ForgeCatalogueItem)
            .where(
                ForgeCatalogueItem.source == snapshot.source,
                ForgeCatalogueItem.snapshot_id != snapshot_id,
            )
            .values(present=False)
        )
    return snapshot_id


def record_failure(source: str, *, error: str, started_at: datetime) -> str:
    """Store a sync that did not produce a snapshot. **No item is touched.**"""
    snapshot_id = secrets.token_hex(16)
    with session_scope() as session:
        session.add(
            ForgeSourceSnapshot(
                id=snapshot_id,
                source=source,
                started_at=started_at,
                finished_at=_now(),
                ok=False,
                error=error,
                counts={},
                filters=[],
                warnings=[],
                last_successful_sync_id=_last_success(session, source),
            )
        )
    return snapshot_id


def _counts_from_items(items: tuple[CatalogueItem, ...]) -> dict[str, int]:
    """The two numbers a sync knows on its own.

    The other five need the adaptation table and the registry, neither of which a sync has
    read. Storing zeros for them would be storing a measurement nobody took; `counts()` is
    where the full card is assembled, from three sources, at the moment it is asked for.
    """
    adaptable = sum(1 for item in items if item.adaptable)
    return {"discovered": len(items), "adaptable": adaptable}


_FROZEN = ConfigDict(extra="forbid", frozen=True)

_ACTIVE = [state.value for state in ACTIVE]
_PUBLISHED = AdaptationState.PUBLISHED.value


class Standing(BaseModel):
    """Where one catalogue item stands, and the adaptation that says so.

    **The adaptation id is here because the row's action needs it.** A catalogue row offers
    *Adapt this tool* or *Open the adaptation*, and a page that knew only the freshness would
    have to go and find the id — one request per row on a page of fifty.
    """

    model_config = _FROZEN

    freshness: Freshness
    adaptation_id: str | None = None
    adaptation_state: AdaptationState | None = None


def landed_of(source: str) -> dict[str, LandedSource]:
    """What the forge has published for a source, keyed by ref.

    **Read out of the forge's own tables, not out of the registry, and that is a narrower
    claim than `LandedSource` was designed for.** Its docstring says the registry is the
    authority on what has landed — and it is, but a contract's `Provenance` carries no source
    content digest, so the registry cannot answer *was it the current version that landed*.
    `ForgeAdaptation.source_digest` can, because it is the digest the adaptation was built
    from.

    What that costs: a contract removed from the registry by hand still reads as landed here,
    because the publish that put it there happened. That is a smaller error than the previous
    behaviour, which passed `{}` and reported every tool in the world as never adapted.
    Recording the source digest on the contract is what closes it, and it belongs to the
    publication boundary rather than here.
    """
    with session_scope() as session:
        rows = session.execute(
            select(ForgeCatalogueItem.ref, ForgeAdaptation.source_digest)
            .join(ForgeAdaptation, ForgeAdaptation.catalogue_item_id == ForgeCatalogueItem.id)
            .where(
                ForgeCatalogueItem.source == source,
                ForgeAdaptation.state == _PUBLISHED,
            )
            .order_by(ForgeAdaptation.updated_at)
        ).all()
    # Later rows win, so a tool published twice is described by its most recent publish.
    return {
        ref: LandedSource(source=source, ref=ref, content_digest=digest) for ref, digest in rows
    }


def standing(items: list[CatalogueItem]) -> dict[str, Standing]:
    """Freshness for a page of items, in two queries rather than one per row.

    **`CatalogueItem.freshness` is the one implementation and this calls it**, rather than
    re-deriving the same verdict from the same two digests — which is how the card and the row
    would come to disagree about a single tool.
    """
    if not items:
        return {}
    ids = [item.id for item in items]
    with session_scope() as session:
        published = {
            item_id: digest
            for item_id, digest in session.execute(
                select(ForgeAdaptation.catalogue_item_id, ForgeAdaptation.source_digest)
                .where(
                    ForgeAdaptation.catalogue_item_id.in_(ids),
                    ForgeAdaptation.state == _PUBLISHED,
                )
                .order_by(ForgeAdaptation.updated_at)
            ).all()
        }
        active = {
            item_id: (adaptation_id, AdaptationState(state))
            for item_id, adaptation_id, state in session.execute(
                select(
                    ForgeAdaptation.catalogue_item_id,
                    ForgeAdaptation.id,
                    ForgeAdaptation.state,
                ).where(
                    ForgeAdaptation.catalogue_item_id.in_(ids),
                    ForgeAdaptation.state.in_(_ACTIVE),
                )
            ).all()
        }

    out: dict[str, Standing] = {}
    for item in items:
        digest = published.get(item.id)
        was_landed = (
            LandedSource(source=item.source, ref=item.ref, content_digest=digest)
            if digest is not None
            else None
        )
        running = active.get(item.id)
        out[item.id] = Standing(
            freshness=item.freshness(was_landed, in_progress=running is not None),
            adaptation_id=running[0] if running else None,
            adaptation_state=running[1] if running else None,
        )
    return out


def _status_filter(status: str):
    """A `Freshness` value as a WHERE clause, so a filter is a query and not a page walk.

    **Filtering after paging is the defect this exists to avoid**: taking fifty rows and
    dropping the ones that do not match gives a page of eleven and a total of sixteen hundred,
    and the next page silently skips whatever the first one dropped.
    """
    published = (
        select(ForgeAdaptation.catalogue_item_id)
        .where(ForgeAdaptation.state == _PUBLISHED)
        .scalar_subquery()
    )
    current = (
        select(ForgeAdaptation.catalogue_item_id)
        .where(
            ForgeAdaptation.state == _PUBLISHED,
            ForgeAdaptation.source_digest == ForgeCatalogueItem.content_digest,
        )
        .scalar_subquery()
    )
    running = (
        select(ForgeAdaptation.catalogue_item_id)
        .where(ForgeAdaptation.state.in_(_ACTIVE))
        .scalar_subquery()
    )
    adaptable = ForgeCatalogueItem.adaptable.is_(True)
    return {
        Freshness.UNSUPPORTED.value: ForgeCatalogueItem.adaptable.is_(False),
        Freshness.CURRENT.value: adaptable & ForgeCatalogueItem.id.in_(current),
        Freshness.OUTDATED.value: adaptable
        & ForgeCatalogueItem.id.in_(published)
        & ForgeCatalogueItem.id.not_in(current),
        Freshness.IN_PROGRESS.value: adaptable
        & ForgeCatalogueItem.id.not_in(published)
        & ForgeCatalogueItem.id.in_(running),
        Freshness.UNADAPTED.value: adaptable
        & ForgeCatalogueItem.id.not_in(published)
        & ForgeCatalogueItem.id.not_in(running),
        # `adapted` is not a `Freshness` member: it is the union of the two landed verdicts,
        # and it is what the overview's *N of M adaptable* figure counts. Offered because a
        # person clicking that number means "the ones we have done", not "the current ones".
        "adapted": adaptable & ForgeCatalogueItem.id.in_(published),
    }.get(status)


def counts(source: str, landed: Mapping[str, LandedSource] | None = None) -> SourceCounts:
    """One source card, assembled from the catalogue, the workflow and the registry.

    `landed` is passed in rather than read here, and that is the boundary this service keeps:
    the registry is files, `services/registry.py` is what reads them, and a catalogue cache
    that opened a layer would be two answers to where declared data lives.

    **Freshness is digest equality, never a date** — `CatalogueItem.freshness` is the one
    implementation, and this counts its verdicts rather than re-deriving them.
    """
    if landed is None:
        landed = landed_of(source)
    with session_scope() as session:
        rows = session.scalars(
            select(ForgeCatalogueItem).where(
                ForgeCatalogueItem.source == source, ForgeCatalogueItem.present.is_(True)
            )
        ).all()
        active = set(
            session.scalars(
                select(ForgeAdaptation.catalogue_item_id).where(
                    ForgeAdaptation.state.not_in([s.value for s in TERMINAL])
                )
            ).all()
        )

    tally = dict.fromkeys(Freshness, 0)
    for row in rows:
        item = CatalogueItem.model_validate(row.metadata_json)
        tally[item.freshness(landed.get(item.ref), in_progress=row.id in active)] += 1

    adapted = tally[Freshness.CURRENT] + tally[Freshness.OUTDATED]
    return SourceCounts(
        discovered=len(rows),
        adaptable=len(rows) - tally[Freshness.UNSUPPORTED],
        unsupported=tally[Freshness.UNSUPPORTED],
        adapted=adapted,
        current=tally[Freshness.CURRENT],
        outdated=tally[Freshness.OUTDATED],
        in_progress=tally[Freshness.IN_PROGRESS],
    )


def latest(source: str) -> ForgeSourceSnapshot | None:
    """The most recent sync attempt, successful or not.

    Attempt rather than success on purpose: a page that only ever saw successes could not say
    *we tried twenty minutes ago and it failed*, which is the sentence that distinguishes stale
    data from abandoned data.
    """
    with session_scope() as session:
        return session.scalars(
            select(ForgeSourceSnapshot)
            .where(ForgeSourceSnapshot.source == source)
            .order_by(ForgeSourceSnapshot.started_at.desc())
            .limit(1)
        ).first()


def one(item_id: str) -> CatalogueItem:
    """One tool, by its opaque id.

    **A primary-key lookup, and it replaces a scan.** The route used to ask `search` for the
    first two hundred rows and walk them, so every tool past the two-hundredth answered 404 —
    invisible against a fixture catalogue of six and certain against a real one of sixteen
    hundred. Raising `KeyError` is what the transport turns into a 404, and it now means
    *no such tool* rather than *not in the first page*.
    """
    with session_scope() as session:
        row = session.get(ForgeCatalogueItem, item_id)
        if row is None or not row.present:
            raise KeyError(item_id)
        return CatalogueItem.model_validate(row.metadata_json)


def search(
    *,
    source: str | None = None,
    query: str = "",
    adaptable_only: bool = False,
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CatalogueItem], int]:
    """A page of the catalogue, and the total the page is a slice of.

    **The total is a second query rather than `len` of the page**, which is the whole point of
    paging: a page that reports its own length as the total says "50 tools" about a source with
    sixteen hundred. That is `MF0202`'s failure mode arriving through the front end instead of
    the adapter.

    Filtering is SQL over the denormalised `display_name`/`summary` columns rather than over
    the JSON document, and browser-side filtering is not offered at all — sixteen hundred rows
    is past the point where sending all of them to filter three is defensible.
    """
    where = [ForgeCatalogueItem.present.is_(True)]
    if source:
        where.append(ForgeCatalogueItem.source == source)
    if adaptable_only:
        where.append(ForgeCatalogueItem.adaptable.is_(True))
    if status:
        clause = _status_filter(status)
        if clause is None:
            raise ValueError(f"no such status: {status}")
        where.append(clause)
    if query.strip():
        like = f"%{query.strip().lower()}%"
        where.append(
            func.lower(ForgeCatalogueItem.ref).like(like)
            | func.lower(ForgeCatalogueItem.display_name).like(like)
            | func.lower(ForgeCatalogueItem.summary).like(like)
        )

    with session_scope() as session:
        total = session.scalar(
            select(func.count()).select_from(ForgeCatalogueItem).where(*where)
        )
        rows = session.scalars(
            select(ForgeCatalogueItem)
            .where(*where)
            .order_by(ForgeCatalogueItem.source, ForgeCatalogueItem.ref)
            .limit(limit)
            .offset(offset)
        ).all()
    return [CatalogueItem.model_validate(row.metadata_json) for row in rows], int(total or 0)
