"""The forge's stored catalogue: syncing it, and (below) reading it (forge part 1 spec, §3–5).

**A sync writes all or nothing.** Every module is read from the source before one transaction
writes them, so a source that fails midway leaves the catalogue as the last good sync left it,
and the failed sync is recorded with why.
"""

import hashlib
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum

import sqlalchemy as sa
from mendel_forge import state as state_module
from mendel_forge.model import Problem, UpstreamModule
from mendel_forge.nfcore.source import TEST_DATASETS, NfCoreSource
from mendel_forge.source import CatalogueSource, SourceUnavailable
from mendel_forge.state import BEST_ORDER, Held, State
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert

from mendel_api import db
from mendel_api.models import (
    CatalogueModule,
    CatalogueSync,
    ForgeAdaptation,
    ForgePullRequest,
    SyncOutcome,
)
from mendel_api.services import registry
from mendel_api.settings import settings

log = logging.getLogger(__name__)


def claim_key(source: str) -> int:
    """The advisory-lock key that claims a source's sync: a stable 63-bit number."""
    return int.from_bytes(hashlib.sha256(f"catalogue_sync:{source}".encode()).digest()[:8],
                          "big") >> 1


@contextmanager
def _claim(source: str) -> Iterator[bool]:
    """**One sync per source at a time**, whoever asked (the daily run or *Sync now*).

    A session-level advisory lock on its own connection: Postgres releases it if the worker dies,
    so a crash never leaves the source claimed, which a `running` row alone would."""
    with db.engine.connect() as connection:
        claimed = connection.execute(sa.text("SELECT pg_try_advisory_lock(:k)"),
                                     {"k": claim_key(source)}).scalar()
        try:
            yield bool(claimed)
        finally:
            if claimed:
                connection.execute(sa.text("SELECT pg_advisory_unlock(:k)"),
                                   {"k": claim_key(source)})


def sync_running(source: str = "nf-core") -> bool:
    """Whether a sync holds the source now. Asked of the lock, not of the rows: a row a crash
    left `running` holds nothing."""
    with _claim(source) as claimed:
        return not claimed


def run_sync(source: CatalogueSource | None = None) -> CatalogueSync | None:
    """Sync `source`; `None` when another sync holds it, and nothing was started."""
    source = source or NfCoreSource(data_url=TEST_DATASETS)
    with _claim(source.name) as claimed:
        if not claimed:
            return None
        return _sync(source)


def _sync(source: CatalogueSource) -> CatalogueSync:
    with db.session_scope() as session:
        # Holding the claim, no other sync is alive: a `running` row is one a crash left.
        session.execute(
            sa.update(CatalogueSync)
            .where(CatalogueSync.source == source.name,
                   CatalogueSync.outcome == SyncOutcome.RUNNING)
            .values(outcome=SyncOutcome.FAILED, finished_at=datetime.now(UTC),
                    error="interrupted: the worker stopped before this sync finished")
        )
        sync = CatalogueSync(source=source.name, started_at=datetime.now(UTC),
                             outcome=SyncOutcome.RUNNING)
        session.add(sync)
        session.flush()
        sync_id = sync.id
    try:
        snapshot = source.sync(settings.forge_cache)
        modules = list(source.modules(snapshot))
        if not modules:
            # A moved upstream or a broken checkout, not an empty catalogue: storing it would
            # mark every module gone.
            raise SourceUnavailable(f"{source.name} at {snapshot.commit} read no modules")
        with db.transaction() as session:
            _store(session, source.name, sync_id, modules)
            done = session.get(CatalogueSync, sync_id)
            done.commit = snapshot.commit
            done.test_data_commit = snapshot.test_data_commit
            done.modules = len(modules)
            done.problems = sum(1 for module in modules if module.problems)
            done.outcome = SyncOutcome.OK
            done.finished_at = datetime.now(UTC)
    except Exception as error:
        log.warning("catalogue sync %d of %s failed: %s", sync_id, source.name, error)
        with db.session_scope() as session:
            failed = session.get(CatalogueSync, sync_id)
            failed.outcome = SyncOutcome.FAILED
            failed.error = str(error)
            failed.finished_at = datetime.now(UTC)
    with db.session_scope() as session:
        return session.get(CatalogueSync, sync_id)


def _store(session, source: str, sync_id: int, modules: list[UpstreamModule]) -> None:
    rows = [_row(source, sync_id, module) for module in modules]
    for start in range(0, len(rows), 500):
        statement = insert(CatalogueModule).values(rows[start:start + 500])
        columns = ("name", "tool_version", "topics", "formats", "upstream_changed", "search",
                   "document", "seen_in", "gone")
        session.execute(statement.on_conflict_do_update(
            index_elements=["source", "path"],
            set_={column: statement.excluded[column] for column in columns},
        ))
    seen = [module.path for module in modules]
    session.execute(
        sa.update(CatalogueModule)
        .where(CatalogueModule.source == source, CatalogueModule.path.not_in(seen))
        .values(gone=True)
    )


