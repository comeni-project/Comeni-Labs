"""A flow declared on comeni-flow: its construction checks, transitions and diagram."""

from enum import StrEnum

import pytest
from comeni_flow.diagram import to_mermaid
from comeni_flow.protocol import Actor, Edge, Node, Protocol, Stage
from pydantic import ValidationError


class Toy(StrEnum):
    ASKING = "asking"
    DONE = "done"


class Go(StrEnum):
    FINISH = "finish"


class Other(StrEnum):
    ELSEWHERE = "elsewhere"


def _flow(**overrides) -> Protocol:
    fields = dict(
        title="Toy", slug="toy", phases=Toy, events=Go, commands=frozenset({"finish"}),
        refusal_code="MD0005",
        stages=(Stage(id="s", title="S"),),
        nodes=(
            Node(id="ask", stage="s", actor=Actor.YOU, label="Ask", phase=Toy.ASKING,
                 built=True, waits=True),
            Node(id="end", stage="s", actor=Actor.ENGINE, label="End", phase=Toy.DONE,
                 built=True),
        ),
        edges=(Edge(source="ask", target="end", event=Go.FINISH, built=True, on="finish"),),
    )
    fields.update(overrides)
    return Protocol(**fields)


def test_a_flow_without_failed_or_retry_is_valid():
    flow = _flow()
    assert flow.failed is None and flow.retry is None


def test_a_waiting_node_left_by_a_non_command_is_refused():
    with pytest.raises(ValidationError, match="ask waits"):
        _flow(commands=frozenset())


def test_a_node_whose_phase_is_not_the_flows_type_is_refused():
    nodes = (Node(id="ask", stage="s", actor=Actor.YOU, label="Ask", phase=Other.ELSEWHERE,
                  built=True, waits=True),
             Node(id="end", stage="s", actor=Actor.ENGINE, label="End", phase=Toy.DONE,
                  built=True))
    with pytest.raises(ValidationError, match="not a Toy"):
        _flow(nodes=nodes)


def test_transitions_lists_each_event_edge():
    assert _flow().transitions() == {(Toy.ASKING, Go.FINISH): Toy.DONE}


def test_a_phase_keeps_its_own_type():
    assert _flow().transitions()[(Toy.ASKING, Go.FINISH)] is Toy.DONE


def test_to_mermaid_draws_each_node():
    drawn = to_mermaid(_flow())
    assert "ask" in drawn and "end" in drawn
