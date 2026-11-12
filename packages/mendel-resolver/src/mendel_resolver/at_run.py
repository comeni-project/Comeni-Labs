"""Which settings are decided at run time, and the lookup each compiles into (#217).

A `param` decision is decided at run time when, once every fact known before the build is
substituted, the facts it still needs nobody knew, and each of them:

- describes an input of the goal, so its value can travel on that input's `meta`, and reaches
  the step through its lineage: the step consumes that input, or descends from a step that does;
- comes from the run: a step a pipeline measurer makes measures it (`measure_steps`), or a
  person said it differs between samples (`constraints.varies`), so each sample's samplesheet
  cell carries it (#466), or both.

The resolver resolves once; if any setting is like this, it routes again with the measured facts
added to what is wanted, so the measuring steps join the graph, and records the lookup.
Implementation and presence decisions are never decided at run time here: the graph is fixed
when the pipeline is built, so they stay questions. A decision under `hit: unique` is decided in
the run only when its rows cannot overlap: a tie there has nobody to ask.
"""

from dataclasses import dataclass

from comeni_core.declared.inspection import InspectionCatalogue
from comeni_core.declared.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.goal.asked import Goal
from comeni_core.logic.when import ABSENT, PRESENT, matches
from comeni_core.plan.at_run import (
    AtRun,
    AtRunCondition,
    AtRunFact,
    AtRunFallback,
    AtRunOp,
    AtRunRow,
    AtRunSource,
    AtRunStep,
    AtRunTest,
)
from comeni_core.plan.ir import PipelineIR
from comeni_core.plan.tiers import Grain
from comeni_core.spell.routes import Via

from mendel_resolver.cases import overlapping
from mendel_resolver.measure_steps import steps_for
from mendel_resolver.rules import Derivation, RuleTable
from mendel_resolver.rules.format import Decision, FactRef, _comparison
from mendel_resolver.rules.table import _visible

AT_RUN_STOP = "!stop"
"""A person's answer to a run-time setting's fallback question: stop the run and name the sample
no row covers (#466). Not a value any setting can take (`!` is outside the substitutable class)."""


@dataclass(frozen=True)
class Needed:
    """One setting to decide at run time, and the facts it waits for, sorted."""

    node_id: str
    param: str
    facts: tuple[str, ...]
    decision: Decision
    sources: tuple[AtRunSource, ...]
    """Where each of `facts` comes from in the run, in the same order."""

    def source(self, fact: str) -> AtRunSource:
        return self.sources[self.facts.index(fact)]


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


def _source(fact: str, measurable: bool, goal: Goal,
            measurements: MeasurementRegistry) -> AtRunSource | None:
    """Where a fact nobody stated comes from in the run, or `None` when nothing there has it."""
    cell = (fact in goal.constraints.varies and fact in measurements.ids()
            and measurements.scope_of(fact) is Grain.SAMPLE)
    if cell and measurable:
        return AtRunSource.CELL_OR_MEASURED
    if cell:
        return AtRunSource.CELL
    if measurable:
        return AtRunSource.MEASURED
    return None


def _tie_free(decision: Decision, unknown: list[str], visible: dict,
              measurements: MeasurementRegistry, derived: dict[str, Derivation]) -> bool:
    """`hit: first` never ties; `unique` is decided in the run only when no case matches two
    rows, which must be shown, not assumed (an unenumerable fact is not tie-free)."""
    if decision.hit != "unique":
        return True
    found = overlapping(decision, unknown, visible, measurements,
                        {f: d.kind for f, d in derived.items()})
    return found == []


