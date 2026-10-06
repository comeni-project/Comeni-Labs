"""A step's other tools, each shown as the whole pipeline it gives (§14.3 of the consultant
build): the amendment, its difference from the current blueprint, or why it cannot be built.

Computed when the step's card is offered, so the options are fixed when the person reads them.
`resolve` is a port; `refusals` names what it raises for a goal that cannot be built, because
this package does not depend on the resolver.
"""

from collections.abc import Callable

from comeni_core.goal.asked import Goal, ProducerPin
from pydantic import BaseModel, ConfigDict

from mendel_authoring.amend import ChooseTool
from mendel_authoring.blueprint import Blueprint
from mendel_authoring.diff import BlueprintDiff, diff_of

Resolve = Callable[[Goal], Blueprint]


class Alternative(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    contract: str
    amendment: ChooseTool
    diff: BlueprintDiff | None = None
    refused: str | None = None
    """Why it cannot be built from this goal — shown, never offered."""


def alternatives_of(
    blueprint: Blueprint,
    goal: Goal,
    node: str,
    candidates: list[str],
    resolve: Resolve,
    refusals: tuple[type[Exception], ...],
) -> list[Alternative]:
    """Every candidate but the step's own, in the order given. One that changes nothing (a
    pin the router finds inert there) is left out: it is not a choice."""
    site = blueprint.sites.get(node)
    if site is None:
        return []
    chosen = blueprint.step(node).module.contract_id
    found: list[Alternative] = []
    for contract in (c for c in candidates if c != chosen):
        amendment = ChooseTool(pin=ProducerPin(site=site, contract=contract))
        try:
            diff = diff_of(blueprint, resolve(amendment.apply(goal)))
        except refusals as refused:
            found.append(
                Alternative(
                    id=f"alt_{len(found) + 1}", contract=contract, amendment=amendment,
                    refused=str(refused),
                )
            )
            continue
        if not diff.empty:
            found.append(
                Alternative(
                    id=f"alt_{len(found) + 1}", contract=contract, amendment=amendment, diff=diff
                )
            )
    return found
