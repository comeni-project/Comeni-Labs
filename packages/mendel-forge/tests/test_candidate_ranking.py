"""How often the right type is the first candidate offered.

**This file is a measurement, not an example.** The forge asks seven `type_id` questions per
module and the answer to each is one of twenty-two declared types; whether a person can answer
them is entirely a question of where the right one sits in the list. Alphabetical order — what
shipped until this test was written — put it first in **one hole out of thirty**.

The corpus is the registry itself: every port of every landed contract is a hole whose answer is
already known, which makes this the one part of the forge with free ground truth.
"""

from pathlib import Path

import pytest
from mendel_resolver.layers import Layers, load

from mendel_forge import candidates

ROOT = Path(__file__).resolve().parents[3]

TARGET = 0.80
"""Spec §4. Below this the question is not answerable by a person reading a list."""


@pytest.fixture(scope="module")
def stack() -> Layers:
    return load([ROOT / "registry"])


def _holes(stack: Layers) -> list[tuple[str, str, str, tuple[str, ...]]]:
    """Every port in the registry as `(tool, port_name, true_type, this contract's inputs)`."""
    out = []
    for contract in stack.registry.contracts.values():
        tool = contract.id.split("@")[0]
        inputs = tuple(port.type_id for port in contract.consumes)
        for port in contract.consumes:
            out.append((tool, port.name, port.type_id, ()))
        for port in contract.produces:
            out.append((tool, port.name, port.type_id, inputs))
    return out


def _top1(stack: Layers) -> tuple[int, int]:
    holes = _holes(stack)
    hit = 0
    for tool, port, truth, inputs in holes:
        offered = candidates.for_field(
            "produces[0].type_id",
            stack,
            excluding=tool,
            port=port,
            tool=tool,
            input_types=inputs,
        )
        if offered and offered[0].value == truth:
            hit += 1
    return hit, len(holes)


def test_the_right_type_is_the_first_candidate(stack: Layers) -> None:
    # **`excluding=tool` is what makes this honest.** Without it the contract being scored is in
    # the evidence its own ranking reads, which is the mistake `_played_by`'s docstring records:
    # every accuracy figure measured that way is meaningless.
    hit, total = _top1(stack)
    assert hit / total >= TARGET, f"top-1 is {hit}/{total} = {hit / total:.0%}, target {TARGET:.0%}"
