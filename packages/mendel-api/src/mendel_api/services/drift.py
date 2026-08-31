"""One contract against its source, and taking a value from it.

Three lines each way: the forge holds the logic, and a service that reshaped its result would
be a second answer to what a drift is.
"""

from mendel_forge import ops
from pydantic import BaseModel

from mendel_api.services import registry
from mendel_api.settings import settings


class AcceptBody(BaseModel):
    field: str
    by: str
    why: str
    """Required, not optional-with-a-default. The reason is the product claim, and a value
    changed with nothing recorded is what `pipeline.yml` exists not to contain."""


def report(contract_id: str) -> ops.DriftReport:
    return ops.drift(
        ops.DriftRequest(
            contract_id=contract_id,
            registry_root=settings.registry_root,
            source_root=settings.registry_root,
            stack=registry.stack(),
        )
    )


def accept(contract_id: str, body: AcceptBody) -> ops.AcceptResult:
    """**The only write into a registry checkout from a request**, and the guard rails are
    `land()`'s: it refuses a detached HEAD, a dirty tree, and the default branch, all before
    anything is written. A human clicking accept is invariant 2's approval; the commit is
    what records that it happened."""
    return ops.accept(
        ops.AcceptRequest(
            contract_id=contract_id,
            field=body.field,
            registry_root=settings.registry_root,
            source_root=settings.registry_root,
            by=body.by,
            why=body.why,
        )
    )
