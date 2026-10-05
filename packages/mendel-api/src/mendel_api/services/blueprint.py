"""The whole pipeline, resolved once, and revealed a step at a time. §1.4.

**Resolve the whole blueprint, reveal it incrementally.** Each *next step* is chosen with
downstream compatibility already known, so a session never makes a locally plausible choice that
dead-ends three steps later — and the browser knows where every node will finally sit before any
of them appears. Build still presents one step at a time; keeping the blueprint private in the
session is not the same as spawning it into the draft.

**Nothing here asks a model to enumerate modules.** The resolver already did. A model is reached
only through `ModelResolver`, only in Spawn, and only for a question the resolver itself declared
tier 4 — so tiers 1 to 3 cost no call at all, which is the checkpoint this file is held to.

**Alternatives are the resolver's, never a model's.** A step backed by a `ProducerDecision`
offers that decision's own candidates; any other step offers what the candidate service ranks for
the port it feeds, in the router's order. Neither list is authored — both are read off declared
data, and a plausible-sounding alternative nobody declared cannot appear.

**This module holds no rows.** It turns a goal into a `Blueprint` and a `Blueprint` into
proposals. The blueprint type itself, and `committed` (an accepted step into the draft), live in
the pure `mendel_authoring.blueprint` since 14.7.8.2 and are re-exported here. The building stage
(`stages/building.py`) is what reads and writes them inside one transaction.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

from comeni_ai import Client
from comeni_core.artifact.digest import digest_of_directory
from comeni_core.artifact.pipeline import Step
from comeni_core.plan.decision import ProducerDecision
from mendel_authoring.blueprint import (  # re-exported: the shell's callers keep `bp.<name>`
    PRESENCE_AXIS,
    SELECTION_AXIS,
    Blueprint,
    committed,
    edges_touching,
)
from mendel_compiler import layout, orchestrate
from mendel_resolver.goal import Goal
from mendel_resolver.ports import FlagOnlyResolver

from mendel_api.authoring.resolver import Call, ModelResolver
from mendel_api.authoring.types import Mode, Option, StepProposal
from mendel_api.settings import settings

__all__ = [
    "KEEP",
    "PRESENCE_AXIS",
    "SELECTION_AXIS",
    "Blueprint",
    "alternatives",
    "committed",
    "proposal",
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


def resolve(
    goal: Goal,
    *,
    mode: Mode,
    client: Client | None = None,
    roots: Sequence[Path] | None = None,
) -> tuple[Blueprint, list[Call]]:
    """Resolve `goal` once, under `mode`'s policy, and fix the reveal order.

    **Build resolves tier 4 with the flag and Spawn with the model** — §1.2, and the only place
    the two modes differ in this file. Spawn with no configured model resolves exactly as Build
    does: the questions stay open, visibly, rather than the session failing or anything being
    guessed. The returned calls are what the caller writes to `ai_invocation`; this function
    writes nothing.
    """
    stack = list(roots or [settings.registry_root])
    adapter = ModelResolver(client) if mode is Mode.SPAWN and client is not None else None
    built = orchestrate.build(
        goal,
        registry_roots=stack,
        resolver=adapter if adapter is not None else FlagOnlyResolver(),
    )
    placed = layout.of(built.ir)
    order = [node.id for node in sorted(placed.nodes, key=lambda n: (n.rank, n.order, n.id))]
    blueprint = Blueprint(
        registry=registry_digest(stack),
        order=order,
        placed={node.id: (node.x, node.y) for node in placed.nodes},
        pipeline=built.pipeline,
    )
    return blueprint, list(adapter.calls) if adapter is not None else []


# ── proposals ─────────────────────────────────────────────────────────────────────────────


def alternatives(blueprint: Blueprint, node_id: str, *, registry) -> list[str]:
    """Other contracts that could fill this step, in the resolver's own order.

    **A decision's candidates first**, because that is the resolver saying in its own record what
    it chose between. Only a step with no decision falls through to the candidate service, asked
    about the port this step actually feeds — `producing(type, states)` for what the consumer
    requires, which is the same ranking `router.py` applies, so the first row is the one the
    resolver would have taken.
    """
    step = blueprint.step(node_id)
    chosen = step.module.contract_id

    for record in blueprint.pipeline.decisions:
        if isinstance(record, ProducerDecision) and record.chosen == chosen:
            return [candidate for candidate in record.candidates if candidate != chosen]

    wanted = _fed(blueprint, step, registry=registry)
    if wanted is None:
        return []
    from mendel_api.services import candidates

    type_id, states, asking = wanted
    # **A contract cannot satisfy its own input** — `CLAUDE.md`'s routing gotcha, and the rule
    # `router.py` applies by excluding cycles. The candidate service matches on what a contract
    # *produces*, so it lists `samtools/sort` as a producer of `alignment.bam` and `multiqc` as a
    # producer of `qc.report`; each consumes the very type it would be standing in for, so
    # neither can replace the step that feeds it. Found twice: the first smoke run offered the
    # sorter as an alternative to STAR, and the first test run offered MultiQC to FastQC — which
    # is why this is a rule about types rather than an exclusion of whichever step was asking.
    excluded = {chosen, asking} if asking else {chosen}
    return [
        row.contract_id
        for row in candidates.producing(type_id, states).candidates
        if row.contract_id not in excluded
        and not _consumes(registry.get(row.contract_id), type_id)
    ]


def _consumes(contract, type_id: str) -> bool:
    """Whether any input of `contract` accepts `type_id`, under any of its alternatives."""
    for port in contract.consumes:
        if port.type_id == type_id:
            return True
        if any(accepted.type_id == type_id for accepted in port.alternatives()):
            return True
    return False


def _fed(
    blueprint: Blueprint, step: Step, *, registry
) -> tuple[str, frozenset[str], str | None] | None:
    """What the first consumer of `step` asks for, and which contract is asking.

    Falls back to what the goal wants of the step when nothing consumes it, with no asker.
    `None` when the step feeds nothing and produces nothing the goal names — a step with no
    question worth asking about its alternatives.
    """
    for consumer in blueprint.pipeline.steps:
        for wired in consumer.inputs:
            if wired.source and wired.source.split(".", 1)[0] == step.id:
                contract = registry.get(consumer.module.contract_id)
                port = next((p for p in contract.consumes if p.name == wired.port), None)
                if port is None:
                    continue
                accepted = port.alternatives()
                if accepted:
                    return accepted[0].type_id, frozenset(accepted[0].states), contract.id
                return port.type_id, frozenset(port.state_required), contract.id

    contract = registry.get(step.module.contract_id)
    goal = blueprint.pipeline.goal
    for output in contract.produces:
        if output.type_id in goal.want:
            return output.type_id, goal.constraints.states_for(output.type_id), None
    return None


def proposal(
    blueprint: Blueprint, node_id: str, *, registry, present: frozenset[str] = frozenset()
) -> dict:
    """The stored payload for offering `node_id`: the block a person reads, and the option map.

    `options` maps every id the engine minted to the contract it stands for, and it is what an
    acceptance is checked against — so the block the browser renders and the set the server
    enforces are written in the same breath and cannot disagree.

    `edges` are the wires accepting the blueprint's own step would add, given the steps already
    in the draft (`present`). **They let the browser apply an acceptance optimistically from what
    it already holds** — Task 8's rule — and they are exactly the wires `committed` would add,
    because both come from `_edges_touching` filtered the same way. An alternative's wires are
    not offered: they depend on its ports, and the server's answer is what draws them.
    """
    step = blueprint.step(node_id)
    chosen = step.module.contract_id
    others = alternatives(blueprint, node_id, registry=registry)
    minted = {f"alt_{index}": contract for index, contract in enumerate(others, start=1)}
    contract = registry.get(chosen)

    block = StepProposal(
        id=f"step-{node_id}",
        node=node_id,
        contract=chosen,
        consumes=sorted({port.type_id for port in contract.consumes if port.type_id}),
        produces=sorted({output.type_id for output in contract.produces}),
        reason=step.why.reason,
        tier=int(step.why.tier),
        alternatives=[
            Option(id=option_id, label=candidate) for option_id, candidate in minted.items()
        ],
    )
    here = set(present) | {node_id}
    wires = [
        edge.model_dump(mode="json")
        for edge in edges_touching(blueprint, node_id)
        if edge.from_node in here and edge.to_node in here
    ]
    return {
        "node": node_id,
        "block": block.model_dump(mode="json"),
        "options": {KEEP: chosen, **minted},
        "edges": wires,
    }
