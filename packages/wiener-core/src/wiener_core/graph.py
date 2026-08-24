"""The pipeline's own graph, coloured by what the run did.

**Wiener has a `Pipeline`, not a `PipelineIR`** — `docs/design/wiener.md` §9.1.1 — and may not
reach for the resolver that turns one into the other (§3.3). So this is Wiener's adapter onto
`dag-core`, the other half of the same split `mendel_compiler.layout` sits on.

§9.1: **nothing new is computed.** The layout is the pipeline's, the colouring is the fold's,
and a graph that cannot disagree with either is one a reader can trust.
"""

from dag_core import Edge, Graph, Node
from dag_core.layout import Layout
from pydantic import BaseModel, ConfigDict

from wiener_core.state import RunState


def graph_of(pipeline) -> Graph:
    """A `Pipeline`'s steps and their wiring, as a neutral graph.

    **Only steps are nodes.** A `Pipeline.channels` entry is an *entry* channel — a
    `params.input` the laboratory fills — so a step fed only by one is a root here, which is
    what it is on the canvas too.

    **Outputs are the wired ports**, because `pipeline.yml` records what a step *consumes* and
    not what its contract declares. That is the `_declared` fallback `dag-core` documents, and
    it is correct whenever the graph is fully wired — which an emitted pipeline is, by
    construction: it would not have emitted otherwise.
    """
    produced: dict[str, list[str]] = {step.id: [] for step in pipeline.steps}
    edges: list[Edge] = []

    for step in pipeline.steps:
        for wired in step.inputs:
            if not wired.source:
                continue
            from_node, _, from_port = wired.source.rpartition(".")
            if from_node not in produced:
                continue
            if from_port not in produced[from_node]:
                produced[from_node].append(from_port)
            edges.append(Edge(from_node=from_node, from_port=from_port,
                              to_node=step.id, to_port=wired.port,
                              type_id=from_port))

    return Graph(
        nodes=tuple(
            Node(
                id=step.id,
                inputs=tuple(wired.port for wired in step.inputs),
                outputs=tuple(produced[step.id]),
                tier=int(step.why.tier) if step.why else 0,
            )
            for step in pipeline.steps
        ),
        edges=tuple(edges),
    )


class NodeRun(BaseModel):
    """What a run did to one step of its pipeline. §9.1's table, and nothing more."""

    model_config = ConfigDict(frozen=True)

    id: str
    process: str
    done: int = 0
    failed: int = 0
    running: int = 0
    total: int = 0
    attempts: int = 1
    """The most any one task of this process needed. **A second ring means something
    retried** — §9.1 — and one ring is not an absence of information."""


class RunGraph(BaseModel):
    """A layout plus what happened on it. Both halves are derived; neither is stored."""

    model_config = ConfigDict(frozen=True)

    layout: Layout
    nodes: tuple[NodeRun, ...] = ()

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)


def coloured(pipeline, layout: Layout, state: RunState) -> RunGraph:
    """Join the fold onto the layout, by process name.

    **It computes no duration and no rate** — §9.2. A live edge means the consumer is running on
    what the producer wrote, which the event stream supports; anything implying MB/s would be a
    number nobody measured.
    """
    by_process: dict[str, list] = {}
    for task in state.tasks.values():
        by_process.setdefault(task.process, []).append(task)

    runs = []
    for step in pipeline.steps:
        tasks = by_process.get(step.process, [])
        runs.append(NodeRun(
            id=step.id,
            process=step.process,
            done=sum(1 for t in tasks if t.status in ("COMPLETED", "CACHED")),
            failed=sum(1 for t in tasks if t.status in ("FAILED", "ABORTED")),
            running=sum(1 for t in tasks if t.status in ("RUNNING", "SUBMITTED")),
            total=len(tasks),
            attempts=max((len(t.attempts) for t in tasks), default=1),
        ))
    return RunGraph(layout=layout, nodes=tuple(runs))
