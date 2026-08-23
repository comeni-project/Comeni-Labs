"""What can feed what, precomputed from the registry.

**This is not a second implementation of the rule.** It walks the same
`InputPort.alternatives()` `validate` walks, and
`test_the_index_agrees_with_the_verb_on_every_pair` holds the two together over the whole
registry. What it buys is that a browser can colour a wire during a drag without a round trip,
and can do so by *looking an answer up* rather than by deciding anything.

**Keyed on a signature rather than on a port pair.** Port-pair keying is roughly 24 million
entries at the ~2,000 contracts issue #77 forecasts; signature keying is bounded by the
vocabulary, which invariant 7 keeps closed.
"""

from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.layers import Layers

__all__ = ["Compatibility", "index", "signature"]


def signature(type_id: str, states: frozenset[str]) -> str:
    """`alignment.bam[coordinate_sorted,indexed]`.

    Sorted, because a `frozenset` has no order and byte-identical output is a hard requirement
    everywhere else in this system — `IREdge.states` carries a `field_serializer` for the same
    reason.
    """
    if not states:
        return type_id
    return f"{type_id}[{','.join(sorted(states))}]"


class Compatibility(BaseModel):
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
