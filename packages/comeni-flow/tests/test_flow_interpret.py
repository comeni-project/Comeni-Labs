"""The interpreter, run on a flow that is not the builder's."""

from dataclasses import dataclass
from enum import StrEnum

import pytest
from comeni_flow.forks import Subject
from comeni_flow.interpret import Refused, follow, run
from comeni_flow.protocol import Actor, Edge, Node, Protocol, Shape, Stage


class Ph(StrEnum):
    START = "start"
    LEFT = "left"
    RIGHT = "right"


class Ev(StrEnum):
    GO = "go"


@dataclass(frozen=True)
class Facts:
    side: str


class Side(Subject):
    def options(self) -> frozenset[str]:
        return frozenset({"left", "right"})

    def value(self, snapshot: Facts) -> str:
        return snapshot.side


def _flow(edges=None, nodes=None) -> Protocol:
    default_nodes = (
        Node(id="wait", stage="s", actor=Actor.YOU, label="Wait", phase=Ph.START, built=True,
             waits=True),
        Node(id="pick", stage="s", actor=Actor.ENGINE, label="Side", phase=Ph.START, built=True,
             shape=Shape.CHOICE, fork=Side(title="Side")),
        Node(id="l", stage="s", actor=Actor.YOU, label="L", phase=Ph.LEFT, built=True,
             waits=True),
        Node(id="r", stage="s", actor=Actor.YOU, label="R", phase=Ph.RIGHT, built=True,
             waits=True),
    )
    default_edges = (
        Edge(source="wait", target="pick", built=True, on="go"),
        Edge(source="pick", target="l", built=True, case="left", event=Ev.GO),
        Edge(source="pick", target="r", built=True, case="right"),
    )
    return Protocol(title="T", slug="t", phases=Ph, events=Ev, commands=frozenset({"go"}),
                    refusal_code="MD0005", stages=(Stage(id="s", title="S"),),
                    nodes=nodes or default_nodes, edges=edges or default_edges)


def test_run_rests_where_a_node_waits():
    assert run(_flow(), "wait", "go", lambda node: None, snapshot=Facts("right")).at == "r"


def test_a_fork_reads_the_callers_snapshot_type():
    ran = run(_flow(), "wait", "go", lambda node: None, snapshot=Facts("left"))
    assert ran.path == ["pick", "l"]


def test_a_refusal_carries_the_flows_own_code():
    with pytest.raises(Refused) as refused:
        follow(_flow(), "wait", "nonsense")
    assert str(refused.value).startswith("MD0005")


def test_a_cycle_is_refused():
    nodes = (
        Node(id="a", stage="s", actor=Actor.ENGINE, label="A", phase=Ph.START, built=True,
             acts=True),
        Node(id="b", stage="s", actor=Actor.ENGINE, label="B", phase=Ph.START, built=True,
             acts=True),
        Node(id="w", stage="s", actor=Actor.YOU, label="W", phase=Ph.START, built=True,
             waits=True),
    )
    edges = (
        Edge(source="w", target="a", built=True, on="go"),
        Edge(source="a", target="b", built=True, on="next"),
        Edge(source="b", target="a", built=True, on="next"),
    )
    with pytest.raises(Refused, match="MD0005"):
        run(_flow(edges=edges, nodes=nodes), "w", "go", lambda node: "next", limit=8)
