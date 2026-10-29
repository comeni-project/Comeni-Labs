"""Declare and validate a flow: stages, nodes and arrows that are the program.

The same declaration generates the diagram, the transition table, retry targets and the
interpreter's paths. Planned elements stay visible but do not enter the running machine.
Construction rejects inconsistent endpoints, events, within-request sections, outgoing arrows
and forks. Moved from `mendel_authoring.protocol` (forge MVP 3, #364) and made generic.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, InstanceOf, model_validator

from comeni_flow.forks import DEFAULT, Subject


class Actor(StrEnum):
    """Who acts at a node. The diagram's fill."""

    YOU = "you"
    ENGINE = "engine"
    AI = "ai"
    SAFETY = "safety"
    STOP = "stop"


class Border(StrEnum):
    """The tier a node's decision lands at, when it lands at one. The diagram's border."""

    NONE = "none"
    TIER12 = "tier12"
    TIER3 = "tier3"
    TIER4 = "tier4"


class Shape(StrEnum):
    BOX = "box"
    ROUND = "round"
    CHOICE = "choice"
    GATE = "gate"




class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Stage(_Frozen):
    id: str
    title: str
    within_request: bool = False
    """Its nodes are the steps one request takes and reports (14.7.8.1): none moves the session,
    and the validator refuses an event on an edge inside it."""


class Node(_Frozen):
    id: str
    stage: str
    actor: Actor
    label: str
    phase: InstanceOf[StrEnum] | None = None
    """The phase this node happens in, a member of the flow's `phases`. `None` only while
    planned: a phase may not exist until the step that builds it."""
    border: Border = Border.NONE
    shape: Shape = Shape.BOX
    built: bool = False
    acts: bool = False
    """A handler runs when a session enters this node (14.7.8.1). It returns the outcome that
    names the arrow on, or nothing: then the session rests here if the node waits, and otherwise
    goes on by its one way straight on (`ask` queues a job and asks: plan 1c)."""
    waits: bool = False
    """A session may rest here, until a command names an arrow out."""
    fork: Subject | None = None
    """A **fork** (spec §12): its outgoing edges are the cases of this subject, and the
    interpreter takes the one the snapshot is in. A fork neither acts nor waits."""


class Edge(_Frozen):
    source: str
    target: str
    label: str = ""
    event: InstanceOf[StrEnum] | None = None
    """Set when following this edge moves the session. `None` for a step inside a phase."""
    returns: bool = False
    """A retry out of `failed`, resuming where the failure happened. Its target is chosen by
    `failed_from`, so return edges are exempt from one-target-per-event."""
    built: bool = False
    on: str | None = None
    """What takes this arrow: a `Command` out of a waiting node, an outcome out of an acting one;
    `None` for the one way straight on (14.7.8.1)."""
    case: str | None = None
    """Out of a fork only: the case of the fork's subject that takes this edge (`DEFAULT` for
    an open subject's fallback)."""


