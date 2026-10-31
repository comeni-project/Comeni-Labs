"""Precompute which declared output forms can satisfy which input forms.

The index uses the same ordered ``InputPort.alternatives()`` consumed by graph validation. It is
keyed by type-and-state signatures so clients can look up compatibility without implementing a
second rule or making a server round trip.
"""

from comeni_core.declared.signature import join
from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.layers import Layers

__all__ = ["Compatibility", "index", "signature"]


def signature(type_id: str, states: frozenset[str]) -> str:
    """`alignment.bam::coordinate_sorted::indexed`."""
    return join(type_id, states)


class Compatibility(BaseModel):
    """Serializable lookup tables for interactive port compatibility checks."""
    model_config = ConfigDict(extra="forbid")

    emits: dict[str, str] = Field(default_factory=dict)
    """`"<contract id>#<port>"` to the signature that port emits."""

    requires: dict[str, list[str]] = Field(default_factory=dict)
    """`"<contract id>#<port>"` to the signatures it accepts, **conventional first**.

    The order is the whole of how a client tells a green wire from an amber one, and it comes
    from `InputPort.alternatives()` rather than from anything decided here.
    """

    satisfies: dict[str, list[str]] = Field(default_factory=dict)
    """An emitted signature to every required signature it satisfies.

    This is the only entry that encodes the *rule*. A client intersects `requires[target]` with
    `satisfies[emits[source]]` and has its answer without comparing a type to a type or
    subtracting one state set from another.
    """


def index(layers: Layers) -> Compatibility:
    emits: dict[str, str] = {}
    requires: dict[str, list[str]] = {}
    emitted: set[tuple[str, frozenset[str]]] = set()
    required: set[tuple[str, frozenset[str]]] = set()

    for contract in layers.registry.all():
        for out in contract.produces:
            emits[f"{contract.id}#{out.name}"] = signature(out.type_id, out.state)
            emitted.add((out.type_id, out.state))
        for inp in contract.consumes:
            alternatives = inp.alternatives()
            requires[f"{contract.id}#{inp.name}"] = [
                signature(a.type_id, a.states) for a in alternatives
            ]
            for alternative in alternatives:
                required.add((alternative.type_id, alternative.states))

    satisfies: dict[str, list[str]] = {}
    for out_type, out_states in sorted(emitted):
        key = signature(out_type, out_states)
        satisfies[key] = sorted(
            signature(in_type, in_states)
            for in_type, in_states in required
            if in_type == out_type and in_states <= out_states
        )
    return Compatibility(emits=emits, requires=requires, satisfies=satisfies)
