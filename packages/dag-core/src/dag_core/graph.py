"""Domain-neutral input shapes for graph layout.

Adapters provide node identifiers, ordered ports, display tiers, and edges. The layout module
uses only these values and does not depend on pipeline or execution models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    id: str
    inputs: tuple[str, ...] = ()
    """Input port names in display order, as selected by the adapter."""
    outputs: tuple[str, ...] = ()
    tier: int = 0
    """Renderer metadata passed through unchanged on the placed node."""


@dataclass(frozen=True)
class Edge:
    from_node: str
    from_port: str
    to_node: str
    to_port: str
    type_id: str = ""
    """Optional edge label passed through unchanged on the routed wire."""


@dataclass(frozen=True)
class Graph:
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
