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

from typing import NamedTuple

from comeni_core.artifact.materialise import _stem, _unique
from comeni_core.declared.contract import ModuleContract
from comeni_core.goal.asked import Goal, GoalInput
from comeni_core.plan.decision import ParamDecision, ProducerDecision
from comeni_core.plan.draft import DraftGraph
from comeni_core.plan.ir import IRChannel, IREdge, IRNode, PipelineIR, ResolvedValue
from comeni_core.plan.tiers import Tier, ValueSource

from mendel_resolver.layers import Layers
from mendel_resolver.ports import FlagOnlyResolver
from mendel_resolver.premises import build_premises
from mendel_resolver.resolve import _layer_of, _resolve_param

__all__ = ["channels_of", "goal_of", "ir_of"]


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

    want: list[str] = []
    for node in graph.nodes:
        for port in contracts[node.id].produces:
            if (node.id, port.name) not in wired_out and port.type_id not in want:
                want.append(port.type_id)

    # ═══ ONE INPUT PER CHANNEL, NOT PER TYPE — spec §3 ════════════════════════════════════
    #
    # This deduplicated by `type_id` in one line —
    #
    #     if all(i.type_id != alternative.type_id for i in have):
    #
    # — and that line was the whole of why the spine's three `annotation.gtf` consumers were a
    # single hole nobody could address. A goal can say *I have two annotations* now.
    have = [
        GoalInput(type_id=channel.type_id, name=channel.name)
        for channel in channels_of(graph, layers)
    ]

    # Sorted by `(type_id, name)`: a `Goal` reaches `pipeline.yml`, and byte-identical output is
    # a hard requirement (invariant 10). It sorted by `type_id` alone, which stopped being a
    # total order the moment two inputs could share one.
    return Goal(
        have=sorted(have, key=lambda i: (i.type_id, i.name)),
        want=sorted(want),
        profile=graph.profile,
    )


def _scope_choice(drawn, source: ValueSource) -> ResolvedValue:
    """Why a channel's scope is not its type's default.

    **Tier 4, and invariant 6 is why.** Whether two GTF ports are fed by one file or by two is
    not derivable from the drawing — both are legal pipelines and they analyse different
    experiments — so a person decided, and a person's decision is flagged however confident they
    were. Same tier `_param_why` stamps for a value somebody typed, and for the same reason.

    **The reason is theirs, empty included.** Boilerplate here would replace what somebody wrote
    with what the resolver would have said, which is A77 exactly: `upgrade` overwrote a
    reviewer's own words with *"selected the first of 1 candidates without judgement"*.
    """
    return ResolvedValue(
        value=drawn.scope,
        tier=Tier.AMBIGUOUS,
        source=source,
        reason=drawn.why or "no reason was given for this channel's scope",
        axis_reason=(
            "how many times this channel delivers is a judgement about the experiment: one "
            "reference for the whole run, or one per sample"
        ),
    )


class DrawnChannel(NamedTuple):
    """One channel a drawing implies: its name, its type, and the sockets it feeds."""

    name: str
    type_id: str
    ports: tuple[str, ...]
    scope: str | None = None
    """What the drawing said this channel's scope is, or `None` for the type's default."""
    why: str = ""
    """The person's reason for that override."""


