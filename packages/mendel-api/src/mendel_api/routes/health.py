"""`/health/registry` — the queue's strip.

Kept out of `main.py`'s bare `/health` on purpose: one says the service is up, the other
walks a directory and reads the database. Conflating them makes a liveness probe do real
work, which is how a health check starts failing for reasons that have nothing to do with
health.
"""

from datetime import datetime

from fastapi import APIRouter
from mendel_resolver import layers
from pydantic import BaseModel
from sqlalchemy import select

from mendel_api.db import session_scope
from mendel_api.models import SourceCheck
from mendel_api.settings import settings

router = APIRouter(prefix="/health", tags=["health"])


class Strip(BaseModel):
    contracts: int
    matching: int
    """Contracts a source could re-read AND that agreed. Not `contracts - drifted`."""
    unverifiable: int
    """Contracts no registered source could re-read — a `comeni/` contract over a vendored
    module, or a namespace with no adapter.

    **Reported rather than folded into `matching`**, which is what `CheckResult.skipped`'s
    own docstring demands: a contract nothing checks looks exactly like a contract that
    agrees. Running this against the real registry is what caught it — 12 contracts, 10
    checked, and the first version claimed 12 matched.
    """
    types: int
    checked_at: datetime | None
    """`None` when no check has ever run. Not zero, and not "just now" — a strip that
    implies a check happened when none did is a quiet falsehood, and this artifact's whole
    design is about not telling those."""


def strip_from(
    *,
    contracts: int,
    checked: int,
    drifted: int,
    unverifiable: int,
    types: int,
    last_check: datetime | None,
) -> Strip:
    return Strip(
        contracts=contracts,
        matching=checked - drifted,
        unverifiable=unverifiable,
        types=types,
        checked_at=last_check,
    )


@router.get(
    "/registry",
    operation_id="registryHealth",
    summary="What the registry holds, and when it was last checked",
)
def registry_health() -> Strip:
    stack = layers.load([settings.registry_root])
    with session_scope() as session:
        last = session.scalar(select(SourceCheck).order_by(SourceCheck.ran_at.desc()))
    contracts = len(stack.registry.all())
    return strip_from(
        contracts=contracts,
        checked=last.checked if last else 0,
        drifted=last.drifted if last else 0,
        unverifiable=last.skipped if last else 0,
        types=len(stack.vocabulary.types),
        last_check=last.ran_at if last else None,
    )
