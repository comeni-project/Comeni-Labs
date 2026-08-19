"""What has landed, and how it stands against its source.

**The check is cached on the registry's digest**, and that cache moved to
`services/checked.py` in phase 5 when the queue became a second caller. The argument for it is
there; what stays here is what a *status* is.
"""

from enum import StrEnum

from pydantic import BaseModel

from mendel_api.services import checked, registry


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


def _standing() -> tuple[frozenset[str], frozenset[str]]:
    """`(drifted ids, unverifiable ids)` for the registry as it now stands.

    **Drifted is either checker.** A contract whose module renamed an `emit:` label breaks
    emission and has no value drift at all, and it read `matching` until phase 5 — the same
    class of falsehood as folding `skipped` into `matching`, one checker over. A reader asking
    *does this still describe its module* does not care which check noticed. Spec §3.5.
    """
    result = checked.result()
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
    stack = registry.stack()
    drifted, skipped = _standing()

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
