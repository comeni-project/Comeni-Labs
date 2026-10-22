"""A canvas edit, read as a person's intent (A1, the one-builder design).

A hand edit is what a person *did*; what the engine keeps through every re-plan is what they
*meant*. This reads the second from the first, and says how it read it, so the reading is shown
and confirmed before it counts: *So you never want trimming here — right?* Pure: it compares two
drafts against the plan they were drawn from, and decides nothing until a person confirms.
"""

from collections.abc import Mapping
from typing import Literal

from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.registry import Registry
from comeni_core.goal.asked import ProducerExclusion, ProducerPin, RoleAbsence, Site, SourcePin
from comeni_core.plan.draft import DraftGraph
from comeni_core.spell.marks import TypeId
from pydantic import BaseModel, ConfigDict

ReadingKind = Literal["want", "unwant", "pin", "role_absent", "exclude", "source"]

_ORDER: dict[str, int] = {
    "unwant": 0, "role_absent": 1, "exclude": 2, "want": 3, "pin": 4, "source": 5,
}


class Reading(BaseModel):
    """One intent read from an edit: what it would write, and the sentence that asks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ReadingKind
    subject: str
    said: str
    intent: RoleAbsence | ProducerExclusion | SourcePin | ProducerPin | TypeId


def read_edit(
    before: DraftGraph, after: DraftGraph, sites: Mapping[str, Site], registry: Registry
) -> list[Reading]:
    """What `before` → `after` means. Layout-only edits mean nothing and return `[]`.

    `sites` is where the plan chose each step's tool (a `Blueprint`'s `sites`); a step the plan
    did not place is read at its output.

    - a step removed whose output nothing reads: that output is no longer wanted;
    - a step removed that fills a role and whose readers accept their input without it: the
      role is switched off;
    - any other step removed: its tool is excluded at its site;
    - a tool swapped on a step: a pin at that step's site;
    - a step added that feeds nothing: its output is wanted, made by its tool;
    - a wire to an existing step's input from another step: that input's source is pinned.
    """
    old = {n.id: n for n in before.nodes}
    new = {n.id: n for n in after.nodes}
    readings: list[Reading] = []

    for node_id in sorted(old.keys() - new.keys()):
        readings.append(_removed(node_id, old[node_id].contract_id, before, sites, registry))

    for node_id in sorted(old.keys() & new.keys()):
        if old[node_id].contract_id != new[node_id].contract_id:
            tool = new[node_id].contract_id
            # A step the plan did not place (a person added it) is pinned where its output is,
            # as it was when it was added; its swap must not read as nothing.
            site = sites.get(node_id) or _output_site(
                registry.contracts.get(old[node_id].contract_id))
            if site is None:
                continue  # an unknown tool: nothing to pin it by; validation names it
            readings.append(Reading(
                kind="pin", subject=node_id,
                said=f"So you want {_process(registry, tool)} for this step instead — right?",
                intent=ProducerPin(site=site, contract=tool)))

    for node_id in sorted(new.keys() - old.keys()):
        if any(e.from_node == node_id for e in after.edges):
            continue  # an insertion: read below, as the source of the input it feeds
        tool = new[node_id].contract_id
        contract = registry.contracts.get(tool)
        for made in contract.produces if contract is not None else ():
            readings.append(Reading(
                kind="want", subject=made.type_id,
                said=f"So you also want {made.type_id}, made by {_process(registry, tool)}"
                     " — right?",
                intent=made.type_id))
            readings.append(Reading(
                kind="pin", subject=node_id,
                said=f"…made by {_process(registry, tool)}.",
                intent=ProducerPin(site=Site(type_id=made.type_id, states=frozenset(made.state)),
                                   contract=tool)))

    wired = {(e.to_node, e.to_port): e.from_node for e in before.edges}
    for edge in sorted(after.edges, key=lambda e: (e.to_node, e.to_port, e.from_node)):
        if edge.to_node not in old or wired.get((edge.to_node, edge.to_port)) == edge.from_node:
            continue
        consumer, producer = new[edge.to_node].contract_id, new[edge.from_node].contract_id
        readings.append(Reading(
            kind="source", subject=f"{edge.to_node}.{edge.to_port}",
            said=f"So {_process(registry, consumer)}'s {edge.to_port} should read from "
                 f"{_process(registry, producer)} — right?",
            intent=SourcePin(consumer=consumer, port=edge.to_port, producer=producer)))

    return sorted(readings, key=lambda r: (_ORDER[r.kind], r.subject))


def read_graph(graph: DraftGraph, registry: Registry) -> list[Reading]:
    """A pipeline drawn by hand, read whole: every tool is the person's choice, pinned where its
    output is, and every output nothing reads is wanted. Unknown tools are skipped; validation
    names them."""
    readings: list[Reading] = []
    read_from = {e.from_node for e in graph.edges}
    for node in sorted(graph.nodes, key=lambda n: n.id):
        contract = registry.contracts.get(node.contract_id)
        site = _output_site(contract)
        if site is None:
            continue
        if node.id not in read_from:
            readings.append(Reading(kind="want", subject=site.type_id, said="",
                                    intent=site.type_id))
        readings.append(Reading(kind="pin", subject=node.id, said="",
                                intent=ProducerPin(site=site, contract=node.contract_id)))
    readings = sorted(readings, key=lambda r: (_ORDER[r.kind], r.subject))
    tools = ", ".join(_process(registry, r.intent.contract) for r in readings if r.kind == "pin")
    return [r.model_copy(update={"said": (
        f"So this is your pipeline, with these tools: {tools} — right?" if i == 0 else "…")})
        for i, r in enumerate(readings)]


def _removed(node_id, tool, before: DraftGraph, sites, registry: Registry) -> Reading:
    contract = registry.contracts.get(tool)
    readers = [e for e in before.edges if e.from_node == node_id]
    if contract is not None and not readers:
        wanted = contract.produces[0].type_id
        return Reading(kind="unwant", subject=wanted,
                       said=f"So you no longer want {wanted} — right?", intent=wanted)
    if contract is not None and contract.roles and _optional(contract, readers, before, registry):
        role = sorted(contract.roles)[0]
        return Reading(kind="role_absent", subject=role,
                       said=f"So you never want {role.replace('_', ' ')} here — right?",
                       intent=RoleAbsence(role=role))
    return Reading(
        kind="exclude", subject=node_id,
        said=f"So you don't want {_process(registry, tool)} at this step — I'll find another "
             "tool. Right?",
        intent=ProducerExclusion(site=sites.get(node_id) or _output_site(contract), contract=tool))


def _optional(contract: ModuleContract, readers, before: DraftGraph, registry: Registry) -> bool:
    """Whether every reader still accepts its input without this step: the step only *refines*
    (what it makes is a type it reads, as trimming makes reads from reads), and the states it
    adds are at most *conventional* for each reader (`state_required_conventional`)."""
    if not {m.type_id for m in contract.produces} <= {p.type_id for p in contract.consumes}:
        return False
    adds = {state for made in contract.produces for state in made.state} - {
        state for port in contract.consumes for state in port.state_required}
    tools = {n.id: n.contract_id for n in before.nodes}
    for edge in readers:
        reader = registry.contracts.get(tools.get(edge.to_node, ""))
        ports = reader.consumes if reader is not None else []
        port = next((p for p in ports if p.name == edge.to_port), None)
        if port is None or adds & set(port.state_required):
            return False
    return True


def _process(registry: Registry, tool: str) -> str:
    contract = registry.contracts.get(tool)
    return contract.nf_process if contract is not None else tool


def _output_site(contract: ModuleContract | None) -> Site | None:
    made = contract.produces[0] if contract is not None and contract.produces else None
    return Site(type_id=made.type_id, states=frozenset(made.state)) if made else None