def _row(source: str, sync_id: int, module: UpstreamModule) -> dict:
    words = [module.name, module.description or "", *module.keywords,
             *(tool.name for tool in module.tools), *module.formats_in, *module.formats_out]
    return {
        "source": source,
        "path": module.path,
        "name": module.name,
        "tool_version": module.tool_version,
        # Within the columns' widths: one odd value upstream must not abort the sync.
        "topics": [topic for topic in module.topics if len(topic) <= 64],
        "formats": sorted({f for f in (*module.formats_in, *module.formats_out) if len(f) <= 32}),
        "upstream_changed": module.upstream_changed,
        "search": " ".join(words).lower(),
        "document": module.model_dump(mode="json"),
        "seen_in": sync_id,
        "gone": False,
    }


def last_sync() -> CatalogueSync | None:
    with db.session_scope() as session:
        return session.scalar(sa.select(CatalogueSync).order_by(CatalogueSync.id.desc()).limit(1))


def test_data_commit() -> str | None:
    """The newest `test-datasets` commit a sync read; a later sync may have failed to read it."""
    with db.session_scope() as session:
        return session.scalar(
            sa.select(CatalogueSync.test_data_commit)
            .where(CatalogueSync.test_data_commit.is_not(None))
            .order_by(CatalogueSync.id.desc())
            .limit(1)
        )


def last_good_sync() -> CatalogueSync | None:
    with db.session_scope() as session:
        return session.scalar(
            sa.select(CatalogueSync)
            .where(CatalogueSync.outcome == SyncOutcome.OK)
            .order_by(CatalogueSync.id.desc())
            .limit(1)
        )


# ═══ Reading the catalogue ════════════════════════════════════════════════════════════════════


class ModuleRow(BaseModel):
    source: str
    path: str
    name: str
    description: str | None
    formats_in: list[str]
    formats_out: list[str]
    tool_version: str | None
    state: State
    registry_version: str | None
    """The contract's version when the registry holds the module, else `None`."""
    contract_id: str | None
    problems: list[Problem]


class Counts(BaseModel):
    """Over the whole catalogue, not the filtered view: a filter's count says how many it
    would show. `in_review` and `merged_not_released` are 0 until pull requests (part 4)."""

    states: dict[State, int]
    topics: dict[str, int]
    formats: dict[str, int]
    sources: dict[str, int]


class SyncView(BaseModel):
    outcome: str
    started_at: datetime
    finished_at: datetime | None
    commit: str | None
    error: str | None
    stale: bool
    """The last sync failed after a good one: the catalogue shown is the good one's."""


class CataloguePage(BaseModel):
    rows: list[ModuleRow]
    total: int
    counts: Counts
    last_good: SyncView | None
    last: SyncView | None
    next_offset: int | None
    registry_at: str


class ModuleDetail(BaseModel):
    row: ModuleRow
    module: UpstreamModule


class Sort(StrEnum):
    BEST = "best"
    NAME = "name"
    UPSTREAM_CHANGED = "upstream_changed"


def _publishing(held: dict[str, Held]) -> dict[str, State]:
    """Modules on their way through a pull request. A merged one reads as merged until the
    registry this installation loads carries that version."""
    with db.session_scope() as session:
        rows = session.execute(
            sa.select(ForgeAdaptation.path, ForgeAdaptation.version, ForgePullRequest.state)
            .join(ForgePullRequest, ForgePullRequest.adaptation == ForgeAdaptation.id)
            .where(ForgePullRequest.state.in_(("open", "merged")))
            .order_by(ForgePullRequest.id)
        ).all()
    found: dict[str, State] = {}
    for path, version, state in rows:
        if state == "open":
            found[path] = State.IN_REVIEW
        elif path not in held or held[path].version != version:
            found[path] = State.MERGED
    return found


def _state_expression(held: dict[str, Held]) -> sa.ColumnElement[str]:
    """`mendel_forge.state.state_of` in SQL, so the state filter and sort run in the database.
    The registry holds tens of modules, so the `CASE` stays small."""
    column, version = CatalogueModule.path, CatalogueModule.tool_version
    whens = [(column == path, state.value) for path, state in _publishing(held).items()]
    whens.append((CatalogueModule.gone.is_(True), State.GONE.value))
    for path, here in held.items():
        whens += [
            (sa.and_(column == path, version.is_(None)), State.UNKNOWN.value),
            (sa.and_(column == path, version == here.version), State.IMPORTED.value),
            (column == path, State.UPDATE.value),
        ]
    return sa.case(*whens, else_=State.NOT_IMPORTED.value)


def _visible(held: dict[str, Held]) -> sa.ColumnElement[bool]:
    """Live modules, and gone ones the registry still holds (listed so a registry tool never
    vanishes from its own catalogue)."""
    return sa.or_(CatalogueModule.gone.is_(False), CatalogueModule.path.in_(list(held)))


