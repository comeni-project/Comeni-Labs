"""Project a blueprint into the reviewed draft and its provenance sidecar.

The projection is recomputed from applicable reviews rather than appended, so steps and wires
removed by a later blueprint cannot remain as stale draft state.
"""

from comeni_core.goal.profile import DataProfile
from comeni_core.plan.draft import DraftGraph, DraftProvenance

from mendel_authoring.blueprint import Blueprint, committed
from mendel_authoring.reviews import Reviewed, fingerprint


def kept(blueprint: Blueprint, reviewed: list[Reviewed]) -> list[Reviewed]:
    """A reviewed step the blueprint no longer has leaves the set."""
    return [r for r in reviewed if r.node in blueprint.order
            and r.fingerprint == fingerprint(blueprint, r.node)]


def next_step(blueprint: Blueprint, reviewed: list[Reviewed]) -> str | None:
    """The first step in the blueprint's order not yet reviewed; `None` when the walk is done.
    After a swap, a step it added before the walk's place — HISAT2's index — comes next."""
    seen = {r.node for r in reviewed}
    return next((node for node in blueprint.order if node not in seen), None)


def drafted(
    blueprint: Blueprint, reviewed: list[Reviewed], profile: DataProfile
) -> tuple[DraftGraph, DraftProvenance]:
    by = {r.node: r for r in kept(blueprint, reviewed)}
    graph, provenance = DraftGraph(profile=profile), DraftProvenance()
    for node in (n for n in blueprint.order if n in by):
        graph, provenance = committed(blueprint, graph, provenance, node, by=by[node].by,
                                      actor_kind=by[node].actor_kind)
    return graph, provenance
