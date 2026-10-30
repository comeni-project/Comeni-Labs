"""Cutting a registry release (forge MVP 6, spec §2).

The API reads public data, refuses what it can and queues; **the worker cuts**, because the worker
alone holds the token. It reads `main` again and tags exactly the commit whose checks it read.

Nothing is committed to `main`: notes are the fragments added since the last tag.
"""

import logging
from datetime import UTC, datetime
from time import monotonic

import sqlalchemy as sa
from comeni_core.diagnostics import coded
from comeni_flow.interpret import Refused
from mendel_forge.publishing import PublishUnavailable
from mendel_forge.releases import (
    Release,
    ReleaseUnavailable,
    Unreleased,
    key,
    newest_first,
    next_version,
    notes_from,
)
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from mendel_api import db, jobs
from mendel_api.models import ForgeAdaptation, ForgePullRequest, ForgeRelease
from mendel_api.services import forging, registry_releases
from mendel_api.services.forge_publish import publisher
from mendel_api.services.github_releases import source
from mendel_api.services.reports import publishing_token_set

log = logging.getLogger(__name__)

CACHE_SECONDS = 60
"""GitHub allows 60 public requests an hour, and one look at this page costs several."""
_seen: tuple[float, Unreleased, list[Release]] | None = None


class ReleaseRow(BaseModel):
    version: str
    state: str
    """`cutting`, `done` or `failed`."""
    says: str | None
    commit: str | None
    cut_by: str
    cut_at: datetime


class MergedTool(BaseModel):
    module: str
    version: str | None
    number: int
    url: str


class ReleasesPage(BaseModel):
    in_use: str
    published: list[Release] = []
    unreleased: Unreleased | None = None
    merged: list[MergedTool] = []
    suggested: str = ""
    notes: str = ""
    recent: list[ReleaseRow] = []
    unavailable: str | None = None
    """Why this installation cannot cut a release, when it cannot."""
    problem: str | None = None
    """Why the page could not read GitHub, when it could not."""


def forget() -> None:
    global _seen
    _seen = None


def _read() -> tuple[Unreleased, list[Release]]:
    global _seen
    if _seen is not None and monotonic() - _seen[0] < CACHE_SECONDS:
        return _seen[1], _seen[2]
    where = source()
    found = where.unreleased(), newest_first(where.releases())
    _seen = (monotonic(), *found)
    return found


def _recent(session) -> list[ReleaseRow]:
    rows = session.scalars(sa.select(ForgeRelease).order_by(ForgeRelease.id.desc()).limit(10))
    return [ReleaseRow(version=r.version, state=r.state, says=r.says, commit=r.commit,
                       cut_by=r.cut_by, cut_at=r.cut_at) for r in rows]


def _merged(session) -> list[MergedTool]:
    """Merged forge pull requests after the last cut release: the page's second list."""
    since = session.scalar(sa.select(sa.func.max(ForgeRelease.cut_at)).where(
        ForgeRelease.state == "done"))
    query = sa.select(ForgeAdaptation, ForgePullRequest).join(
        ForgePullRequest, ForgePullRequest.adaptation == ForgeAdaptation.id
    ).where(ForgePullRequest.state == "merged")
    if since is not None:
        query = query.where(ForgePullRequest.merged_at > since)
    return [MergedTool(module=f"{a.source}/{a.path}", version=a.version, number=p.number,
                       url=p.url) for a, p in session.execute(query.order_by(ForgePullRequest.id))]


def overview() -> ReleasesPage:
    with db.session_scope() as session:
        recent, merged = _recent(session), _merged(session)
    page = ReleasesPage(in_use=registry_releases.describe(), recent=recent, merged=merged,
                        unavailable=None if publishing_token_set() else forging.NO_TOKEN)
    try:
        unreleased, published = _read()
    except ReleaseUnavailable as error:
        return page.model_copy(update={"problem": str(error)})
    return page.model_copy(update={
        "unreleased": unreleased, "published": published,
        "suggested": next_version(unreleased.last), "notes": notes_from(unreleased.fragments),
    })


def _refused(says: str) -> Refused:
    return Refused(coded("MF0519", says))


def _check(version: str, now: Unreleased) -> None:
    if key(version) is None:
        raise _refused(f"{version!r} is not a version: vMAJOR.MINOR.PATCH")
    if now.last and key(now.last) and key(version) <= key(now.last):
        raise _refused(f"{version} is not newer than {now.last}")
    if now.ahead == 0:
        raise _refused("there is nothing to release: main has not moved since "
                       f"{now.last}")
    if now.checks != "green":
        raise _refused(now.says or f"CI on main is {now.checks}")


async def start(version: str, notes: str, by: str) -> ReleasesPage:
    """A person's click: refused what it can be now, then queued for the worker."""
    if not publishing_token_set():
        raise Refused(forging.NO_TOKEN)
    forget()
    try:
        now, _ = _read()
    except ReleaseUnavailable as error:
        raise _refused(str(error)) from None
    _check(version, now)
    try:
        with db.transaction() as session:
            session.execute(sa.delete(ForgeRelease).where(
                ForgeRelease.version == version, ForgeRelease.state == "failed"))
            session.add(ForgeRelease(version=version, notes=notes, state="cutting", cut_by=by,
                                     cut_at=datetime.now(UTC)))
    except IntegrityError:
        raise _refused("a release is being cut: wait for it to finish") from None
    try:
        queued = await jobs.enqueue("cut_forge_release", version,
                                    job_id=f"cut-forge-release:{version}")
    except Exception:
        queued = False
    if not queued:
        _end(version, "failed", "it could not be queued: try again", None)
        raise _refused("the release could not be queued: try again")
    return overview()


def _end(version: str, state: str, says: str | None, commit: str | None) -> None:
    with db.session_scope() as session:
        row = session.scalar(sa.select(ForgeRelease).where(ForgeRelease.version == version))
        row.state, row.says, row.commit = state, says, commit
    forget()


def cut(version: str) -> None:
    """Read `main` again, and tag exactly that commit. Any refusal is recorded on the row."""
    with db.session_scope() as session:
        notes = session.scalar(sa.select(ForgeRelease.notes).where(
            ForgeRelease.version == version))
    try:
        github = publisher()
        if github is None:
            raise PublishUnavailable(forging.NO_TOKEN)
        now = source().unreleased()
        _check(version, now)
        github.cut_release(version, notes, now.commit)
    except (Refused, PublishUnavailable, ReleaseUnavailable) as error:
        log.warning("release %s was not cut: %s", version, error)
        _end(version, "failed", str(error), None)
        return
    _end(version, "done", None, now.commit)
