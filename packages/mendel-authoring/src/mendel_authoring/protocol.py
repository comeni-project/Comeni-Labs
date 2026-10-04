"""The authoring protocol as one declarative object: who acts, in which stage, and what moves.

**This is the only definition.** `state.TRANSITIONS` and `state.RETRY_TARGETS` are computed from
the built edges here, and `docs/design/diagrams/` is generated from the whole object (one
diagram, with sections), so the picture a person argues about and the machine that runs cannot
drift apart. The design lives here too, **planned** (`built=False`) and
drawn dashed; each substep that builds a part flips it. The rules' prose stays on the protocol
page: this object holds structure, not argument.

Because a drawing mistake is now a behaviour mistake, `Protocol` refuses to exist when it is
inconsistent (spec §5, *Checked when it loads*).
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from mendel_authoring.types import Command, Event, Phase


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
    phase: Phase | None = None
    """The session phase this node happens in. `None` only while planned: `gathering` does not
    exist until the substep that builds it."""
    border: Border = Border.NONE
    shape: Shape = Shape.BOX
    built: bool = False
    acts: bool = False
    """A handler runs when a session enters this node (14.7.8.1). It returns the outcome that
    names the arrow on, or nothing, and the session rests here."""
    waits: bool = False
    """A session may rest here, until a command names an arrow out."""


class Edge(_Frozen):
    source: str
    target: str
    label: str = ""
    event: Event | None = None
    """Set when following this edge moves the session. `None` for a step inside a phase."""
    returns: bool = False
    """A retry out of `failed`, resuming where the failure happened. Its target is chosen by
    `failed_from`, so return edges are exempt from one-target-per-event."""
    built: bool = False
    on: str | None = None
    """What takes this arrow: a `Command` out of a waiting node, an outcome out of an acting one;
    `None` for the one way straight on (14.7.8.1)."""


class Protocol(_Frozen):
    title: str = "The authoring protocol"
    slug: str = "authoring-protocol"
    """The diagram's file name in `docs/design/diagrams/`, without `.md`."""
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
        seen: dict[tuple[Phase, Event], str] = {}
        for edge in self.edges:
            arrow = f"{edge.source}→{edge.target}"
            for end in (edge.source, edge.target):
                if end not in nodes:
                    raise ValueError(f"edge {arrow} names an undeclared node {end!r}")
            if edge.event is Event.RETRY and not edge.returns:
                raise ValueError(f"{arrow} carries retry without returns")
            if edge.returns and (
                edge.event is not Event.RETRY or nodes[edge.source].phase is not Phase.FAILED
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
        commands = {c.value for c in Command}
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
            if takes_part and sum(1 for e in out if e.on is None) > 1:
                raise ValueError(f"{node.id} has more than one way straight through")
        return self

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

    def _phase(self, node_id: str) -> Phase:
        return next(n.phase for n in self.nodes if n.id == node_id)

    def transitions(self) -> dict[tuple[Phase, Event], Phase]:
        """Every legal move: each built event edge that is not a return."""
        return {
            (self._phase(e.source), e.event): self._phase(e.target)
            for e in self.edges
            if e.built and e.event is not None and not e.returns
        }

    def retry_targets(self) -> frozenset[Phase]:
        """The phases a retry out of `failed` may resume."""
        return frozenset(self._phase(e.target) for e in self.edges if e.built and e.returns)


_FILL = {
    Actor.YOU: "fill:#1f3a5f,stroke:#6fa8dc,color:#fff",
    Actor.ENGINE: "fill:#1e3d2f,stroke:#6fbf8f,color:#fff",
    Actor.AI: "fill:#4a2f1f,stroke:#e0a060,color:#fff",
    Actor.SAFETY: "fill:#3a1f3a,stroke:#c080c0,color:#fff",
    Actor.STOP: "fill:#4a1f1f,stroke:#e06060,color:#fff",
}
_BORDER = {
    Border.TIER12: "stroke:#6fbf8f",
    Border.TIER3: "stroke:#f0d040,stroke-width:4px",
    Border.TIER4: "stroke:#ff5050,stroke-width:4px",
}
_PLANNED = "stroke-dasharray:6 4,opacity:0.55"
_KEY = {
    Actor.YOU: "Blue fill · you",
    Actor.ENGINE: "Green fill · engine: same input, same answer",
    Actor.AI: "Orange fill · AI: typed answers only, always marked",
    Actor.SAFETY: "Purple fill · safety level: what the AI may see",
    Actor.STOP: "Red fill · stop: can't continue",
    Border.TIER12: "Green border · tier 1–2: settled",
    Border.TIER3: "Yellow border · tier 3: a rule decided, check its fact",
    Border.TIER4: "Red border · tier 4: no rule could, you decide",
}
_KEY_TITLE = "Key: fill is who acts, border is the tier, dashed is planned"
_OPEN = {
    Shape.BOX: ('["', '"]'),
    Shape.ROUND: ('(["', '"])'),
    Shape.CHOICE: ('{"', '"}'),
    Shape.GATE: ('{{"', '"}}'),
}


def _node(node: Node) -> str:
    left, right = _OPEN[node.shape]
    return f"        {node.id}{left}{node.label}{right}:::{node.actor.value}"


def _edge(edge: Edge) -> str:
    if edge.built:
        arrow = f' -- "{edge.label}" --> ' if edge.label else " --> "
    else:
        arrow = f' -. "{edge.label}" .-> ' if edge.label else " -.-> "
    return f"    {edge.source}{arrow}{edge.target}"


def to_mermaid(protocol: Protocol) -> str:
    """The flowchart, stage by stage, in declaration order. Fill is who acts, border is tier,
    dashed is designed and not built."""
    lines = ["flowchart LR"]
    for actor, style in _FILL.items():
        lines.append(f"    classDef {actor.value} {style}")
    for stage in protocol.stages:
        lines.append(f'    subgraph {stage.id} ["{stage.title}"]')
        lines.append("        direction TB")
        lines += [_node(n) for n in protocol.nodes if n.stage == stage.id]
        lines.append("    end")
        lines.append(f"    style {stage.id} fill:transparent,stroke:#555")
    lines += [_edge(e) for e in protocol.edges]
    for node in protocol.nodes:
        styles = [_BORDER[node.border]] if node.border is not Border.NONE else []
        if not node.built:
            styles.append(_PLANNED)
        if styles:
            lines.append(f"    style {node.id} {','.join(styles)}")
    lines.append(f'    subgraph KEY ["{_KEY_TITLE}"]')
    lines.append("        direction TB")
    for which, text in _KEY.items():
        cls = which.value if isinstance(which, Actor) else Actor.ENGINE.value
        lines.append(f'        key_{which.value}["{text}"]:::{cls}')
    lines.append('        key_planned["Dashed · designed, not built yet"]:::engine')
    lines.append("    end")
    for border, style in _BORDER.items():
        lines.append(f"    style key_{border.value} {style}")
    lines.append(f"    style key_planned {_PLANNED}")
    lines.append("    style KEY fill:transparent,stroke:#333")
    return "\n".join(lines) + "\n"


# ── the protocol ─────────────────────────────────────────────────────────────────────────────
#
# Built: the loop as it runs today. Planned: the consultant as designed in
# `docs/design/authoring-protocol.md`, transcribed from its drawing. A substep that builds a part
# gives its nodes phases and flips `built`; `state.TRANSITIONS` follows by derivation.


def _n(id: str, stage: str, actor: Actor, label: str, phase: Phase | None = None, **kw) -> Node:
    return Node(id=id, stage=stage, actor=actor, label=label, phase=phase, **kw)


def _built(id: str, stage: str, actor: Actor, label: str, phase: Phase, **kw) -> Node:
    return _n(id, stage, actor, label, phase, built=True, **kw)


def _e(source: str, target: str, label: str = "", **kw) -> Edge:
    return Edge(source=source, target=target, label=label, **kw)


def _move(source: str, target: str, event: Event, label: str = "", **kw) -> Edge:
    return Edge(source=source, target=target, label=label, event=event, built=True, **kw)


_YOU, _ENGINE, _AI, _SAFETY, _STOP = Actor.YOU, Actor.ENGINE, Actor.AI, Actor.SAFETY, Actor.STOP
_P, _E = Phase, Event

# ── ②a inside: reading a sample (14.7.6, 14.7.7) ─────────────────────────────────────────────
#
# One request's steps, all in `gathering`, and none moves the session: what an inspection settles
# reaches the session through the gap's own `FACT_ADDED`, as a click does. Everything here runs on
# our server, in the request or the sample's own process, except the two steps whose labels name
# door 6, where a model reads the start of the file.

_G = _P.GATHERING

_SAMPLE_NODES = (
    _built(
        "sample_level",
        "sample",
        _SAFETY,
        "Does the protection level<br/>allow an upload?",
        _G,
        shape=Shape.GATE,
    ),
    _built("sample_refused", "sample", _STOP, "Refused, and says why", _G),
    _built(
        "sample_head",
        "sample",
        _ENGINE,
        "Keep the first 4 MB of each, in memory<br/>(longer files are cut, never refused)",
        _G,
    ),
    _built(
        "sample_claim",
        "sample",
        _ENGINE,
        "Which trusted formats claim<br/>the extension? (every file agreeing)",
        _G,
        shape=Shape.CHOICE,
    ),
    _built(
        "sample_nothing", "sample", _STOP, "Nothing reads this type yet:<br/>the question stays", _G
    ),
    # The characteriser (14.7.7): built in 14.7.7.2.
    _built(
        "sample_door",
        "sample",
        _SAFETY,
        "Does the protection level<br/>let a model read it?",
        _G,
        shape=Shape.GATE,
    ),
    _built(
        "sample_excerpt",
        "sample",
        _ENGINE,
        "Keep up to 8 KB of its text<br/>(gzip unpacked by its first bytes)",
        _G,
    ),
    _built(
        "sample_families", "sample", _AI, "AI, through door 6:<br/>which families could it be?", _G
    ),
    _built(
        "sample_types",
        "sample",
        _AI,
        "AI, through door 6: which type,<br/>which states and facts?",
        _G,
    ),
    _built(
        "sample_ai_admit",
        "sample",
        _ENGINE,
        "Admit every id<br/>against the registry",
        _G,
        shape=Shape.CHOICE,
    ),
    _built(
        "sample_ai_stamped",
        "sample",
        _ENGINE,
        "Stamped: read by AI<br/>(check the premise)",
        _G,
        border=Border.TIER3,
    ),
    _built(
        "sample_hand_back",
        "sample",
        _ENGINE,
        "A type the engine reads:<br/>your browser sends it again",
        _G,
    ),
    _built("sample_unpack", "sample", _ENGINE, "Unpack if compressed, up to 16 MB", _G),
    _built(
        "sample_confirm",
        "sample",
        _ENGINE,
        "Does the content<br/>confirm the format?",
        _G,
        shape=Shape.CHOICE,
    ),
    _built(
        "sample_unreadable",
        "sample",
        _STOP,
        "Unreadable, with the reason<br/>(a bomb, too slow, a crash, not this format)",
        _G,
    ),
    _n(
        "sample_tie",
        "sample",
        _YOU,
        "Several formats confirm:<br/>you choose",
        shape=Shape.CHOICE,
        border=Border.TIER4,
    ),
    _built("sample_measure", "sample", _ENGINE, "Measure: one pass,<br/>every measure fed", _G),
    _built(
        "sample_undetermined",
        "sample",
        _ENGINE,
        "Below its threshold:<br/>undetermined, left open",
        _G,
        border=Border.TIER4,
    ),
    _built("sample_admit", "sample", _ENGINE, "Admit each value<br/>against the registry", _G),
    _built(
        "sample_kept",
        "sample",
        _ENGINE,
        "Already said: your word stands,<br/>a difference is shown",
        _G,
    ),
    _built(
        "sample_stamped",
        "sample",
        _ENGINE,
        "Stamped: measured by<br/>its pieces and versions",
        _G,
        border=Border.TIER3,
    ),
    _built("sample_back", "sample", _ENGINE, "Back to the questions", _G, shape=Shape.ROUND),
)

_SAMPLE_EDGES = (
    _e("sample_level", "sample_refused", "above level 0", built=True),
    _e("sample_level", "sample_head", "level 0", built=True),
    _e("sample_head", "sample_claim", "one file or a pair", built=True),
    _e(
        "sample_head",
        "sample_refused",
        "any other count, a form it can't read, or cut short",
        built=True,
    ),
    _e("sample_claim", "sample_door", "none", built=True),
    _e("sample_door", "sample_nothing", "above level 0", built=True),
    _e("sample_door", "sample_excerpt", "level 0", built=True),
    _e("sample_excerpt", "sample_nothing", "too little text, or no model", built=True),
    _e("sample_excerpt", "sample_families", "queued for the AI", built=True),
    _e("sample_families", "sample_back", "none fits: the AI couldn't tell", built=True),
    _e("sample_families", "sample_types", "one or more", built=True),
    _e("sample_types", "sample_ai_admit", built=True),
    _e(
        "sample_ai_admit",
        "sample_back",
        "an id nothing declares: refused, the question stays",
        built=True,
    ),
    _e("sample_ai_admit", "sample_kept", "you already said it", built=True),
    _e("sample_ai_admit", "sample_ai_stamped", "nothing here reads that type", built=True),
    _e("sample_ai_admit", "sample_hand_back", "the engine reads that type", built=True),
    _e("sample_hand_back", "sample_confirm", "claimed by the type the AI named", built=True),
    _e("sample_ai_stamped", "sample_back", built=True),
    _e("sample_claim", "sample_unpack", "one or more", built=True),
    _e("sample_unpack", "sample_unreadable", "a bomb", built=True),
    _e("sample_unpack", "sample_confirm", built=True),
    _e("sample_confirm", "sample_unreadable", "none of them", built=True),
    _e("sample_confirm", "sample_back", "several: the question stays", built=True),
    _e("sample_confirm", "sample_tie", "several, at a later step"),
    _e("sample_confirm", "sample_measure", "exactly one", built=True),
    _e("sample_measure", "sample_unreadable", "took too long", built=True),
    _e("sample_measure", "sample_undetermined", "not enough to say", built=True),
    _e("sample_measure", "sample_admit", "decided", built=True),
    _e(
        "sample_admit",
        "sample_refused",
        "already answered, or this question takes no sample",
        built=True,
    ),
    _e("sample_admit", "sample_back", "the registry refuses a value: dropped", built=True),
    _e("sample_admit", "sample_kept", "you already said it", built=True),
    _e("sample_admit", "sample_stamped", "new", built=True),
    _e("sample_stamped", "sample_back", built=True),
    _e("sample_kept", "sample_back", built=True),
    _e("sample_undetermined", "sample_back", built=True),
    _e("sample_nothing", "sample_back", built=True),
    _e("sample_unreadable", "sample_back", built=True),
)

PROTOCOL = Protocol(
    stages=(
        Stage(id="describe", title="① You describe it"),
        Stage(id="gather", title="② The engine gathers what it needs"),
        Stage(id="sample", title="②a Inside: reading a sample", within_request=True),
        Stage(id="check", title="③ You check the goal"),
        Stage(id="build", title="④ Your consultant builds it with you"),
        Stage(id="anytime", title="Any time"),
        Stage(id="wrong", title="When it goes wrong"),
    ),
    nodes=(
        # ① built
        _built(
            "say",
            "describe",
            _YOU,
            "You say what you want<br/>(files optional)",
            _P.UNDERSTANDING,
            shape=Shape.ROUND,
        ),
        # The type in two steps (14.7.4, #194): the family from a short list, then the goal from
        # each chosen family shown whole.
        _built(
            "family",
            "describe",
            _AI,
            "AI picks the kind of result<br/>from a short list",
            _P.UNDERSTANDING,
        ),
        _built(
            "read_goal",
            "describe",
            _AI,
            "AI reads it into a typed goal,<br/>from each chosen family whole",
            _P.UNDERSTANDING,
        ),
        # ② built in 14.7.3; the upload branch stays planned (14.7.6, 14.7.7)
        _built(
            "list_needs",
            "gather",
            _ENGINE,
            "Engine lists what the target needs<br/>inputs, and facts rules will read",
            _P.GATHERING,
        ),
        _built(
            "next_gap",
            "gather",
            _ENGINE,
            "Anything on the list<br/>still unknown?",
            _P.GATHERING,
            shape=Shape.CHOICE,
        ),
        _built("ask", "gather", _AI, "AI phrases each question<br/>in plain words", _P.GATHERING),
        _built("reply", "gather", _YOU, "You answer", _P.GATHERING, shape=Shape.CHOICE),
        _built(
            "suggest",
            "gather",
            _AI,
            "AI reads your words<br/>into a suggestion you confirm",
            _P.GATHERING,
        ),
        _built("upload", "gather", _YOU, "You upload a file", _P.GATHERING, shape=Shape.ROUND),
        *_SAMPLE_NODES,
        _built("said", "gather", _ENGINE, "→ you said", _P.GATHERING),
        _built(
            "left_open", "gather", _ENGINE, "Left open<br/>→ you choose in the build", _P.GATHERING
        ),
        _built(
            "stopped",
            "gather",
            _STOP,
            "Stop: can't build without it<br/>(e.g. no genome)",
            _P.STOPPED,
            shape=Shape.ROUND,
        ),
        # ③ built
        _built(
            "card",
            "check",
            _YOU,
            "Goal card: every fact<br/>and where it came from",
            _P.GOAL_REVIEW,
        ),
        _built(
            "readback",
            "check",
            _AI,
            "AI reads the goal back<br/>in its own words",
            _P.GOAL_REVIEW,
        ),
        # ④ built
        _built("resolve", "build", _ENGINE, "Engine resolves the pipeline", _P.RESOLVING),
        _built(
            "offer",
            "build",
            _ENGINE,
            "Next step:<br/>does it need you?",
            _P.BUILDING,
            shape=Shape.CHOICE,
        ),
        _built(
            "step_settled",
            "build",
            _ENGINE,
            "Tier 1–2 · placed, one obvious answer",
            _P.BUILDING,
            border=Border.TIER12,
        ),
        _built(
            "step_rule",
            "build",
            _ENGINE,
            "Tier 3 · placed by a rule<br/>check its fact",
            _P.BUILDING,
            border=Border.TIER3,
        ),
        _built(
            "step_choice", "build", _YOU, "Tier 4 · you choose", _P.BUILDING, border=Border.TIER4
        ),
        _built("done", "build", _ENGINE, "Pipeline complete", _P.COMPLETE, shape=Shape.ROUND),
        # ④ planned
        _n("plan", "build", _AI, "The plan, in plain stages", _P.BUILDING),
        _n(
            "pace",
            "build",
            _YOU,
            "Go through it together,<br/>or stop only where I need you?",
            _P.BUILDING,
            shape=Shape.CHOICE,
        ),
        _n(
            "wrap",
            "build",
            _AI,
            "Wrap-up: what you get,<br/>what you need, who decided what",
            _P.COMPLETE,
            shape=Shape.ROUND,
        ),
        # any time, planned
        _n(
            "ask_any",
            "anytime",
            _YOU,
            "Ask anything:<br/>why? what if? what's a BAM?",
            shape=Shape.ROUND,
        ),
        _n("explain", "anytime", _AI, "AI answers only from sources,<br/>and shows them"),
        # when it goes wrong, built
        _built(
            "failed",
            "wrong",
            _STOP,
            "Failed: say why,<br/>offer a retry",
            _P.FAILED,
            shape=Shape.ROUND,
        ),
    ),
    edges=(
        # built: today's loop
        _e("say", "family", built=True),
        _e("family", "read_goal", "each family, whole", built=True),
        _e("family", "say", "none fits: it asks you", built=True),
        _move("family", "failed", _E.PROVIDER_FAILED, "model failed"),
        _move("read_goal", "failed", _E.PROVIDER_FAILED, "model failed"),
        _e("readback", "card", "in the AI's words", built=True),
        _move("card", "resolve", _E.GOAL_ACCEPTED, "that's right"),
        _move("card", "family", _E.GOAL_REVISED, "not quite"),
        _move("resolve", "offer", _E.BLUEPRINT_STORED),
        _move("resolve", "failed", _E.BUILD_FAILED, "can't build it"),
        _move("resolve", "failed", _E.PROVIDER_FAILED, "model failed"),
        _e("offer", "step_settled", "settled", built=True),
        _e("offer", "step_rule", "a rule decided", built=True),
        _e("offer", "step_choice", "no rule could", built=True),
        _move("step_settled", "offer", _E.PROPOSAL_SETTLED),
        _move("step_rule", "offer", _E.PROPOSAL_SETTLED),
        _move("step_choice", "offer", _E.PROPOSAL_SETTLED, "you choose"),
        _move("offer", "done", _E.NOTHING_LEFT, "nothing left"),
        _move("offer", "resolve", _E.GOAL_ACCEPTED, "the goal changed"),
        _move("done", "resolve", _E.GOAL_ACCEPTED, "the goal changed"),
        _move("failed", "family", _E.RETRY, "retry", returns=True),
        _move("failed", "resolve", _E.RETRY, "retry", returns=True),
        # built: gathering (14.7.3)
        _move("read_goal", "list_needs", _E.WANT_RETURNED),
        _e("list_needs", "next_gap", built=True),
        _e("next_gap", "ask", "yes", built=True),
        _e("ask", "reply", built=True),
        _e("read_goal", "suggest", "you mentioned it", built=True),
        _e("reply", "suggest", "typed in your words", built=True),
        _e("suggest", "reply", "you confirm with a click", built=True),
        _e("reply", "said", "I know it", built=True),
        _e("reply", "left_open", "can't share it", built=True),
        _move("reply", "stopped", _E.INPUT_UNAVAILABLE, "I don't have that input"),
        _move("said", "next_gap", _E.FACT_ADDED),
        _move("left_open", "next_gap", _E.FACT_ADDED),
        _move("next_gap", "card", _E.NOTHING_MISSING, "nothing unknown"),
        _move("list_needs", "say", _E.WANT_UNREACHABLE, "nothing makes it: it asks you"),
        # a file answers it (14.7.6, 14.7.7): the request runs section ②a and comes back. No event
        # of its own: what the sample settles moves the session as a click does.
        _e("reply", "upload", "upload a sample (when something here reads it)", built=True),
        _e("upload", "sample_level", "uploaded", built=True),
        *_SAMPLE_EDGES,
        _e("sample_back", "next_gap", built=True),
        # planned: the consultant build (14.7.8)
        _e("resolve", "plan"),
        _e("plan", "pace"),
        _e("pace", "offer"),
        _e("done", "wrap"),
        _e("ask_any", "explain"),
    ),
)
"""The authoring protocol. **Edit this, not `state.TRANSITIONS`**, which is derived from it."""
