"""`/tools` — every tool, at whatever stage of its life it has reached.

**Replaces `/sources` and `/contracts` as the list the interface reads.** They asked the same
question of the same objects at two stages, and answering it twice is what made a person have to
learn that a tool is one thing here and another thing there. Spec §1.3.

Read-only. A tool changes state by being drafted (`POST /sources/draft`), answered (the queue) or
landed — verbs that live where their consequences do.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from mendel_api.services import tools as service
from mendel_api.services.contracts import Status
from mendel_api.services.sources import State
from mendel_api.services.tools import Board

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", operation_id="listTools", summary="Every tool, and how far along it is")
def board(
    state: Annotated[State | None, Query(description="Only this stage of a tool's life")] = None,
    against: Annotated[
        Status | None, Query(description="Only this agreement status. Landed tools only")
    ] = None,
) -> Board:
    """**Counts come back over everything, never over the filtered view.**

    A facet counting only what is shown reads 12 in the one you are standing in and 0 in every
    other, which is the opposite of what a facet is for — a defect both of the screens this
    replaces had already found and fixed independently.
    """
    return service.board(
        state=state.value if state else None,
        against=against.value if against else None,
    )
