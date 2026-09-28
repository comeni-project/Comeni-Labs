# The consultant, substeps 14.7.2–14.7.4: protocol as code, gathering, samples

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task by task, in one hand. `CLAUDE.md` says subagents are for review and design only. Steps
> use checkbox (`- [ ]`) syntax: **tick each step as it completes**, and where a step was carried
> out differently than written, tick it and record the deviation in the execution record at the
> end. Plans here are corrected during execution by design.

**Goal:** Scenario 1 of the walk completes. *Paired-end RNA-seq to gene counts*, with or without an
uploaded FASTQ, reaches a goal holding reads, a genome and an annotation, with `paired` and
`read_length` known or deliberately open, and the build starts.

**Architecture:** The engine computes what an analysis still needs (the gap list) by walking back
from the want through the registry. Each gap is a proposal of kind `gap` the person answers by
click, by typed value, or (from 14.7.4) by uploading a file an inspector measures. Facts carry
their source into the goal, and an open measurement is simply absent, so the tiers carry it as
tier 4. The protocol is a declarative object: the state machine is derived from it and its diagram is
generated from it, with the design drawn dashed until built.

**Tech stack:** Python 3.12 (FastAPI, SQLAlchemy, Alembic, Pydantic), React 19 + TypeScript +
TanStack Query + Vitest, LiteLLM to a local Ollama `gemma3:12b` for the walk.

**Spec:** [`docs/superpowers/specs/2026-09-28-the-consultant-design.md`](../specs/2026-09-28-the-consultant-design.md).
**Protocol:** [`docs/design/authoring-protocol.md`](../../design/authoring-protocol.md).
**Issues:** Task 14 #119 → 14.7 #126 → 14.7.2 #132, 14.7.3 #133 (#105, #113, #114), 14.7.4 #134.
Each task below is a sub-issue of its substep (#138–#154), numbered in its heading.

**Not in this plan:** 14.7.5 (characteriser) and 14.7.6 (consultant build) are planned after
14.7.4 is walked. 14.7.6 is knowingly optimistic, and writing its code now would be writing
against a guess.

## Global constraints

- **Nothing is guessed.** A fact comes from the person, a file, or stays open. No model proposes a
  likely value in gathering, in either mode. (Protocol rule 5.)
- **The engine decides what is missing.** No model call judges sufficiency. (Rule 1.)
- **A prompt change is a new version file.** `builder.goal.v2` joins `prompts.RETIRED` and is never
  edited.
- **Every code is declared** in `comeni_core/diagnostics.yml` and emitted through `coded()`;
  regenerate `docs/handbook/reference/diagnostics.md` with
  `uv run python tools/generate_diagnostics_doc.py`.
- **Database tests run against a throwaway Postgres**, never the stack's:
  `docker run -d --rm --name walk-testdb -e POSTGRES_USER=mendel -e POSTGRES_PASSWORD=mendel -e POSTGRES_DB=mendel -p 127.0.0.1:5442:5432 postgres:17-alpine`,
  then `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel` on each
  `pytest` line and **on make's command line** for `make check` (`-include .env` beats the
  environment).
- **Run Python tests from the repository root.** `registry_root` defaults to `./registry` relative
  to the working directory.
- **Frontend comments cite issues as "issue 105", never `#105`**: the colour guard reads it as hex.
- **Watch every new guard fail against the specific defect** before calling it done.
- **Touching `router.py`, `resolve.py`, `rules/` or `comeni_core/artifact/pipeline.py` means
  `make verify`**, or `make check` + `make guards` + `make slow` when `check` stops on the five base
  failures (`test_forge_jobs.py` ×4, `test_full_cycle.py::test_the_loop_closes`).
- **The APIs run from baked images:** `docker compose up -d --build api ai-worker web` before a
  browser check.

## Review focus

The inputs the spec implies and no happy-path test covers, most likely first. Each has its test
in the owning task.

1. **A want the gap engine cannot walk** (a type nothing produces and nobody could have, such as a
   typo the model slipped past admission). Expected: an honest stop naming it, never an empty gap
   list that sends an unbuildable goal to the card. Task 14.7.3.3.
2. **The same measurement asked twice** after it was answered *can't share it*. Expected: an
   `OPEN` fact removes the gap for good. Task 14.7.3.3.
3. **A typed value outside the measurement's declaration** (`read_length: -5`, `paired: "maybe"`).
   Expected: MI0208 refusal, the gap stays offered, and nothing is recorded. Task 14.7.3.5.
4. **A reload in the middle of gathering.** Expected: the pending gap comes back once, and the
   facts gathered so far are intact. Task 14.7.3.5.
5. **A FASTQ head that is not FASTQ** (a FASTA, a BAM, a truncated gzip). Expected: the inspector
   refuses with a declared code, and the gap stays open for another file or an answer. Task
   14.7.4.2.

---

## 14.7.2 — The protocol as code (#132)

Rewritten on 2026-09-28 after a second brainstorm (spec §5, commit `0ebc2c3`): **the protocol
object is the only definition, and `state.TRANSITIONS` is derived from it.** Retry is a set of
return edges and is refused outside them; the designed consultant lives in the same object,
marked planned and drawn dashed. The operator waived plan review for this substep.

**One import cycle to break first.** `protocol.py` needs `Event`, and `state.py` will need
`PROTOCOL`. `Event` moves to `types.py` beside `Phase`, and `state.py` re-exports it, so the 52
call sites spelling `st.Event` / `state.Event` keep working.

### Task 14.7.2.1 (#138): the protocol object, its load-time checks, and its Mermaid

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (gains `Event`),
  `packages/mendel-api/src/mendel_api/authoring/state.py` (imports `Event` from `types`)
- Create: `packages/mendel-api/src/mendel_api/authoring/protocol.py`
- Test: `packages/mendel-api/tests/test_authoring_protocol.py`

**Interfaces:**
- Produces: `Actor`, `Border`, `Shape`, `Stage`, `Node`, `Edge`, `Protocol` (with
  `transitions() -> dict[tuple[Phase, Event], Phase]` and `retry_targets() -> frozenset[Phase]`),
  `PROTOCOL`, `to_mermaid(protocol: Protocol) -> str`. Later substeps flip `built` and set
  `phase`/`event` on planned parts; they do not change these types.

- [x] **Step 1: Move `Event`.** Cut the `Event` class from `state.py` into `types.py` directly
  after `Phase`, unchanged. In `state.py`, import it: `from mendel_api.authoring.types import
  Event, Phase, ProposalState`. Run `uv run pytest -q packages/mendel-api/tests/test_authoring_state.py`.
  Expected: all pass (a move, no behaviour).

- [x] **Step 2: Write the failing tests.**

