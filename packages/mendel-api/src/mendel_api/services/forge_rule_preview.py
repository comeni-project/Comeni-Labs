"""Try a stored rule with hypothetical premises, without changing an adaptation."""

from comeni_core.diagnostics import coded
from comeni_core.goal.premise import PremiseOrigin
from comeni_core.logic.when import PredicateError
from comeni_core.spell.marks import ParamValue
from mendel_forge.forging.values import validate_value
from mendel_resolver.premises import Premise
from mendel_resolver.rules import RuleTable
from mendel_resolver.rules.format import Fired
from pydantic import BaseModel, ConfigDict, Field

from mendel_api.services import forging


class PreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str
    expected: int = Field(ge=1)
    premises: dict[str, ParamValue] = Field(default_factory=dict)


class Preview(BaseModel):
    revision: int
    effects: list[Fired]


def read(adaptation_id: str, body: PreviewBody) -> Preview:
    state = forging.load(adaptation_id)
    item = state.items.get(body.item)
    if (item is None or not body.item.startswith("rules:rule:")
            or item.status.value in {"removed", "rejected"}):
        raise forging.Refused(coded("MF0506", "choose a current decision rule to try"))
    if item.current.n != body.expected:
        raise forging.Refused(coded("MF0506", "the rule changed since you looked; reload it"))
    decision = validate_value(item.key, item.value)
    premises = {key: Premise(id=key, value=value, origin=PremiseOrigin.ASSERTED)
                for key, value in body.premises.items() if value is not None}
    try:
        table = RuleTable(decisions=[decision], layer_of={decision.key(): "forge-preview"})
        effects = table.effects_for(premises)
    except (PredicateError, TypeError, ValueError) as exc:
        raise forging.Refused(coded("MF0506", f"cannot try these premises: {exc}")) from exc
    return Preview(revision=item.current.n, effects=effects)
