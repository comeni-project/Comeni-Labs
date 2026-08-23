"""A drawn graph becomes a `PipelineIR` and a `Goal`. **Derived, never guessed.**

This is what spec §6 rests on. *"A builder edits a pipeline, and `pipeline.yml` is already the
save file"* is only true if a drawn graph can become one — and `Pipeline.of` requires a `Goal`,
keyword-only and required, which a drawn graph does not have.

**So the goal is derived from the graph.** What the graph reads from entry channels is what you
have; what its terminal nodes produce is what you want. Both facts are already in the contracts
and the vocabulary, so this is arithmetic over declared data with no model in it. The derived
goal is *narrower* than one a person would write — it says nothing about constraints or measured
data — and that is stated here rather than implied, because a reader of a kept draft will
otherwise wonder why its goal is so thin.

**Settings run the resolver's own ladder, and that is the point rather than a shortcut.**
`_resolve_param` is what `mendel build` calls, so a drawn node's settings come out at the same
tiers, with the same premises and the same reasons, as a resolved node's. That is spec §2's
*"the same knowledge from a different route"* applied to values — and it is what makes `compare`
mean anything: the two halves then differ only where you actually drew something different, not
because one route reads defaults and the other reads rules.

`MD0224` is what found this. A contract declares a positional slot a param fills, so a graph with
no settings emits a workflow with a hole in it and the compiler refuses the file that had just
been written.

**Every module choice exits at tier 4.** Nothing about a drawn graph was resolved, so
nothing may claim a lower tier: tier 1 means *no choice existed* and a person picking
`star/align` over
`hisat2/align` had a choice and made it. Invariant 6 — tier 4 is always flagged, even when the
person was certain. That is the honesty mechanism, and a builder is exactly where it would be
tempting to skip.
"""

from comeni_core.declared.contract import ModuleContract
from comeni_core.goal.asked import Goal, GoalInput
from comeni_core.plan.decision import ParamDecision, ProducerDecision
from comeni_core.plan.draft import DraftGraph
from comeni_core.plan.ir import IREdge, IRNode, PipelineIR, ResolvedValue
from comeni_core.plan.tiers import Tier, ValueSource

from mendel_resolver.layers import Layers
from mendel_resolver.ports import FlagOnlyResolver
from mendel_resolver.premises import build_premises
from mendel_resolver.resolve import _layer_of, _resolve_param

__all__ = ["goal_of", "ir_of"]


def _contracts(graph: DraftGraph, layers: Layers) -> dict[str, ModuleContract]:
    """Every node's contract. Raises rather than reports — `validate` is what reports, and
    materialising an invalid graph is a caller error rather than a user one."""
    return {n.id: layers.registry.get(n.contract_id) for n in graph.nodes}


def goal_of(graph: DraftGraph, layers: Layers) -> Goal:
    """What this drawing is for, read off the drawing.

    `want` is what nothing downstream consumes — a terminal output. `have` is every input the
    graph does not wire, whose type declares an `entry_channel`, because that is precisely what
    arrives from `params` rather than from a step.
    """
    contracts = _contracts(graph, layers)
    wired_out = {(e.from_node, e.from_port) for e in graph.edges}
    wired_in = {(e.to_node, e.to_port) for e in graph.edges}

    want: list[str] = []
    have: list[GoalInput] = []
    for node in graph.nodes:
        contract = contracts[node.id]
        for port in contract.produces:
            if (node.id, port.name) not in wired_out and port.type_id not in want:
                want.append(port.type_id)
        for port in contract.consumes:
            if (node.id, port.name) in wired_in:
                continue
            for alternative in port.alternatives():
                if alternative.type_id in layers.vocabulary.entry_channels:
                    if all(i.type_id != alternative.type_id for i in have):
                        have.append(GoalInput(type_id=alternative.type_id))
                    break

    # Sorted: a `Goal` reaches `pipeline.yml`, and byte-identical output is a hard requirement.
    return Goal(
        have=sorted(have, key=lambda i: i.type_id),
        want=sorted(want),
        profile=graph.profile,
    )


