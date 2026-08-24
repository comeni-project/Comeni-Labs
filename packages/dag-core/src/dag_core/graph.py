"""The neutral shape a layout takes.

**Nothing here knows what a pipeline is.** A node has an id, a stripe and its ports in the
order they are drawn; an edge joins two ports. Mendel's adapter builds one from a `PipelineIR`
and Wiener's from a `Pipeline`, and the arithmetic next door never learns the difference.

`docs/design/wiener.md` §9.1.1.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    id: str
    inputs: tuple[str, ...] = ()
    """Port names, in the order the canvas draws them.

    **The adapter decides whether these are the DECLARED ports or the wired ones**, which is
    where that question belongs: the layout cannot know what a contract declares, and getting
    it wrong is what put a wire 39 pixels from its chevron in Plan 3C.
    """
    outputs: tuple[str, ...] = ()
    tier: int = 0
    """A stripe the renderer draws on the node. Mendel puts the resolution tier here; Wiener
    puts the tier the step's decision was settled at. The layout only passes it through."""


@dataclass(frozen=True)
class Edge:
    from_node: str
    from_port: str
    to_node: str
    to_port: str
    type_id: str = ""
    """What flows along it, as a label. The layout places it and never reads it."""


@dataclass(frozen=True)
class Graph:
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
