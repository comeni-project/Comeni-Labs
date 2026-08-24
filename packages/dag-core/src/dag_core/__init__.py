"""Laying out a directed graph. **Pure** — invariant 1 covers this package.

A layout takes nodes with named ports and edges between them, and returns where to draw each.
**Nothing here knows what a pipeline is**, which is the whole reason the package exists: the
builder's canvas and Wiener's run graph are the same picture from two sources, and one
implementation is what stops them drifting apart.

`docs/design/wiener.md` §9.1.1 is the decision. Each half brings its own adapter — Mendel's
turns a `PipelineIR` into a `Graph`, Wiener's turns a `Pipeline` into one — and the arithmetic
below is shared and moved unchanged from `mendel_compiler.layout`, where it was written for
Plan 3C.
"""

from dag_core.graph import Edge, Graph, Node
from dag_core.layout import Layout, Placed, Point, Wire, of

__all__ = ["Edge", "Graph", "Layout", "Node", "Placed", "Point", "Wire", "of"]
