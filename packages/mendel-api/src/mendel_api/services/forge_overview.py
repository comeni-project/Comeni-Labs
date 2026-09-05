"""One query per band of the forge's front page, and no item on it.

**The overview counts and never lists.** `docs/design/forge-review.md` §3 records an Overview
page that was designed and cut for answering the same question as the queue, so the moment a
tool ref or an adaptation id appears here it has become the page that was cut. Plan 3B's landing
page holds the same line and a test holds it there; this is that rule for the forge's own front
door.

**Counts describe the unfiltered world.** §7: *counts always describe the unfiltered snapshot;
the page result describes the current filter*. A facet that counts only what is shown reads 12
in the band you are standing in and 0 in every other, which is the opposite of what a facet is
for — a defect both screens this replaces had already found and fixed independently.
"""

from datetime import UTC, datetime, timedelta

from mendel_forge.workflow import AdaptationState
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from mendel_api.db import session_scope
from mendel_api.models import ForgeAdaptation, ForgeSourceSnapshot
from mendel_api.services import forge_catalogue
from mendel_api.services.forge_state import AI_HELD
from mendel_api.settings import settings

_FROZEN = ConfigDict(extra="forbid", frozen=True)

STALE_REVIEW_HOURS = 72
"""How long a candidate may sit in `review` before it is *waiting on somebody*.

Three days rather than a working day, because a curator is not a queue consumer: an adaptation
raised on a Friday and read on a Monday is the ordinary case, and a number that flags it teaches
people to ignore the flag.
"""

SNAPSHOT_STALE_HOURS = 24
"""When a source's catalogue stops being something to rely on. Upstream moves daily at most, and
a snapshot older than this is one nobody has refreshed rather than one nothing changed in."""


class SourceRow(BaseModel):
    """One source's counts, plus whether its last look at upstream worked."""

    model_config = _FROZEN

    source: str
    discovered: int
    adaptable: int
    adapted: int
    current: int
    outdated: int
    in_progress: int
    unsupported: int
    last_synced_at: datetime | None = None
    snapshot_stale: bool = False
    sync_error: str = ""
    """The stored code, never upstream's message — `MI0104`, and the reason is on that entry."""


class Stages(BaseModel):
    """How many adaptations are at each stage a person might act on.

    `published` and `archived` are absent on purpose: they are finished, and a band counting
    them would be a band whose number only ever grows, which reads as work rather than history.
    """

    model_config = _FROZEN

    scaffolding: int = 0
    queued: int = 0
    generating: int = 0
    validating: int = 0
    review: int = 0
    changes_requested: int = 0
    failed: int = 0


class AiLane(BaseModel):
    """What the AI worker is doing, and how long the front of its queue has waited.

    **`waiting` is counted from the database, not from Redis.** A queue depth read from the
    broker counts jobs; this counts adaptations, and they disagree exactly when something has
    gone wrong — a job delivered whose row never moved. Counting the thing a person cares about
    is what makes that visible instead of reassuring.
    """

    model_config = _FROZEN

    concurrency: int
    active: int
    waiting: int
    oldest_wait_seconds: int


class NeedsYou(BaseModel):
    """What needs somebody, in the four shapes it comes in.

    **Not `Attention`, and the name is load-bearing.** `services/attention.py` already has a
    class by that name, and FastAPI disambiguates two schemas sharing one by qualifying BOTH
    with their module path — so adding this one silently renamed the existing
    `Attention` to `mendel_api__services__attention__Attention` in the served document, and
    the generated client stopped compiling on a screen that had not been touched.

    Nothing in the API suite noticed: `make check` does not typecheck the frontend, and the
    schema is only a contract when both consumers are built. The board it broke is the
    front door.
    """

    model_config = _FROZEN

    failed_syncs: int = 0
    failed_adaptations: int = 0
    stale_review_count: int = 0
    outdated_count: int = 0


class Overview(BaseModel):
    model_config = _FROZEN

    sources: tuple[SourceRow, ...] = ()
    stages: Stages
    ai_lane: AiLane
    attention: NeedsYou


def _by_state() -> dict[str, int]:
    with session_scope() as session:
        rows = session.execute(
            select(ForgeAdaptation.state, func.count()).group_by(ForgeAdaptation.state)
        ).all()
    return {state: int(count) for state, count in rows}


