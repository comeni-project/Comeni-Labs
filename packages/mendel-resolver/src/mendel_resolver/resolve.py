"""Turn a routed goal into a fully evidenced pipeline IR.

Resolution validates declared types, builds rule premises, routes producers, wires compatible
outputs to inputs, resolves parameters through the four-tier ladder, and records every ambiguity.
Values and selections retain the tier, source, reason, and premise evidence that justify them.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from comeni_core.declared.constraints import Setup, Verdict, evaluate
from comeni_core.declared.contract import InputPort, ModuleContract, OutputPort, Param
from comeni_core.declared.inspection import InspectionCatalogue
from comeni_core.declared.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import UnknownTypeError, Vocabulary
from comeni_core.diagnostics import coded
from comeni_core.goal.asked import (
    Constraints,
    InputState,
    ProducerExclusion,
    ProducerPin,
    RoleAbsence,
    SourcePin,
)
from comeni_core.goal.premise import PremiseRecord
from comeni_core.plan.at_run import AtRun, AtRunFallback, AtRunSource, Confirm, MetaAtRun
from comeni_core.plan.decision import (
    DecisionRecord,
    FactDecision,
    ParamAsked,
    ParamDecision,
    SourceAsked,
    SourceDecision,
)
from comeni_core.plan.ir import EntryType, IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.plan.tiers import PremiseOrigin, ValueSource

from mendel_resolver import at_run
from mendel_resolver.goal import Goal
from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver
from mendel_resolver.premises import Premise, build_premises
from mendel_resolver.router import (
    ConstraintViolation,
    IntentConflict,
    UnroutableError,
    _have_satisfies,
    route,
)
from mendel_resolver.router import _layer_name as _layer_of
from mendel_resolver.rules import RuleTable


@dataclass(frozen=True, slots=True)
class ParamContext:
    """The fixed resolution inputs shared by every parameter of one node."""

    node_id: str
    roles: tuple[str, ...]
    implementation: str
    from_layer: str | None
    goal: Goal
    rules: RuleTable
    premises: Mapping[str, Premise]
    resolver: AmbiguityResolver
    backed: Mapping[str, object]
    measurements: MeasurementRegistry | None = None
    at_run: "Mapping[str, at_run.Needed]" = None  # type: ignore[assignment]
    """This node's settings to decide at run time, by parameter name (#217)."""
    deferring: frozenset = frozenset()
    """`(contract id, param)` settings this pass asks nobody about: they may be decided at run
    time, which the next pass settles."""


def _constraints_hold(contract: ModuleContract, node: IRNode,
                      types: dict[str, str] | None = None) -> Verdict:
    """The step's constraints once its parameters are resolved (#460). A connection a row
    forbids, or an input a row requires and cannot have, is refused at build time; a row that
    depends on an input each run may leave empty is left to the run."""
    states = {r.port: r.state for r in node.inputs}
    given = {p.name for p in contract.consumes if p.required}
    given |= {p for p, s in states.items() if s is InputState.REQUIRED}
    unknown = frozenset(p for p, s in states.items() if s is InputState.OPTIONAL)
    params = {p.name: (node.param(p.name).value if node.param(p.name) else None)
              for p in contract.params}
    verdict = evaluate(contract, Setup(given=frozenset(given), params=params, unknown=unknown,
                                       types=types or {}))
    why = "; ".join(verdict.sentences) or "its constraints"
    if verdict.missing:
        raise ConstraintViolation(coded(
            "MD0609", f"{contract.id} needs {', '.join(verdict.missing)}, which is not "
            f"connected: {why} — `mendel explain MD0609`."))
    if verdict.forbidden:
        raise ConstraintViolation(coded(
            "MD0610", f"{contract.id} cannot have {', '.join(verdict.forbidden)} with these "
            f"settings: {why} — `mendel explain MD0610`."))
    return verdict


def _not_withheld(withheld: list, port: InputPort, consumer: str) -> None:
    """MD0608 when the only output that could feed `port` is one its step does not write."""
    for _node, output, producer in withheld:
        for alternative in port.alternatives():
            if output.type_id == alternative.type_id and alternative.states <= output.state:
                raise ConstraintViolation(coded(
                    "MD0608", f"{consumer}'s {port.name} needs {producer}'s {output.name}, "
                    f"which is written only when {output.produced_when}, and this pipeline's "
                    "settings do not meet that — `mendel explain MD0608`."))


