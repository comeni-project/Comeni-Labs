"""The live tail. Redis is the fan-out; Postgres is the record.

A browser that has been closed for a day does not scroll back through Redis — it asks Postgres
for a page and then subscribes from the id that page ended at. `docs/design/wiener.md` §7.2.

**Capped and lossy on purpose.** A three-day run must not grow a stream without bound, and
losing the tail is survivable precisely because the record is somewhere else.
"""

from redis import Redis
from wiener_core.events import RunEvent

from wiener_api.settings import settings

_client: Redis | None = None


def client() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def key(run_id: str) -> str:
    return f"wiener:run:{run_id}"


def publish(run_id: str, event: RunEvent, redis: Redis | None = None,
            maxlen: int | None = None) -> str:
    """Append one event to a run's tail, and return the id a reader resumes from."""
    return (redis or client()).xadd(
        key(run_id),
        {"seq": event.seq, "kind": event.kind, "at_ms": event.at_ms,
         "json": event.model_dump_json()},
        maxlen=maxlen or settings.stream_maxlen,
        approximate=True,
    )


def last_id(run_id: str, redis: Redis | None = None) -> str:
    """Where a subscriber should resume from after paging the record.

    `"0-0"` when the stream is empty or gone, which reads as *from the beginning of what
    Redis still has* — the honest answer when the cap has already dropped the early entries,
    since the page the browser just read came from Postgres anyway.
    """
    entries = (redis or client()).xrevrange(key(run_id), count=1)
    return entries[0][0] if entries else "0-0"
