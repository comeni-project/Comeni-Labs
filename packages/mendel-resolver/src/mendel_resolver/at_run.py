"""Which settings are decided at run time, and the lookup each compiles into (#217).

A `param` decision is decided at run time when, once every fact known before the build is
substituted, it still needs exactly one fact that nobody knew, and that fact:

- is measured by a step a pipeline measurer makes (`measure_steps`);
- describes an input of the goal, so its value can travel on that input's `meta`;
- reaches the step through its lineage: the step consumes that input, or descends from a step
  that does.

The resolver resolves once; if any setting is like this, it routes again with the measurements
added to what is wanted, so the measuring steps join the graph, and records the lookup.
Implementation and presence decisions are never decided at run time: the graph is fixed when the
pipeline is built, so they stay questions, as before. A decision under `hit: unique` stays one
too: an overlap at run time has nobody to ask.
"""

from dataclasses import dataclass

from comeni_core.declared.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal
from comeni_core.logic.when import ABSENT, PRESENT, matches
from comeni_core.plan.at_run import AtRun, AtRunOp, AtRunRow, AtRunStep, AtRunTest
from comeni_core.plan.ir import PipelineIR

from mendel_resolver.rules import Derivation, RuleTable
from mendel_resolver.rules.format import Decision, FactRef, _comparison
from mendel_resolver.rules.table import _visible


@dataclass(frozen=True)
class Needed:
    """One setting to decide at run time, and the fact it waits for."""

    node_id: str
    param: str
    fact: str
    decision: Decision
    type_id: str
    """The input the fact describes."""


def _lineage(ir: PipelineIR, registry: Registry, goal: Goal) -> dict[str, set[str]]:
    """For each node, the goal's input types it consumes or descends from. In node order, which
    is the route's order: a source always comes before what it feeds."""
    have = {given.type_id for given in goal.have}
    fed = {(edge.to_node, edge.to_port) for edge in ir.edges}
    lineage: dict[str, set[str]] = {}
    for node in ir.nodes:
        contract = registry.get(node.contract_id)
        types: set[str] = set()
        for port in contract.consumes:
            if (node.id, port.name) in fed:
                continue
            types |= {alt.type_id for alt in port.alternatives() if alt.type_id in have}
        for edge in ir.edges:
            if edge.to_node == node.id:
                types |= lineage.get(edge.from_node, set())
        lineage[node.id] = types
    return lineage


def _bases(fact: str, derived: dict[str, Derivation], seen: frozenset = frozenset()) -> set[str]:
    """The measured facts a fact rests on: itself, or what its derivation reads."""
    if fact not in derived or fact in seen:
        return {fact}
    derivation = derived[fact]
    seen = seen | {fact}
    if derivation.source is not None:
        return _bases(derivation.source, derived, seen)
    if derivation.aggregate is not None:
        return {derivation.aggregate.measurement}
    return set().union(*(_bases(k, derived, seen) for row in derivation.rows for k in row.when))


def _read(decision: Decision) -> set[str]:
    return {key for row in decision.rows for key in row.when} | {
        row.then.fact for row in decision.rows if isinstance(row.then, FactRef)
    }


def needed(ir: PipelineIR, registry: Registry, rules: RuleTable, premises: dict,
           measurements: MeasurementRegistry, goal: Goal) -> list[Needed]:
    """Every setting of `ir` to decide at run time, in node then parameter order.

    Refuses (`MD0328`) a decision that waits on two facts the pipeline could measure: one
    lookup reads one measured fact, and two would need their values joined together."""
    derived = {d.fact: d for d in rules.derivations}
    lineage = _lineage(ir, registry, goal)
    overridden = {o.name for o in goal.constraints.params}
    found = []
    for node in ir.nodes:
        contract = registry.get(node.contract_id)
        for param in contract.params:
            if param.name in overridden:
                continue
            decision = rules.decision_for(contract.roles, param.name, contract.id)
            if decision is None or decision.hit == "unique":
                continue
            if rules.value_for(contract.roles, param.name, premises,
                               implementation=contract.id) is not None:
                continue
            visible = _visible(decision, premises)
            bases = set().union(*(_bases(f, derived) for f in _read(decision))) if decision.rows \
                else set()
            unknown = sorted(f for f in bases if f not in visible)
            if not unknown:
                continue
            reachable = [f for f in unknown if _measurable(f, node.id, lineage, registry,
                                                           measurements)]
            if len(unknown) > 1 and len(reachable) == len(unknown):
                raise ValueError(coded(
                    "MD0328",
                    f"{contract.id}.{param.name} is decided by a rule that waits on "
                    f"{', '.join(unknown)}, and the pipeline could measure each, but a setting "
                    "decided at run time reads one measured fact. State all but one in the "
                    "goal, or split the rule — `mendel explain MD0328`."))
            if len(unknown) == 1 and reachable:
                found.append(Needed(node.id, param.name, unknown[0], decision,
                                    measurements.get(unknown[0]).describes))
    return found