def resolve(
    goal: Goal,
    registry: Registry,
    rules: RuleTable,
    measurements: MeasurementRegistry,
    *,
    vocabulary: Vocabulary,
    resolver: AmbiguityResolver | None = None,
    layer_names: Sequence[str] = (),
    prior: Sequence[DecisionRecord] = (),
    facts_read: Mapping[str, frozenset[str] | None] | None = None,
    inspection: InspectionCatalogue | None = None,
) -> PipelineIR:
    """Resolve ``goal`` against one loaded registry stack, deciding at run time the settings
    whose rule waits on a fact only the pipeline can measure (#217).

    Once, as always; and when such a setting exists, again with the measurements wanted too, so
    the steps that measure them join the graph. The second graph must hold the first one
    whole: measuring adds steps, it never moves one. See `_resolve_once` for the rest.
    """
    args = dict(vocabulary=vocabulary, resolver=resolver, layer_names=layer_names,
                prior=prior, facts_read=facts_read)
    measurements.check_varies(goal)
    premises = build_premises(goal=goal, derivations=rules.derivations,
                              measurements=measurements)
    answered = frozenset(record.key for record in prior
                         if getattr(record, "human_override", None) is not None)
    # **The real resolver routes; settings that may be decided in the run wait.** The first
    # pass asks every question but those, so the route it makes is the one that will be
    # measured; the pass after replays its answers and either decides each waiting setting in
    # the run or asks it, once (final review: a discovery pass that guessed the route moved
    # whenever a model broke a tie differently).
    deferring = at_run.deferrable(registry, rules, premises, measurements, goal, answered)
    # Every pass asks through this, so a question reaches the real resolver once, and a later
    # pass gets the very answer the first did: its value, its reason and who gave it.
    remembering = _Remembering(resolver or FlagOnlyResolver())
    args["resolver"] = remembering
    first = _resolve_once(goal, registry, rules, measurements, deferring=deferring, **args)
    needs = at_run.needed(first, registry, rules, premises, measurements, goal, answered)
    # `inspection`: the measurers, for confirming estimates; without it nothing is confirmed.
    estimates = at_run.estimates(first, registry, goal, inspection)
    if not deferring and not needs and not estimates:
        return first

    def again(which: Goal, plan=None) -> PipelineIR:
        """Another pass, through the same remembering resolver: no question is asked twice."""
        return _resolve_once(which, registry, rules, measurements, at_run_plan=plan, **args)

    if not needs and not estimates:
        return again(goal)
    # Only what a step measures is routed for; a fact from the samplesheet needs no step (#466).
    facts = sorted({f for need in needs for f in need.facts
                    if need.source(f) is not AtRunSource.CELL})
    measured = sorted({*facts, *(e.fact for e in estimates)})
    wanted = [f"measurement.{fact}" for fact in measured
              if f"measurement.{fact}" not in goal.want]
    widened = goal.model_copy(update={"want": [*goal.want, *wanted]})
    plan: dict[str, dict[str, at_run.Needed]] = {}
    for need in needs:
        plan.setdefault(need.node_id, {})[need.param] = need
    try:
        second = again(widened, plan)
    except UnroutableError:
        # A measurer this goal cannot feed: the settings are what they were before measuring
        # existed, questions included.
        return again(goal)
    kept = {node.id: node.contract_id for node in second.nodes}
    moved = [n.id for n in first.nodes if kept.get(n.id) != n.contract_id]
    edges = {edge.model_dump_json() for edge in second.edges}
    if moved or not {edge.model_dump_json() for edge in first.edges} <= edges:
        if not needs:
            # Only confirmations asked for the second route, and they are optional: a build
            # that stood before them is never refused because of them (Task 8 review).
            return again(goal)
        raise ValueError(coded(
            "MD0329",
            f"routing again to measure {', '.join(measured)} moved {moved or 'an edge'}: "
            "measuring may add steps to a pipeline and never change one — "
            "`mendel explain MD0329`."))
    # Which step measures each fact is read off the graph the router made, never guessed.
    measuring = {
        fact: next(node for node in second.nodes
                   if f"measurement.{fact}" in {p.type_id for p in
                                                 registry.get(node.contract_id).produces})
        for fact in measured
    }
    second.confirms = [
        Confirm(measurement=e.fact, estimate=e.value, measured_at=measuring[e.fact].id,
                used_by=list(e.used_by))
        for e in estimates
    ]
    _name_the_measurers(second, {fact: measuring[fact].contract_id for fact in facts})
    _say_why_it_measures(second, measuring, needs, estimates)
    second.meta_at_run = [
        MetaAtRun(measurement=fact, meta_key=fact, type_id=measurements.get(fact).describes,
                  measured_at=measuring[fact].id, measured_port=fact)
        for fact in facts
    ]
    return second


class _Remembering:
    """The resolver a build asks through: each question once, its answer kept for any later
    pass, so every pass of one build sees the same answers and the real resolver, a model or a
    replay of a person's record, is never asked twice."""

    def __init__(self, inner: AmbiguityResolver) -> None:
        self.inner = inner
        self._said: dict[str, object] = {}

    def resolve(self, ambiguity):
        key = ambiguity.key()
        if key not in self._said:
            self._said[key] = self.inner.resolve(ambiguity)
        return self._said[key]