```python
"""The protocol is one object: the machine is derived from it and the diagram is drawn from it.

A drawing mistake is now a behaviour mistake, so the object refuses to exist when it is
inconsistent. Each refusal below is watched failing against a deliberately broken protocol.
"""

import pytest
from mendel_api.authoring import protocol as p
from mendel_api.authoring.types import Event, Phase

S = (p.Stage(id="s", title="S"),)


def _node(id, phase=Phase.UNDERSTANDING, *, built=True, stage="s"):
    return p.Node(id=id, stage=stage, actor=p.Actor.ENGINE, label=id, phase=phase, built=built)


def test_the_real_protocol_loads_and_has_built_and_planned_parts():
    assert p.PROTOCOL.edges, "a loop over no edges asserts nothing"
    assert any(n.built for n in p.PROTOCOL.nodes)
    assert any(not n.built for n in p.PROTOCOL.nodes), "the design is in the object, planned"


def test_an_edge_to_an_undeclared_node_is_refused():
    with pytest.raises(ValueError, match="undeclared node 'ghost'"):
        p.Protocol(stages=S, nodes=(_node("a"),), edges=(p.Edge(source="a", target="ghost"),))


def test_a_node_in_an_undeclared_stage_is_refused():
    with pytest.raises(ValueError, match="undeclared stage 'nowhere'"):
        p.Protocol(stages=S, nodes=(_node("a", stage="nowhere"),), edges=())


def test_a_built_node_without_a_phase_is_refused():
    with pytest.raises(ValueError, match="built node 'a' has no phase"):
        p.Protocol(stages=S, nodes=(_node("a", phase=None),), edges=())


def test_a_built_edge_touching_a_planned_node_is_refused():
    nodes = (_node("a"), _node("b", Phase.GOAL_REVIEW, built=False))
    edge = p.Edge(source="a", target="b", event=Event.GOAL_RETURNED, built=True)
    with pytest.raises(ValueError, match="built edge a→b touches a planned node"):
        p.Protocol(stages=S, nodes=nodes, edges=(edge,))


def test_one_phase_and_event_with_two_targets_is_refused():
    nodes = (_node("a"), _node("b", Phase.GOAL_REVIEW), _node("c", Phase.FAILED))
    edges = (
        p.Edge(source="a", target="b", event=Event.GOAL_RETURNED, built=True),
        p.Edge(source="a", target="c", event=Event.GOAL_RETURNED, built=True),
    )
    with pytest.raises(ValueError, match="understanding on goal_returned leads to both"):
        p.Protocol(stages=S, nodes=nodes, edges=edges)


def test_a_return_edge_must_leave_failed_on_retry():
    nodes = (_node("a"), _node("b", Phase.RESOLVING))
    edge = p.Edge(source="a", target="b", event=Event.RETRY, returns=True, built=True)
    with pytest.raises(ValueError, match="return edge a→b does not leave failed"):
        p.Protocol(stages=S, nodes=nodes, edges=(edge,))


def test_retry_is_only_ever_a_return_edge():
    nodes = (_node("f", Phase.FAILED), _node("b", Phase.RESOLVING))
    edge = p.Edge(source="f", target="b", event=Event.RETRY, built=True)
    with pytest.raises(ValueError, match="f→b carries retry without returns"):
        p.Protocol(stages=S, nodes=nodes, edges=(edge,))


def test_planned_parts_are_left_out_of_the_machine():
    nodes = (_node("a"), _node("b", Phase.GOAL_REVIEW), _node("c", None, built=False))
    edges = (
        p.Edge(source="a", target="b", event=Event.GOAL_RETURNED, built=True),
        p.Edge(source="b", target="c", label="later"),
    )
    proto = p.Protocol(stages=S, nodes=nodes, edges=edges)
    assert proto.transitions() == {(Phase.UNDERSTANDING, Event.GOAL_RETURNED): Phase.GOAL_REVIEW}


def test_the_key_names_every_actor_every_border_and_planned():
    """A new actor cannot be drawn without the key saying what its colour means."""
    rendered = p.to_mermaid(p.PROTOCOL)
    for actor in p.Actor:
        assert f"key_{actor.value}" in rendered
    for border in p.Border:
        if border is not p.Border.NONE:
            assert f"key_{border.value}" in rendered
    assert "key_planned" in rendered


def test_planned_parts_are_drawn_dashed():
    nodes = (_node("a"), _node("c", None, built=False))
    proto = p.Protocol(stages=S, nodes=nodes, edges=(p.Edge(source="a", target="c", label="x"),))
    rendered = p.to_mermaid(proto)
    assert 'a -. "x" .-> c' in rendered
    assert "style c stroke-dasharray" in rendered


def test_rendering_is_deterministic():
    assert p.to_mermaid(p.PROTOCOL) == p.to_mermaid(p.PROTOCOL)
```

- [x] **Step 3: Run them.** `uv run pytest -q packages/mendel-api/tests/test_authoring_protocol.py`.
  Expected: FAIL, `ImportError: cannot import name 'protocol'`.

- [x] **Step 4: Write `protocol.py`: types, checks, derivation, renderer.**

```python
"""The authoring protocol as one declarative object: who acts, in which stage, and what moves.

**This is the only definition.** `state.TRANSITIONS` and `state.RETRY_TARGETS` are computed from
the built edges here, and `docs/design/authoring-protocol-diagram.md` is generated from the whole
object, so the picture a person argues about and the machine that runs cannot drift apart. The
design lives here too, **planned** (`built=False`) and drawn dashed; each substep that builds a
part flips it. The rules' prose stays on the protocol page: this object holds structure, not
argument.

Because a drawing mistake is now a behaviour mistake, `Protocol` refuses to exist when it is
inconsistent (spec §5, *Checked when it loads*).
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from mendel_api.authoring.types import Event, Phase


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


class Protocol(_Frozen):
    stages: tuple[Stage, ...]
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        stages = {s.id for s in self.stages}
        nodes = {n.id: n for n in self.nodes}
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
        return self

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
    lines.append('    subgraph KEY ["Key: fill is who acts, border is the tier, dashed is planned"]')
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
```

- [x] **Step 5: Encode `PROTOCOL`** below the renderer: today's loop **built**, the design
  **planned**, transcribed from the hand-drawn diagram in `docs/design/authoring-protocol.md`.
  Stages: `describe` *① You describe it*, `gather` *② The engine gathers what it needs*,
  `check` *③ You check the goal*, `build` *④ Your consultant builds it with you*, `anytime`
  *Any time*, `wrong` *When it goes wrong*.

  **Built nodes** (id, stage, actor, phase, extras): `say` describe/you/UNDERSTANDING ROUND;
  `read_goal` describe/ai/UNDERSTANDING; `card` check/you/GOAL_REVIEW; `resolve` build/engine/
  RESOLVING; `offer` build/engine/BUILDING CHOICE; `step_settled` build/engine/BUILDING TIER12;
  `step_rule` build/engine/BUILDING TIER3; `step_choice` build/you/BUILDING TIER4; `done`
  build/engine/COMPLETE ROUND; `failed` wrong/stop/FAILED ROUND.

  **Built edges**, one per entry in the hand-written `TRANSITIONS` plus the two returns:
  `read_goal→card` GOAL_RETURNED; `read_goal→failed` PROVIDER_FAILED; `card→resolve`
  GOAL_ACCEPTED *that's right*; `card→read_goal` GOAL_REVISED *not quite*; `resolve→offer`
  BLUEPRINT_STORED; `resolve→failed` BUILD_FAILED; `resolve→failed` PROVIDER_FAILED;
  `step_settled→offer`, `step_rule→offer`, `step_choice→offer` PROPOSAL_SETTLED (three edges, one
  transition); `offer→done` NOTHING_LEFT *nothing left*; `offer→resolve` and `done→resolve`
  GOAL_ACCEPTED *the goal changed*; `failed→read_goal` and `failed→resolve` RETRY `returns=True`.
  Plain built edges: `say→read_goal`; `offer→step_settled` *settled*, `offer→step_rule` *a rule
  decided*, `offer→step_choice` *no rule could*.

  **Planned nodes** (`built=False`, `phase=None` unless the phase already exists): gather:
  `list_needs` engine; `next_gap` engine CHOICE *anything still unknown?*; `ask` ai; `reply` you
  CHOICE; `upload` you ROUND; `safety` safety GATE; `read_engine` engine *measured*; `read_ai` ai
  *read by AI*; `said` engine *you said*; `left_open` engine *left open: you choose in the build*;
  `stopped` stop ROUND *can't build without it*. build: `plan` ai BUILDING; `pace` you BUILDING
  CHOICE; `wrap` ai COMPLETE ROUND. anytime: `ask_any` you ROUND; `explain` ai.

  **Planned edges** (`built=False`, no events yet): `read_goal→list_needs`, `list_needs→next_gap`,
  `next_gap→ask` *yes*, `ask→reply`, `reply→said` *I know it*, `reply→upload` *not sure*,
  `reply→stopped` *I don't have that input*, `upload→safety` *uploaded*, `upload→left_open`
  *can't share it*, `safety→read_engine` *engine knows the type*, `safety→read_ai` *it doesn't*,
  `said→next_gap`, `read_engine→next_gap`, `read_ai→next_gap`, `left_open→next_gap`,
  `next_gap→card` *nothing unknown*, `resolve→plan`, `plan→pace`, `pace→offer`, `done→wrap`,
  `ask_any→explain`.

  Labels are short plain text; `<br/>` is allowed, double quotes are not.

