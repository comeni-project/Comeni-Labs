"""What an analysis still needs, computed and not asked of a model (protocol rule 1).

Walks back from the want the way `router.route` does, but over **every** candidate producer, not
only the chosen one: a gap asked for and then not needed costs one question, and a gap missed
costs the build (#114). Deterministic: same want and facts in, same gaps out, in the same order.
"""

from collections.abc import Iterable, Mapping
from typing import NamedTuple

from comeni_core.goal.asked import Constraints
from mendel_resolver.layers import Layers
from mendel_resolver.rules.format import Decision, FactRef

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
    optional: bool = False
    """For an input: every port on the walk that reads it is `required: false` (#481). Asked,
    but *I don't have one* leaves it out instead of stopping the build."""


class Unreachable(NamedTuple):
    """A want nothing produces. An honest stop, never an empty gap list (review focus 1)."""

    subject: str


def _decided_in_the_run(stack: Layers, measurement: str, decisions: list,
                        inputs: set[str]) -> bool:
    """Every decision reading it settles a parameter, it describes one of this goal's inputs,
    and a step the build can add measures it: what `mendel_resolver.at_run` decides at run
    time. Without the input, nothing measures it, so it is asked (final review)."""
    declared = stack.measurements.measurements.get(measurement)
    return (
        bool(decisions)
        and all(target.effect == "param" for d in decisions for target in d.targets())
        and declared is not None and declared.describes in inputs
        and bool(stack.routing.producers_of(f"measurement.{measurement}", frozenset()))
    )


def _premise_measurements(stack: Layers) -> dict[str, list[Decision]]:
    """Measurement ids a rule reads, in its `when` or as the fact a `then` takes (#461),
    directly or through a derivation, each with the decisions that read it, in table order.

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
            taken = [row.then.fact] if isinstance(row.then, FactRef) else []
            for key in [*row.when, *taken]:
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


def absent_of(draft_id: str) -> list[str]:
    """The inputs the person said they do not have, for `gaps(absent=...)`."""
    from mendel_api.services import decisions

    return sorted(i.type_id for i in decisions.read(draft_id).inputs if not i.present)


def required_of(constraints: Constraints | dict | None) -> dict[str, list[str]]:
    """The goal's required states per type, for `gaps(required=...)`."""
    if constraints is None:
        return {}
    found = Constraints.model_validate(constraints) if isinstance(constraints, dict) \
        else constraints
    return {r.type_id: list(r.states) for r in found.required_states}


def gaps(want: list[str], facts: list[Fact], stack: Layers,
         required: Mapping[str, Iterable[str]] | None = None,
         absent: Iterable[str] = ()) -> list[Gap] | Unreachable:
    """Every input and measurement the want needs that no fact settles yet, inputs first.

    `required` is the goal's required states per wanted type: a producer whose output cannot
    carry them is not walked, so its inputs are not asked for (#479).
    `absent` is the inputs the person said they do not have: an optional one is left out and
    not asked again (#481).

    An `OPEN` fact settles its gap too: *can't share it* is an answer, and asking again would
    be the protocol ignoring it (review focus 2).

    A fact only a tool reads off the sample's label, that no rule reads and no trusted inspector
    measures, is not a gap (#338): the step that reads it stops for it instead.
    """
    known = {(f.kind, f.subject) for f in facts} | {(FactKind.INPUT, t) for t in absent}
    leaves: list[str] = []
    seen: set[str] = set()
    # Who reads each type, recorded before the `seen` check cuts a second visit short, so a type
    # two contracts consume names both (Part I.1 §4).
    consumers: dict[str, list[str]] = {}
    # Whether any port on the walk needs the type, rather than reading it only if given.
    needed: dict[str, bool] = {}
    seen_needed: set[str] = set()

    wanted_states = {t: frozenset(states) for t, states in (required or {}).items()}

    def walk(type_id: str, visiting: frozenset[str], states: frozenset[str] = frozenset(),
             optional: bool = False) -> None:
        # A type first reached behind an optional input is walked again when a required port
        # reaches it, so what lies behind it is marked needed too (#481).
        if type_id in seen and (optional or type_id in seen_needed):
            return
        first = type_id not in seen
        seen.add(type_id)
        if not optional:
            seen_needed.add(type_id)
        # A contract cannot satisfy its own input (the router's rule): a trimmer makes reads
        # only from reads, so reads with nothing but trimmers behind them are still a leaf the
        # person has to supply.
        producers = [
            c
            for c in stack.registry.producers_of(type_id, states)
            if c.id not in visiting and all(port.type_id != type_id for port in c.consumes)
        ]
        if not producers:
            if first:
                leaves.append(type_id)
            return
        for contract in producers:
            for port in contract.consumes:
                if port.type_id:
                    # Behind an optional input, even a required port only reads what is given.
                    behind = optional or not port.required
                    needed[port.type_id] = needed.get(port.type_id, False) or not behind
                    readers = consumers.setdefault(port.type_id, [])
                    if contract.id not in readers:
                        readers.append(contract.id)
                    walk(port.type_id, visiting | {contract.id}, optional=behind)

    for type_id in want:
        states = wanted_states.get(type_id, frozenset())
        if not stack.registry.producers_of(type_id, states):
            return Unreachable(type_id)
        walk(type_id, frozenset(), states)

    from mendel_api.services import measurers

    premises = _premise_measurements(stack)
    # **Not asked: what the pipeline measures for a setting** (#217). A fact only settings'
    # rules read, describing an input, and measured by a step the build can add, is decided in
    # the run, so nobody is stopped for it. A person may still state it; it is just not asked.
    premises = {
        m: decisions for m, decisions in premises.items()
        if not _decided_in_the_run(stack, m, decisions, set(leaves))
    }
    measurable = {piece.measures for piece in measurers.usable_pieces(stack).measurers.values()}
    # **Not asked: what only a tool reads and no sample can measure** (#338). It is left
    # unknown, and each step whose tool reads it stops for it on the board, as tier 4.
    measurements = set(premises) | {
        m.id
        for m in stack.measurements.measurements.values()
        if m.meta_key and m.describes in leaves and m.id in measurable
    }
    out = [
        Gap(FactKind.INPUT, t, "the pipeline needs it and nothing can make it",
            used_by=tuple(consumers.get(t, ())), optional=not needed.get(t, True))
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
