"""What has landed, and how it stands against its source.

**The check is cached on the registry's digest**, not on a clock. `ops.check` reads every
vendored module — measured at 0.40s for twelve contracts — which is fine once per registry
state and not fine per request. A digest key means a changed registry invalidates it and an
unchanged one never re-reads; a time-based cache would serve a stale answer for exactly as
long as it was wrong.

**The cold path is what breaks first at scale.** At the 5,800 contracts the design says this
page must survive, 0.40s becomes roughly three minutes. The fix then is a table the worker
writes, which the operator's decision on 2026-08-18 deliberately declined for now.
"""

from enum import StrEnum
from functools import lru_cache

from comeni_core.artifact.digest import digest_of_directory
from mendel_forge import ops
from mendel_resolver import layers
from pydantic import BaseModel

from mendel_api.settings import settings


class Status(StrEnum):
    DRIFTED = "drifted"
    """The source says something the contract does not."""
    UNVERIFIABLE = "unverifiable"
    """No registered source could re-read it. **Never folded into `matching`** — a contract
    nothing checks looks exactly like a contract that agrees."""
    MATCHING = "matching"

    @property
    def rank(self) -> int:
        """Worst first, the same argument as the queue's consequence order."""
        return {Status.DRIFTED: 1, Status.UNVERIFIABLE: 2, Status.MATCHING: 3}[self]


class ContractRow(BaseModel):
    id: str
    roles: list[str]
    source: str
    """The namespace it came from — `nf-core`, `comeni`. The part before the first `/`."""
    status: Status


class Listing(BaseModel):
    rows: list[ContractRow]
    total: int
    """Every contract in the registry, before filtering."""
    counts: dict[str, int]
    """Status -> how many, **over the whole registry** rather than the filtered view. A facet
    that counted only what is shown would read 12 in the one you are standing in and 0 in
    every other."""


@lru_cache(maxsize=4)
def _checked(digest: str) -> tuple[frozenset[str], frozenset[str]]:
    """`(drifted ids, unverifiable ids)` for a registry in this exact state.

    The digest is the argument rather than a global, so `lru_cache` does the invalidation and
    there is no hand-written expiry to get wrong.
    """
    result = ops.check(
        ops.CheckRequest(registry_root=settings.registry_root, source_root=settings.source_root)
    )
    return frozenset(d.contract_id for d in result.drift), frozenset(result.skipped)


def _status(contract_id: str, drifted: frozenset[str], skipped: frozenset[str]) -> Status:
    if contract_id in drifted:
        return Status.DRIFTED
    if contract_id in skipped:
        return Status.UNVERIFIABLE
    return Status.MATCHING


def listing(
    *,
    against: Status | None = None,
    role: str | None = None,
    source: str | None = None,
) -> Listing:
    stack = layers.load([settings.registry_root])
    digest = str(digest_of_directory(settings.registry_root))
    drifted, skipped = _checked(digest)

    rows = [
        ContractRow(
            id=contract.id,
            roles=sorted(contract.roles),
            source=contract.id.split("/", 1)[0],
            status=_status(contract.id, drifted, skipped),
        )
        for contract in stack.registry.all()
    ]

    counts = {status.value: 0 for status in Status}
    for row in rows:
        counts[row.status.value] += 1
    total = len(rows)

    if against is not None:
        rows = [r for r in rows if r.status is against]
    if role is not None:
        rows = [r for r in rows if role in r.roles]
    if source is not None:
        rows = [r for r in rows if r.source == source]

    rows.sort(key=lambda r: (r.status.rank, r.id))
    return Listing(rows=rows, total=total, counts=counts)