- [x] **Step 6: Run the tests.** Expected: 12 passed (the plan first said 13; there are twelve tests). Then `uv run pytest -q
  packages/mendel-api/tests/test_authoring_state.py` still passes (nothing reads `PROTOCOL` yet).

- [x] **Step 7: Watch two checks fail against the real object.** Temporarily set `built=False` on
  `card`: import fails with *built edge read_goal→card touches a planned node*. Temporarily add a
  second built `read_goal→done` GOAL_RETURNED edge: *understanding on goal_returned leads to both*.
  Restore both, and record the two messages in the execution record.

- [x] **Step 8: Commit** —
  `feat(living): the authoring protocol as one object, checked when it loads — 14.7.2.1 (#132)`;
  close #138 citing it.

### Task 14.7.2.2 (#139): the state machine is derived, and retry is held to the return edges

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/state.py`
- Test: `packages/mendel-api/tests/test_authoring_state.py`,
  `packages/mendel-api/tests/test_authoring_protocol.py`

**Interfaces:**
- Consumes: `PROTOCOL.transitions()`, `PROTOCOL.retry_targets()`.
- Produces: `state.TRANSITIONS` (same type as today, now computed), `state.RETRY_TARGETS:
  frozenset[Phase]`; `advance()` refuses a retry outside `RETRY_TARGETS` with **MI0212**.

- [x] **Step 1: Capture today's table as the test's expectation.** In
  `test_authoring_protocol.py`, add the hand-written table **once**, as the proof the derivation
  changed nothing. It is deleted in 14.7.3.1, where the machine is meant to change and the
  existing arrow-by-arrow tests in `test_authoring_state.py` carry the contract.

```python
from mendel_api.authoring import state as st

TODAY = {
    (Phase.UNDERSTANDING, Event.GOAL_RETURNED): Phase.GOAL_REVIEW,
    (Phase.UNDERSTANDING, Event.PROVIDER_FAILED): Phase.FAILED,
    (Phase.GOAL_REVIEW, Event.GOAL_ACCEPTED): Phase.RESOLVING,
    (Phase.GOAL_REVIEW, Event.GOAL_REVISED): Phase.UNDERSTANDING,
    (Phase.RESOLVING, Event.BLUEPRINT_STORED): Phase.BUILDING,
    (Phase.RESOLVING, Event.BUILD_FAILED): Phase.FAILED,
    (Phase.RESOLVING, Event.PROVIDER_FAILED): Phase.FAILED,
    (Phase.BUILDING, Event.PROPOSAL_SETTLED): Phase.BUILDING,
    (Phase.BUILDING, Event.NOTHING_LEFT): Phase.COMPLETE,
    (Phase.BUILDING, Event.GOAL_ACCEPTED): Phase.RESOLVING,
    (Phase.COMPLETE, Event.GOAL_ACCEPTED): Phase.RESOLVING,
}


def test_the_derived_machine_is_the_one_that_was_written_by_hand():
    """Deleted in 14.7.3.1: a one-time proof that deriving the table changed no behaviour."""
    assert st.TRANSITIONS == TODAY
    assert st.TRANSITIONS is not TODAY


def test_the_machine_is_read_from_the_protocol():
    assert st.TRANSITIONS == p.PROTOCOL.transitions()
    assert st.RETRY_TARGETS == p.PROTOCOL.retry_targets() == {Phase.UNDERSTANDING, Phase.RESOLVING}
    assert st.RETRY_FALLBACK in st.RETRY_TARGETS
```

  And in `test_authoring_state.py`, after `test_an_unrecorded_failure_retries_from_the_beginning`:

```python
def test_a_retry_cannot_resume_where_the_protocol_draws_no_return():
    """Tightened in 14.7.2: before, any recorded `failed_from` was accepted."""
    with pytest.raises(ValueError) as raised:
        st.advance(Phase.FAILED, st.Event.RETRY, Phase.BUILDING)
    assert "MI0212" in str(raised.value)
    assert "resolving" in str(raised.value) and "understanding" in str(raised.value)
```

- [x] **Step 2: Run both files.** Expected: FAIL: `st.TRANSITIONS is not TODAY` holds but
  `RETRY_TARGETS` does not exist, and the retry into `building` is accepted.

- [x] **Step 3: Declare MI0212** in `packages/comeni-core/src/comeni_core/diagnostics.yml` beside
  MI0200, same shape: summary *a retry cannot resume into that phase*, long form *A retry leaves
  `failed` for the phase that failed, and only where the authoring protocol draws a return edge.
  Resuming anywhere else would enter a phase whose preconditions nobody checked.* Regenerate with
  `uv run python tools/generate_diagnostics_doc.py`.

- [x] **Step 4: Derive in `state.py`.** Replace the literal `TRANSITIONS` dict with

```python
from mendel_api.authoring.protocol import PROTOCOL

TRANSITIONS: dict[tuple[Phase, Event], Phase] = PROTOCOL.transitions()
"""Every legal move, **derived** from the built event edges of `protocol.PROTOCOL`: change the
protocol, not this line. `failed` is not a source here: leaving it needs a second input, which
phase failed, so `advance` handles `RETRY` against `RETRY_TARGETS` first."""

RETRY_TARGETS: frozenset[Phase] = PROTOCOL.retry_targets()
"""Where a retry may resume: the targets of the protocol's return edges."""
```

  keeping the `PROPOSAL_SETTLED` note in the docstring. In `advance`, after the
  `phase is not Phase.FAILED` check:

```python
        target = failed_from or RETRY_FALLBACK
        if target not in RETRY_TARGETS:
            onward = ", ".join(sorted(p.value for p in RETRY_TARGETS))
            raise ValueError(
                coded("MI0212", f"a retry cannot resume into {target.value}; it may resume into {onward}")
            )
        return target
