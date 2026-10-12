"""Canvas frames from recorded artifacts, without resolving the goal or reading rows."""

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.draft import DraftGraph, DraftNode, DraftProvenance
from dag_core import Edge, Graph, Node
from dag_core.layout import of as layout_of
from mendel_authoring.blueprint import Blueprint, committed
from mendel_authoring.decisions import ActorKind

from mendel_api.authoring.canvas import CanvasFrame
from mendel_api.authoring.envelopes import OfferContext
from mendel_api.services import build


def _placed(graph, steps):
    neutral = Graph(
        nodes=tuple(Node(s.id, tuple(p.name for p in s.ports if p.side == "in"),
                         tuple(p.name for p in s.ports if p.side == "out"), s.tier) for s in steps),
        edges=tuple(Edge(e.from_node, e.from_port, e.to_node, e.to_port) for e in graph.edges),
    )
    return {n.id: {"x": n.x, "y": n.y} for n in layout_of(neutral).nodes}


def _blueprint_frame(blueprint, graph, context, proposal_id, current, placement, layers):
    pipeline = blueprint.pipeline
    ids = {n.id for n in graph.nodes}
    feeds = {channel.name: [] for channel in pipeline.channels}
    for step in pipeline.steps:
        if step.id not in ids:
            continue
        for item in step.inputs:
            if item.channel in feeds:
                feeds[item.channel].append(f"{step.id}.{item.port}")
    fed = {(e.to_node, e.to_port) for e in graph.edges}
    fed.update(tuple(port.split(".", 1)) for ports in feeds.values() for port in ports)
    steps = build.step_views(pipeline, layers, ids=[n.id for n in graph.nodes],
                             fed=fed, entered=set())
    states = {f"{s.id}.{p.name}": p.states for s in steps for p in s.ports if p.side == "in"}
    channels = [build.ChannelView(
        name=c.name, scope=c.scope.value, param=c.param, type_id=c.type_id,
        count=build._counted(pipeline) if c.scope.value == "sample" else None,
        states=states[feeds[c.name][0]], ports=feeds[c.name],
    ) for c in pipeline.channels if feeds[c.name]]
    if set(placement) != ids:
        placement = {**_placed(graph, steps), **placement}
    return CanvasFrame(context=context, proposal_id=proposal_id, current=current,
                       graph=graph, steps=steps, channels=channels, placement=placement)


def preview_frames(blueprint: Blueprint, context: OfferContext,
                   proposal_id: str, layers) -> CanvasFrame:
    graph = DraftGraph(profile=blueprint.pipeline.goal.profile)
    provenance = DraftProvenance()
    for node in blueprint.order:
        graph, provenance = committed(blueprint, graph, provenance, node,
                                      by="resolver", actor_kind=ActorKind.RESOLVER)
    placement = {node: {"x": pos[0], "y": pos[1]}
                 for node, pos in blueprint.placed.items() if node in blueprint.order}
    return _blueprint_frame(blueprint, graph, context, proposal_id, True, placement, layers)


def frame_of(*, blueprint, graph, provenance, pending, proposal_id, context,
             current, ownership, placement, layers) -> CanvasFrame | None:
    if ownership == "manual":
        if not graph.nodes:
            return None
        # A hand edit can remove a step and leave its wires behind; an edge to nothing is not drawn.
        kept = {n.id for n in graph.nodes}
        graph = graph.model_copy(update={"edges": [
            e for e in graph.edges if e.from_node in kept and e.to_node in kept]})
        ir = build.ir_of(graph, layers, provenance=provenance)
        pipeline = Pipeline.of(ir, layers.registry, layers.vocabulary, layers.measurements,
                               layers.paths, goal=build.goal_of(graph, layers))
        shown = build._view(ir, pipeline, layers)
        return CanvasFrame(context=context, proposal_id=None, current=current, graph=graph,
                           steps=shown.steps, channels=[c for c in shown.channels if c.ports],
                           placement={n.id: {"x": n.x, "y": n.y} for n in shown.layout.nodes})
    if blueprint is None:
        return None
    visible = {n.id: n for n in graph.nodes}
    if pending is not None:
        if pending.node in visible and visible[pending.node].contract_id != pending.block.contract:
            raise ValueError("the offered step disagrees with the visible contract")
        visible.setdefault(pending.node, DraftNode(id=pending.node,
                                                   contract_id=pending.block.contract))
    edges = {(e.from_node, e.from_port, e.to_node, e.to_port): e
             for e in [*graph.edges, *(pending.edges if pending else [])]
             if e.from_node in visible and e.to_node in visible}
    drawn = graph.model_copy(update={"nodes": list(visible.values()),
                                     "edges": list(edges.values())})
    return _blueprint_frame(blueprint, drawn, context, proposal_id, current,
                            {n: at for n, at in placement.items() if n in visible}, layers)