def _escaped(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def read_page(
    *,
    state: State | None = None,
    topics: list[str] = (),
    formats: list[str] = (),
    source: str | None = None,
    q: str | None = None,
    sort: Sort = Sort.BEST,
    offset: int = 0,
    limit: int = 50,
) -> CataloguePage:
    held = state_module.held(registry.stack())
    state_of = _state_expression(held).label("state")
    where = [_visible(held)]
    if state is not None:
        where.append(state_of == state.value)
    if topics:
        where.append(CatalogueModule.topics.overlap(list(topics)))
    if formats:
        where.append(CatalogueModule.formats.overlap(list(formats)))
    if source:
        where.append(CatalogueModule.source == source)
    needle = (q or "").strip().lower()
    if needle:
        where.append(CatalogueModule.search.ilike(f"%{_escaped(needle)}%", escape="\\"))
    with db.session_scope() as session:
        counted = sa.select(sa.func.count()).select_from(CatalogueModule).where(*where)
        total = session.scalar(counted)
        query = sa.select(CatalogueModule, state_of).where(*where)
        query = query.order_by(*_order(sort, needle, state_of), CatalogueModule.path)
        found = session.execute(query.offset(offset).limit(limit)).all()
        rows = [_row_view(module, State(value), held) for module, value in found]
        counts = _counts(session, held)
    end = offset + len(rows)
    return CataloguePage(
        rows=rows, total=total, counts=counts,
        last_good=_view(last_good_sync()), last=_view(last_sync()),
        next_offset=end if end < total else None,
        registry_at=registry.registry_label(),
    )


def _order(sort: Sort, needle: str, state_of) -> list:
    if sort is Sort.NAME:
        return [CatalogueModule.name]
    if sort is Sort.UPSTREAM_CHANGED:
        return [CatalogueModule.upstream_changed.desc().nulls_last()]
    if needle:
        return [sa.func.word_similarity(needle, CatalogueModule.search).desc(),
                CatalogueModule.name]
    rank = sa.case(*[(state_of == s.value, n) for n, s in enumerate(BEST_ORDER)],
                   else_=len(BEST_ORDER))
    return [rank, CatalogueModule.name]


def _counts(session, held: dict[str, Held]) -> Counts:
    visible = _visible(held)
    state_of = _state_expression(held)
    states = {s: 0 for s in State}
    for value, n in session.execute(
        sa.select(state_of, sa.func.count()).where(visible).group_by(state_of)
    ):
        states[State(value)] = n

    def tally(column) -> dict[str, int]:
        item = sa.func.unnest(column).label("item")
        inner = sa.select(item).where(visible).subquery()
        grouped = sa.select(inner.c.item, sa.func.count()).group_by(inner.c.item)
        return dict(session.execute(grouped.order_by(inner.c.item)).all())

    sources = dict(session.execute(
        sa.select(CatalogueModule.source, sa.func.count()).where(visible)
        .group_by(CatalogueModule.source)
    ).all())
    return Counts(states=states, topics=tally(CatalogueModule.topics),
                  formats=tally(CatalogueModule.formats), sources=sources)


def _row_view(module: CatalogueModule, state: State, held: dict[str, Held]) -> ModuleRow:
    document = UpstreamModule.model_validate(module.document)
    here = held.get(module.path)
    return ModuleRow(
        source=module.source, path=module.path, name=module.name,
        description=document.description, formats_in=document.formats_in,
        formats_out=document.formats_out, tool_version=module.tool_version, state=state,
        registry_version=here.version if here else None,
        contract_id=here.contract_id if here else None, problems=document.problems,
    )


def _view(sync: CatalogueSync | None) -> SyncView | None:
    if sync is None:
        return None
    good = last_good_sync()
    stale = sync.outcome == SyncOutcome.FAILED and good is not None and good.id < sync.id
    return SyncView(outcome=sync.outcome, started_at=sync.started_at,
                    finished_at=sync.finished_at, commit=sync.commit, error=sync.error,
                    stale=stale)


def read_module(source: str, path: str) -> ModuleDetail:
    """One module, gone or not. `KeyError` when the catalogue has never seen it."""
    held = state_module.held(registry.stack())
    with db.session_scope() as session:
        found = session.execute(
            sa.select(CatalogueModule, _state_expression(held))
            .where(CatalogueModule.source == source, CatalogueModule.path == path)
        ).first()
    if found is None:
        raise KeyError(f"{source}/{path}")
    module, value = found
    return ModuleDetail(row=_row_view(module, State(value), held),
                        module=UpstreamModule.model_validate(module.document))


def detail_for(upstream_path: str, source: str = "nf-core") -> ModuleDetail | None:
    try:
        return read_module(source, upstream_path)
    except KeyError:
        return None


def sync_job_id() -> str:
    """Keyed on the last sync, so two clicks before the job starts share one id (ARQ refuses
    the second), and a finished sync never blocks the next for as long as ARQ keeps its result."""
    last = last_sync()
    return f"sync_catalogue:after:{last.id if last else 0}"