def _measurable(fact: str, node_id: str, lineage: dict[str, set[str]], registry: Registry,
                measurements: MeasurementRegistry) -> bool:
    if fact not in measurements.ids():
        return False
    describes = measurements.get(fact).describes
    return (describes is not None and describes in lineage.get(node_id, set())
            and bool(registry.producers_of(f"measurement.{fact}", frozenset())))


def _spelled(expected) -> tuple[AtRunTest, list] | None:
    """A row's expectation on the measured fact, in the closed tests; `None` for one that never
    decides once a value was measured (`absent`)."""
    if expected == ABSENT:
        return None
    if expected == PRESENT:
        return AtRunTest.ANY, []
    if isinstance(expected, dict):
        if "not" in expected:
            return AtRunTest.NE, [expected["not"]]
        return AtRunTest.IN, list(expected["in"])
    comparison = _comparison(expected)
    if comparison is not None:
        symbol, literal = comparison
        return AtRunTest(symbol), [literal]
    return AtRunTest.EQ, [expected]


def rows_of(decision: Decision, fact: str, premises: dict, rules: RuleTable,
            measurements: MeasurementRegistry) -> list[AtRunRow] | None:
    """The decision's rows with every known fact substituted, or `None` when a row reads
    something only the measured fact could decide and the lookup cannot say (a derived fact in
    `when`): such a setting falls to a lower tier instead."""
    derived = {d.fact: d for d in rules.derivations}
    visible = _visible(decision, premises)
    rows = []
    for row in decision.rows:
        test, operand, keep = AtRunTest.ANY, [], True
        for key, expected in row.when.items():
            if key == fact:
                spelled = _spelled(expected)
                if spelled is None:
                    keep = False
                    break
                test, operand = spelled
            elif key in visible:
                if not matches({key: expected}, visible):
                    keep = False
                    break
            else:
                return None
        if not keep:
            continue
        then = row.then
        if isinstance(then, FactRef):
            if then.fact == fact:
                kind = measurements.get(fact).kind
                rows.append(AtRunRow(test=test, operand=operand, takes_fact=True,
                                     integer=kind is MeasurementKind.INTEGER))
            elif then.fact in derived and derived[then.fact].source == fact \
                    and derived[then.fact].transform:
                chain = derived[then.fact]
                rows.append(AtRunRow(
                    test=test, operand=operand, takes_fact=True,
                    transform=[AtRunStep(op=AtRunOp(s.op), by=s.by) for s in chain.transform],
                    integer=chain.kind is MeasurementKind.INTEGER,
                ))
            elif then.fact in visible:
                rows.append(AtRunRow(test=test, operand=operand, then=visible[then.fact].value))
            else:
                return None
        else:
            rows.append(AtRunRow(test=test, operand=operand, then=then))
    return rows


def lookup(need: Needed, rows: list[AtRunRow], measured_by: str, fallback, fallback_reason: str
           ) -> AtRun:
    return AtRun(
        fact=need.fact,
        meta_key=need.fact,
        measured_by=measured_by,
        rule=need.decision.key(),
        rows=rows,
        fallback=fallback,
        fallback_reason=fallback_reason,
    )
