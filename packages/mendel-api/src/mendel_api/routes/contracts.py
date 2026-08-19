"""`/contracts` — what has landed, and what has moved under it.

**There is no free-text write verb here and that is the point.** A contract changes through
the queue (a question) or through drift resolution (a diff you accept), both of which record
who and why. A free-text edit surface has nowhere to put the reason, and
`test_there_is_no_way_to_write_a_contract` makes adding one a deliberate act rather than a
drift.

**`accept` is a write and belongs to the second of those two paths.** It takes a value the
*source* states, not one a caller composes, and it carries `by` and `why` into a commit — the
same standard the queue's answers meet. It arrived with phase 5.

**Route order matters here and nowhere else in this app.** `/{id:path}` is greedy: registered
before them, it swallows `…@1.21.0/drift` whole and answers 200 with the module page's body,
which looks like a working route and is not.
"""


from fastapi import APIRouter
from mendel_forge.ops import AcceptResult, DriftReport

from mendel_api.refusals import REFUSES
from mendel_api.services import drift as drift_service
from mendel_api.services.drift import AcceptBody
from mendel_api.services.module_page import ModulePage
from mendel_api.services.module_page import read as read_module

router = APIRouter(prefix="/contracts", tags=["contracts"])


# **`GET /contracts` was deleted with `Contracts.tsx`.** `GET /tools?state=landed` answers it,
# and `Listing` survives only because `services/tools.py` composes it. The per-contract routes
# below stay: the module page and the drift screens are not superseded by anything.
#
@router.get(
    "/{id:path}/drift",
    operation_id="readDrift",
    summary="What moved between a contract and its source, and what it means",
    responses=REFUSES,
)
def drift(id: str) -> DriftReport:
    return drift_service.report(id)


@router.post(
    "/{id:path}/drift/accept",
    operation_id="acceptDrift",
    summary="Take the source's value for one field",
    responses=REFUSES,
)
def accept(id: str, body: AcceptBody) -> AcceptResult:
    return drift_service.accept(id, body)


@router.get(
    "/{id:path}",
    operation_id="readContract",
    summary="One contract, its module, and what points at it",
    responses=REFUSES,
)
def one(id: str) -> ModulePage:
    return read_module(id)
