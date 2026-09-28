"""What an analysis still needs, computed and not asked of a model (protocol rule 1).

Walks back from the want the way `router.route` does, but over **every** candidate producer, not
only the chosen one: a gap asked for and then not needed costs one question, and a gap missed
costs the build (#114). Deterministic: same want and facts in, same gaps out, in the same order.
"""

from typing import NamedTuple

from mendel_resolver.layers import Layers

from mendel_api.authoring.types import Fact, FactKind


class Gap(NamedTuple):
    kind: FactKind
    subject: str
    why: str


class Unreachable(NamedTuple):
    """A want nothing produces. An honest stop, never an empty gap list (review focus 1)."""

    subject: str


def _premise_measurements(stack: Layers) -> set[str]:
    """Measurement ids a rule's `when` reads, directly or through a derivation.

    A derivation reads its `source`, its aggregate's measurement, or the keys of its own rows'
    `when`, and any of those may itself be derived, so the walk follows them to declared
    measurements.
    """
    declared = set(stack.measurements.measurements)
    reads: dict[str, set[str]] = {}
    for d in stack.rules.derivations:
        sources = {key for row in d.rows for key in row.when}
        if d.source:
            sources.add(d.source)
        if d.aggregate:
            sources.add(d.aggregate.measurement)
        reads[d.fact] = sources

    def resolve(key: str, visiting: frozenset[str]) -> set[str]:
        if key in visiting:
            return set()
        found = {key} if key in declared else set()
        for source in reads.get(key, ()):
            found |= resolve(source, visiting | {key})
        return found

    read: set[str] = set()
    for decision in stack.rules.decisions:
        for row in decision.rows:
            for key in row.when:
                read |= resolve(key, frozenset())
    return read


def gaps(want: list[str], facts: list[Fact], stack: Layers) -> list[Gap] | Unreachable:
    """Every input and measurement the want needs that no fact settles yet, inputs first.

    An `OPEN` fact settles its gap too: *can't share it* is an answer, and asking again would
    be the protocol ignoring it (review focus 2).
    """
    known = {(f.kind, f.subject) for f in facts}
    leaves: list[str] = []
    seen: set[str] = set()

    def walk(type_id: str, visiting: frozenset[str]) -> None:
        if type_id in seen:
            return
        seen.add(type_id)
        # A contract cannot satisfy its own input (the router's rule): a trimmer makes reads
        # only from reads, so reads with nothing but trimmers behind them are still a leaf the
        # person has to supply.
        producers = [
            c
            for c in stack.registry.producers_of(type_id, frozenset())
            if c.id not in visiting and all(port.type_id != type_id for port in c.consumes)
        ]
        if not producers:
            leaves.append(type_id)
            return
        for contract in producers:
            for port in contract.consumes:
                if port.type_id:
                    walk(port.type_id, visiting | {contract.id})

    for type_id in want:
        if not stack.registry.producers_of(type_id, frozenset()):
            return Unreachable(type_id)
        walk(type_id, frozenset())

    measurements = _premise_measurements(stack) | {
        m.id
        for m in stack.measurements.measurements.values()
        if m.meta_key and m.describes in leaves
    }
    out = [
        Gap(FactKind.INPUT, t, "the pipeline needs it and nothing can make it")
        for t in leaves
        if (FactKind.INPUT, t) not in known
    ]
    out += [
        Gap(FactKind.MEASUREMENT, m, "a step reads it to decide")
        for m in sorted(measurements)
        if (FactKind.MEASUREMENT, m) not in known
    ]
    return out
