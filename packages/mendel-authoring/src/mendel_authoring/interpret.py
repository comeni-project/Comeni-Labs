"""Run the protocol (14.7.8.1): where a session rests, and the nodes it passes on the way.

**Pure.** `enter` is the shell's: it runs an acting node's handler and returns its outcome, or
`None` to rest. Everything else — which arrow, when to stop, what to refuse — is here, read off
the protocol, so the diagram is the program and not a picture of it.
"""

from collections.abc import Callable
from typing import NamedTuple

from comeni_core.diagnostics import coded

from mendel_authoring.forks import DEFAULT, Snapshot
from mendel_authoring.protocol import Edge, Node, Protocol
from mendel_authoring.types import Phase

NO_SNAPSHOT = Snapshot()
"""What a run reads when the shell passes nothing: every subject takes its declared default."""


class Refused(ValueError):
    """MI0216: no arrow from here is named by what arrived."""


class Ran(NamedTuple):
    at: str
    """Where the session rests."""
    path: list[str]
    """Every node entered, in order, ending at `at`."""


def follow(
    protocol: Protocol, at: str, on: str | None, *, returning_to: Phase | None = None
) -> Edge:
    """The built arrow out of `at` that `on` names; `None` names the one way straight on.

    Out of a node that enters a within-request section, the section's ways out are its own. Of
    several return arrows, the one back to `returning_to`, the phase that failed, is taken."""
    found = [e for e in protocol.edges if e.built and e.source == at and e.on == on]
    if not found:
        found = [e for e in protocol.exits(at) if e.on == on]
    if len(found) > 1 and returning_to is not None:
        phase = {n.id: n.phase for n in protocol.nodes}
        found = [e for e in found if not e.returns or phase[e.target] is returning_to]
    if not found:
        named = "the way straight on" if on is None else repr(on)
        raise Refused(coded("MI0216", f"from {at!r}, nothing leads on by {named}"))
    return found[0]


def run(
    protocol: Protocol,
    at: str,
    command: str | None,
    enter: Callable[[str], str | None],
    *,
    returning_to: Phase | None = None,
    limit: int = 64,
    snapshot: Snapshot = NO_SNAPSHOT,
) -> Ran:
    """Follow `command` out of `at`, then on through every node until the session rests.

    An acting node is entered, and its outcome names the arrow on; `None` rests there if it waits
    or has no single way on, and otherwise goes straight on. A node
    that neither acts nor waits, with one way on, is passed straight through. Anything else is
    where the session rests. More than `limit` nodes without resting is a cycle, refused.
    `command=None` resumes: `at` itself is entered. A fork is never entered: it takes the edge
    for the case `snapshot` is in (spec §12).
    """
    nodes: dict[str, Node] = {n.id: n for n in protocol.nodes}
    if command is None:
        # **Resuming** (14.7.8.1): the session is entered where it rests, as if just arrived.
        node = nodes[at]
    else:
        node = nodes[follow(protocol, at, command, returning_to=returning_to).target]
    path = [node.id]
    while len(path) <= limit:
        if node.fork is not None:
            node = nodes[_case(protocol, node, snapshot).target]
        elif node.acts:
            outcome = enter(node.id)
            if outcome is None:
                # **Work that names nothing**: a node that waits rests here (`resolve`); one that
                # does not, with one way on, goes on (`ask` queues a job and asks: plan 1c).
                if node.waits or not _one_way_on(protocol, node.id):
                    return Ran(node.id, path)
                node = nodes[follow(protocol, node.id, None).target]
            else:
                node = nodes[follow(protocol, node.id, outcome).target]
        elif not node.waits and _one_way_on(protocol, node.id):
            node = nodes[follow(protocol, node.id, None).target]
        else:
            return Ran(node.id, path)
        path.append(node.id)
    raise Refused(coded("MI0216", f"ran {limit} nodes from {at!r} without resting: a cycle"))


def _one_way_on(protocol: Protocol, at: str) -> bool:
    return (
        sum(
            1
            for e in protocol.edges
            if e.built and e.source == at and e.on is None and e.case is None
        )
        == 1
    )


def _case(protocol: Protocol, node: Node, snapshot: Snapshot) -> Edge:
    """The edge out of fork `node` for the case `snapshot` is in, or its `DEFAULT`."""
    value = node.fork.value(snapshot)
    out = {e.case: e for e in protocol.edges if e.built and e.source == node.id}
    found = out.get(value) or out.get(DEFAULT)
    if found is None:
        raise Refused(
            coded("MI0216", f"fork {node.id!r} has no edge for {value!r}, and no default")
        )
    return found