def _say_why_it_measures(ir: PipelineIR, measuring: Mapping[str, IRNode],
                         needs: Sequence["at_run.Needed"],
                         estimates: Sequence["at_run.Estimate"]) -> None:
    """A measuring step's presence says what it measures and for whom: nobody asked for it,
    the build added it (Task 8 review)."""
    said: dict[str, list[str]] = {}
    for need in needs:
        for fact in need.facts:
            if need.source(fact) is AtRunSource.CELL:
                continue
            said.setdefault(measuring[fact].id, []).append(
                f"measures {fact} in the run, for {need.node_id}.{need.param}")
    for estimate in estimates:
        said.setdefault(measuring[estimate.fact].id, []).append(
            f"confirms {estimate.fact}, estimated on part of the data, on all of it: "
            f"{', '.join(estimate.used_by)} rest on it")
    for node in ir.nodes:
        if node.id in said:
            node.presence = node.presence.model_copy(
                update={"reason": "; ".join(sorted(set(said[node.id])))})


def _name_the_measurers(ir: PipelineIR, measured_by: Mapping[str, str]) -> None:
    """Each run-time setting names the step that actually measures its fact."""
    for node in ir.nodes:
        for binding in node.params:
            lookup = binding.value.at_run
            if lookup is None:
                continue
            facts = [f.model_copy(update={"measured_by": measured_by[f.measurement]})
                     if f.source is not AtRunSource.CELL else f for f in lookup.facts]
            named = lookup.model_copy(update={"facts": facts})
            by = {f.measurement: f.measured_by for f in facts}
            binding.value = binding.value.model_copy(update={
                "at_run": named,
                "reason": _at_run_reason(named),
                "premise": [p.model_copy(update={"by": by[p.id]}) if by.get(p.id) else p
                            for p in binding.value.premise],
            })