def needed(ir: PipelineIR, registry: Registry, rules: RuleTable, premises: dict,
           measurements: MeasurementRegistry, goal: Goal,
           answered: frozenset[str] = frozenset()) -> list[Needed]:
    """Every setting of `ir` to decide at run time, in node then parameter order.

    `answered`: settings a person has answered (`<node>.<param>`), which stay theirs: a rule
    decided later never displaces a person's answer (Task 6 review)."""
    derived = {d.fact: d for d in rules.derivations}
    lineage = _lineage(ir, registry, goal)
    overridden = {o.name for o in goal.constraints.params}
    found = []
    for node in ir.nodes:
        contract = registry.get(node.contract_id)
        for param in contract.params:
            if param.name in overridden or f"{node.id}.{param.name}" in answered:
                continue
            # Only an `ext` setting is written per task from the sample's `meta` (final review).
            if param.via is not Via.EXT:
                continue
            decision = rules.decision_for(contract.roles, param.name, contract.id)
            if decision is None:
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
            root = _root(ir, registry, node.id)
            sources = [
                _source(f, _measurable(f, node.id, lineage, registry, measurements), goal,
                        measurements) if _reaches(f, node.id, lineage, measurements, root)
                else None
                for f in unknown
            ]
            if any(s is None for s in sources):
                continue
            if not _tie_free(decision, unknown, visible, measurements, derived):
                continue
            if rows_of(decision, set(unknown), premises, rules, measurements) is not None:
                found.append(Needed(node.id, param.name, tuple(unknown), decision,
                                    tuple(sources)))
    return found


def _reaches(fact: str, node_id: str, lineage: dict[str, set[str]],
             measurements: MeasurementRegistry, root: str | None) -> bool:
    """The fact describes the input whose `meta` the step reads: the one behind its first
    input, as nf-core passes `meta` along (Task 5 review: an input reaching the step some other
    way, as a genome reaches an aligner through its index, carries no `meta` to it)."""
    if fact not in measurements.ids():
        return False
    describes = measurements.get(fact).describes
    return (describes is not None and describes in lineage.get(node_id, set())
            and describes == root)


def _root(ir: PipelineIR, registry: Registry, node_id: str) -> str | None:
    """The goal input type behind a step's first input, following first inputs upstream, as the
    emitter's `_meta_root` follows them; `None` when it cannot be told."""
    by_id = {n.id: n for n in ir.nodes}
    seen: set[str] = set()
    while node_id not in seen and node_id in by_id:
        seen.add(node_id)
        node = by_id[node_id]
        contract = registry.get(node.contract_id)
        ports = (contract.nf_inputs[0].ports if contract.nf_inputs
                 else [p.name for p in contract.consumes][:1])
        if not ports:
            return None
        edge = next((e for e in ir.edges if e.to_node == node_id and e.to_port == ports[0]),
                    None)
        if edge is None:
            port = next((p for p in contract.consumes if p.name == ports[0]), None)
            if port is None:
                return None
            return node.entry_type(port.name, port.type_id)
        node_id = edge.from_node
    return None


def _measurable(fact: str, node_id: str, lineage: dict[str, set[str]], registry: Registry,
                measurements: MeasurementRegistry) -> bool:
    if fact not in measurements.ids():
        return False
    describes = measurements.get(fact).describes
    return (describes is not None and describes in lineage.get(node_id, set())
            and bool(registry.producers_of(f"measurement.{fact}", frozenset())))


def _spelled(expected) -> tuple[AtRunTest, list]:
    """A row's expectation on one fact, in the closed tests."""
    if expected == ABSENT:
        return AtRunTest.ABSENT, []
    if expected == PRESENT:
        return AtRunTest.PRESENT, []
    if isinstance(expected, dict):
        if "not" in expected:
            return AtRunTest.NE, [expected["not"]]
        return AtRunTest.IN, list(expected["in"])
    comparison = _comparison(expected)
    if comparison is not None:
        symbol, literal = comparison
        return AtRunTest(symbol), [literal]
    return AtRunTest.EQ, [expected]


