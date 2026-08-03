"""The four-tier ladder. Every value exits at exactly one tier and carries it."""

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
    produced: dict[str, tuple[str, str, frozenset[str]]] = {}

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
            source = produced.get(port.type_id)
            if source is not None:
                ir.edges.append(
                    IREdge(
                        from_node=source[0],
                        from_port=source[1],
                        to_node=node.id,
                        to_port=port.name,
                        type_id=port.type_id,
                        states=source[2],
                    )
                )

        for port in contract.produces:
            produced[port.type_id] = (node.id, port.name, port.state)

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
