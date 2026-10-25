"""Resolve each alternative tool as a whole-pipeline amendment.

Alternatives are computed when a step card is offered and retain either the resulting blueprint
diff or a refusal. Resolution is injected so this pure package does not depend on the resolver.
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
    blueprint: Blueprint | None = None
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
            resolved = resolve(amendment.apply(goal))
            diff = diff_of(blueprint, resolved)
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
                    id=f"alt_{len(found) + 1}", contract=contract, amendment=amendment,
                    diff=diff, blueprint=resolved,
                )
            )
    return found
