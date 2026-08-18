"""`/registry` — reading the declared data, never writing it.

Writing goes through the forge and a human's approval (invariant 2). This router is
deliberately read-only, and there is no POST here to add later by accident.
"""

from fastapi import APIRouter

from mendel_api.refusals import REFUSES
from mendel_api.services.lookup import TypeCard
from mendel_api.services.lookup import type_ as lookup_type

router = APIRouter(prefix="/registry", tags=["registry"])


@router.get(
    "/types/{id}",
    operation_id="lookupType",
    summary="A type's states, and which contracts use it",
    responses=REFUSES,
)
def type_card(id: str) -> TypeCard:
    return lookup_type(id)
