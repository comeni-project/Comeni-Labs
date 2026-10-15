"""The whole pipeline, resolved once, and revealed a step at a time. §1.4.

**Resolve the whole blueprint, reveal it incrementally.** Each *next step* is chosen with
downstream compatibility already known, so a session never makes a locally plausible choice that
dead-ends three steps later — and the browser knows where every node will finally sit before any
of them appears. Build still presents one step at a time; keeping the blueprint private in the
session is not the same as spawning it into the draft.

**Nothing here asks a model.** The resolver enumerated the modules, and tier 4 is resolved with
the flag: a person answers it in the walk (spec §13.1 of the consultant build). `ModelResolver`
stays in `authoring/resolver.py`, unwired, for a later Tier-4 answers fork.

**A choice's options are the resolver's, never a model's**: the producer decision's own
candidates, offered by the building stage (`stages/building.step_payload`, spec §13.6).

**This module holds no rows.** It turns a goal into a `Blueprint`. The blueprint type itself,
and `committed` (an accepted step into the draft), live in the pure `mendel_authoring.blueprint`
since 14.7.8.2 and are re-exported here. The building stage
(`stages/building.py`) is what reads and writes them inside one transaction.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

from comeni_core.artifact.digest import digest_of_directory
from mendel_authoring.blueprint import (  # re-exported: the shell's callers keep `bp.<name>`
    PRESENCE_AXIS,
    SELECTION_AXIS,
    Blueprint,
    committed,
)
from mendel_compiler import layout, orchestrate
from mendel_resolver.goal import Goal
from mendel_resolver.ports import FlagOnlyResolver

from mendel_api.settings import settings

__all__ = [
    "KEEP",
    "PRESENCE_AXIS",
    "SELECTION_AXIS",
    "Blueprint",
    "candidates",
    "committed",
    "registry_digest",
    "resolve",
]

KEEP = "keep"
"""The option id meaning *the step as the blueprint proposes it*.

Minted by the engine like every other option id, so accepting the default is posting an id
rather than posting nothing — a request with no option cannot be told apart from a request that
forgot one.
"""

def registry_digest(roots: Sequence[Path]) -> str:
    """One digest for a layer stack.

    A single layer is its own digest, so the common case stores the value every other part of
    the system already prints. A stack is a digest of its layers' digests in order — order
    matters, because the same two layers stacked the other way round are a different registry.
    """
    digests = [str(digest_of_directory(root)) for root in roots]
    if len(digests) == 1:
        return digests[0]
    return "sha256:" + hashlib.sha256("\n".join(digests).encode()).hexdigest()


def resolve(goal: Goal, *, roots: Sequence[Path] | None = None) -> tuple[Blueprint, list]:
    """Resolve `goal` once and fix the reveal order. **Tier 4 is resolved with the flag**: the
    questions stay open, visibly, for a person in the walk; nothing is guessed. The second value
    is the model calls made, always none now, kept so a later Tier-4 answers fork can return
    them for `ai_invocation`."""
    stack = list(roots or [settings.registry_root])
    built = orchestrate.build(goal, registry_roots=stack, resolver=FlagOnlyResolver())
    placed = layout.of(built.ir)
    order = [node.id for node in sorted(placed.nodes, key=lambda n: (n.rank, n.order, n.id))]
    blueprint = Blueprint(
        registry=registry_digest(stack),
        order=order,
        placed={node.id: (node.x, node.y) for node in placed.nodes},
        pipeline=built.pipeline,
        sites={node.id: node.site for node in built.ir.nodes if node.site is not None},
    )
    return blueprint, []


def candidates(blueprint: Blueprint, node_id: str) -> list[str]:
    """The router's own candidates at the site `node_id`'s tool was chosen at (§14.3 of the
    consultant build), in the registry's order. One that would cycle or fill an absent role
    shows up in `alternatives_of` as a refusal or as no change, never as a silent option."""
    from mendel_api.services import registry

    site = blueprint.sites.get(node_id)
    if site is None:
        return []
    # **A contract that consumes the type it would stand in for is not an alternative** — the
    # router's own rule (a contract cannot satisfy its own input), applied by type. MultiQC
    # produces `qc.report` and consumes it; offered as FastQC's alternative, the "swap" quietly
    # built FastQC *and* MultiQC. Found twice before (the sorter for STAR, MultiQC for FastQC).
    return [
        c.id
        for c in registry.stack().registry.producers_of(site.type_id, site.states)
        if not _consumes(c, site.type_id)
    ]


def _consumes(contract, type_id: str) -> bool:
    """Whether any input of `contract` accepts `type_id`, under any of its alternatives."""
    return any(
        port.type_id == type_id
        or any(accepted.type_id == type_id for accepted in port.alternatives())
        for port in contract.consumes
    )
