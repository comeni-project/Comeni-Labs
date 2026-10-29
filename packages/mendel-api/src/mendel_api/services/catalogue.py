"""The forge's stored catalogue: syncing it, and (below) reading it (forge part 1 spec, §3–5).

**A sync writes all or nothing.** Every module is read from the source before one transaction
writes them, so a source that fails midway leaves the catalogue as the last good sync left it,
and the failed sync is recorded with why.
"""

import logging
from datetime import UTC, datetime

import sqlalchemy as sa
from mendel_forge.model import UpstreamModule
from mendel_forge.nfcore.source import NfCoreSource
from mendel_forge.source import CatalogueSource
from sqlalchemy.dialects.postgresql import insert

from mendel_api import db
from mendel_api.models import CatalogueModule, CatalogueSync, SyncOutcome
from mendel_api.settings import settings

log = logging.getLogger(__name__)


def run_sync(source: CatalogueSource | None = None) -> CatalogueSync:
    source = source or NfCoreSource()
    with db.session_scope() as session:
        sync = CatalogueSync(source=source.name, started_at=datetime.now(UTC),
                             outcome=SyncOutcome.RUNNING)
        session.add(sync)
        session.flush()
        sync_id = sync.id
    try:
        snapshot = source.sync(settings.forge_cache)
        modules = list(source.modules(snapshot))
        with db.transaction() as session:
            _store(session, source.name, sync_id, modules)
            done = session.get(CatalogueSync, sync_id)
            done.commit = snapshot.commit
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
        "topics": module.topics,
        "formats": sorted({*module.formats_in, *module.formats_out}),
        "upstream_changed": module.upstream_changed,
        "search": " ".join(words).lower(),
        "document": module.model_dump(mode="json"),
        "seen_in": sync_id,
        "gone": False,
    }


def last_sync() -> CatalogueSync | None:
    with db.session_scope() as session:
        return session.scalar(sa.select(CatalogueSync).order_by(CatalogueSync.id.desc()).limit(1))


def last_good_sync() -> CatalogueSync | None:
    with db.session_scope() as session:
        return session.scalar(
            sa.select(CatalogueSync)
            .where(CatalogueSync.outcome == SyncOutcome.OK)
            .order_by(CatalogueSync.id.desc())
            .limit(1)
        )
