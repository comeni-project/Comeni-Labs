"""`/registry` — reading the declared data, never writing it.

Writing goes through the forge and a human's approval (invariant 2). This router is
deliberately read-only, and there is no POST here to add later by accident.
"""

from comeni_core.diagnostics import coded
from comeni_core.plan.tiers import TIER_VOCABULARY
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mendel_api.refusals import REFUSES
from mendel_api.services import module_page
from mendel_api.services.lookup import TypeCard
from mendel_api.services.lookup import type_ as lookup_type
from mendel_api.services.module_page import ModulePage

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


@router.get(
    "/tools/{contract_id:path}",
    operation_id="readTool",
    summary="An imported tool: everything the registry says about it",
    responses=REFUSES,
)
def read_tool(contract_id: str) -> ModulePage:
    """`{contract_id:path}` because an id carries `/` and `@` (`nf-core/star/align@2.7.11b`)."""
    try:
        return module_page.read(contract_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=coded("MF0504", f"no tool {contract_id!r} in the registry")
        ) from None