def _resolve_once(
    goal: Goal,
    registry: Registry,
    rules: RuleTable,
    measurements: MeasurementRegistry,
    *,
    vocabulary: Vocabulary,
    resolver: AmbiguityResolver | None = None,
    layer_names: Sequence[str] = (),
    prior: Sequence[DecisionRecord] = (),
    facts_read: Mapping[str, frozenset[str] | None] | None = None,
    at_run_plan: Mapping[str, Mapping[str, "at_run.Needed"]] | None = None,
    deferring: frozenset = frozenset(),
) -> PipelineIR:
    """Resolve ``goal`` against one loaded registry stack.

    ``prior`` supplies independent evidence for values claimed as human decisions. An unbacked
    human claim is demoted and remains reviewable. ``facts_read`` maps each contract to profile
    facts read by its implementation; missing facts become reviewable decisions. Passing ``None``
    means no conformance inventory was supplied and preserves the ordinary resolver boundary.
    """
    # A29. `Annotated[str, "type-id"]` says somebody named this; it does not say the name
    # is of a declared type. `router._have_satisfies` only *compares*, so a `have` entry
    # that satisfies nothing was never looked up and never rejected — and a patient name
    # and a filesystem path reached the publication payload as `type_id`, with a sentence of
    # clinical notes as a `required_states` key.
    #
    # Keyword and **required**, like `measurements` and for the same reason A2 gives: an
    # optional guard is the guard the next verb forgets. `mendel upgrade` is the verb that
    # matters here, because its goal comes from a stranger's bundle rather than from a file
    # the operator wrote.
    _declared_types(goal, vocabulary)
    # A56. What a *person* actually answered, keyed by decision. Built from the caller's
    # records, so a resolver claiming `HUMAN` cannot also supply the proof of it.
    backed = {
        record.key: record.human_override
        for record in prior
        if getattr(record, "human_override", None) is not None
    }
    # Invariant 15 was enforced in `mendel build`'s own re-route through
    # `MeasurementRegistry.profile()` — an application-layer step, which is not a property
    # of anything. `mendel upgrade` takes its goal from a bundle rather than a file, so the
    # one verb that reads something a stranger wrote was the one verb with no check, and a
    # bundle carrying `sample_name: PATIENT-00417` upgraded to exit 0 with the string in
    # the new IR. A guard in a caller is a guard the next caller forgets.
    #
    # Required rather than defaulted, deliberately: an optional guard is the same guard
    # one keyword away from being forgotten again. Audit 2026-08-06, A2.
    for measured in goal.profile.measurements:
        measurements.check(measured.measurement, measured.value)

    resolver = resolver or FlagOnlyResolver()
    # Built once, here, and threaded. Not rebuilt per decision: a premise set is a function
    # of the goal and the derivations, so building it twice is two chances to build it
    # differently — and `same goal in -> same pipeline out` is the claim that would pay.
    premises = build_premises(goal=goal, derivations=rules.derivations, measurements=measurements)
    # A `presence: absent` decision is read here rather than inside `route()`, because it is
    # a *decision* and the router does not hold a rule table's semantics — it holds a graph.
    # Roles rather than contract ids for the same reason the decision targets one.
    absent = frozenset(
        role
        for role in _roles_in(registry)
        if (fired := rules.presence_for(role, premises)) is not None and fired.value == "absent"
    )
    # **A person's switched-off roles join the rules'** (A1): the same semantics, a different
    # author. When the goal cannot be reached with them, the one that blocks it is named.
    person = goal.constraints.roles_absent()
    try:
        plan = route(goal, registry, rules, resolver, premises=premises,
                     absent_roles=absent | person)
    except IntentConflict:
        raise
    except UnroutableError as exc:
        blocking = _blocking_absence(goal, registry, rules, premises, absent, person)
        if blocking is None:
            raise
        raise IntentConflict(
            coded("MD0319", f"you switched off the role {blocking.role!r}, and this goal needs "
                  f"it: {exc}. Turn it back on, or stop asking for what only it leads to — "
                  "`mendel explain MD0319`."),
            intent=blocking,
        ) from exc
    ir = PipelineIR(
        profile=goal.profile,
        registry_layers=list(layer_names),
        # Read off the loaded data rather than passed in: a displacement is a fact each
        # loader discovered, and asking the caller to forward it is asking them to forget.
        # A published pipeline whose overlay quietly rerouted it is unauditable.
        #
        # All four kinds, in loader order (`layers.Layers.displaced` is the same list). This
        # read measurements+contracts alone for a plan and a half, so an overlay `vocabularies/`
        # or `rules/` block reached the published artifact recording nothing (A51) — A23/A24
        # gave those kinds a `Displacement`, but `resolve()` never collected it. Each kind now
        # carries its own list, so completeness is a property of the arguments, not of the
        # caller remembering to forward a fifth thing.
        displaced=[
            *measurements.displaced,
            *vocabulary.displaced,
            *registry.displaced,
            *rules.displaced,
        ],
    )
    # Every output emitted so far, in order. Keyed on type_id alone this was a dict, so the
    # last producer of a type won and SAMTOOLS_INDEX's `.bai` was handed to featureCounts —
    # valid Nextflow, no flag, and `-stub-run` cannot catch it because nf-core stubs never
    # read their inputs. A consumer must be fed a source that satisfies its required states.
    produced: list[tuple[str, str, str, frozenset[str]]] = []
    # Outputs a step writes only under a condition this pipeline does not meet (#460).
    withheld: list[tuple[str, OutputPort, str]] = []

    for step in plan.steps:
        contract = registry.get(step.contract_id)
        node = IRNode(
            id=step.node_id,
            contract_id=contract.id,
            site=step.site,
            selection=ResolvedValue(
                value=contract.id,
                tier=step.selection_tier,
                source=step.selection_source,
                reason=step.selection_reason,
                premise=step.selection_premise,
                axis_reason=step.selection_axis_reason,
                from_layer=step.from_layer,
                displaced_layer=step.displaced_layer,
            ),
            # Why the step is here at all — a downstream port required its output, or the
            # goal asked for it. Structural in both cases, and separate from `selection`
            # because which contract fills it very often is not. A113.
            presence=ResolvedValue(
                value=None,
                tier=step.presence_tier,
                reason=step.presence_reason or "required by the pipeline",
            ),
            inputs=step.inputs,
        )

        # The contract's layer is distinct from the layer whose rule selected the step.
        context = ParamContext(
            node_id=node.id,
            roles=tuple(contract.roles),
            implementation=contract.id,
            from_layer=_layer_of(registry, contract.id),
            goal=goal,
            rules=rules,
            premises=premises,
            resolver=resolver,
            backed=backed,
            measurements=measurements,
            at_run=(at_run_plan or {}).get(step.node_id, {}),
            deferring=deferring,
        )
        for param in contract.params:
            value, decision = _resolve_param(param, context)
            node.set_param(param.name, value)
            if decision is not None:
                ir.decisions.append(decision)

        # **What a tool reads comes from somewhere** (#338): a fact its code reads off the
        # sample's label, and nobody supplied, is tier 4, as an unsupplied setting is.
        known = {entry.measurement for entry in goal.profile.measurements}
        for fact in sorted((facts_read or {}).get(contract.id) or ()):
            if fact in known:
                continue
            ir.decisions.append(
                FactDecision(
                    key=f"{node.id}.fact.{fact}",
                    subject=fact,
                    reason=f"{contract.id} reads {fact}, and it is not known",
                    resolved_by="flag-only",
                    candidates=_values_of(measurements.get(fact)),
                    unknown=[fact],
                )
            )

        off = {r.port for r in node.inputs if r.state is InputState.OFF}
        # Sources first: a row on `type.<input>` reads the type each one connects (#464).
        sources = {}
        types: dict[str, str] = {}
        for port in contract.consumes:
            if port.name in off:
                continue
            pinned = goal.constraints.source_at(contract.id, port.name)
            sources[port.name] = _source_for(
                produced, port, node.id, ir.decisions, resolver,
                pinned=_node_of(ir, pinned.producer) if pinned else None)
            alternatives = port.alternatives()
            held_at = next((n for n, a in enumerate(alternatives)
                            if _have_satisfies(goal, a.type_id, a.states)), None)
            held = alternatives[held_at].type_id if held_at is not None else None
            source = sources[port.name]
            # The router takes the first alternative it can satisfy, and the pipeline's own
            # input satisfies one at once: a produced later alternative must not override it,
            # or the step is wired and checked with a type the router never chose (#464).
            if source is not None and pinned is None and held_at is not None and held_at < next(
                    n for n, a in enumerate(alternatives)
                    if a.type_id == source[2] and a.states <= source[3]):
                sources[port.name] = None
            if sources[port.name] is not None:
                types[port.name] = sources[port.name][2]
            elif held is not None or (not port.required and not port.type_id):
                # A switched-on optional input fed from outside asks for its first alternative.
                entry = held if held is not None else alternatives[0].type_id
                types[port.name] = entry
                if len(alternatives) > 1 or not port.type_id:
                    node.entry_types.append(EntryType(port=port.name, type_id=entry))
        verdict = _constraints_hold(contract, node, types)
        for port in contract.consumes:
            if port.name in off:
                continue
            source = sources[port.name]
            if source is None and not any(_have_satisfies(goal, a.type_id, a.states)
                                          for a in port.alternatives()):
                _not_withheld(withheld, port, contract.id)
            if source is not None:
                from_node, from_port, type_id, states = source
                ir.edges.append(
                    IREdge(
                        from_node=from_node,
                        from_port=from_port,
                        to_node=node.id,
                        to_port=port.name,
                        # The type the *source* emits, which for a single-alternative port
                        # is the port's own type and for an `accepts` port is whichever
                        # alternative actually matched.
                        type_id=type_id,
                        states=states,
                    )
                )

        for port in contract.produces:
            if port.name in verdict.produced:
                produced.append((node.id, port.name, port.type_id, port.state))
            else:
                withheld.append((node.id, port, contract.id))

        ir.nodes.append(node)

    # Already resolved and recorded, by `route()`, where the answer could still change the
    # selection. This loop used to call `resolver.resolve()` itself — after `ir.nodes` and
    # `ir.edges` were built — so the answer went into a record and nowhere else, and asking
    # a second time is a second chance to disagree with the pipeline that exists. With a
    # model behind the port it is also a second charge. Audit 2026-08-06, A8.
    ir.decisions.extend(plan.decisions)

    return ir


