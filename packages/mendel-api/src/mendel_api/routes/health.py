"""`/health/registry` and `/health/ai` — what a person checks when something is not moving.

Kept out of `main.py`'s bare `/health` on purpose: one says the service is up, the others
walk a directory, read the database and open a socket. Conflating them makes a liveness probe
do real work, which is how a health check starts failing for reasons that have nothing to do
with health.
"""

import asyncio
import contextlib
from datetime import datetime

from arq.connections import RedisSettings, create_pool
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mendel_api.db import session_scope
from mendel_api.jobs import AI_QUEUE
from mendel_api.models import SourceCheck
from mendel_api.services import registry
from mendel_api.settings import model_access, settings

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
    stack = registry.stack()
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


# ── the AI lane ───────────────────────────────────────────────────────────────────────

PROBE_SECONDS = 2.0
"""How long the model probe waits before saying *did not answer*.

**Short on purpose.** This is a health endpoint, not a request: a model that takes twelve
seconds to accept a connection is a model an operator needs told about, and a probe that waited
for it would make the page that reports the problem hang on the problem.
"""


class AiHealth(BaseModel):
    """Three separate facts, because they fail separately and are fixed separately.

    **A single `ok` would be the wrong shape.** No worker is a compose problem, no model is a
    `.env` problem, and a queue with eleven things in it is neither — it is the system working.
    Collapsing them gives an operator a red light and no next step, which is what §7's *honest
    empty and error states* is about one layer down.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    configured: bool
    """Whether a model is configured at all. `False` is the **no-AI lane**, not a fault: a
    laboratory that wants no model calls does not set one, and every deterministic verb still
    works. `MI0106` says the same thing where an adaptation meets it."""
    model: str = ""
    """The model id, so an operator can see *which* — never the key or the base URL.

    A base URL is a network fact about somebody's deployment and a key is a credential; the id
    is what distinguishes `ollama/qwen2.5-coder:14b` from a hosted model, which is the whole
    question this field answers.
    """
    model_available: bool | None = None
    """Whether the endpoint answered inside `PROBE_SECONDS`.

    **`None` means not probed rather than not reachable**, and the distinction is the reason
    this is three-valued: a hosted provider is not probed at all — a health check that called
    one would bill somebody for asking whether the wires are connected — so `False` here always
    means *we asked a local endpoint and it did not answer*.
    """
    worker_available: bool
    """Whether an AI worker has checked in with Redis.

    ARQ writes a health key on a schedule and expires it, so its presence is a statement about
    a process that is running now rather than one that once started. A queue that never drains
    with no worker is the failure this exists to name, and it is invisible from the work queue —
    an adaptation simply sits at `queued`.
    """
    queue_depth: int = 0
    """How many jobs are waiting on `arq:queue:ai`.

    Counted from Redis rather than from the database, and that is the opposite of the choice
    `AiLane.waiting` makes on the overview — deliberately. That one counts *adaptations*
    because that is what a curator cares about; this one counts *jobs*, and the two disagreeing
    is itself the signal that something was delivered whose row never moved.
    """
    concurrency: int = 1


async def _worker_and_depth() -> tuple[bool, int]:
    """Ask Redis, and treat *cannot reach Redis* as *no worker*.

    Reporting a worker on a broker nobody can talk to would be the most confident possible
    wrong answer, and the queue depth is unknowable in the same breath.
    """
    # **One attempt, and a short one.** `create_pool` retries five times with a delay by
    # default, so a health endpoint asked *is the broker up* while the broker is down took
    # several seconds to answer *no* — hanging on exactly the fault it exists to report. The
    # worker keeps the retries; it is trying to do work, and this is trying to describe it.
    where = RedisSettings.from_dsn(settings.redis_url)
    where.conn_retries = 0
    where.conn_timeout = PROBE_SECONDS
    pool = None
    try:
        pool = await create_pool(where)
        depth = await pool.zcard(AI_QUEUE)
        # ARQ's own key, and it expires — so this says a worker is running now.
        alive = await pool.exists(f"{AI_QUEUE}:health-check")
        return bool(alive), int(depth or 0)
    except Exception:
        return False, 0
    finally:
        if pool is not None:
            with contextlib.suppress(Exception):
                await pool.aclose()


async def _model_answers(base_url: str) -> bool:
    """Open a socket to the configured endpoint. **No request, and no model name.**

    A `GET /` would be an Ollama-shaped assumption and a completion would cost a generation;
    what is being asked is *is anything listening there*, and a TCP connect answers exactly
    that without knowing whose server it is.
    """
    from urllib.parse import urlsplit

    parts = urlsplit(base_url if "//" in base_url else f"//{base_url}")
    if not parts.hostname:
        return False
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(parts.hostname, port), timeout=PROBE_SECONDS
        )
    except (TimeoutError, OSError):
        return False
    writer.close()
    with contextlib.suppress(Exception):
        await writer.wait_closed()
    return True


@router.get(
    "/ai",
    operation_id="aiHealth",
    summary="Whether the AI lane can do anything, and what is waiting",
)
async def ai_health() -> AiHealth:
    """**Three things an operator checks when a generation is not happening**, and the plan
    names all three: worker unavailable, model unavailable, queue depth.

    It reports and never enqueues. A health endpoint that started work to find out whether work
    can start is a health endpoint that changes the thing it measures.
    """
    access = model_access()
    worker, depth = await _worker_and_depth()
    return AiHealth(
        configured=access is not None,
        model=access.model if access else "",
        # A hosted provider is deliberately not probed — see the field.
        model_available=(
            await _model_answers(access.base_url)
            if access is not None and access.base_url
            else None
        ),
        worker_available=worker,
        queue_depth=depth,
        concurrency=settings.ai_max_jobs,
    )

