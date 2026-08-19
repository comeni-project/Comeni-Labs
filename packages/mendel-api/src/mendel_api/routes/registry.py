"""`/registry` — reading the declared data, never writing it.

Writing goes through the forge and a human's approval (invariant 2). This router is
deliberately read-only, and there is no POST here to add later by accident.
"""

from comeni_core.plan.tiers import TIER_VOCABULARY
from fastapi import APIRouter
from pydantic import BaseModel

from mendel_api.refusals import REFUSES
from mendel_api.services.lookup import TypeCard
from mendel_api.services.lookup import type_ as lookup_type

router = APIRouter(prefix="/registry", tags=["registry"])


class TierCard(BaseModel):
    """One tier, as an interface needs to say it."""

    tier: int
    name: str
    group: str
    what: str
    colour: str
    """A **token name** — `pea`, `measured`, `undecided` — never a hex. The palette is
    `tokens.css`'s job, and a value here would be a second palette able to disagree with it."""


@router.get(
    "/tiers",
    operation_id="listTiers",
    summary="The four tiers, and what each is called where a person reads it",
)
def tiers() -> list[TierCard]:
    """**The vocabulary, served rather than retyped.**

    The four names lived in a React file and in `docs/design/dashboard.html` — two copies with
    nothing holding them together, which is exactly the drift `diagnostics.yml` exists to
    prevent. `comeni_core.plan.tiers.TIER_VOCABULARY` is now the single declaration and this is
    how an interface reads it.
    """
    return [
        TierCard(
            tier=int(tier),
            name=words.name,
            group=words.group,
            what=words.what,
            colour=words.colour,
        )
        for tier, words in sorted(TIER_VOCABULARY.items())
    ]


@router.get(
    "/types/{id}",
    operation_id="lookupType",
    summary="A type's states, and which contracts use it",
    responses=REFUSES,
)
def type_card(id: str) -> TypeCard:
    return lookup_type(id)