def _node_of(ir: PipelineIR, contract_id: str) -> str | None:
    """The node a contract was placed as, so far."""
    return next((n.id for n in ir.nodes if n.contract_id == contract_id), None)


def _source_for(
    produced: list[tuple[str, str, str, frozenset[str]]],
    port: InputPort,
    node_id: str,
    decisions: list[DecisionRecord],
    resolver: AmbiguityResolver,
    *,
    pinned: str | None = None,
) -> tuple[str, str, str, frozenset[str]] | None:
    """Pick an upstream output that actually satisfies this port.

    Matching on `type_id` alone is what wired an index file into featureCounts. A source
    qualifies only if its emitted states are a superset of the port's required states —
    the same test `Registry.producers_of` uses, applied to what the pipeline has actually
    built rather than to what the registry could build.

    Among qualifying sources the one with the **smallest surplus** wins — fewest states
    beyond those asked for — which is the same rule `router.py` uses when ranking producers,
    and for the same reason: asking for a coordinate-sorted BAM should get a coordinate-sorted
    BAM, not whatever the pipeline most recently refined it into. Ties break on emission
    order, latest first.

    When more than one source is equally good that is a genuine choice, so it is recorded at
    tier 4 rather than taken silently — invariant 8 applied inside the graph rather than at
    its edges.

    A port may declare several alternatives; they are tried in declaration order and the
    first with any qualifying source wins, matching how the router picked which one to
    route. `prefer` then breaks ties *within* that alternative — it never promotes a later
    alternative over an earlier one, because alternative order is the author saying which
    kind of input they would rather have.
    """
    for alternative in port.alternatives():
        qualifying = [
            source
            for source in produced
            if source[2] == alternative.type_id and alternative.states <= source[3]
        ]
        if qualifying:
            required = alternative.states
            break
    else:
        return None

    def surplus(source: tuple[str, str, str, frozenset[str]]) -> int:
        return len(source[3] - required)

    # **A person chose this port's source** (A1, a `SourcePin`): it wires, and it is recorded as
    # theirs whenever it differs from what the smallest surplus would have taken.
    if pinned is not None:
        theirs = [source for source in qualifying if source[0] == pinned]
        if theirs:
            engine = min(qualifying, key=lambda s: (surplus(s), -produced.index(s)))
            if theirs[-1] != engine:
                chosen_ref = f"{theirs[-1][0]}.{theirs[-1][1]}"
                decisions.append(
                    SourceDecision(
                        key=f"{node_id}.source:{port.name}",
                        subject=f"source:{port.name}",
                        candidates=sorted(f"{n}.{p}" for n, p, _, _ in qualifying),
                        chosen=chosen_ref,
                        human_override=chosen_ref,
                        reason=f"you chose {theirs[-1][0]} to feed {port.name}, over "
                               f"{engine[0]}",
                        confidence=1.0,
                        resolved_by="person",
                    )
                )
            return theirs[-1]

    best = min(surplus(source) for source in qualifying)
    equally_good = [source for source in qualifying if surplus(source) == best]
    if port.prefer and len(equally_good) > 1:
        preferred = [source for source in equally_good if port.prefer <= source[3]]
        equally_good = preferred or equally_good
    chosen = equally_good[-1]
    if len(equally_good) > 1:
        ambiguity = SourceAsked(
            node_id=node_id,
            subject=f"source:{port.name}",
            candidates=sorted(f"{n}.{p}" for n, p, _, _ in equally_good),
            type_id=chosen[2],
            required=sorted(required),
        )
        resolution = resolver.resolve(ambiguity)
        # The answer selects. This used to compute `equally_good[-1]`, call the resolver,
        # and then record `chosen=f"{chosen[0]}.{chosen[1]}"` — overwriting the resolver's
        # answer in the very statement that recorded it, so a published bundle could
        # contradict its own pipeline with no mutation at all. Audit 2026-08-06, A8.
        #
        # A non-candidate answer falls back rather than being trusted, exactly as
        # `router._choose` and `ReplayResolver._still_applies` do.
        chosen = next(
            (s for s in equally_good if f"{s[0]}.{s[1]}" == resolution.value),
            equally_good[-1],
        )
        decisions.append(
            SourceDecision(
                key=ambiguity.key(),
                subject=ambiguity.subject,
                candidates=ambiguity.candidates,
                # What was wired, not what was asked for.
                chosen=f"{chosen[0]}.{chosen[1]}",
                reason=resolution.why,
                confidence=resolution.confidence,
                resolved_by=resolution.by,
            )
        )
    return chosen


