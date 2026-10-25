"""Store a resolved pipeline in reveal order and project accepted steps into a draft.

Committing a step preserves per-decision provenance and adds only wires whose two endpoints are
already present. The caller supplies the resolved pipeline; this module performs no I/O.
"""

from comeni_core.artifact.pipeline import Pipeline, Step
from comeni_core.goal.asked import Site
from comeni_core.plan.decision import ProducerDecision
from comeni_core.plan.draft import (
    DraftEdge,
    DraftGraph,
    DraftNode,
    DraftParam,
    DraftProvenance,
    NodeSettled,
    ParamSettled,
    Settled,
)
from comeni_core.plan.tiers import Tier, ValueSource
from pydantic import BaseModel, ConfigDict

from mendel_authoring.decisions import ActorKind

SELECTION_AXIS = "which contract fills this step"
ENGINE = "engine"
"""Who placed a step the walk did not stop at."""
PRESENCE_AXIS = "whether this step exists at all"


class Blueprint(BaseModel):
    """What the resolver produced for a goal, stored whole, with the order it is revealed in.

    `pipeline` is the complete artifact — every step, setting, decision and reason — rather than
    a projection of it, because a proposal needs the reasons and a later task needs the rest, and
    a second shape of "what the resolver said" is a second thing that can disagree with the first.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    registry: str
    """The layer stack's digest when this was resolved. Compared before any proposal applies."""
    order: list[str]
    """Step ids in reveal order: `(rank, order, id)` off the same layout the canvas draws."""
    placed: dict[str, tuple[int, int]] = {}
    """Where each step sits in the finished pipeline, from `dag-core` — §1.4's second reason.

    **Every node is drawn at its final position from the moment it appears**, so the graph does
    not re-lay itself out under the person each time a step is accepted. The canvas reads these
    rather than running a layout of its own: one implementation for both canvases, which is why
    `dag-core` exists. Empty for a blueprint stored before this field did."""
    pipeline: Pipeline
    sites: dict[str, Site] = {}
    """Where each step's tool was chosen (§14.3 of the consultant build): a step's alternatives
    are the router's candidates at its site, and a person's pin names it. Empty for a step the
    router did not choose (none today) and for a blueprint stored before this field."""

    def step(self, node_id: str) -> Step:
        found = next((step for step in self.pipeline.steps if step.id == node_id), None)
        if found is None:
            raise KeyError(node_id)
        return found

    def after(self, node_id: str | None) -> str | None:
        """The step revealed after `node_id`, or the first when `None`, or `None` at the end."""
        if node_id is None:
            return self.order[0] if self.order else None
        index = self.order.index(node_id) + 1
        return self.order[index] if index < len(self.order) else None


# ── committing an accepted step ───────────────────────────────────────────────────────────


