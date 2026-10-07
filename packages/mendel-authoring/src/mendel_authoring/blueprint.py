"""The pipeline the resolver produced for a goal, and placing an accepted step into the draft.

Pure: the shell resolves a goal into a `Blueprint` (`mendel_api.services.blueprint.resolve`) and
hands it here; nothing in this module reaches a row, a queue or a model. Moved from the shell in
14.7.8.2, without `mode`, which nothing read.
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

from mendel_authoring.ports import Contracts

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
    contract_id: str | None = None,
    registry: Contracts | None = None,
) -> tuple[DraftGraph, DraftProvenance]:
    """The draft and its sidecar once `node_id` is accepted as `contract_id`.

    **Edges only between accepted steps.** An edge is added when both of its ends are in the
    graph — in either direction, so a step accepted after its consumer still joins it — and an
    edge to a step the person rejected is never drawn. When an alternative was chosen, an edge
    is kept only where the alternative actually has the port, because a wire into a port that
    does not exist is not a pipeline anybody asked for.

    **Provenance is per decision** (§1.8), and three cases are distinguished:

    - the blueprint's own step, settled at tiers 1 to 3, keeps the resolver's tier and reason —
      acknowledging it changed nothing about who decided it;
    - a tier-4 step chosen by the model in Spawn keeps the model as its author;
    - a person accepting a tier-4 default, or choosing any alternative, is the author of that
      choice, and says so.
    """
    step = blueprint.step(node_id)
    contract_id = contract_id or step.module.contract_id
    own = contract_id == step.module.contract_id
    present = {node.id for node in graph.nodes} | {node_id}

    params = (
        [
            DraftParam(name=setting.name, value=setting.value, why=setting.why.reason)
            for setting in step.settings
            if setting.why.source is ValueSource.MODEL
        ]
        if own
        else []
    )
    nodes = [node for node in graph.nodes if node.id != node_id]
    nodes.append(DraftNode(id=node_id, contract_id=contract_id, params=params))

    edges = list(graph.edges)
    known = {(e.from_node, e.from_port, e.to_node, e.to_port) for e in edges}
    for candidate in edges_touching(blueprint, node_id):
        if candidate.from_node not in present or candidate.to_node not in present:
            continue
        if not own and not _has_port(registry, contract_id, candidate, node_id):
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
            selection=_selection(blueprint, step, own=own, by=by),
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


def _has_port(registry: Contracts, contract_id: str, edge: DraftEdge, node_id: str) -> bool:
    contract = registry.get(contract_id)
    if edge.to_node == node_id:
        return any(port.name == edge.to_port for port in contract.consumes)
    return any(port.name == edge.from_port for port in contract.produces)


def _selection(blueprint: Blueprint, step: Step, *, own: bool, by: str) -> Settled:
    if not own:
        return Settled(
            source=ValueSource.HUMAN,
            tier=Tier.AMBIGUOUS,
            reason="chosen by a person over the resolver's proposal",
            axis_reason=SELECTION_AXIS,
            by=by,
        )
    if step.why.source is ValueSource.HUMAN:
        # A person's pin in the goal (§14.3 of the consultant build): the blueprint's own step
        # already says who chose it and over what — keep that reason. Credit the reviewer only
        # when a person reviewed it: a pin already in the goal is placed quietly, by the engine,
        # and the engine never signs a person's choice.
        return _settled(step.why, by="" if by == ENGINE else by)
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