def _blocking_absence(goal, registry, rules, premises, absent, person) -> RoleAbsence | None:
    """The first of the person's switched-off roles (sorted) without which the goal routes, or
    `None` when the goal fails for another reason. Deterministic: roles are tried in order."""
    for role in sorted(person):
        try:
            route(goal, registry, rules, FlagOnlyResolver(), premises=premises,
                  absent_roles=absent | (person - {role}))
        except UnroutableError:
            continue
        return RoleAbsence(role=role)
    return None


def _values_of(measurement) -> list:
    """The answers a person can give: an enum's values, or yes and no."""
    if measurement.kind is MeasurementKind.BOOLEAN:
        return [True, False]
    return list(measurement.values)


def _roles_in(registry: Registry) -> list[str]:
    """Every role some contract in this stack fills, sorted.

    Sorted because the set it builds feeds a routing decision, and an iteration order that
    depends on registry insertion is exactly what invariant 10 forbids — even where the
    result is a set and the order cannot show. It costs nothing and it removes the question.
    """
    return sorted({role for contract in registry.all() for role in contract.roles})


def _resolve_param(
    param: Param,
    context: ParamContext,
) -> tuple[ResolvedValue, ParamDecision | None]:
    # Tier 1 — the goal states it outright. No choice exists.
    override = next((o for o in context.goal.constraints.params if o.name == param.name), None)
    if override is not None:
        return ResolvedValue(
            value=override.value,
            tier=Tier.STRUCTURAL,
            source=ValueSource.SAID,
            reason=f"specified in the goal as {param.name}",
        ), None

    # A tie under `hit: unique`: the rows disagree, so neither the rule nor a default
    # decides; the question is asked with every value the rows give (#461).
    ties = context.rules.ties_for(
        context.roles, param.name, context.premises, implementation=context.implementation
    )
    if ties:
        return _ask(param, context, [pin.value for pin in ties])

    # Tier 3 — a declared rule matches the measured profile.
    pin = context.rules.value_for(
        context.roles, param.name, context.premises, implementation=context.implementation
    )
    if pin is not None:
        return ResolvedValue(
            value=pin.value,
            tier=Tier.DATA_PROFILED,
            # No trailing colon when the row has nothing of its own to add. A row may be
            # justified entirely by its block (a one-row rule often is), and `MD0301` allows
            # that — but "rule param:strandedness: " reads as a truncation rather than as an
            # absence, which is half of what A78 was.
            reason=pin.reason_line(),
            # The facts the row read, so a reader of `pipeline.yml` can check the premise
            # tier 3 asks them to check. A108.
            premise=pin.premise,
            # The block's methodology, kept apart from the row's choice. One field carried
            # both and printed the axis citation as the row's reason. A79, A107.
            axis_reason=pin.axis_because(),
            # Provenance arrives *with* the value rather than beside it. It was two
            # lookups on the table a caller had to remember to make, which is how the
            # other consumer of the same table forgot both. Audit A15, A22.
            from_layer=pin.from_layer,
            displaced_layer=pin.displaced_layer,
        ), None

    # Deferred: perhaps decided at run time. Nobody is asked yet; the next pass decides it in
    # the run or asks, once (final review).
    if (context.implementation, param.name) in context.deferring and not (
            context.at_run or {}).get(param.name):
        return ResolvedValue(
            value=None, tier=Tier.AMBIGUOUS,
            reason="not yet settled: it may be decided in the run",
        ), None

    # Decided at run time (#217): the rule waits on a fact the pipeline measures, and is
    # compiled into a lookup over it. Between tier 3 and tier 2, because it *is* the rule,
    # decided later; the lower tiers become its fallback.
    need = (context.at_run or {}).get(param.name)
    if need is not None:
        decided = _at_run(param, context, need)
        if decided is not None:
            return decided

    # Tier 2 — a documented default exists for this context.
    if param.default is not None:
        # The *document*, and the layer that wrote it. Both were missing: the reason was
        # `contract default for {name}`, which names the field it is explaining rather than
        # justifying it, and `from_layer` stayed null even when an overlay supplied the
        # value — so a laboratory raising featureCounts' `-Q` from 0 to 30, discarding every
        # read below mapping quality 30, produced a byte-identical justification. A76, A128.
        return ResolvedValue(
            value=param.default,
            tier=Tier.CONVENTION,
            reason=param.because or "the contract declares this default and states no reason",
            from_layer=context.from_layer,
        ), None

    # Tier 4 — nothing decided it. Ask the port, record it, flag it.
    # Tier 2 already returned when a default existed, so there is exactly one candidate and
    # it is None. Real alternatives arrive with the rule-tables spec, which gives a parameter
    # a declared domain to draw them from.
    return _ask(param, context, [None])


