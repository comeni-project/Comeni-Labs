# dag-core

`dag-core` computes a deterministic visual layout for a directed graph. Mendel uses it for the
builder canvas, and Wiener uses it for run graphs. Each caller adapts its domain model into the
neutral `Graph`, `Node`, and `Edge` values exported by this package.

The package owns layout arithmetic only. It does not know about pipeline contracts, resolution,
execution state, HTTP, or persistence. Adapters choose node identifiers, port order, and display
tier before calling `dag_core.of()`.

## Layout contract

- Graphs are acyclic; callers validate that boundary.
- Ranks flow from left to right using the longest path from a root.
- Nodes in a rank are ordered deterministically with a median heuristic that considers producer
  positions and consumer port order.
- Every node uses the same dimensions, keeping the main path aligned and independent of port
  count; siblings are packed without overlap.
- Wires leave a node's right edge, enter the consumer's left edge, and use orthogonal segments.
- All coordinates are integers and identical inputs produce identical layouts.

The frontend duplicates a small set of geometry constants because it owns interactive node
placement. `tests/test_geometry_agrees.py` keeps those values synchronized with
`frontend/src/build/geometry.ts`.

## Public surface

`dag_core` exports the neutral graph types, placed-layout types, and `of()`:

```python
from dag_core import Edge, Graph, Node, of

graph = Graph(
    nodes=(
        Node(id="prepare", outputs=("reads",)),
        Node(id="align", inputs=("reads",)),
    ),
    edges=(Edge("prepare", "reads", "align", "reads"),),
)

layout = of(graph)
```

Port tuples are ordered for display. An adapter with contract information should supply declared
ports; an adapter with only artifact wiring may supply wired ports when the graph is fully wired.
Unknown edge-port names fall back to the node spine during layout because validation belongs to
the caller.

## Checks

Run the package guard and its direct behavioral consumers from the repository root:

```console
uv run pytest packages/dag-core/tests -q
uv run pytest packages/mendel-compiler/tests/test_layout.py packages/wiener-core/tests/test_graph.py -q
```