def rows_of(decision: Decision, facts: set[str], premises: dict, rules: RuleTable,
            measurements: MeasurementRegistry) -> list[AtRunRow] | None:
    """The decision's rows with every known fact substituted and a condition kept on each of
    `facts`, or `None` when a row reads something neither known nor among `facts` (a derived
    fact in `when`, say): such a setting falls to a lower tier instead."""
    derived = {d.fact: d for d in rules.derivations}
    visible = _visible(decision, premises)
    rows = []
    for row in decision.rows:
        conditions, keep = [], True
        for key, expected in row.when.items():
            if key in facts:
                test, operand = _spelled(expected)
                conditions.append(AtRunCondition(fact=key, test=test, operand=operand))
            elif key in visible:
                if not matches({key: expected}, visible):
                    keep = False
                    break
            else:
                return None
        if not keep:
            continue
        conditions.sort(key=lambda c: c.fact)
        then = row.then
        if isinstance(then, FactRef):
            if then.fact in facts:
                kind = measurements.get(then.fact).kind
                rows.append(AtRunRow(when=conditions, takes=then.fact,
                                     integer=kind is MeasurementKind.INTEGER))
            elif then.fact in derived and derived[then.fact].source in facts \
                    and derived[then.fact].transform:
                chain = derived[then.fact]
                rows.append(AtRunRow(
                    when=conditions, takes=chain.source,
                    transform=[AtRunStep(op=AtRunOp(s.op), by=s.by) for s in chain.transform],
                    integer=chain.kind is MeasurementKind.INTEGER,
                ))
            elif then.fact in visible:
                rows.append(AtRunRow(when=conditions, then=visible[then.fact].value))
            else:
                return None
        else:
            rows.append(AtRunRow(when=conditions, then=then))
    return rows


def fallback_of(param, ask) -> tuple[object, str, AtRunFallback, object]:
    """What a run-time setting is when no row matches: `(value, why, kind, decision)`.

    A default; else, for a setting the tool can do without, nothing, so the tool's own behaviour
    stands; else the person's answer to `ask()`, which returns `(value, reason)` or
    `(value, reason, decision)`: a value, `AT_RUN_STOP` to stop the run naming the sample, or
    nothing yet, an open question (#466)."""
    from comeni_core.spell.routes import OMITTABLE

    if param.default is not None:
        return param.default, param.because or "the contract's default", AtRunFallback.VALUE, None
    if param.via in OMITTABLE:
        return (None, "left to the tool: without a value it uses its own", AtRunFallback.TOOL,
                None)
    value, why, *rest = ask()
    decision = rest[0] if rest else None
    if value == AT_RUN_STOP:
        return None, why, AtRunFallback.STOP, decision
    return value, why, AtRunFallback.VALUE if value is not None else AtRunFallback.QUESTION, \
        decision


def lookup(need: Needed, rows: list[AtRunRow], measured_by: dict[str, str], fallback,
           fallback_reason: str) -> AtRun:
    """`measured_by`: the step measuring each measured fact, by fact."""
    return AtRun(
        facts=[AtRunFact(measurement=f, meta_key=f, source=need.source(f),
                         measured_by=(measured_by.get(f) if need.source(f) is not AtRunSource.CELL
                                      else None))
               for f in need.facts],
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
    any route exists: its rule waits only on facts that describe an input of the goal and that
    the run has, measured by a pipeline measurer or carried by the samplesheet because they vary
    (#466). The first pass asks nobody about these; the pass that follows either decides them at
    run time or asks, once (final review)."""
    have = {given.type_id for given in goal.have}
    derived = {d.fact: d for d in rules.derivations}
    overridden = {o.name for o in goal.constraints.params}
    found = set()
    for contract in registry.all():
        for param in contract.params:
            if param.name in overridden or param.via is not Via.EXT:
                continue
            decision = rules.decision_for(contract.roles, param.name, contract.id)
            if decision is None:
                continue
            if rules.value_for(contract.roles, param.name, premises,
                               implementation=contract.id) is not None:
                continue
            visible = _visible(decision, premises)
            bases = set().union(set(), *(_bases(f, derived) for f in _read(decision)
                                         if f not in visible))
            unknown = sorted(f for f in bases if f not in visible)
            if unknown and all(
                f in measurements.ids() and measurements.get(f).describes in have
                and _source(f, bool(registry.producers_of(f"measurement.{f}", frozenset())),
                            goal, measurements) is not None
                for f in unknown
            ) and _tie_free(decision, unknown, visible, measurements, derived):
                found.add((contract.id, param.name))
    return frozenset(found)
