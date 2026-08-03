"""The four-tier ladder. Every value exits at exactly one tier and carries it."""

from comeni_core.contract import InputPort
from comeni_core.decision import Ambiguity, DecisionRecord
from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.registry import Registry

from mendel_resolver.goal import Goal
from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver
from mendel_resolver.router import route
from mendel_resolver.rules import RuleTable


def resolve(
    goal: Goal,
    registry: Registry,
    rules: RuleTable,
    resolver: AmbiguityResolver | None = None,
) -> PipelineIR:
    resolver = resolver or FlagOnlyResolver()
    plan = route(goal, registry)
    ir = PipelineIR()
    # Every output emitted so far, in order. Keyed on type_id alone this was a dict, so the
    # last producer of a type won and SAMTOOLS_INDEX's `.bai` was handed to featureCounts —
    # valid Nextflow, no flag, and `-stub-run` cannot catch it because nf-core stubs never
    # read their inputs. A consumer must be fed a source that satisfies its required states.
    produced: list[tuple[str, str, str, frozenset[str]]] = []

    for step in plan.steps:
        contract = registry.get(step.contract_id)
        node = IRNode(id=step.node_id, contract_id=contract.id)

        for param in contract.params:
            node.params[param.name] = _resolve_param(
                node_id=node.id,
                param_name=param.name,
                tier_hint=param.tier_hint,
                default=param.default,
                goal=goal,
                rules=rules,
                resolver=resolver,
                decisions=ir.decisions,
            )

        for port in contract.consumes:
            source = _source_for(produced, port, node.id, ir.decisions, resolver)
            if source is not None:
                from_node, from_port, _, states = source
                ir.edges.append(
                    IREdge(
                        from_node=from_node,
                        from_port=from_port,
                        to_node=node.id,
                        to_port=port.name,
                        type_id=port.type_id,
                        states=states,
                    )
                )

        for port in contract.produces:
            produced.append((node.id, port.name, port.type_id, port.state))

        ir.nodes.append(node)

    for ambiguity in plan.ambiguities:
        resolution = resolver.resolve(ambiguity)
        ir.decisions.append(
            DecisionRecord(
                key=ambiguity.key(),
                subject=ambiguity.subject,
                candidates=ambiguity.candidates,
                chosen=resolution.chosen,
                reason=resolution.reason,
                confidence=resolution.confidence,
                resolved_by=resolution.resolved_by,
            )
        )

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
    """
    qualifying = [
        source
        for source in produced
        if source[2] == port.type_id and port.state_required <= source[3]
    ]
    if not qualifying:
        return None

    def surplus(source: tuple[str, str, str, frozenset[str]]) -> int:
        return len(source[3] - port.state_required)

    best = min(surplus(source) for source in qualifying)
    equally_good = [source for source in qualifying if surplus(source) == best]
    chosen = equally_good[-1]
    if len(equally_good) > 1:
        ambiguity = Ambiguity(
            node_id=node_id,
            subject=f"source:{port.name}",
            candidates=sorted(f"{n}.{p}" for n, p, _, _ in equally_good),
            context={"type_id": port.type_id, "required": sorted(port.state_required)},
        )
        resolution = resolver.resolve(ambiguity)
        decisions.append(
            DecisionRecord(
                key=ambiguity.key(),
                subject=ambiguity.subject,
                candidates=ambiguity.candidates,
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
    if param_name in goal.constraints:
        return ResolvedValue(
            value=goal.constraints[param_name],
            tier=Tier.STRUCTURAL,
            reason=f"specified in the goal as {param_name}",
        )

    # Tier 3 — a declared rule matches the measured profile.
    rule = rules.match(param_name, goal.profile)
    if rule is not None and "value" in rule.then:
        return ResolvedValue(
            value=rule.then["value"],
            tier=Tier.DATA_PROFILED,
            reason=f"rule {rule.id}: {rule.citation}",
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
        candidates=[default] if default is not None else [None],
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
