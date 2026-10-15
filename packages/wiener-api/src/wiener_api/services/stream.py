"""The live tail. Redis is the fan-out; Postgres is the record.

A browser that has been closed for a day does not scroll back through Redis — it asks Postgres
for a page and then subscribes from the id that page ended at. `docs/design/wiener.md` §7.2.

**Capped and lossy on purpose.** A three-day run must not grow a stream without bound, and
losing the tail is survivable precisely because the record is somewhere else.
"""

import logging

from redis import Redis
from wiener_core.events import RunEvent

from wiener_api.settings import settings

log = logging.getLogger(__name__)
_client: Redis | None = None


def client() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def key(run_id: str) -> str:
    return f"wiener:run:{run_id}"


def publish(run_id: str, event: RunEvent, redis: Redis | None = None,
            maxlen: int | None = None, *, ended: bool = False) -> str:
    """Append one event to a run's tail, and return the id a reader resumes from.

    **The tail lives as long as the run does** (issue 274): nothing removed it, so every run
    kept up to `stream_maxlen` entries for good. An event that leaves the run `ended` gives
    the tail `stream_ttl_seconds` to live; any other clears an expiry, because a run called
    lost that speaks again is live. One round trip either way."""
    pipe = (redis or client()).pipeline(transaction=False)
    pipe.xadd(
        key(run_id),
        {"seq": event.seq, "kind": event.kind, "at_ms": event.at_ms,
         "json": event.model_dump_json()},
        maxlen=maxlen or settings.stream_maxlen,
        approximate=True,
    )
    if ended:
        pipe.expire(key(run_id), settings.stream_ttl_seconds)
    else:
        pipe.persist(key(run_id))
    return pipe.execute()[0]


def retire(run_id: str, redis: Redis | None = None) -> None:
    """Let a run's tail go `stream_ttl_seconds` from now: for a run that ended without an event
    to say so — the heartbeat's verdict that it is lost."""
    (redis or client()).expire(key(run_id), settings.stream_ttl_seconds)


def drop(run_id: str, redis: Redis | None = None) -> None:
    """Remove a run's tail at once: the run was deleted (Part H). A Redis that does not answer
    costs nothing lasting, since the tail expires on its own; it is logged, as a failed
    publish is by its caller."""
    try:
        (redis or client()).delete(key(run_id))
    except Exception:  # noqa: BLE001 — the record is gone; the tail expires anyway
        log.warning("could not drop the tail of deleted run %s", run_id, exc_info=True)


def last_id(run_id: str, redis: Redis | None = None) -> str:
    """Where a subscriber should resume from after paging the record.

    `"0-0"` when the stream is empty or gone, which reads as *from the beginning of what
    Redis still has* — the honest answer when the cap has already dropped the early entries,
    since the page the browser just read came from Postgres anyway.
    """
    entries = (redis or client()).xrevrange(key(run_id), count=1)
    return entries[0][0] if entries else "0-0"


def read(run_id: str, after: str, block_ms: int = 1_000, count: int = 100,
         redis: Redis | None = None) -> list[tuple[str, dict]]:
    """Block briefly for entries after `after`. Empty list when nothing arrived in time.

    Blocking rather than polling, and **briefly** rather than forever: the socket has to wake
    up on a quiet stream to notice that the run has finished. A six-hour STAR align emits
    nothing while it runs, which is the same fact §17's `LOST` window is blunt about.
    """
    streams = (redis or client()).xread({key(run_id): after}, count=count, block=block_ms)
    return streams[0][1] if streams else []