_SAID = {
    AtRunSource.CELL: "from the samplesheet",
    AtRunSource.MEASURED: "measured in the pipeline",
    AtRunSource.CELL_OR_MEASURED: "from the samplesheet, measured where left blank",
}


def _at_run_reason(lookup: AtRun) -> str:
    facts = "; ".join(
        f"{f.measurement} {_SAID[f.source]}" + (f" by {f.measured_by}" if f.measured_by else "")
        for f in lookup.facts)
    otherwise = {
        AtRunFallback.TOOL: "the tool's own value",
        AtRunFallback.STOP: "the run stops and names the sample",
        AtRunFallback.QUESTION: "a question still open",
    }.get(lookup.fallback_is, str(lookup.fallback))
    return (f"decided at run time by rule {lookup.rule} from {facts}; where no "
            f"row applies, {otherwise}")


def _at_run(
    param: Param, context: ParamContext, need: "at_run.Needed"
) -> tuple[ResolvedValue, ParamDecision | None] | None:
    """The setting as a lookup over facts from the run, or `None` when its rows cannot be one."""
    rows = at_run.rows_of(need.decision, set(need.facts), context.premises, context.rules,
                          context.measurements)
    if rows is None:
        return None

    def ask():
        asked, decision = _ask(param, context, [None])
        return asked.value, asked.reason, decision

    fallback, why, kind, decision = at_run.fallback_of(param, ask)
    # Named once the graph exists (`_name_the_measurers`): the router picks the steps.
    pending = {f: "comeni/measure/pending@0.0.0" for f in need.facts}
    lookup = at_run.lookup(need, rows, pending, fallback, why).model_copy(
        update={"fallback_is": kind})
    return ResolvedValue(
        value=fallback,
        tier=Tier.DATA_PROFILED,
        source=ValueSource.RESOLVER,
        reason=_at_run_reason(lookup),
        premise=[PremiseRecord(id=f, value=None, origin=PremiseOrigin.UNMEASURED,
                               by=pending[f] if need.source(f) is not AtRunSource.CELL
                               else None)
                 for f in need.facts],
        axis_reason=need.decision.because or "",
        at_run=lookup,
    ), decision


def _ask(
    param: Param, context: ParamContext, candidates: list
) -> tuple[ResolvedValue, ParamDecision | None]:
    """Tier 4: ask the port with these candidates, record the answer, and flag it."""
    ambiguity = ParamAsked(
        node_id=context.node_id,
        subject=param.name,
        candidates=candidates,
        tier_hint=param.tier_hint,
    )
    resolution = context.resolver.resolve(ambiguity)
    if candidates != [None] and resolution.value not in candidates:
        # A tie's values are a closed set (#461): an answer outside it is forged or stale,
        # so it is dropped and the question stays open and flagged, as `router._choose` does.
        resolution = resolution.model_copy(update={"value": None})
    # **This site trusts the answer; the other two do not, and the asymmetry is deliberate.**
    # `router._choose` and `_source_for` fall back when a resolver names something that is
    # not a candidate, because there the candidates are a closed set drawn from the registry
    # — a non-candidate answer is either forged or stale, and neither is worth acting on.
    # A parameter has no declared domain yet: its candidate list is literally `[None]`, so
    # "not a candidate" would mean "any answer at all", and falling back would make tier 4
    # unable to answer anything. Plan 2 Task 11 gives a `Param` its legal values, and this
    # site becomes symmetric with the other two on the day it does. A33.
    # A54 said the decision must carry the evidence behind a `source: HUMAN`, and that is
    # still right. A56 is that the evidence was taken *from the claim*: `human_override` was
    # written as `resolution.value` whenever the resolver said `HUMAN`, so a resolver both
    # cleared its own tier-4 review and produced the proof `MD0220` checks against.
    #
    # `HUMAN` is unlike `confidence` and `reason`, which are claims a resolver is entitled to
    # make about its own work. This one asserts that *somebody else* — a person — answered,
    # and it is what moves the value out of `needs_review()`. So it is honoured only where a
    # record the caller supplied says a person really did answer this question, with this
    # value. `ReplayResolver` replaying a real override satisfies that; a model asserting it
    # does not. Invariant 6 is what would otherwise break, and Plan 2 wires a model here.
    #
    # A false claim is **demoted, not refused**. The property invariant 6 asks for is that
    # tier 4 stays flagged, and demoting restores exactly that. Raising would let a broken or
    # hostile adapter halt a laboratory's build instead — a denial of service in exchange for
    # a guarantee demotion already gives.
    # A person's *tool* (a pin in `goal.constraints.producers`) never reaches here: the router
    # honours it before the resolver is asked, and the goal itself is its evidence.
    override = context.backed.get(ambiguity.key())
    honoured = resolution.how is ValueSource.HUMAN and override == resolution.value
    decision = ParamDecision(
        key=ambiguity.key(),
        subject=param.name,
        candidates=ambiguity.candidates,
        chosen=resolution.value,
        reason=resolution.why,
        confidence=resolution.confidence,
        resolved_by=resolution.by,
        human_override=resolution.value if honoured else None,
    )
    # **Tier 4 stays tier 4 when a human answers it.** Collapsing an override to tier 1
    # would read as "no choice existed", which is what a *goal pin* means and is exactly
    # what this did not happen. Resolution met a real ambiguity and could not settle it;
    # somebody settled it afterwards, and a reviewer reading a curated pipeline needs to
    # see that it contains a question rather than that it contains none.
    #
    # What clears is the review, not the tier: `needs_review()` skips a value whose source
    # is HUMAN and `overrides()` lists it instead. Invariant 6 says tier 4 is always
    # *flagged*; it does not say the flag can never be answered.
    return ResolvedValue(
        value=resolution.value,
        tier=Tier.AMBIGUOUS,
        # Not `resolution.how`: see the note above. An unbacked `HUMAN` becomes `RESOLVER`,
        # which is what keeps the value in `needs_review()`.
        source=ValueSource.HUMAN if honoured else ValueSource.RESOLVER,
        reason=resolution.why,
    ), decision