def ir_of(graph: DraftGraph, layers: Layers, *, by: str = "") -> PipelineIR:
    """The drawing as an IR, with every choice recorded as somebody's.

    `by` names a model when one drew this. Empty means a person did, and the two land in
    different fields — `model_override` versus `human_override` — because a pipeline an agent
    assembled must not be indistinguishable from one a person drew by hand.
    """
    contracts = _contracts(graph, layers)
    goal = goal_of(graph, layers)
    resolver = FlagOnlyResolver()
    # Built once and threaded, exactly as `resolve()` does it: a premise set is a function of
    # the goal and the derivations, so building it twice is two chances to build it differently.
    premises = build_premises(
        goal=goal, derivations=layers.rules.derivations, measurements=layers.measurements
    )
    drawn_by_model = bool(by)
    source = ValueSource.MODEL if drawn_by_model else ValueSource.HUMAN
    who = "drawn by a model" if drawn_by_model else "drawn by a person"

    decisions: list = []
    nodes = [
        IRNode(
            id=node.id,
            contract_id=node.contract_id,
            # **Empty, and filled below.** A `DraftParam` is not a `ParamBinding`: it carries
            # the answer and the reason, and the tier is this module's to stamp rather than the
            # client's to claim.
            params=[],
            selection=ResolvedValue(
                value=node.contract_id,
                tier=Tier.AMBIGUOUS,
                source=source,
                reason=f"{who} in the builder rather than resolved from a goal",
                axis_reason="which contract fills this step",
            ),
            presence=ResolvedValue(
                value=None,
                tier=Tier.AMBIGUOUS,
                source=source,
                reason=f"this step exists because it was {who}",
                axis_reason="whether this step exists at all",
            ),
        )
        for node in graph.nodes
    ]

    # Settings, through the same ladder `resolve()` uses. A param the person already set in the
    # builder wins — it is on the `DraftNode` — and everything else is decided here.
    for ir_node, drawn in zip(nodes, graph.nodes, strict=True):
        contract = contracts[drawn.id]
        typed = {p.name: p for p in drawn.params}
        for param in contract.params:
            answer = typed.get(param.name)
            if answer is not None:
                # **The server stamps the tier, not the client.** A browser claiming tier 1 on
                # a value somebody typed would put a lie in `pipeline.yml` that nothing
                # downstream could catch. Tier 4 because a person who typed a value had a
                # choice and made it, and invariant 6 says that is flagged even when they were
                # certain.
                ir_node.set_param(
                    param.name,
                    ResolvedValue(
                        value=answer.value,
                        tier=Tier.AMBIGUOUS,
                        source=source,
                        reason=answer.why or f"set in the builder, {who}, with no reason given",
                        axis_reason=param.because or f"{param.name} is a declared setting",
                    ),
                )
                override = (
                    {"model_override": answer.value, "model_override_by": by}
                    if drawn_by_model
                    else {"human_override": answer.value}
                )
                decisions.append(
                    ParamDecision(
                        # **`<node>.<param>` with no prefix.** `Pipeline`'s MD0220 check looks
                        # a param decision up by exactly this key to confirm that a value
                        # claiming `source: human` is backed by a person actually answering it.
                        # A prefixed key is a decision the artifact cannot find, and the value
                        # is then a review cleared by assertion — which is what MD0220 exists
                        # to refuse. It refused this, correctly, the first time it ran.
                        key=f"{drawn.id}.{param.name}",
                        subject=f"{drawn.id}.{param.name}",
                        reason=f"set in the builder, {who}",
                        resolved_by="builder",
                        tier=Tier.AMBIGUOUS,
                        chosen=answer.value,
                        override_reason=answer.why,
                        **override,
                    )
                )
                continue
            ir_node.set_param(
                param.name,
                _resolve_param(
                    node_id=ir_node.id,
                    param_name=param.name,
                    roles=contract.roles,
                    implementation=contract.id,
                    tier_hint=param.tier_hint,
                    default=param.default,
                    because=param.because,
                    from_layer=_layer_of(layers.registry, contract.id),
                    goal=goal,
                    rules=layers.rules,
                    premises=premises,
                    resolver=resolver,
                    backed={},
                    decisions=decisions,
                ),
            )

    edges = []
    for edge in graph.edges:
        port = next(
            p for p in contracts[edge.from_node].produces if p.name == edge.from_port
        )
        edges.append(
            IREdge(
                from_node=edge.from_node,
                from_port=edge.from_port,
                to_node=edge.to_node,
                to_port=edge.to_port,
                # Read off the PRODUCING port, which is the only honest source: a drawn edge
                # states four names and knows nothing about types.
                type_id=port.type_id,
                states=port.state,
            )
        )

    for node in graph.nodes:
        override = {"model_override": node.contract_id, "model_override_by": by} if drawn_by_model \
            else {"human_override": node.contract_id}
        decisions.append(
            ProducerDecision(
                key=f"producer:{node.id}",
                subject=node.id,
                reason=f"{who} in the builder",
                resolved_by="builder",
                tier=Tier.AMBIGUOUS,
                candidates=[node.contract_id],
                chosen=node.contract_id,
                **override,
            )
        )

    return PipelineIR(
        nodes=nodes,
        edges=edges,
        decisions=decisions,
        profile=graph.profile,
        registry_layers=[p.name for p in layers.paths],
    )
