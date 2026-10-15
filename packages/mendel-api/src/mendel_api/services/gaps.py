"""What an analysis still needs, computed and not asked of a model (protocol rule 1).

Walks back from the want the way `router.route` does, but over **every** candidate producer, not
only the chosen one: a gap asked for and then not needed costs one question, and a gap missed
costs the build (#114). Deterministic: same want and facts in, same gaps out, in the same order.
"""

from typing import NamedTuple

from mendel_resolver.layers import Layers
from mendel_resolver.rules.format import Decision

from mendel_api.authoring.types import Fact, FactKind


class Gap(NamedTuple):
    kind: FactKind
    subject: str
    why: str
    used_by: tuple[str, ...] = ()
    """For an input, or a measurement carried in its type's `meta`: every candidate contract on
    the walk that consumes the type, in walk order (Part I.1 §4)."""
    decides: tuple[Decision, ...] = ()
    """For a measurement a rule reads: each decision whose `when` reads it, in table order."""


class Unreachable(NamedTuple):
    """A want nothing produces. An honest stop, never an empty gap list (review focus 1)."""

    subject: str


def _premise_measurements(stack: Layers) -> dict[str, list[Decision]]:
    """Measurement ids a rule's `when` reads, directly or through a derivation, each with the
    decisions that read it, in table order.

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

    read: dict[str, list[Decision]] = {}
    for decision in stack.rules.decisions:
        measured: set[str] = set()
        for row in decision.rows:
            for key in row.when:
                measured |= resolve(key, frozenset())
        for measurement in sorted(measured):
            read.setdefault(measurement, []).append(decision)
    return read


def _carried_by(measurement, leaves: list[str], consumers: dict[str, list[str]]
                ) -> tuple[str, ...]:
    """A measurement carried in its type's `meta` is read by whatever reads that type."""
    if measurement.meta_key and measurement.describes in leaves:
        return tuple(consumers.get(measurement.describes, ()))
    return ()


def gaps(want: list[str], facts: list[Fact], stack: Layers) -> list[Gap] | Unreachable:
    """Every input and measurement the want needs that no fact settles yet, inputs first.

    An `OPEN` fact settles its gap too: *can't share it* is an answer, and asking again would
    be the protocol ignoring it (review focus 2).
    """
    known = {(f.kind, f.subject) for f in facts}
    leaves: list[str] = []
    seen: set[str] = set()
    # Who reads each type, recorded before the `seen` check cuts a second visit short, so a type
    # two contracts consume names both (Part I.1 §4).
    consumers: dict[str, list[str]] = {}

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
                    readers = consumers.setdefault(port.type_id, [])
                    if contract.id not in readers:
                        readers.append(contract.id)
                    walk(port.type_id, visiting | {contract.id})

    for type_id in want:
        if not stack.registry.producers_of(type_id, frozenset()):
            return Unreachable(type_id)
        walk(type_id, frozenset())

    premises = _premise_measurements(stack)
    measurements = set(premises) | {
        m.id
        for m in stack.measurements.measurements.values()
        if m.meta_key and m.describes in leaves
    }
    out = [
        Gap(FactKind.INPUT, t, "the pipeline needs it and nothing can make it",
            used_by=tuple(consumers.get(t, ())))
        for t in leaves
        if (FactKind.INPUT, t) not in known
    ]
    out += [
        Gap(FactKind.MEASUREMENT, m, "a step reads it to decide",
            used_by=_carried_by(stack.measurements.get(m), leaves, consumers),
            decides=tuple(premises.get(m, ())))
        for m in sorted(measurements)
        if (FactKind.MEASUREMENT, m) not in known
    ]
    return out