def _oldest_wait_seconds() -> int:
    """How long the oldest queued adaptation has been waiting, in whole seconds.

    Zero when nothing is waiting, rather than `None`: a band that has to render *no oldest wait*
    differently from *nothing waiting* is a band with two empty states for one fact.
    """
    with session_scope() as session:
        oldest = session.scalar(
            select(func.min(ForgeAdaptation.updated_at)).where(
                ForgeAdaptation.state == AdaptationState.QUEUED.value
            )
        )
    if oldest is None:
        return 0
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    return max(0, int((datetime.now(UTC) - oldest).total_seconds()))


def _stale_reviews(hours: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    with session_scope() as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(ForgeAdaptation)
                .where(
                    ForgeAdaptation.state == AdaptationState.REVIEW.value,
                    ForgeAdaptation.updated_at < cutoff,
                )
            )
            or 0
        )


def _failed_syncs() -> int:
    """Sources whose *most recent* snapshot failed.

    **Most recent, not any.** Counting every failed snapshot ever would make a source that broke
    once in March permanently red, and the number would only grow — which is the same defect as
    counting finished adaptations in `Stages`.
    """
    with session_scope() as session:
        latest = (
            select(
                ForgeSourceSnapshot.source,
                func.max(ForgeSourceSnapshot.started_at).label("at"),
            )
            .group_by(ForgeSourceSnapshot.source)
            .subquery()
        )
        return int(
            session.scalar(
                select(func.count())
                .select_from(ForgeSourceSnapshot)
                .join(
                    latest,
                    (ForgeSourceSnapshot.source == latest.c.source)
                    & (ForgeSourceSnapshot.started_at == latest.c.at),
                )
                .where(ForgeSourceSnapshot.ok.is_(False))
            )
            or 0
        )


def overview(landed: dict | None = None) -> Overview:
    """The whole front page, in one call.

    `landed` maps a tool ref to what the registry already has, and it is passed in rather than
    read here: `forge_catalogue.counts` needs it to tell *adapted* from *outdated*, and the
    registry is a different store with a different refresh. A default of `{}` reports every
    adaptable tool as un-adapted, which is wrong but visibly so.
    """
    landed = landed or {}
    by_state = _by_state()
    sources = []
    with session_scope() as session:
        names = sorted(
            {row for (row,) in session.execute(select(ForgeSourceSnapshot.source).distinct())}
        )
    for name in names:
        counts = forge_catalogue.counts(name, landed)
        snapshot = forge_catalogue.latest(name)
        synced = snapshot.finished_at if snapshot else None
        if synced is not None and synced.tzinfo is None:
            synced = synced.replace(tzinfo=UTC)
        sources.append(
            SourceRow(
                source=name,
                discovered=counts.discovered,
                adaptable=counts.adaptable,
                adapted=counts.adapted,
                current=counts.current,
                outdated=counts.outdated,
                in_progress=counts.in_progress,
                unsupported=counts.unsupported,
                last_synced_at=synced,
                snapshot_stale=(
                    synced is None
                    or synced < datetime.now(UTC) - timedelta(hours=SNAPSHOT_STALE_HOURS)
                ),
                sync_error="" if snapshot is None or snapshot.ok else (snapshot.error or ""),
            )
        )

    return Overview(
        sources=tuple(sources),
        stages=Stages(**{state.value: by_state.get(state.value, 0) for state in _STAGES}),
        ai_lane=AiLane(
            concurrency=settings.ai_max_jobs,
            active=sum(by_state.get(state.value, 0) for state in AI_HELD),
            waiting=by_state.get(AdaptationState.QUEUED.value, 0),
            oldest_wait_seconds=_oldest_wait_seconds(),
        ),
        attention=NeedsYou(
            failed_syncs=_failed_syncs(),
            failed_adaptations=by_state.get(AdaptationState.FAILED.value, 0),
            stale_review_count=_stale_reviews(STALE_REVIEW_HOURS),
            outdated_count=sum(row.outdated for row in sources),
        ),
    )


_STAGES = (
    AdaptationState.SCAFFOLDING,
    AdaptationState.QUEUED,
    AdaptationState.GENERATING,
    AdaptationState.VALIDATING,
    AdaptationState.REVIEW,
    AdaptationState.CHANGES_REQUESTED,
    AdaptationState.FAILED,
)
"""The stages `Stages` reports, in the order a tool passes through them.

**Derived from `AdaptationState` minus the finished two rather than typed out**, is what this
should be — and it is not, because the order matters and a set has none. What holds it instead
is `test_every_unfinished_state_is_a_stage`, which fails when a state is added to the workflow
and not to this tuple. That is the same arrangement `HINTS` uses for `HoleKind`.
"""