def channels_of(graph: DraftGraph, layers: Layers) -> list[DrawnChannel]:
    """Every channel this drawing reads from outside, named.

    ═══ THE GROUPING IS THE PERSON'S; THE ORDER AND THE NAMES ARE THE SHAPE'S ═══════════════

    `DraftChannel` says which sockets share a channel — a decision only a person can make,
    because one GTF feeding two steps and two GTFs feeding one each are both legal pipelines
    that analyse different experiments. Everything unlisted keeps the default, **one channel per
    type**, which is what every drawing meant before this existed.

    ═══ ORDERED ON SHAPE, NEVER ON IDENTITY — spec §11.2 ════════════════════════════════════

    `useGraph.nextId` mints `star_align_1`, `star_align_2` … from the ids currently *taken*, so
    adding two STAR nodes and deleting the first leaves `star_align_2` where drawing one fresh
    gives `star_align_1`. **Two structurally identical graphs, two different node ids** — and an
    order keyed on them would make a person's `params.*` depend on the order they clicked.

    So a channel sorts on `(depth of its shallowest consumer, that consumer's contract, the port
    name)`. Depth is computed from the edges here rather than taken from `dag_core.layout`:
    the arithmetic is six lines, and the alternative is a dependency from `mendel-resolver` onto
    a layout package for one integer.

    **Two isomorphic consumers tie**, and the tie is broken by type id and then by the sorted
    port keys — which does read a node id, and is the one place it can. Two graphs that differ
    only by which of two *interchangeable* nodes came first are isomorphic: whichever way the
    tie falls, the emitted workflow describes the same computation. That is a weaker claim than
    the rest of this function makes and it is written down rather than buried.
    """
    contracts = _contracts(graph, layers)
    wired_in = {(e.to_node, e.to_port) for e in graph.edges}
    depth = _depths(graph)

    # Every socket fed from outside, with the type it reads.
    sockets: list[tuple[str, str]] = []
    for node in graph.nodes:
        for port in contracts[node.id].consumes:
            if (node.id, port.name) in wired_in:
                continue
            for alternative in port.alternatives():
                if alternative.type_id in layers.vocabulary.entry_channels:
                    sockets.append((f"{node.id}.{port.name}", alternative.type_id))
                    break

    declared = {key: n for n, channel in enumerate(graph.channels) for key in channel.ports}
    # A drawn channel may also say what scope it is, which is a judgement about an experiment
    # rather than a fact about the type — see `DraftChannel.scope`.
    said = {n: channel for n, channel in enumerate(graph.channels)}
    groups: dict[tuple, list[str]] = {}
    types: dict[tuple, str] = {}
    for key, type_id in sockets:
        # A socket a person has grouped keys on that group; everything else keys on its type,
        # which is the one-channel-per-type default.
        group = ("drawn", declared[key]) if key in declared else ("type", type_id)
        groups.setdefault(group, []).append(key)
        types[group] = type_id

    def rank(group: tuple) -> tuple:
        ports = sorted(groups[group])
        shallowest = min(
            (depth[k.split(".", 1)[0]], contracts[k.split(".", 1)[0]].id, k.split(".", 1)[1])
            for k in ports
        )
        return (*shallowest, types[group], tuple(ports))

    taken: dict[str, None] = {}
    return [
        DrawnChannel(
            name=_unique(_stem(types[group]), taken),
            type_id=types[group],
            ports=tuple(sorted(groups[group])),
            scope=said[group[1]].scope if group[0] == "drawn" else None,
            why=said[group[1]].why if group[0] == "drawn" else "",
        )
        for group in sorted(groups, key=rank)
    ]


def _depths(graph: DraftGraph) -> dict[str, int]:
    """How far along the flow each node sits — longest path from a root.

    Six lines rather than a dependency on `dag_core.layout`, which computes the same integer as
    part of placing boxes on a screen. Cycles are `validate`'s to report (`MD0503`); this stops
    rather than looping, so a cyclic draft gets a bad order rather than a hang.
    """
    into: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        if edge.to_node in into:
            into[edge.to_node].append(edge.from_node)
    depth: dict[str, int] = {}

    def of(node: str, seen: frozenset[str]) -> int:
        if node in depth:
            return depth[node]
        if node in seen:
            return 0
        got = max((of(p, seen | {node}) + 1 for p in into.get(node, [])), default=0)
        depth[node] = got
        return got

    for node in graph.nodes:
        of(node.id, frozenset())
    return depth


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
        # **The wiring the drawing decided**, so materialisation does not have to re-derive it
        # and cannot derive it differently. Empty for a goal-driven build, which is one channel
        # per type and needs no map.
        channels=[
            IRChannel(
                name=c.name,
                type_id=c.type_id,
                ports=sorted(c.ports),
                scope=_scope_choice(c, source) if c.scope else None,
            )
            for c in channels_of(graph, layers)
        ],
        nodes=nodes,
        edges=edges,
        decisions=decisions,
        profile=graph.profile,
        registry_layers=[p.name for p in layers.paths],
    )
