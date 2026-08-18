"""What a type is, and who already uses it.

**A decision aid rather than a dictionary.** The states say what may be asserted about a
value; the users say whether this is the normal choice, which is the question a curator
actually has mid-decision and the one a description cannot answer.
"""

from mendel_resolver import layers
from pydantic import BaseModel

from mendel_api.settings import settings


class TypeCard(BaseModel):
    id: str
    states: list[str]
    """Sorted. `vocabulary.types[id]` is a frozenset and frozensets have no stable order —
    the same trap `IREdge.states` carries a serialiser for."""
    produced_by: list[str]
    consumed_by: list[str]


def type_(id: str) -> TypeCard:
    stack = layers.load([settings.registry_root])
    states = stack.vocabulary.types.get(id)
    if states is None:
        raise ValueError(
            f"{id!r} is not declared in this registry"
            f"\n  declared: {', '.join(sorted(stack.vocabulary.types))}"
        )

    produced_by, consumed_by = [], []
    for contract in stack.registry.all():
        if any(p.type_id == id for p in contract.produces):
            produced_by.append(contract.id)
        if any(c.type_id == id for c in contract.consumes):
            consumed_by.append(contract.id)

    return TypeCard(
        id=id,
        states=sorted(states),
        produced_by=sorted(produced_by),
        consumed_by=sorted(consumed_by),
    )
