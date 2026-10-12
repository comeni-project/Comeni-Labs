"""The daily sweep (Part H spec §5.2): what is past its limit goes, and every pass is recorded.

Two categories on this side: the builder's model replies (their text, never their record) and
drafts nobody has changed (whole, as a person deleting them would). The forge's calls are about
registry tools, never a sample, and are not swept. Limits are read from the installation's
settings on every pass, so a change on the menu reaches the next one.
"""

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from comeni_core.settings import catalogue
from comeni_core.settings.retention import days
from pydantic import BaseModel, ConfigDict

from mendel_api.db import session_scope
from mendel_api.models import AiInvocation, PipelineDraft, RetentionSweep
from mendel_api.services import deletion
from mendel_api.services.installation import installation

CATEGORIES = ("model_replies", "drafts")


class LastSweep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ran_at: datetime
    removed: dict[str, int]


def _limit(setting) -> int | None:
    return days(str(installation().get(setting)))


def sweep(now: datetime) -> dict[str, int]:
    removed = dict.fromkeys(CATEGORIES, 0)
    if (limit := _limit(catalogue.MODEL_REPLIES)) is not None:
        with session_scope() as db:
            removed["model_replies"] = deletion.clear_replies(
                db, sa.and_(AiInvocation.agent == "builder",
                            AiInvocation.started_at < now - timedelta(days=limit)),
                "retention")
    if (limit := _limit(catalogue.DRAFTS)) is not None:
        with session_scope() as db:
            old = list(db.scalars(sa.select(PipelineDraft.id).where(
                PipelineDraft.updated_at < now - timedelta(days=limit))))
        for draft_id in old:
            try:
                deletion.delete_draft(draft_id)
            except ValueError:
                continue  # a gate is running on it: the next pass takes it
            removed["drafts"] += 1
    with session_scope() as db:
        for category, count in removed.items():
            db.add(RetentionSweep(ran_at=now, category=category, removed=count))
    return removed


def last() -> LastSweep | None:
    """The newest pass and what it removed, for the Settings page."""
    with session_scope() as db:
        ran_at = db.scalar(sa.select(sa.func.max(RetentionSweep.ran_at)))
        if ran_at is None:
            return None
        rows = db.execute(sa.select(RetentionSweep.category, RetentionSweep.removed)
                          .where(RetentionSweep.ran_at == ran_at)).all()
    return LastSweep(ran_at=ran_at, removed=dict(rows))


async def retention_sweep(ctx: dict) -> dict[str, int]:
    """The cron entry point: the clock is read here, never inside `sweep`, so a test names its
    own moment."""
    return sweep(datetime.now(UTC))