class Protocol(_Frozen):
    """A flow, declared. **Generic through its fields**: `phases` and `events` are the flow's own
    enums, `commands` what may leave a node that waits, `failed`/`retry` its failure machinery if
    it has any, and `refusal_code` the code its interpreter refuses with. A phase or event keeps
    its own type (`InstanceOf`), so a flow's code can compare members by identity."""

    title: str
    slug: str
    """The diagram's file name in `docs/explanation/diagrams/`, without `.md`."""
    phases: type[StrEnum]
    events: type[StrEnum]
    commands: frozenset[str]
    failed: InstanceOf[StrEnum] | None = None
    """The phase a failure lands in; `None` for a flow with no retry machinery."""
    retry: InstanceOf[StrEnum] | None = None
    """The event that resumes out of `failed`; `None` with it."""
    refusal_code: str
    """The declared diagnostic the interpreter refuses with (`MI0216` for the builder)."""
    stages: tuple[Stage, ...]
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        stages = {s.id for s in self.stages}
        nodes = {n.id: n for n in self.nodes}
        shared = sorted(stages & set(nodes))
        if shared:
            # Mermaid draws a stage as a subgraph with the same namespace as its nodes.
            raise ValueError(f"{shared} is both a stage and a node")
        for node in self.nodes:
            if node.stage not in stages:
                raise ValueError(f"node {node.id!r} is in an undeclared stage {node.stage!r}")
            if node.built and node.phase is None:
                raise ValueError(f"built node {node.id!r} has no phase")
            if node.phase is not None and not isinstance(node.phase, self.phases):
                raise ValueError(
                    f"node {node.id!r}: {node.phase!r} is not a {self.phases.__name__}"
                )
        seen: dict[tuple[StrEnum, StrEnum], str] = {}
        for edge in self.edges:
            arrow = f"{edge.source}→{edge.target}"
            for end in (edge.source, edge.target):
                if end not in nodes:
                    raise ValueError(f"edge {arrow} names an undeclared node {end!r}")
            if edge.event is not None and not isinstance(edge.event, self.events):
                raise ValueError(f"{arrow}: {edge.event!r} is not a {self.events.__name__}")
            if self.retry is not None and edge.event is self.retry and not edge.returns:
                raise ValueError(f"{arrow} carries retry without returns")
            if edge.returns and (
                self.retry is None
                or edge.event is not self.retry
                or nodes[edge.source].phase is not self.failed
            ):
                raise ValueError(f"return edge {arrow} does not leave failed on retry")
            if not edge.built:
                continue
            if not (nodes[edge.source].built and nodes[edge.target].built):
                raise ValueError(f"built edge {arrow} touches a planned node")
            if edge.event is None or edge.returns:
                continue
            key = (nodes[edge.source].phase, edge.event)
            if key in seen and seen[key] != nodes[edge.target].phase:
                raise ValueError(
                    f"{key[0]} on {key[1]} leads to both {seen[key]} and {nodes[edge.target].phase}"
                )
            seen[key] = nodes[edge.target].phase
        within = {s.id for s in self.stages if s.within_request}
        for edge in self.edges:
            if (
                edge.event is not None
                and {nodes[edge.source].stage, nodes[edge.target].stage} <= within
            ):
                raise ValueError(
                    f"{edge.source}→{edge.target} carries {edge.event}, and a within-request "
                    "section never moves the session"
                )
        for stage in self.stages:
            if not stage.within_request:
                continue
            leaving = [
                e.on
                for e in self.edges
                if e.built
                and nodes[e.source].stage == stage.id
                and nodes[e.target].stage != stage.id
            ]
            if any(on is not None for on in leaving) and (
                None in leaving or len(set(leaving)) != len(leaving)
            ):
                raise ValueError(f"the ways out of section {stage.id} need a name each, once")
        commands = self.commands
        for node in self.nodes:
            out = [e for e in self.edges if e.source == node.id and e.built]
            # Return arrows may share a name: the failure (`failed_from`) chooses between them.
            named = [e.on for e in out if e.on is not None and not e.returns]
            twice = sorted({n for n in named if named.count(n) > 1})
            if twice:
                raise ValueError(f"{node.id}: {twice} names two arrows out — twice is ambiguous")
            inside = node.stage in {st.id for st in self.stages if st.within_request}
            if named and not (node.acts or node.waits or inside) and node.built:
                # Nothing could take a named arrow: no handler returns an outcome here, and no
                # session rests here for a command (final review of 1a). A section's ways out
                # are the exception: the node entering the section takes them (`exits`).
                raise ValueError(
                    f"{node.id} neither acts nor waits, so {sorted(named)} is never taken"
                )
            if node.waits and not node.acts and node.built:
                # Only a command leaves a node that rests and does nothing: an outcome would
                # need a handler to return it.
                strays = sorted(set(named) - commands)
                if strays:
                    raise ValueError(f"{node.id} waits, and {strays} is not a command")
            # A node that takes no part yet (today's whole protocol) may fan out unnamed; 1b marks
            # each node and the rule then holds everywhere.
            takes_part = node.acts or node.waits or bool(named)
            # A fork's case edges carry no `on`, and are not ways straight through (spec §12).
            if takes_part and sum(1 for e in out if e.on is None and e.case is None) > 1:
                raise ValueError(f"{node.id} has more than one way straight through")
        for edge in self.edges:
            if edge.case is not None and nodes[edge.source].fork is None:
                raise ValueError(
                    f"{edge.source}→{edge.target} names case {edge.case!r}, and its source "
                    "is not a fork"
                )
        _validate_forks(self.nodes, self.edges)
        return self

    def fork_keys(self) -> frozenset[str]:
        """The snapshot keys this protocol's forks read: what the shell resolves into a snapshot.
        A subject whose `snapshot_key()` is `None` reads nothing the shell must resolve."""
        return frozenset(
            key for n in self.nodes if n.fork is not None and (key := n.fork.snapshot_key())
        )

    def exits(self, node_id: str) -> list[Edge]:
        """The ways out of the within-request section `node_id` leads into, if it leads into one.

        **A section within a request is one step** (14.7.8.1): the node entering it acts, runs
        the section's steps inside its request, and its outcome names a way *out* of the
        section. The steps inside are drawn so the card and the picture share ids, and are never
        run by the interpreter."""
        within = {s.id for s in self.stages if s.within_request}
        stage_of = {n.id: n.stage for n in self.nodes}
        into = {stage_of[e.target] for e in self.edges if e.built and e.source == node_id}
        if len(into) != 1 or not into <= within or stage_of.get(node_id) in into:
            return []
        (section,) = into
        return [
            e
            for e in self.edges
            if e.built and stage_of[e.source] == section and stage_of[e.target] != section
        ]

    def _phase(self, node_id: str) -> StrEnum:
        return next(n.phase for n in self.nodes if n.id == node_id)

    def transitions(self) -> dict[tuple[StrEnum, StrEnum], StrEnum]:
        """Every legal move: each built event edge that is not a return."""
        return {
            (self._phase(e.source), e.event): self._phase(e.target)
            for e in self.edges
            if e.built and e.event is not None and not e.returns
        }

    def retry_targets(self) -> frozenset[StrEnum]:
        """The phases a retry out of `failed` may resume."""
        return frozenset(self._phase(e.target) for e in self.edges if e.built and e.returns)