def committed(
    blueprint: Blueprint,
    graph: DraftGraph,
    provenance: DraftProvenance,
    node_id: str,
    *,
    by: str,
    actor_kind: ActorKind = ActorKind.PERSON,
) -> tuple[DraftGraph, DraftProvenance]:
    """The draft and its sidecar once the blueprint's step `node_id` is reviewed by `by`.

    **Always the blueprint's own step**: a person's other tool arrives as a pin in the goal, so
    the blueprint already holds it (spec §14.3) — there is no alternative to graft on here.
    **Edges only between reviewed steps**, in either direction, so a step reviewed after its
    consumer still joins it.

    **Provenance is per decision** (§1.8):

    - a step settled at tiers 1 to 3 keeps the resolver's tier and reason;
    - a person's pinned tool keeps its own reason (*you chose … over …*), credited to the person;
    - a model's tier-4 choice keeps the model as its author;
    - a person accepting a tier-4 default is the author of that choice, and says so.
    """
    step = blueprint.step(node_id)
    contract_id = step.module.contract_id
    present = {node.id for node in graph.nodes} | {node_id}

    params = [
        DraftParam(name=setting.name, value=setting.value, why=setting.why.reason)
        for setting in step.settings
        if setting.why.source is ValueSource.MODEL
    ]
    nodes = [node for node in graph.nodes if node.id != node_id]
    nodes.append(DraftNode(id=node_id, contract_id=contract_id, params=params))

    edges = list(graph.edges)
    known = {(e.from_node, e.from_port, e.to_node, e.to_port) for e in edges}
    for candidate in edges_touching(blueprint, node_id):
        if candidate.from_node not in present or candidate.to_node not in present:
            continue
        spelled = (
            candidate.from_node, candidate.from_port, candidate.to_node, candidate.to_port
        )
        if spelled not in known:
            edges.append(candidate)
            known.add(spelled)

    stamped = [entry for entry in provenance.nodes if entry.node != node_id]
    stamped.append(
        NodeSettled(
            node=node_id,
            selection=_selection(blueprint, step, by=by, actor_kind=actor_kind),
            presence=_settled(step.presence) if step.presence is not None else None,
        )
    )
    keys = {f"{node_id}.{param.name}" for param in params}
    settled_params = [entry for entry in provenance.params if entry.key not in keys]
    for setting in step.settings:
        key = f"{node_id}.{setting.name}"
        if key in keys:
            settled_params.append(
                ParamSettled(key=key, settled=_settled(setting.why, by=_model_of(blueprint, key)))
            )

    return (
        graph.model_copy(update={"nodes": nodes, "edges": edges}),
        DraftProvenance(nodes=stamped, params=settled_params, channels=provenance.channels),
    )


def edges_touching(blueprint: Blueprint, node_id: str) -> list[DraftEdge]:
    """Every wire in the blueprint with `node_id` at either end."""
    found: list[DraftEdge] = []
    for consumer in blueprint.pipeline.steps:
        for wired in consumer.inputs:
            if not wired.source:
                continue
            producer, port = wired.source.split(".", 1)
            if node_id in (producer, consumer.id):
                found.append(
                    DraftEdge(
                        from_node=producer,
                        from_port=port,
                        to_node=consumer.id,
                        to_port=wired.port,
                    )
                )
    return found


def _selection(blueprint: Blueprint, step: Step, *, by: str, actor_kind: ActorKind) -> Settled:
    if step.why.source is ValueSource.HUMAN:
        # A person's pin in the goal (§14.3 of the consultant build): the blueprint's own step
        # already says who chose it and over what — keep that reason. Credit the reviewer only
        # when a person reviewed it: a pin already in the goal is placed quietly, by the engine,
        # and the engine never signs a person's choice.
        return _settled(step.why, by=by if actor_kind is ActorKind.PERSON else "")
    if step.why.source is ValueSource.MODEL:
        chooser = next(
            (
                record.model_override_by or record.resolved_by
                for record in blueprint.pipeline.decisions
                if isinstance(record, ProducerDecision)
                and record.chosen == step.module.contract_id
            ),
            "",
        )
        return _settled(step.why, by=chooser)
    if step.why.tier is Tier.AMBIGUOUS:
        return Settled(
            source=ValueSource.HUMAN,
            tier=Tier.AMBIGUOUS,
            reason="accepted by a person where no rule could decide",
            axis_reason=step.why.axis_reason or SELECTION_AXIS,
            by=by,
        )
    return _settled(step.why)


def _settled(why, *, by: str = "") -> Settled:
    """A `Why` from the blueprint, carried into the sidecar with its author intact."""
    return Settled(
        source=why.source,
        tier=why.tier,
        reason=why.reason,
        axis_reason=why.axis_reason,
        by=by,
    )


def _model_of(blueprint: Blueprint, key: str) -> str:
    """Which model settled a setting, read off its decision record rather than assumed.

    Matched on the full key — `<node>.<param>` — because a parameter decision is per step, and a
    suffix match would attribute one step's answer to another step's setting of the same name.
    """
    for record in blueprint.pipeline.decisions:
        if record.key == key:
            return record.model_override_by or record.resolved_by
    return ""