def _declared_types(goal: Goal, vocabulary: Vocabulary) -> None:
    """Every type a goal names must be one some layer declared.

    Closing A29 is a side effect of doing the obvious thing — a closed vocabulary rather
    than another blocklist. An undeclared type in a goal was already a user error worth a
    clear message; nothing had ever asked.
    """
    named = (
        [held.type_id for held in goal.have]
        + list(goal.want)
        + [required.type_id for required in goal.constraints.required_states]
        + [pin.site.type_id for pin in goal.constraints.producers]
    )
    for type_id in named:
        if type_id not in vocabulary.types:
            raise UnknownTypeError(
                f"{type_id!r} is not a declared type.\n"
                f"  Declared: {', '.join(sorted(vocabulary.types)) or '(none)'}\n"
                f"  A goal names types, not files: declare one in "
                f"<layer>/vocabularies/<type_id>.yml, or correct the goal."
            )
    for required in goal.constraints.required_states:
        # States too: `required_states` was where a sentence of clinical notes reached a
        # bundle as a *key*, and a state that no type declares is a goal asking for
        # something no contract can satisfy.
        vocabulary.validate(required.type_id, required.states)
    for pin in goal.constraints.producers:
        # A person's pin names a site; held to the vocabulary like every type a goal names.
        vocabulary.validate(pin.site.type_id, pin.site.states)


def inert_intents(
    ir: PipelineIR, constraints: Constraints, registry: Registry
) -> list[RoleAbsence | ProducerExclusion | SourcePin]:
    """A person's structural intents (A1) that applied nowhere in `ir`, as `inert_pins` says of
    pins: an exclusion whose site is asked nowhere or whose tool is no candidate there, a role
    no tool in the registry fills, a source pin whose consumer is not in the plan or has no such
    port. In that order, each in its declared order. `ir` must be fresh from `resolve()`.
    """
    asked = {node.site for node in ir.nodes if node.site is not None}
    exclusions = [
        e for e in constraints.exclusions
        if e.site not in asked
        or e.contract not in {c.id for c in registry.producers_of(e.site.type_id, e.site.states)}
    ]
    filled = {role for contract in registry.contracts.values() for role in contract.roles}
    roles = [a for a in constraints.absent_roles if a.role not in filled]
    placed = {node.contract_id for node in ir.nodes}
    sources = [
        p for p in constraints.sources
        if p.consumer not in placed
        or p.port not in {port.name for port in registry.contracts[p.consumer].consumes}
    ]
    return [*exclusions, *roles, *sources]


def inert_pins(ir: PipelineIR, pins: Sequence[ProducerPin]) -> list[ProducerPin]:
    """The person's pins that applied nowhere in `ir` — its tool fills no step at the pin's site.

    A pin is inert when its tool is not a candidate there (the registry dropped it) or its site
    is asked nowhere (a typed state). The router passes over such a pin, so a caller must say
    so: a person's choice that quietly did nothing is the silent guess this product exists to
    remove (§14.3 of the consultant build; final review of 3c run 1). `ir` must be fresh from
    `resolve()`: a node's `site` is carried in memory, not in a dump.
    """
    placed = {(node.site, node.contract_id) for node in ir.nodes if node.site is not None}
    return [pin for pin in pins if (pin.site, pin.contract) not in placed]
