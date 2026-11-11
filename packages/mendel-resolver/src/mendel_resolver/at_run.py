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

from comeni_core.declared.inspection import InspectionCatalogue
from comeni_core.declared.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal
from comeni_core.logic.when import ABSENT, PRESENT, matches
from comeni_core.plan.at_run import AtRun, AtRunOp, AtRunRow, AtRunStep, AtRunTest
from comeni_core.plan.ir import PipelineIR

from mendel_resolver.measure_steps import steps_for
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
           measurements: MeasurementRegistry, goal: Goal,
           answered: frozenset[str] = frozenset()) -> list[Needed]:
    """Every setting of `ir` to decide at run time, in node then parameter order.

    `answered`: settings a person has answered (`<node>.<param>`), which stay theirs: a rule
    decided later never displaces a person's answer (Task 6 review).

    Refuses (`MD0328`) a decision that waits on two facts the pipeline could measure and that
    would otherwise compile: one lookup reads one measured fact."""
    derived = {d.fact: d for d in rules.derivations}
    lineage = _lineage(ir, registry, goal)
    overridden = {o.name for o in goal.constraints.params}
    found = []
    for node in ir.nodes:
        contract = registry.get(node.contract_id)
        for param in contract.params:
            if param.name in overridden or f"{node.id}.{param.name}" in answered:
                continue
            decision = rules.decision_for(contract.roles, param.name, contract.id)
            if decision is None or decision.hit == "unique":
                continue
            if rules.value_for(contract.roles, param.name, premises,
                               implementation=contract.id) is not None:
                continue
            visible = _visible(decision, premises)
            # Only what is not known is expanded to what it rests on: a derived fact already
            # computed needs nothing measured.
            bases = set().union(set(), *(_bases(f, derived) for f in _read(decision)
                                         if f not in visible))
            unknown = sorted(f for f in bases if f not in visible)
            if not unknown:
                continue
            reachable = [f for f in unknown if _measurable(f, node.id, lineage, registry,
                                                           measurements)]
            if (len(unknown) > 1 and len(reachable) == len(unknown)
                    and _compilable(decision, set(unknown), visible, derived)):
                raise ValueError(coded(
                    "MD0328",
                    f"{contract.id}.{param.name} is decided by a rule that waits on "
                    f"{', '.join(unknown)}, and the pipeline could measure each, but a setting "
                    "decided at run time reads one measured fact. State all but one in the "
                    "goal, or split the rule — `mendel explain MD0328`."))
            if (len(unknown) == 1 and reachable
                    and rows_of(decision, unknown[0], premises, rules, measurements) is not None):
                found.append(Needed(node.id, param.name, unknown[0], decision,
                                    measurements.get(unknown[0]).describes))
    return found


def _compilable(decision: Decision, facts: set[str], visible: dict,
                derived: dict[str, Derivation]) -> bool:
    """Would the rows compile into a lookup if every one of `facts` were measured? Only then
    is waiting on several of them refused rather than left a question."""
    for row in decision.rows:
        if any(key not in visible and key not in facts for key in row.when):
            return False
        then = row.then
        if isinstance(then, FactRef) and then.fact not in visible and then.fact not in facts:
            chain = derived.get(then.fact)
            if chain is None or chain.source not in facts or not chain.transform:
                return False
    return True


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


@dataclass(frozen=True)
class Estimate:
    """A `head` fact a build decision used, and which decisions."""

    fact: str
    value: object
    used_by: tuple[str, ...]


def estimates(ir: PipelineIR, registry: Registry, goal: Goal,
              catalogue: InspectionCatalogue | None = None) -> list[Estimate]:
    """Every fact read from part of the data (`coverage: head`) that a selection or a setting
    of `ir` rested on, where a pipeline measurer of our code can read it in full from an input
    the goal has. Sorted by fact (#465).

    Only `by: code` measurers: a fact the server measured is one our code measures, and the
    same code over all the data is the confirmation. A person's statement is not an estimate
    and is never re-measured."""
    if catalogue is None:
        return []
    have = {given.type_id for given in goal.have}
    # Our code's steps only, by the format each reads: a tool's parser confirms nothing the
    # server estimated (Task 8 review).
    measurable = {
        measurer.measures
        for step in steps_for(catalogue, registry)
        if step.format is not None and set(step.format.reads) & have
        for measurer in step.measurers
    }
    used: dict[str, tuple[object, set[str]]] = {}

    def note(premises, where: str) -> None:
        for premise in premises:
            if premise.coverage == "head" and premise.id in measurable:
                used.setdefault(premise.id, (premise.value, set()))[1].add(where)

    for node in ir.nodes:
        note(node.selection.premise, f"selection:{node.id}")
        for binding in node.params:
            note(binding.value.premise, f"setting:{node.id}.{binding.name}")
    return [Estimate(fact, value, tuple(sorted(where)))
            for fact, (value, where) in sorted(used.items())]


def deferrable(registry: Registry, rules: RuleTable, premises: dict,
               measurements: MeasurementRegistry, goal: Goal,
               answered: frozenset[str] = frozenset()) -> frozenset[tuple[str, str]]:
    """`(contract id, param)` for every setting that may be decided at run time, judged before
    any route exists: its rule waits only on facts that describe an input of the goal and that a
    pipeline measurer measures. The first pass asks nobody about these; the pass that follows
    either decides them at run time or asks, once (final review)."""
    have = {given.type_id for given in goal.have}
    derived = {d.fact: d for d in rules.derivations}
    overridden = {o.name for o in goal.constraints.params}
    found = set()
    for contract in registry.all():
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
            bases = set().union(set(), *(_bases(f, derived) for f in _read(decision)
                                         if f not in visible))
            unknown = [f for f in bases if f not in visible]
            if unknown and all(
                f in measurements.ids() and measurements.get(f).describes in have
                and registry.producers_of(f"measurement.{f}", frozenset()) for f in unknown
            ):
                found.add((contract.id, param.name))
    return frozenset(found)
