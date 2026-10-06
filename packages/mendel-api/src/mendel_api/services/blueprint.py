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
    )
    return blueprint, []
