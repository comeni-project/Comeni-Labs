"""Canvas frames from recorded artifacts, without resolving the goal or reading rows."""

from comeni_core.plan.draft import DraftGraph, DraftProvenance
from mendel_authoring.blueprint import Blueprint, committed
from mendel_authoring.decisions import ActorKind

from mendel_api.authoring.canvas import CanvasFrame
from mendel_api.authoring.envelopes import OfferContext
from mendel_api.services import build


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
