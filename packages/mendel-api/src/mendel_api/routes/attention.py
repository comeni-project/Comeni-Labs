"""`/attention` — what needs a person, across both halves.

One `GET`, because the page asks one question. Four services back it and the join belongs where
the data is — the same argument `sources.catalogue` already makes, and the reason this is not
four requests the browser has to reconcile.
"""

from fastapi import APIRouter

from mendel_api.services import attention as service
from mendel_api.services.attention import Attention

router = APIRouter(prefix="/attention", tags=["attention"])


@router.get("", operation_id="whatNeedsYou", summary="What needs a person, across both halves")
def attention() -> Attention:
    return service.whats_open()