```

  (Match `_refusal`'s actual `coded(...)` call shape; read it before writing.)

- [x] **Step 5: Run.** `uv run pytest -q packages/mendel-api/tests/test_authoring_state.py
  packages/mendel-api/tests/test_authoring_protocol.py`. Expected: all pass. Then the authoring
  suite against the throwaway database: `MENDEL_DATABASE_URL=… uv run pytest -q
  packages/mendel-api/tests -k authoring`. Expected: pass.

- [x] **Step 6: Watch the derivation fail against a drawing mistake.** Temporarily delete the
  `card→read_goal` GOAL_REVISED edge: `test_the_derived_machine_is_the_one_that_was_written_by_hand`
  and the arrow-by-arrow state test both fail naming `goal_revised`. Restore; record the message
  in the execution record.

- [x] **Step 7: Commit** — `feat(living): the state machine is derived from the protocol; retry
  held to its return edges — 14.7.2.2 (#132)`; close #139.

### Task 14.7.2.3 (#140): the generated diagram and `make docs`

**Files:**
- Create: `tools/generate_protocol_doc.py`, `docs/design/authoring-protocol-diagram.md` (generated)
- Modify: `Makefile` (the `docs:` target), `docs/design/authoring-protocol.md`
- Test: `tests/repo/test_protocol_doc.py`

- [ ] **Step 1: Write the failing test.**

```python
"""The protocol diagram is generated, and a stale one fails the build."""

import subprocess
import sys

from support.paths import ROOT


def test_the_protocol_diagram_is_fresh():
    run = subprocess.run(
        [sys.executable, "tools/generate_protocol_doc.py", "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
```

  (Check `tests/README.md` and `support.paths` for the real name of the root constant first.)
  Run: `uv run pytest -q tests/repo/test_protocol_doc.py`. Expected: FAIL (no such file).

- [ ] **Step 2: Write the generator**, the same shape as `tools/generate_diagnostics_doc.py`:
  compare, print the fixing command, exit 1 under `--check`.

```python
#!/usr/bin/env python
"""Render `docs/design/authoring-protocol-diagram.md` from `mendel_api.authoring.protocol`.

A whole generated file, not a block spliced into the hand-written protocol page:
`generate_diagnostics_doc.py` records why (`--check` could only ever see the block).
"""

import sys
from pathlib import Path

from mendel_api.authoring.protocol import PROTOCOL, to_mermaid

DOC = Path(__file__).parent.parent / "docs" / "design" / "authoring-protocol-diagram.md"

HEADER = """<!-- generated by tools/generate_protocol_doc.py — do not edit -->

# The authoring protocol, drawn

**Generated from `mendel_api/authoring/protocol.py`**, which is also where the running state
machine comes from, so this picture is the machine. Solid is built; dashed is designed and not
built yet. The rules, the argument and the changelog are on
[the protocol page](authoring-protocol.md).

"""


def render() -> str:
    return HEADER + "```mermaid\n" + to_mermaid(PROTOCOL) + "```\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        if not DOC.exists() or DOC.read_text() != text:
            print(f"{DOC.name} is stale — run: uv run python tools/generate_protocol_doc.py")
            return 1
        return 0
    DOC.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Add it to `make docs`**, after the diagnostics line:
  `uv run python tools/generate_protocol_doc.py --check`. Run `make docs`. Expected: FAIL,
  *authoring-protocol-diagram.md is stale*.

- [ ] **Step 4: Generate it**, `uv run python tools/generate_protocol_doc.py`, then open the
  Mermaid in a browser and look at it: every stage drawn, dashed parts dashed, the key complete.
  Expected: `make docs` and the test pass.

- [ ] **Step 5: Replace the hand-drawn diagram** in `docs/design/authoring-protocol.md` with a
  pointer: *The diagram is [generated from the code](authoring-protocol-diagram.md); solid is
  built, dashed is designed.* Add a changelog line: *2026-09-28: the diagram is generated from
  `protocol.py`, and the state machine is derived from the same object (14.7.2).*

- [ ] **Step 6: Watch it fail stale.** Change one node label in `protocol.py`, run `make docs`,
  see *stale*; restore. Then `make links` (expected: 0 broken) and commit —
  `docs(living): the protocol diagram, generated and checked by make docs — 14.7.2.3 (#132)`.
  Close #140 and #132.

---

## 14.7.3 — Gathering without files (#133)

### Task 14.7.3.1 (#141): facts, the `gathering` and `stopped` phases, and their events

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py`,
  `packages/mendel-api/src/mendel_api/authoring/state.py`,
  `packages/mendel-api/src/mendel_api/authoring/protocol.py`,
  `packages/mendel-api/src/mendel_api/models.py`
- Create: `packages/mendel-api/migrations/versions/<rev>_gathering_facts.py`
- Test: `packages/mendel-api/tests/test_authoring_state.py`, `test_authoring_types.py`

**Interfaces:**
- Produces: `Phase.GATHERING`, `Phase.STOPPED`; `Event.WANT_RETURNED`, `FACT_ADDED`,
  `NOTHING_MISSING`, `INPUT_UNAVAILABLE`; `FactKind`, `FactSource`, `Fact`;
  `PipelineAuthoringSession.facts: list[dict]`, the `want: list[TypeId]` on the session (stored
  in the existing `goal` column as `{"want": [...], "constraints": {...}}` until the card
  composes a full `Goal`. No new column for it).

- [ ] **Step 1: Write the failing tests**

```python
# test_authoring_state.py
def test_gathering_sits_between_the_want_and_the_card():
    assert st.advance(Phase.UNDERSTANDING, st.Event.WANT_RETURNED) is Phase.GATHERING
    assert st.advance(Phase.GATHERING, st.Event.FACT_ADDED) is Phase.GATHERING
    assert st.advance(Phase.GATHERING, st.Event.NOTHING_MISSING) is Phase.GOAL_REVIEW
    assert st.advance(Phase.GATHERING, st.Event.INPUT_UNAVAILABLE) is Phase.STOPPED


def test_stopped_is_terminal_and_not_a_failure():
    """An honest stop is the protocol ending correctly. RETRY is for failures."""
    with pytest.raises(ValueError, match="MI0200"):
        st.advance(Phase.STOPPED, st.Event.RETRY)
    assert not any(src is Phase.STOPPED for (src, _ev) in st.TRANSITIONS)

# test_authoring_types.py
def test_a_fact_says_where_it_came_from_and_an_open_one_has_no_value():
    said = t.Fact(kind=t.FactKind.MEASUREMENT, subject="read_length", value=150,
                  source=t.FactSource.PERSON_SAID)
    assert said.source is t.FactSource.PERSON_SAID
    with pytest.raises(ValidationError):
        t.Fact(kind=t.FactKind.MEASUREMENT, subject="read_length", value=150,
               source=t.FactSource.OPEN)
```

- [ ] **Step 2: Run them to see them fail.** Expected: `AttributeError: GATHERING`.
- [ ] **Step 3: Implement.** In `types.py`:

```python
class FactKind(StrEnum):
    INPUT = "input"
    MEASUREMENT = "measurement"


class FactSource(StrEnum):
    """Where a fact came from, which is what the goal card and the tier-3 premise show."""

    MEASURED = "measured"        # an inspector read the file (14.7.4)
    MODEL_READ = "model_read"    # the characteriser read it (14.7.5)
    PERSON_SAID = "person_said"  # the person stated it
    OPEN = "open"                # nobody knows; the tiers carry it as tier 4


class Fact(_Shape):
    kind: FactKind
    subject: str = Field(min_length=1, max_length=128)
    """A type id for an input, a measurement id for a measurement."""
    value: HumanParamValue | None = None
    states: list[str] = []
    source: FactSource
    sample: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _open_has_no_value(self) -> "Fact":
        if self.source is FactSource.OPEN and self.value is not None:
            raise ValueError("an open fact has no value: nobody knows it")
        return self
```

  Add `GATHERING = "gathering"` and `STOPPED = "stopped"` to `Phase`. In `types.py`, add the four
  events to `Event` with one-line docstrings. In `protocol.py`, **build the planned stage ②**:
  give `list_needs`, `next_gap`, `ask`, `reply`, `said` and `left_open` `phase=GATHERING` and
  `stopped` `phase=STOPPED`, set `built=True` on them, and on their edges set `built=True` and the
  events: `read_goal→list_needs` WANT_RETURNED, `said→next_gap` and `left_open→next_gap`
  FACT_ADDED, `next_gap→card` NOTHING_MISSING, `reply→stopped` INPUT_UNAVAILABLE. `upload`,
  `safety`, `read_engine` and `read_ai` stay planned (14.7.4, 14.7.5). `TRANSITIONS` follows by
  derivation; there is no table to edit. **Delete** `test_the_derived_machine_is_the_one_that_was_written_by_hand`
  and its `TODAY` (14.7.2.2): the machine is meant to change now, and the arrow-by-arrow tests in
  `test_authoring_state.py` gain the four new arrows instead. Retire `read_goal→card`
  GOAL_RETURNED if 14.7.3.4 does (see there).

- [ ] **Step 4: The migration.** `uv run alembic revision -m "gathering facts"` from
  `packages/mendel-api`, then:

```python
def upgrade() -> None:
    op.add_column(
        "pipeline_authoring_session",
        sa.Column("facts", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("pipeline_authoring_session", "facts")
```

  and `facts: Mapped[list] = mapped_column(JSON, default=list)` on the model. The phase column is
  `String(16)`, and `gathering` fits.

- [ ] **Step 5: Run** the state, types and protocol tests, plus `alembic upgrade head` against the
  throwaway database. Expected: all pass, and the protocol test forces the new edges.
- [ ] **Step 6: Commit** — `feat(living): facts, and the gathering and stopped phases — 14.7.3.1 (#133)`.

### Task 14.7.3.2 (#142): a profile with mixed sources (`comeni-core`)

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/measurement.py`
- Test: `packages/comeni-core/tests/test_measurement_registry.py` (or the file holding
  `profile()`'s tests; `grep -rn "def test.*profile" packages/comeni-core/tests`)

**Interfaces:**
- Produces: `MeasurementRegistry.profile_of(entries: Sequence[tuple[str, ParamValue | list[ParamValue], ValueSource, str | None]]) -> DataProfile`.

- [ ] **Step 1: Failing test**

```python
def test_profile_of_keeps_each_entrys_own_source(registry):
    profile = registry.profile_of([
        ("read_length", 150, ValueSource.GOAL, None),
        ("paired", True, ValueSource.MODEL, None),
    ])
    assert {(m.measurement, m.source) for m in profile.measurements} == {
        ("paired", ValueSource.MODEL), ("read_length", ValueSource.GOAL)}


def test_profile_of_validates_like_profile(registry):
    with pytest.raises(BadMeasurementValueError):
        registry.profile_of([("read_length", -5, ValueSource.GOAL, None)])
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement** beside `profile()`, which then calls it:

```python
    def profile_of(self, entries) -> DataProfile:
        """`profile()` for entries that do not share a source.

        The gathering stage folds facts from a person, an inspector and a model into one goal, and
        `profile()` stamps a single source on every entry. This is the one other validating
        constructor. `tests/guards/test_construction.py` allows it by name, the same way it
        allows `profile()`.
        """
        for measurement_id, value, _source, _by in entries:
            self.check(measurement_id, value)
        return DataProfile(measurements=[
            Measured(measurement=m, value=v, source=s, by=b)
            for m, v, s, b in sorted(entries, key=lambda e: e[0])
        ])
```

- [ ] **Step 4: Update `tests/guards/test_construction.py`** to allow `profile_of`, then **watch
  that guard fail** by constructing a `DataProfile` in a scratch function under `packages/`, run the
  guard, see it named, and delete the scratch function.
- [ ] **Step 5: Run** the `comeni-core` tests and `make guards`. Commit —
  `feat(core): profile_of, a validated profile with a source per entry — 14.7.3.2 (#133)`.

### Task 14.7.3.3 (#143): the gap engine

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/gaps.py`
- Test: `packages/mendel-api/tests/test_gaps.py`

**Interfaces:**
- Consumes: `registry.stack() -> Layers` (`.registry.producers_of`, `.rules.decisions`,
  `.rules.derivations`, `.measurements.measurements`), `Fact`, `FactKind`, `FactSource`.
- Produces: `class Gap(NamedTuple): kind: FactKind; subject: str; why: str`,
  `class Unreachable(NamedTuple): subject: str`,
  `gaps(want: list[str], facts: list[Fact], stack) -> list[Gap] | Unreachable`.

- [ ] **Step 1: Failing tests** (no database, only the registry):

```python
from mendel_api.authoring.types import Fact, FactKind, FactSource
from mendel_api.services import gaps as g
from mendel_api.services import registry


def _kinds(result):
    return [(gap.kind.value, gap.subject) for gap in result]


def test_gene_counts_needs_reads_a_genome_an_annotation_and_the_facts_rules_read():
    result = g.gaps(["counts.matrix"], [], registry.stack())
    got = _kinds(result)
    inputs = [s for k, s in got if k == "input"]
    measurements = [s for k, s in got if k == "measurement"]
    assert set(inputs) == {"fastq.reads", "genome.fasta", "annotation.gtf"}
    assert {"read_length", "paired", "strandedness"} <= set(measurements)
    # inputs first, then measurements
    assert got.index(("input", inputs[-1])) < got.index(("measurement", measurements[0]))


def test_a_fact_removes_its_gap_and_an_open_one_is_not_asked_again():
    facts = [
        Fact(kind=FactKind.INPUT, subject="genome.fasta", source=FactSource.PERSON_SAID),
        Fact(kind=FactKind.MEASUREMENT, subject="read_length", source=FactSource.OPEN),
    ]
    subjects = {gap.subject for gap in g.gaps(["counts.matrix"], facts, registry.stack())}
    assert "genome.fasta" not in subjects and "read_length" not in subjects
    assert "annotation.gtf" in subjects


def test_a_want_nothing_can_make_is_unreachable_not_an_empty_list():
    """Review focus 1: an empty list would send an unbuildable goal to the card."""
    result = g.gaps(["no.such.type"], [], registry.stack())
    assert result == g.Unreachable("no.such.type")
```

  Before writing the second assertion's measurement set, confirm it against the registry:
  `grep -rn "when:" registry/rules` for rule premises (today `read_length`), and every measurement
  with a `meta_key` whose `describes` is a leaf input reached (`paired` → `single_end`,
  `strandedness`). If the registry says otherwise, the test follows the registry, and the deviation
  goes in the execution record.

- [ ] **Step 2: Run to see them fail.**
- [ ] **Step 3: Implement.**

```python
"""What an analysis still needs, computed and not asked of a model (protocol rule 1).

Walks back from the want the way `router.route` does, but over **every** candidate producer, not
only the chosen one: a gap asked for and then not needed costs one question, and a gap missed
costs the build (#114). Deterministic: same want and facts in, same gaps out, in the same order.
"""

from typing import NamedTuple

from mendel_api.authoring.types import Fact, FactKind, FactSource


class Gap(NamedTuple):
    kind: FactKind
    subject: str
    why: str


class Unreachable(NamedTuple):
    subject: str


def _premise_measurements(stack) -> set[str]:
    """Measurement ids a rule's `when` reads, directly or through a derivation's source."""
    declared = set(stack.measurements.measurements)
    derived = {d.fact: (d.source or (d.aggregate.measurement if d.aggregate else None))
               for d in stack.rules.derivations}
    read: set[str] = set()
    for decision in stack.rules.decisions:
        for row in decision.rows:
            for key in row.when:
                source = derived.get(key, key)
                if source in declared:
                    read.add(source)
    return read


def gaps(want: list[str], facts: list[Fact], stack) -> list[Gap] | Unreachable:
    known = {(f.kind, f.subject) for f in facts}
    leaves: list[str] = []
    seen: set[str] = set()

    def walk(type_id: str, visiting: frozenset[str]) -> Unreachable | None:
        if type_id in seen:
            return None
        seen.add(type_id)
        producers = [c for c in stack.registry.producers_of(type_id, frozenset())
                     if c.id not in visiting]
        if not producers:
            leaves.append(type_id)
            return None
        for contract in producers:
            for port in contract.consumes:
                if port.type_id:
                    walk(port.type_id, visiting | {contract.id})
        return None

    for type_id in want:
        if not stack.registry.producers_of(type_id, frozenset()):
            return Unreachable(type_id)
        walk(type_id, frozenset())

    measurements = _premise_measurements(stack) | {
        m.id for m in stack.measurements.measurements.values()
        if m.meta_key and m.describes in leaves
    }
    out = [Gap(FactKind.INPUT, t, "the pipeline needs it and nothing can make it")
           for t in leaves if (FactKind.INPUT, t) not in known]
    out += [Gap(FactKind.MEASUREMENT, m, "a step reads it to decide")
            for m in sorted(measurements) if (FactKind.MEASUREMENT, m) not in known]
    return out
```

  The order of `leaves` follows the walk, which follows `producers_of`'s `(-priority, id)` order, so
  it is deterministic. Ranking by `dag-core` is a refinement for the walk to ask for, not an MVP
  requirement. Record it in the execution record if it is left out.

- [ ] **Step 4: Run the tests.** Expected: 3 passed. Commit —
  `feat(living): the gap engine — what an analysis still needs, computed — 14.7.3.3 (#133)`.

### Task 14.7.3.4 (#144): the want-only goal prompt

**Files:**
- Create: `packages/mendel-api/src/mendel_api/authoring/prompts/builder.goal.v3.md`
- Modify: `authoring/prompts.py`, `authoring/types.py`, `services/authoring_ai.py`,
  `services/authoring_jobs.py`
- Test: `test_authoring_prompts.py`, `test_authoring_ai.py`, `test_authoring_routes.py`,
  `test_authoring_spawn.py` (their `GOAL` fixtures)

**Interfaces:**
- Produces: `WantUnderstanding(_Shape)`: `want: list[TypeId]`, `constraints: Constraints`,
  `summary: Prose`, `questions: list[AskedQuestion] = []`; `prompts.GOAL = "builder.goal.v3"`;
  `RETIRED = ("builder.goal.v1", "builder.goal.v2")`.

- [ ] **Step 1: Failing tests.** In `test_authoring_prompts.py`, the goal prompt no longer says
  `goal.have is what already exists` and does say `You are not asked what they have`. In
  `test_authoring_types.py`, `WantUnderstanding` has no field named `have` (the #105 lesson, held).
  In `test_authoring_ai.py`, a recorded `{"want": ["counts.matrix"], "constraints": {},
  "summary": "gene counts from paired reads", "questions": []}` is admitted, and one whose `want`
  names an undeclared type is refused MI0204.
- [ ] **Step 2: Run to see them fail.**
- [ ] **Step 3: Write `builder.goal.v3.md`.** Copy the invariant block from v2 verbatim (the test
  requires it at the top), then: *what they want to end up with*, as declared type ids; any
  constraint they **stated**; one plain summary sentence; and a question only when the want itself
  is ambiguous. The key line: *You are not asked what they have. The engine works that out from
  what they want and asks them itself. Do not write inputs, states or measurements.* Point `GOAL`
  at v3 and add v2 to `RETIRED`.
- [ ] **Step 4: Switch `understand()`** to `shape=WantUnderstanding` and an `_admit_want` that
  checks every `want` id against `stack.vocabulary.types` (MI0204, as `_admit_goal` does for
  `have`).
- [ ] **Step 5: Rewrite `_understand` in `authoring_jobs.py`:** answer the turn with a `Narrative`
  block holding the summary (plus any want questions as today), store
  `{"want": ..., "constraints": ...}` on the session, move with `WANT_RETURNED`, and call
  `authoring.offer_next_gap(session_id)` (Task 14.7.3.5). **Spawn does not skip gathering:** gaps
  need a person in both modes (rule 5). Remove the goal proposal here; the goal card is offered by
  `offer_next_gap` when nothing is missing. Remove the `read_goal→card` GOAL_RETURNED edge from
  `PROTOCOL` if nothing else uses the event (`grep -rn GOAL_RETURNED packages/`); the transition
  goes with it by derivation.
- [ ] **Step 6: Update the fixtures** in the four test files to the want-only shape, run the
  authoring tests, and commit —
  `feat(living): the goal call asks for the want only — builder.goal.v3 — 14.7.3.4 (#133, #105)`.

### Task 14.7.3.5 (#145): gap proposals, answered by click or typed value

**Files:**
- Modify: `services/authoring.py`, `routes/authoring.py`, `authoring/types.py`,
  `packages/comeni-core/src/comeni_core/diagnostics.yml`
- Test: `packages/mendel-api/tests/test_authoring_gathering.py` (new)

**Interfaces:**
- Consumes: `gaps()`, `Fact`, `profile_of()`, `Event.FACT_ADDED` / `NOTHING_MISSING` / `INPUT_UNAVAILABLE`.
- Produces: `GAP = "gap"` proposal kind; `offer_next_gap(session_id) -> str | None`;
  `answer_gap(proposal_id, option: str, value: HumanParamValue | None, *, by: str) -> Phase`;
  `compose_goal(session_id) -> Goal`; `DecideProposal.value: HumanParamValue | None`;
  `AuthoringProposalView.kind: Literal["goal", "step", "gap"]`; codes **MI0208** (*a value that
  does not fit the measurement*) and **MI0209** (*the goal cannot be built: its want is something
  nothing can make*).

- [ ] **Step 1: Failing tests** against the throwaway database, driving the service directly.
  The helpers come first. They read rows the way `test_authoring_building.py` does, so no
  service function exists only for a test:

```python
from mendel_api.authoring import state as st
from mendel_api.authoring.types import Mode, Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession
from mendel_api.services import authoring, drafts
from mendel_api.services import blueprint as bp
from comeni_core.plan.draft import DraftGraph


def _gathering(want: list[str]) -> str:
    """A session moved to GATHERING with a want and no facts, its first gap offered."""
    draft_id = drafts.create(DraftGraph(), "t", "ana")
    sid = authoring.open_session(draft_id, mode=Mode.BUILD, who="ana")
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).goal = {"want": want, "constraints": {}}
    authoring.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring.offer_next_gap(sid)
    return sid


def _payload(pid: str) -> dict:
    with session_scope() as db:
        return dict(db.get(PipelineAuthoringProposal, pid).payload)


def _pending_for(sid: str, subject: str) -> str:
    """Answer every earlier gap with its first non-stopping option until `subject` is offered."""
    while (pid := authoring.pending_id(sid)) and _payload(pid)["subject"] != subject:
        options = [o for o in _payload(pid)["options"] if o not in ("dont_have", "value", "not_sure")]
        authoring.answer_gap(pid, options[0], None, by="ana")
    return authoring.pending_id(sid)


def _answer_until(sid: str, subject: str, option: str) -> None:
    authoring.answer_gap(_pending_for(sid, subject), option, None, by="ana")


def _facts(sid: str) -> list[dict]:
    with session_scope() as db:
        return list(db.get(PipelineAuthoringSession, sid).facts)


def test_answering_every_gap_reaches_the_card_with_a_goal_that_builds(clean):
    sid = _gathering(want=["counts.matrix"])   # helper: a session moved to GATHERING with a want
    while (pid := authoring.pending_id(sid)) and "subject" in _payload(pid):
        subject = _payload(pid)["subject"]
        if subject == "read_length":
            authoring.answer_gap(pid, "value", 150, by="ana")
        elif subject in ("paired",):
            authoring.answer_gap(pid, "yes", None, by="ana")
        elif subject == "strandedness":
            authoring.answer_gap(pid, "reverse", None, by="ana")
        else:
            authoring.answer_gap(pid, "have_it", None, by="ana")
    assert authoring.current_phase(sid) is Phase.GOAL_REVIEW
    goal = authoring.compose_goal(sid)
    assert {h.type_id for h in goal.have} == {"fastq.reads", "genome.fasta", "annotation.gtf"}
    assert {m.measurement: m.value for m in goal.profile.measurements}["read_length"] == 150
    bp.resolve(goal, mode=Mode.BUILD)   # does not raise: #114's defect, closed


def test_cant_share_leaves_a_measurement_open_and_out_of_the_profile(clean):
    sid = _gathering(want=["counts.matrix"])
    _answer_until(sid, "read_length", "cant_share")
    goal = authoring.compose_goal(sid)
    assert "read_length" not in {m.measurement for m in goal.profile.measurements}


def test_dont_have_an_input_stops_honestly(clean):
    sid = _gathering(want=["counts.matrix"])
    _answer_until(sid, "genome.fasta", "dont_have")
    assert authoring.current_phase(sid) is Phase.STOPPED
    assert "genome.fasta" in authoring.read(sid)["turns"][-1]["blocks"][0]["text"]


def test_a_value_outside_the_declaration_is_refused_and_nothing_recorded(clean):
    """Review focus 3."""
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    with pytest.raises(ValueError, match="MI0208"):
        authoring.answer_gap(pid, "value", -5, by="ana")
    assert authoring.pending_id(sid) == pid and _facts(sid) == []


def test_a_reload_mid_gathering_keeps_the_facts_and_one_pending_gap(clean):
    """Review focus 4. `read` is what a reload calls."""
    sid = _gathering(want=["counts.matrix"])
    _answer_until(sid, "annotation.gtf", "have_it")
    view = authoring.read(sid)
    assert view["pending_proposal"]["kind"] == "gap"
    assert len([f for f in view["facts"] if f["subject"] == "fastq.reads"]) == 1
```

- [ ] **Step 2: Run to see them fail.**
- [ ] **Step 3: Declare MI0208 and MI0209** in `diagnostics.yml` after MI0207, with `says`, `fix`,
  `explanation` in the reader-facing register (no provenance, per `CLAUDE.md` rule 4), and
  regenerate the diagnostics page.
- [ ] **Step 4: Implement in `services/authoring.py`:**
  - `offer_next_gap`: compute `gaps(want, facts, stack)`. On `Unreachable`, write an MI0209 notice
    (the `_note` helper from `a9e94cb`) and move to FAILED. On an empty list, compose the goal and
    propose it exactly as `_understand` used to (kind `GOAL`, the `GoalSummary` built from the
    facts: `have` lists inputs, `do` is the model's summary, `get` the want), then move with
    NOTHING_MISSING. Otherwise propose the first gap: kind `GAP`, payload `{"subject", "kind",
    "why", "options": {...}}`, block a `Question` with options:
    - input: `have_it` *I have it*, `cant_share` *I have it, but can't share it*, `dont_have`
      *I don't have one*. (`upload` arrives in 14.7.4.)
    - measurement with declared `values`: one option per value, then `not_sure`, `cant_share`.
    - measurement `boolean`: `yes`, `no`, `not_sure`, `cant_share`.
    - measurement `integer`/`number`: `value` (the typed field), `not_sure`, `cant_share`.
    - `not_sure` asks for a file: until 14.7.4 it records the fact `OPEN`, and the block says
      *upload arrives soon*, which the walk will flag if it bites. It never guesses.
  - `answer_gap`: settle the proposal (`decide` with `chosen_option`). For `value`, run
    `stack.measurements.check(subject, value)` first and raise MI0208 before anything is written.
    Append the fact to `session.facts` (`PERSON_SAID`, or `OPEN` for `cant_share`/`not_sure`
    measurements; an input `cant_share` is `PERSON_SAID`, since they have it), move FACT_ADDED,
    then `offer_next_gap`. `dont_have` on an input writes a notice naming it and moves
    INPUT_UNAVAILABLE.
  - `compose_goal`: `Goal(have=[GoalInput(type_id=f.subject, states=frozenset(f.states)) for
    input facts], want=..., constraints=..., profile=stack.measurements.profile_of([(f.subject,
    f.value, _SOURCE[f.source], None) for measurement facts not OPEN]))` with
    `_SOURCE = {PERSON_SAID: ValueSource.GOAL, MODEL_READ: ValueSource.MODEL}`.
  - `read()` returns `facts`.
- [ ] **Step 5: The route.** `DecideProposal.value: HumanParamValue | None = None`; in `decide`, a
  `GAP` kind calls `answer_gap(proposal_id, body.option, body.value, by=who)` and returns
  `AuthoringDecided` from the view. Add `facts` to `AuthoringSessionView`.
- [ ] **Step 6: Run** the new file and all `test_authoring*.py`, then `make client` (the view and
  the decide body changed). Commit —
  `feat(living): gaps offered and answered, facts folded into the goal — 14.7.3.5 (#133, #114)`.

### Task 14.7.3.6 (#146): reading a typed reply to a gap (`builder.gap.v1`)

**Files:**
- Create: `authoring/prompts/builder.gap.v1.md`
- Modify: `authoring/prompts.py` (`GAP`, `TEMPLATES` becomes four, and its test's count),
  `services/authoring_ai.py` (`read_gap_reply`), `services/authoring_jobs.py`
- Test: `test_authoring_ai.py`, `test_authoring_prompts.py`

**Interfaces:**
- Produces: `GapReply(_Shape)`: `chose: OptionId | None`, `value: HumanParamValue | None`,
  `unsure: bool = False`; `read_gap_reply(request, *, options, client) -> Outcome`.

- [ ] **Step 1: Failing tests:** a recorded reply `{"chose": "q_yes"}` to the paired gap is admitted;
  `{"chose": "q_maybe"}` is refused MI0205 (never offered); a reply with both `chose` and `value`
  is refused by the shape. **A reply the model cannot map re-offers the gap's options as clickable
  and records nothing**, never a guess.
- [ ] **Step 2: Run to see them fail.**
- [ ] **Step 3: The prompt** (invariant block first): *The engine asked the person one question,
  and they answered in their own words. Map the answer to one of these option ids, or to a typed
  value when the option `value` is offered. If the answer does not say, set `unsure`: never
  choose for them.*
- [ ] **Step 4: Route `say` in `GATHERING`** to a job that calls `read_gap_reply` against the
  pending gap's option ids and, when admitted, calls `answer_gap`. `unsure` answers the turn with
  a narrative *I couldn't tell from that. Here are the options* and leaves the gap pending.
- [ ] **Step 5: Run and commit** —
  `feat(living): a typed reply to a gap, read by id and never guessed — 14.7.3.6 (#133)`.

### Task 14.7.3.7 (#147): the page — gap cards, facts on the goal card, the new phases

**Files:**
- Create: `frontend/src/build/living/blocks/GapCard.tsx`, `frontend/src/build/living/GapCard.test.tsx`
- Modify: `DecisionLog.tsx`, `format.ts` (`phaseWords`, `waitingOn`), `blocks/GoalCard.tsx`,
  `useAuthoringSession.ts` (decide with `value`), `LivingSurface.tsx` (placeholder)

**Interfaces:**
- Consumes: the regenerated `frontend/src/api/` types (`kind: "gap"`, `facts`,
  `DecideProposal.value`).

- [ ] **Step 1: Failing tests** in `GapCard.test.tsx`: a boolean gap draws its options as buttons,
  and clicking *yes* calls `onAnswer("yes", undefined)`; an integer gap draws a number field plus
  *not sure* and *can't share it*, and `150` + *Use this* calls `onAnswer("value", 150)`; the
  card says **why** the engine asked (the payload's `why`). In `Conversation.test.tsx`: the goal
  card lists each input with its source (*you said*), and a heading **Left open, you'll choose
  during the build** lists open measurements. In `LivingSurface.test.tsx`: `gathering` reads
  *gathering what it needs* and `stopped` reads *stopped: something is missing*.
- [ ] **Step 2: Run to see them fail:** `cd frontend && npx vitest run src/build/living/`.
- [ ] **Step 3: Implement** `GapCard` on `BlockFrame`/`Primary`/`Secondary` from `blocks/parts`,
  render it in `DecisionLog` for `pending.kind === "gap"`, and extend the rest. No new colours:
  `tokens.test.ts` refuses an unmapped one.
- [ ] **Step 4: Run** `npx vitest run`, `npx tsc -b`, `npx oxlint src/build/living`. Commit —
  `feat(living): gap cards, and facts with their sources on the goal card — 14.7.3.7 (#133)`.

### Task 14.7.3.8 (#148): the ladder, then walk scenario 1 by answering

- [ ] **Step 1:** `make check MENDEL_DATABASE_URL=…5442…` (expected: only the five base failures),
  `make guards`, `make slow`, `make docs`, `make links`.
- [ ] **Step 2:** `docker compose up -d --build api ai-worker web` and `make migrate`.
- [ ] **Step 3: Walk it in Chrome.** *Paired-end RNA-seq to gene counts*, answer every gap by
  clicking, type 150 for read length, confirm, and see the first step offered. Then again with
  *can't share it* for read length, and see the aligner arrive as a **tier-4** choice. Then
  *I don't have one* for the genome, and see the honest stop.
- [ ] **Step 4: File every defect as an issue** under 14.7.3, with mechanical ones fixed before
  closing the substep (the protocol in the walk plan).
- [ ] **Step 5:** Tick this plan, write the execution record, and close #105, #114 and #133 with
  the commits. Comment on #113 with what the walk showed.

---

## 14.7.4 — Samples at protection level 0, and the FASTQ inspector (#134)

### Task 14.7.4.1 (#149): the protection level

**Files:**
- Create: `packages/mendel-api/src/mendel_api/authoring/protection.py`
- Modify: `packages/mendel-api/src/mendel_api/settings.py`, `.env.example`, `diagnostics.yml`
- Test: `packages/mendel-api/tests/test_protection.py`

**Interfaces:**
- Produces: `ProtectionLevel(IntEnum)` with `OPEN_0 = 0` only; `Crossing(StrEnum)`: `UPLOAD`,
  `SAMPLE_TO_MODEL`; `allows(level, crossing) -> bool`; `require(crossing)`, which raises
  **MI0210** (*this installation's protection level does not allow that*);
  `settings.protection_level`, from `COMENI_PROTECTION_LEVEL`, default 0.

- [ ] **Step 1: Failing tests:** level 0 allows both crossings; an unknown level refuses to load
  with a sentence, not a traceback; `require` raises MI0210 when a (test-patched) table says no.
- [ ] **Step 2–4:** implement, declare MI0210, and document `COMENI_PROTECTION_LEVEL` in
  `.env.example` with one line: *0 is open, and the only level built; see
  `docs/design/authoring-protocol.md`*. Commit —
  `feat(living): the protection level, with level 0 the only one built — 14.7.4.1 (#134)`.

### Task 14.7.4.2 (#150): the FASTQ inspector

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/inspect/__init__.py`,
  `services/inspect/fastq.py`, `packages/mendel-api/tests/fixtures/samples/` (four small heads),
  `packages/mendel-api/tests/test_inspect_fastq.py`

**Interfaces:**
- Produces: `Inspected(NamedTuple): type_id: str; states: list[str]; measurements: dict[str,
  ParamValue]`; `inspect_fastq(name: str, head: bytes) -> Inspected`;
  `INSPECTORS: dict[str, Callable]` keyed by type id (`{"fastq.reads": inspect_fastq}`);
  `inspector_for(name: str, head: bytes) -> tuple[str, Callable] | None`; code **MI0211**
  (*that file is not what its name says*).

- [ ] **Step 1: Fixtures.** Four heads, 8 records each: `s1_R1.fastq` (150 bp),
  `s1_R1.fastq.gz` (the same, gzipped), `short_1.fastq` (50 bp), and `not_fastq.fa` (a FASTA).
- [ ] **Step 2: Failing tests**

```python
def test_a_150bp_r1_is_paired_by_its_name_and_measured_by_its_records():
    got = inspect_fastq("s1_R1.fastq", (FIX / "s1_R1.fastq").read_bytes())
    assert got.type_id == "fastq.reads"
    assert got.measurements == {"read_length": 150, "paired": True}


def test_gzip_is_read_through():
    got = inspect_fastq("s1_R1.fastq.gz", (FIX / "s1_R1.fastq.gz").read_bytes())
    assert got.measurements["read_length"] == 150


def test_a_file_named_one_thing_and_holding_another_is_refused():
    """Review focus 5."""
    with pytest.raises(ValueError, match="MI0211"):
        inspect_fastq("x.fastq", (FIX / "not_fastq.fa").read_bytes())
```

- [ ] **Step 3: Implement.** Decompress when the head starts `\x1f\x8b` (`gzip.decompress` on a
  truncated head raises, so read with `zlib.decompressobj(16 + zlib.MAX_WBITS)` and keep what
  decodes). Records are 4 lines, line 1 starts `@` and line 3 starts `+`, otherwise MI0211.
  `read_length` is the modal sequence length. `paired` is `True` when the name matches
  `_R?[12](_\d+)?\.f(ast)?q(\.gz)?$`, and **absent** otherwise: a lone file named `reads.fq`
  proves nothing about pairing, and the gap stays for the person.
- [ ] **Step 4: Run and commit** —
  `feat(living): the FASTQ inspector — paired and read length, measured — 14.7.4.2 (#134)`.

### Task 14.7.4.3 (#151): `ValueSource.INSPECTED` (`comeni-core`)

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/review/answer.py`, and every exhaustive match on
  `ValueSource` (`grep -rn "ValueSource\." packages/ --include=*.py | grep -v tests`)
- Test: wherever `ValueSource` membership is asserted (`grep -rn "ValueSource" tests/`)

- [ ] **Step 1:** add `INSPECTED = "inspected"` with a docstring (*measured from a sample by a
  declared inspector; `Measured.by` names it*), and run `make check` to find what the new member
  breaks. **Stop and report if it touches `SCHEMA_VERSION`**: that is a `comeni-core` break, not
  a feature, and the operator decides.
- [ ] **Step 2:** fix what the run named, `make verify`, commit —
  `feat(core): ValueSource.INSPECTED — 14.7.4.3 (#134)`.

### Task 14.7.4.4 (#152): uploading a sample

**Files:**
- Modify: `packages/mendel-api/pyproject.toml` (`python-multipart>=0.0.9`, as `wiener-api` has),
  `routes/authoring.py`, `services/authoring.py`
- Create: `packages/mendel-api/src/mendel_api/services/samples.py`
- Test: `packages/mendel-api/tests/test_authoring_samples.py`

**Interfaces:**
- Produces: `POST /api/pipeline/authoring/{session_id}/samples` (multipart `file`) →
  `AuthoringSampleRead { sample: str, facts: list[Fact] }`;
  `samples.store(session_id, name, head) -> str` under
  `settings.workspace_root / "samples" / session_id`, keeping the first 4 MiB;
  `samples.delete_all(session_id)`; the gap option `upload`.

- [ ] **Step 1: Failing tests:** uploading `s1_R1.fastq` to a session whose pending gap is
  `fastq.reads` records `fastq.reads` (MEASURED), `read_length` 150 and `paired` True (MEASURED,
  `sample` set), and the next gap is neither of those; a file over the cap is stored truncated and
  still inspected; the route refuses MI0210 when `require(UPLOAD)` says no; MI0211 leaves the gap
  pending and records nothing.
- [ ] **Step 2–3: Implement.** `require(Crossing.UPLOAD)` first; store; `inspector_for`; append the
  facts; `FACT_ADDED`; `offer_next_gap`. A type with no inspector (a FASTA) answers with a notice:
  *the characteriser arrives in 14.7.5; tell me what it is for now*, and the gap stays. `compose_goal`
  maps `MEASURED` to `ValueSource.INSPECTED` with `by="inspect:fastq"`. Every gap gains the option
  `upload` beside *not sure*, and *not sure* now **asks for the upload** instead of recording OPEN.
- [ ] **Step 4:** `make client`, run the tests, commit —
  `feat(living): upload a sample, measured by its inspector — 14.7.4.4 (#134)`.

### Task 14.7.4.5 (#153): the page — upload on a gap card

**Files:**
- Modify: `frontend/src/build/living/blocks/GapCard.tsx`, `GoalCard.tsx`,
  `useAuthoringSession.ts` (a `useUploadSample` mutation, per `reported.test.ts`'s rule that a
  mutation is a hook returning it)
- Test: `GapCard.test.tsx`, `Conversation.test.tsx`

- [ ] **Step 1: Failing tests:** a gap card has *Upload a file* and posts the chosen file; while
  uploading it says so; the goal card shows `read_length 150 · measured from s1_R1.fastq`.
- [ ] **Step 2–3: Implement, and run** `npx vitest run`, `npx tsc -b`. Commit —
  `feat(living): upload a file from a gap card — 14.7.4.5 (#134)`.

### Task 14.7.4.6 (#154): the ladder, then walk scenario 1 by uploading

- [ ] **Step 1:** the full ladder, as in 14.7.3.8.
- [ ] **Step 2: Walk it:** upload a real paired FASTQ head, see `paired` and `read_length`
  measured and not asked, answer the genome and annotation, confirm, and see STAR chosen at
  **tier 3** with the premise *measured*. Then plan 14.7.5 and 14.7.6 from what the walk shows.
- [ ] **Step 3:** issues for every defect, the execution record, close #134.

---

## Execution record

| Task | What was done differently from the plan | Why |
|---|---|---|

- **14.7.2.1 (2026-09-28).** Step 7's two refusals against the real object: setting `card`
  planned → *built edge read_goal→card touches a planned node*; adding a second built
  `read_goal→done` GOAL_RETURNED → *understanding on goal_returned leads to both goal_review and
  complete*. Both restored. The derived table equals today's hand-written one already
  (`PROTOCOL.transitions() == state.TRANSITIONS`), checked by hand ahead of 14.7.2.2's test.
  Plan said 13 tests; there are 12.
- **14.7.2.2 (2026-09-28).** Step 2 failed as expected on `RETRY_TARGETS` and the retry into
  `building`. Step 6: deleting `card→read_goal` GOAL_REVISED failed
  `test_the_derived_machine_is_the_one_that_was_written_by_hand` and
  `test_every_arrow_in_the_diagram_is_a_transition[goal_review-goal_revised-understanding]`
  (*MI0200: a session in goal_review cannot handle goal_revised*); restored. MI0212's refusal
  lists the resumable phases on a second line, the way MI0200 lists onward events. Only
  `understanding` and `resolving` can fail, so no stored `failed_from` is outside the new set.
