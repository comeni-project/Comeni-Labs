"""The four-tier ladder. Every value exits at exactly one tier and carries it."""

from collections.abc import Sequence

from comeni_core.contract import InputPort
from comeni_core.decision import Ambiguity, DecisionRecord
from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.tiers import ValueSource
from comeni_core.vocabulary import UnknownTypeError, Vocabulary

from mendel_resolver.goal import Goal
from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver
from mendel_resolver.router import route
from mendel_resolver.rules import RuleTable


def resolve(
    goal: Goal,
    registry: Registry,
    rules: RuleTable,
    measurements: MeasurementRegistry,
    *,
    vocabulary: Vocabulary,
    resolver: AmbiguityResolver | None = None,
    layer_names: Sequence[str] = (),
) -> PipelineIR:
    # A29. `Annotated[str, "type-id"]` says somebody named this; it does not say the name
    # is of a declared type. `router._have_satisfies` only *compares*, so a `have` entry
    # that satisfies nothing was never looked up and never rejected — and a patient name
    # and a filesystem path reached a `PublishBundle` as `type_id`, with a sentence of
    # clinical notes as a `required_states` key.
    #
    # Keyword and **required**, like `measurements` and for the same reason A2 gives: an
    # optional guard is the guard the next verb forgets. `mendel upgrade` is the verb that
    # matters here, because its goal comes from a stranger's bundle rather than from a file
    # the operator wrote.
    _declared_types(goal, vocabulary)
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
    plan = route(goal, registry, rules, resolver)
    ir = PipelineIR(
        profile=goal.profile,
        registry_layers=list(layer_names),
        # Read off the loaded data rather than passed in: a displacement is a fact each
        # loader discovered, and asking the caller to forward it is asking them to forget.
        # A published pipeline whose overlay quietly rerouted it is unauditable.
        #
        # The vocabulary's own displacements join this list in Part E, when `resolve()`
        # takes a vocabulary. Until then A24 is reported by `mendel build` and not by the
        # artifact, which is recorded here rather than left to be rediscovered.
        displaced=[*measurements.displaced, *registry.displaced],
    )
    # Every output emitted so far, in order. Keyed on type_id alone this was a dict, so the
    # last producer of a type won and SAMTOOLS_INDEX's `.bai` was handed to featureCounts —
    # valid Nextflow, no flag, and `-stub-run` cannot catch it because nf-core stubs never
    # read their inputs. A consumer must be fed a source that satisfies its required states.
    produced: list[tuple[str, str, str, frozenset[str]]] = []

    for step in plan.steps:
        contract = registry.get(step.contract_id)
        node = IRNode(
            id=step.node_id,
            contract_id=contract.id,
            selection=ResolvedValue(
                value=contract.id,
                tier=step.selection_tier,
                reason=step.selection_reason,
                from_layer=step.from_layer,
                displaced_layer=step.displaced_layer,
            ),
        )

        for param in contract.params:
            node.set_param(param.name, _resolve_param(
                node_id=node.id,
                param_name=param.name,
                tier_hint=param.tier_hint,
                default=param.default,
                goal=goal,
                rules=rules,
                resolver=resolver,
                decisions=ir.decisions,
            ))

        for port in contract.consumes:
            source = _source_for(produced, port, node.id, ir.decisions, resolver)
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
            produced.append((node.id, port.name, port.type_id, port.state))

        ir.nodes.append(node)

    # Already resolved and recorded, by `route()`, where the answer could still change the
    # selection. This loop used to call `resolver.resolve()` itself — after `ir.nodes` and
    # `ir.edges` were built — so the answer went into a record and nowhere else, and asking
    # a second time is a second chance to disagree with the pipeline that exists. With a
    # model behind the port it is also a second charge. Audit 2026-08-06, A8.
    ir.decisions.extend(plan.decisions)

    return ir


def _source_for(
    produced: list[tuple[str, str, str, frozenset[str]]],
    port: InputPort,
    node_id: str,
    decisions: list[DecisionRecord],
    resolver: AmbiguityResolver,
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

    best = min(surplus(source) for source in qualifying)
    equally_good = [source for source in qualifying if surplus(source) == best]
    if port.prefer and len(equally_good) > 1:
        preferred = [source for source in equally_good if port.prefer <= source[3]]
        equally_good = preferred or equally_good
    chosen = equally_good[-1]
    if len(equally_good) > 1:
        ambiguity = Ambiguity(
            node_id=node_id,
            subject=f"source:{port.name}",
            candidates=sorted(f"{n}.{p}" for n, p, _, _ in equally_good),
            context={"type_id": chosen[2], "required": sorted(required)},
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
            (s for s in equally_good if f"{s[0]}.{s[1]}" == resolution.chosen),
            equally_good[-1],
        )
        decisions.append(
            DecisionRecord(
                key=ambiguity.key(),
                subject=ambiguity.subject,
                candidates=ambiguity.candidates,
                # What was wired, not what was asked for.
                chosen=f"{chosen[0]}.{chosen[1]}",
                reason=resolution.reason,
                confidence=resolution.confidence,
                resolved_by=resolution.resolved_by,
            )
        )
    return chosen


def _resolve_param(
    *,
    node_id: str,
    param_name: str,
    tier_hint: int | None,
    default: object,
    goal: Goal,
    rules: RuleTable,
    resolver: AmbiguityResolver,
    decisions: list[DecisionRecord],
) -> ResolvedValue:
    # Tier 1 — the goal states it outright. No choice exists.
    override = next((o for o in goal.constraints.params if o.name == param_name), None)
    if override is not None:
        return ResolvedValue(
            value=override.value,
            tier=Tier.STRUCTURAL,
            source=ValueSource.GOAL,
            reason=f"specified in the goal as {param_name}",
        )

    # Tier 3 — a declared rule matches the measured profile.
    pin = rules.value_for(param_name, goal.profile)
    if pin is not None:
        return ResolvedValue(
            value=pin.value,
            tier=Tier.DATA_PROFILED,
            reason=f"rule {pin.decision.decides.key()}: {pin.because()}",
            # Provenance arrives *with* the value rather than beside it. It was two
            # lookups on the table a caller had to remember to make, which is how the
            # other consumer of the same table forgot both. Audit A15, A22.
            from_layer=pin.from_layer,
            displaced_layer=pin.displaced_layer,
        )

    # Tier 2 — a documented default exists for this context.
    if default is not None:
        return ResolvedValue(
            value=default,
            tier=Tier.CONVENTION,
            reason=f"contract default for {param_name}",
        )

    # Tier 4 — nothing decided it. Ask the port, record it, flag it.
    ambiguity = Ambiguity(
        node_id=node_id,
        subject=param_name,
        # Tier 2 already returned when a default existed, so there is exactly one
        # candidate and it is None. Real alternatives arrive with the rule-tables
        # spec, which gives a parameter a declared domain to draw them from.
        candidates=[None],
        context={"tier_hint": tier_hint},
    )
    resolution = resolver.resolve(ambiguity)
    decisions.append(
        DecisionRecord(
            key=ambiguity.key(),
            subject=param_name,
            candidates=ambiguity.candidates,
            chosen=resolution.chosen,
            reason=resolution.reason,
            confidence=resolution.confidence,
            resolved_by=resolution.resolved_by,
        )
    )
    return ResolvedValue(value=resolution.chosen, tier=Tier.AMBIGUOUS, reason=resolution.reason)


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
