"""`/contracts` — what has landed, read only.

**There is no write verb here and that is the point.** Contracts change through the queue (a
question) or through drift resolution (a diff you accept), both of which record *why*. A
free-text edit surface has nowhere to put a reason, and `test_there_is_no_way_to_write_a_contract`
makes adding one a deliberate act rather than a drift.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from mendel_api.refusals import REFUSES
from mendel_api.services.contracts import Listing, Status, listing
from mendel_api.services.module_page import ModulePage
from mendel_api.services.module_page import read as read_module

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("", operation_id="listContracts", summary="Every contract, worst first")
def contracts(
    against: Annotated[Status | None, Query(description="Only this status.")] = None,
    role: Annotated[str | None, Query(description="Only contracts with this role.")] = None,
    source: Annotated[str | None, Query(description="Only this namespace.")] = None,
) -> Listing:
    return listing(against=against, role=role, source=source)


@router.get(
    "/{id:path}",
    operation_id="readContract",
    summary="One contract, its module, and what points at it",
    responses=REFUSES,
)
def one(id: str) -> ModulePage:
    return read_module(id)
