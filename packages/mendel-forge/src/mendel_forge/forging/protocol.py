"""Forging's flow, declared on `comeni-flow` like the builder's (spec §1–2).

The person reviews and decides; the AI drafts when the person asks it to; the engine assembles
the draft layer. A failed assembly goes back to review, re-opening the piece it blames (§2). There
is no retry machinery: going back to review is the retry.
"""

from enum import StrEnum

from comeni_flow.protocol import Actor, Edge, Node, Protocol, Shape, Stage


class Phase(StrEnum):
    ASKING = "asking"
    DRAFTING = "drafting"
    REVIEWING = "reviewing"
    ASSEMBLING = "assembling"
    ASSEMBLED = "assembled"


class Event(StrEnum):
    REVIEW = "review"
    DRAFT = "draft"
    ASSEMBLE = "assemble"
    DONE = "done"
    REOPEN = "reopen"


class Command(StrEnum):
    """What a person may send from a node that waits."""

    DRAFT = "draft"
    ASSEMBLE = "assemble"
    REOPEN = "reopen"


def _node(id: str, actor: Actor, label: str, phase: Phase, **kw) -> Node:
    return Node(id=id, stage="forge", actor=actor, label=label, phase=phase, built=True, **kw)


def _edge(source: str, target: str, on: str, event: Event, label: str = "") -> Edge:
    return Edge(source=source, target=target, on=on, event=event, built=True, label=label)


FORGING = Protocol(
    title="The forging protocol",
    slug="forging-protocol",
    phases=Phase,
    events=Event,
    commands=frozenset(c.value for c in Command),
    refusal_code="MF0506",
    stages=(Stage(id="forge", title="Forging a tool"),),
    nodes=(
        _node("ask", Actor.AI, "The AI asks what it cannot settle", Phase.ASKING, acts=True,
              shape=Shape.ROUND),
        _node("review", Actor.YOU, "You answer, write, approve, change or reject",
              Phase.REVIEWING, waits=True),
        _node("draft", Actor.AI, "The AI drafts the next piece", Phase.DRAFTING, acts=True),
        _node("assemble", Actor.ENGINE, "Write the draft layer; load and conformance",
              Phase.ASSEMBLING, acts=True, shape=Shape.GATE),
        _node("assembled", Actor.YOU, "Assembled: loads and conforms", Phase.ASSEMBLED,
              waits=True, shape=Shape.ROUND),
    ),
    edges=(
        _edge("ask", "review", "asked", Event.REVIEW),
        _edge("review", "draft", Command.DRAFT, Event.DRAFT, "draft with the AI"),
        _edge("draft", "review", "drafted", Event.REVIEW),
        _edge("review", "assemble", Command.ASSEMBLE, Event.ASSEMBLE, "all approved"),
        _edge("assemble", "assembled", "loaded", Event.DONE),
        _edge("assemble", "review", "failed", Event.REOPEN, "re-opens the blamed piece"),
        _edge("assembled", "review", Command.REOPEN, Event.REOPEN, "change something"),
    ),
)