def _validate_forks(nodes: tuple[Node, ...], edges: tuple[Edge, ...]) -> None:
    """Require each fork to be passive and to cover its subject exactly once."""
    for node in nodes:
        if node.fork is None:
            continue
        if node.acts or node.waits:
            raise ValueError(f"fork {node.id} acts or waits; the interpreter decides it")
        # Planned edges still cover a designed case even though the interpreter follows only
        # built edges. Reaching a planned case at runtime is therefore a separate refusal.
        out = [edge for edge in edges if edge.source == node.id]
        if any(edge.case is None for edge in out):
            raise ValueError(f"{node.id}: every edge out of a fork names a case")
        cases = [edge.case for edge in out]
        twice = sorted({case for case in cases if cases.count(case) > 1})
        if twice:
            raise ValueError(f"{node.id}: case {twice} twice")
        options = node.fork.options()
        if options is None:
            if DEFAULT not in cases:
                raise ValueError(
                    f"{node.id} switches on an open subject and has no DEFAULT ({DEFAULT!r})"
                )
            continue
        missing = sorted(options - set(cases))
        extra = sorted(set(cases) - options)
        if missing:
            raise ValueError(f"{node.id}: no edge for {missing}")
        if extra:
            raise ValueError(f"{node.id}: {extra} is not a case of {node.fork.title!r}")


