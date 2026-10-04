# Consultant 1a — the core: `mendel-authoring` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The protocol, its state machine and its interpreter live in a new pure package. The protocol is one diagram with sections. A node can say whether it acts or waits, and an arrow can say which command or outcome takes it. The interpreter can run a protocol given those answers. Nothing in the running product changes yet.

**Architecture:** `packages/mendel-authoring` depends on `comeni-core` and `pydantic` only, and the purity guards hold it there. `protocol.py`, `state.py` and the session vocabulary (`Phase`, `Event`, `ProposalState`) move into it from `mendel-api`. `mendel_api.authoring.types` re-exports the three names so its 24 importers keep working. The sample's inside becomes a section of the one protocol, and `detail=` goes. `mendel_authoring.interpret` is pure: given the protocol, where a session is, what arrived, and a way to enter a node, it says where the session comes to rest. Part 1b binds the shell's handlers to it.

**Tech Stack:** Python 3.12, pydantic 2, uv workspace, pytest.

**Spec:** `docs/superpowers/specs/2026-10-04-the-consultant-build-design.md` §3, §7, §9, §10. This is part 14.7.8.1, split in two; see the ruling below. Issue #136.

## Global Constraints

- **`mendel-authoring` never imports `mendel-api`, FastAPI, SQLAlchemy, ARQ, a model client, or anything that reaches the network.** It depends on `comeni-core` and `pydantic` (spec §3.1).
- **It joins invariant 1** and both purity guards (spec §3.1).
- **The diagram's generator imports only `mendel-authoring`** (spec §3.1).
- **One protocol, one generated page** (spec §7).
- **Behaviour unchanged:** the existing suite passes, with only the edits named here (moved imports, the merged diagram's tests).
- Python tests always run with `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`; `make check` on its own before each commit; `make verify` after a change to `pyproject.toml` files.
- Guards are watched failing and recorded in `tests/fixtures/guard-ledger.md`.

## Rulings against the spec, for the operator

1. **Part 1 is split into 1a (this plan, the pure core) and 1b** (the shell: the stored node, the dispatcher, the handlers, the binding test, the stage modules). Labelling every arrow with its command or outcome depends on reading each route and job as it moves. A plan written before that would guess, and this repository's plans have repeatedly predicted types that did not exist. So 1b's plan is written after 1a lands. Cost if wrong: one more plan document.
2. **The blocks (cards) stay in the shell for now.** Spec §3.1 puts *blocks* in the core. They are the API's and the AI's shapes, and part 3 redesigns the step cards anyway, so they move then, once, in their final shape. Cost if wrong: a later move.
3. **`mendel_api.authoring.types` re-exports `Phase`, `Event` and `ProposalState`.** A re-export is not a second definition, and it spares 24 importers a churn that 1b reshapes again. Cost if wrong: 24 import lines later.
4. **The grouping keeps its name, `Stage`**, and gains `within_request`, rather than being renamed `Section`: the diagram already calls them stages. Cost if wrong: a rename.

## Review Focus

1. **A cycle in the protocol** (a showing node whose only arrow leads back to itself) must not hang the interpreter: it stops at a declared limit and says so. Pinned in Task 5.
2. **Two arrows out of one node taken by the same command or outcome** would make the run ambiguous. The protocol refuses to load. Pinned in Task 4.
3. **A command that names no arrow from where the session is** is refused with MI0216, naming the node and the command, never a `KeyError`. Pinned in Task 5.
4. **The merged diagram still draws every sample step built today**: the 14.7.6 and 14.7.7 tests that read the detail now read the section. Pinned in Task 3.
5. **The diagram page is regenerated, and the old page is gone**, with no dead link to it anywhere. Pinned in Task 3.

---

## File structure

| File | Responsibility |
|---|---|
| Create `packages/mendel-authoring/pyproject.toml`, `README.md`, `LICENSE`, `src/mendel_authoring/__init__.py`, `py.typed` | the package |
| Move `packages/mendel-api/src/mendel_api/authoring/protocol.py` → `packages/mendel-authoring/src/mendel_authoring/protocol.py` | the protocol and its drawing |
| Move `packages/mendel-api/src/mendel_api/authoring/state.py` → `packages/mendel-authoring/src/mendel_authoring/state.py` | the derived machine |
| Create `packages/mendel-authoring/src/mendel_authoring/types.py` | `Phase`, `Event`, `ProposalState`, `Command` |
| Create `packages/mendel-authoring/src/mendel_authoring/interpret.py` | `follow`, `run` |
| Move `packages/mendel-api/tests/test_authoring_protocol.py` → `packages/mendel-authoring/tests/test_protocol.py` | the protocol's tests |
| Create `packages/mendel-authoring/tests/test_interpret.py` | the interpreter's |
| Modify `packages/mendel-api/src/mendel_api/authoring/types.py` | re-export the three |
| Modify every `from mendel_api.authoring import state` / `.protocol` importer | the new home |
| Modify `pyproject.toml` (root), `tests/guards/test_purity.py`, `tests/guards/test_purity_runtime.py` | workspace, guards |
| Modify `tools/generate_protocol_doc.py` | one page, from the core |
| Delete `docs/design/diagrams/inspecting-a-sample.md` | merged |
| Modify `packages/comeni-core/src/comeni_core/diagnostics.yml` | MI0216 |
| Modify `CLAUDE.md`, `ARCHITECTURE.md`, `docs/design/invariants.md` §1 | invariant 1's list; the packages |

---

### Task 1: The package, and its purity

**Files:**
- Create: `packages/mendel-authoring/pyproject.toml`, `README.md`, `LICENSE` (a copy of `packages/mendel-resolver/LICENSE`), `src/mendel_authoring/__init__.py`, `src/mendel_authoring/py.typed`, `tests/test_package.py`
- Modify: `pyproject.toml` (root): `[tool.uv.sources]` and `dependencies`
- Modify: `tests/guards/test_purity.py` (`CLOSED_PACKAGES`), `tests/guards/test_purity_runtime.py:37` (`_PACKAGES`)

**Interfaces:**
- Produces: the importable package `mendel_authoring`.

- [x] **Step 1: Write the failing test**

`packages/mendel-authoring/tests/test_package.py`:

```python
"""`mendel-authoring` is the protocol's core: pure, and the shell's arrow points at it."""


def test_the_package_imports():
    import mendel_authoring

    assert mendel_authoring.__doc__
```

In `tests/guards/test_purity.py`, add to `CLOSED_PACKAGES`:

```python
    "mendel-authoring": {
        "collections", "collections.abc", "enum", "typing", "pydantic", "comeni_core",
        "mendel_authoring",
    },
```

and a note above the dict's closing, in the file's own style:

```python
# `mendel-authoring` was added 2026-10-04 as a whole package (14.7.8, the consultant build), and
# this is the sixth such note. It holds the authoring protocol — the diagram the engine runs —
# and its interpreter. **It allows nothing new**: every name on its line is on another pure
# package's line already. A protocol that knows a database, a queue or a model is a shell
# wearing the core's name, and this line is where that is refused rather than reviewed.
```

In `tests/guards/test_purity_runtime.py:37`: `_PACKAGES = ("comeni-core", "mendel-resolver", "mendel-compiler", "mendel-authoring")`.

- [x] **Step 2: Run them; expected FAIL**

`uv run pytest packages/mendel-authoring tests/guards/test_purity.py tests/guards/test_purity_runtime.py -q`
Expected: `ModuleNotFoundError: mendel_authoring`, and the purity guard's `test_each_guarded_package_has_source_to_scan` failing for the missing `src/`.

- [x] **Step 3: Create the package**

`packages/mendel-authoring/pyproject.toml`:

```toml
[project]
name = "mendel-authoring"
version = "0.1.0"
requires-python = ">=3.12"
description = "The authoring protocol — the diagram the engine runs — and its interpreter. Pure."
license = "Apache-2.0"
license-files = ["LICENSE"]
readme = "README.md"
authors = [{name = "Rafael Correia"}]

# A lower bound and no cap, as `mendel-resolver` argues (docs/guides/releasing.md).
dependencies = ["comeni-core>=0.1.0", "pydantic>=2.12"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mendel_authoring"]
```

`src/mendel_authoring/__init__.py`:

```python
"""The authoring protocol, and the interpreter that runs it.

**The diagram is the program.** `protocol.PROTOCOL` declares the conversation's sections, nodes
and arrows; `docs/design/diagrams/` is drawn from it, the session's legal moves are derived from
it (`state`), and `interpret` runs it. The shell (`mendel-api`) binds a handler to each acting
node and stores where each session rests; nothing here touches a row, a queue or a model.
"""
```

`README.md`: two sentences on what the package is and that it is pure, and a pointer to the
spec; no internal history.

Root `pyproject.toml`: add `"mendel-authoring"` to `dependencies` and
`mendel-authoring = { workspace = true }` to `[tool.uv.sources]`. Add `"mendel-authoring>=0.1.0"`
to `packages/mendel-api/pyproject.toml`'s `dependencies`.

Run `uv sync`.

- [x] **Step 4: Run them; expected PASS.** Then watch the guard fail: add `import fastapi` to
`__init__.py`, run `uv run pytest tests/guards/test_purity.py -q -k mendel`. Expected: FAIL
naming `fastapi`. Revert, and add a row to `tests/fixtures/guard-ledger.md`.

- [x] **Step 5: `make verify`, then commit.** `feat(authoring): mendel-authoring, the protocol's pure package (#136)`

---

### Task 2: The protocol, the machine and the vocabulary move into the core

**Files:**
- Create: `packages/mendel-authoring/src/mendel_authoring/types.py`
- Move (`git mv`): `protocol.py`, `state.py` (from `packages/mendel-api/src/mendel_api/authoring/`), and `packages/mendel-api/tests/test_authoring_protocol.py` → `packages/mendel-authoring/tests/test_protocol.py`
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (`Phase`, `Event`, `ProposalState` re-exported)
- Modify: every importer (find them with the grep in Step 3)
- Modify: `tools/generate_protocol_doc.py:14`

**Interfaces:**
- Produces: `mendel_authoring.types.{Phase, Event, ProposalState}`, `mendel_authoring.protocol.{PROTOCOL, Protocol, Node, Edge, Stage, Actor, Border, Shape, to_mermaid}` and `mendel_authoring.state.{advance, TRANSITIONS, RETRY_TARGETS, …}`, unchanged in behaviour.

- [ ] **Step 1: Write the failing test** (`packages/mendel-authoring/tests/test_package.py`)

```python
def test_the_core_owns_the_protocol_the_machine_and_the_vocabulary():
    from mendel_authoring import protocol, state, types

    assert protocol.PROTOCOL.nodes and state.TRANSITIONS
    assert {p.value for p in types.Phase} >= {"gathering", "building"}


def test_the_shell_reexports_the_vocabulary_it_does_not_own():
    from mendel_api.authoring import types as shell
    from mendel_authoring import types as core

    assert shell.Phase is core.Phase and shell.Event is core.Event
    assert shell.ProposalState is core.ProposalState


def test_the_generator_needs_nothing_from_the_shell():
    import ast
    from support_paths import ROOT  # see below

    tree = ast.parse((ROOT / "tools" / "generate_protocol_doc.py").read_text())
    imported = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(m.startswith("mendel_api") for m in imported)
```

`support_paths` is not on this package's path. Use `ROOT = Path(__file__).resolve().parents[3]`,
as the shell's tests do.

- [ ] **Step 2: Run them; expected FAIL** (`ImportError` on `mendel_authoring.protocol`).

- [ ] **Step 3: Move**

1. Cut `Phase`, `Event` and `ProposalState` (with their docstrings) from
   `mendel_api/authoring/types.py` into `mendel_authoring/types.py`. In their place in the shell:

   ```python
   from mendel_authoring.types import Event, Phase, ProposalState  # noqa: F401 — re-exported:
   # the core owns the session's vocabulary (14.7.8.1); the shell's importers keep this path.
   ```

   If anything else those three classes reference lives only in the shell's `types.py`, it moves
   too; if that would pull in a block, stop and record it in the execution record.
2. `git mv` `protocol.py` and `state.py` into `src/mendel_authoring/`. In each, replace
   `from mendel_api.authoring.types import …` with `from mendel_authoring.types import …`, and
   `from mendel_api.authoring.protocol import PROTOCOL` with `from mendel_authoring.protocol
   import PROTOCOL`.
3. Find every importer:
   `git grep -n -E "mendel_api\.authoring(\.| import )(protocol|state)\b" -- packages tests tools`
   and change each to `mendel_authoring`. This includes `from mendel_api.authoring import state
   as st` becoming `from mendel_authoring import state as st`.
4. `git mv packages/mendel-api/tests/test_authoring_protocol.py
   packages/mendel-authoring/tests/test_protocol.py`, and fix its imports.
5. `tools/generate_protocol_doc.py:14`: `from mendel_authoring.protocol import PROTOCOL,
   Protocol, to_mermaid`.

- [ ] **Step 4: Run them; expected PASS.** Then the whole suite:
`MENDEL_DATABASE_URL=… uv run pytest -q -x` (from the root). Expected: as before this task. The
protocol's purity is now guarded: `uv run pytest tests/guards -q`.

- [ ] **Step 5: `make check`, then commit.** `refactor(authoring): the protocol, its machine and the session's vocabulary move into the core (#136)`

---

### Task 3: One diagram, with sections

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/protocol.py` (`Stage.within_request`; `INSPECTING` folded into `PROTOCOL`; `Node.detail` and `Protocol.details()` removed)
- Modify: `packages/mendel-authoring/tests/test_protocol.py` (the detail tests become section tests)
- Modify: `tools/generate_protocol_doc.py` (one page)
- Delete: `docs/design/diagrams/inspecting-a-sample.md`; update `docs/design/diagrams/README.md`
- Modify: any doc linking the deleted page (`git grep -n "inspecting-a-sample" -- docs`)

**Interfaces:**
- Produces: `Stage.within_request: bool`, and the section `sample` whose node ids are prefixed `sample_`.

- [ ] **Step 1: Write the failing tests** (in `test_protocol.py`, replacing the block of detail tests from `# ── a node may carry a detailed diagram` through `test_the_machine_ignores_details`, and the three 14.7.6 and 14.7.7 tests that read `read_engine`'s detail)

```python
# ── one diagram, with sections (14.7.8.1) ───────────────────────────────────────────────────


def _sample():
    return [n for n in p.PROTOCOL.nodes if n.stage == "sample"]


def test_the_sample_inside_is_a_section_of_the_one_protocol():
    stages = {s.id: s for s in p.PROTOCOL.stages}
    assert stages["sample"].within_request
    labels = " ".join(n.label for n in _sample()).lower()
    for step in ("4 mb", "protection", "extension", "unpack", "confirm", "measure",
                 "undetermined", "admit", "nothing reads", "8 kb", "families", "read by ai"):
        assert step in labels, f"the section does not draw {step!r}"
    assert all(n.id.startswith("sample_") for n in _sample())


def test_a_section_within_a_request_never_moves_the_session():
    inside = {n.id for n in _sample()}
    moving = [e for e in p.PROTOCOL.edges if e.event is not None
              and e.source in inside and e.target in inside]
    assert moving == []


def test_the_upload_enters_the_section_and_the_section_returns_to_the_questions():
    edges = {(e.source, e.target) for e in p.PROTOCOL.edges}
    assert ("upload", "sample_level") in edges and ("sample_back", "next_gap") in edges
    assert not {"safety", "read_engine", "read_ai"} & {n.id for n in p.PROTOCOL.nodes}


def test_the_characteriser_is_drawn_step_by_step_and_built():
    nodes = {n.id: n for n in p.PROTOCOL.nodes}
    for step in ("door", "excerpt", "families", "types", "ai_admit", "ai_stamped", "hand_back"):
        assert nodes[f"sample_{step}"].built, step


def test_there_is_one_diagram():
    assert not hasattr(p.PROTOCOL, "details") and not hasattr(p, "INSPECTING")
```

Keep `test_the_protection_level_is_asked_before_a_byte_is_kept` and `test_every_way_out_of_an_upload_is_drawn` by rewriting their lookups from `…["read_engine"].detail` to `p.PROTOCOL`, with ids prefixed `sample_` (`("sample_level", "sample_head")`, `("sample_confirm", "sample_back")` and so on).

- [ ] **Step 2: Run them; expected FAIL.**

- [ ] **Step 3: Fold the section in**

In `protocol.py`:
1. `Stage` gains `within_request: bool = False`, documented: *its nodes are the steps one request takes and reports; none moves the session, and the validator refuses an event on an edge inside it.*
2. Remove `Node.detail`, `Protocol.details()`, the detail checks in `_consistent`, and the
   slug-uniqueness check (one page now). Add to `_consistent`: an edge with an `event` whose two
   ends are both in a `within_request` stage is refused (*a within-request section never moves the
   session*).
3. Move `INSPECTING`'s three stages into `PROTOCOL.stages` as **one** stage,
   `Stage(id="sample", title="②a Inside: reading a sample", within_request=True)`, placed after
   `gather`. Its nodes join `PROTOCOL.nodes`, each id prefixed `sample_` and each in stage
   `sample`. **Drop its `got` node**: the main protocol's `upload` is the same step. Its edges join
   `PROTOCOL.edges`, with both ends prefixed.
4. **Replace the main protocol's coarse sample nodes with the section.**
   - Remove the nodes `safety`, `read_engine` and `read_ai`, and every edge touching them.
   - Add `_e("upload", "sample_level", "uploaded", built=True)` and
     `_e("sample_back", "next_gap", built=True)`.
5. In `_node`, delete the *detailed diagram* marker. In `to_mermaid`, nothing else changes: a
   stage is still a subgraph.

In `tools/generate_protocol_doc.py`: write only `PROTOCOL`'s page. The *A detail of …* header
branch and the index of details go. The index page `docs/design/diagrams/README.md` lists one
diagram. `git rm docs/design/diagrams/inspecting-a-sample.md`. Fix every link to it
(`git grep -n "inspecting-a-sample"`).

- [ ] **Step 4: Run them; expected PASS.** `uv run python tools/generate_protocol_doc.py &&
uv run python tools/generate_protocol_doc.py --check`, then `make links doc-paths`. Read the
generated mermaid: the `sample` subgraph sits after `gather`, and nothing is drawn twice.

- [ ] **Step 5: `make check`, then commit.** `refactor(authoring): one diagram, with sections — the sample's inside is a section (#136)`

---

### Task 4: A node acts or waits; an arrow names what takes it

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/types.py` (`Command`)
- Modify: `packages/mendel-authoring/src/mendel_authoring/protocol.py` (`Node.acts`, `Node.waits`, `Edge.on`, the validator)
- Test: `packages/mendel-authoring/tests/test_protocol.py`

**Interfaces:**
- Produces:
  - `types.Command`, a `StrEnum` with: `describe`, `answer_gap`, `upload_sample`, `confirm_goal`, `revise_goal`, `choose_pacing`, `continue`, `answer_fact`, `choose`, `ask`, `keep`, `retry` (spec §3.2). 1b adds a job's result commands as it binds them.
  - `Node.acts: bool = False` (a handler runs on entry).
  - `Node.waits: bool = False` (the session may rest here for a command).
  - `Edge.on: str | None = None` (from a waiting node, a `Command` value; from an acting node, an outcome the handler returns; `None`, the one way on from a node that passes straight through).

- [ ] **Step 1: Write the failing tests**

```python
from mendel_authoring.protocol import Edge, Node, Protocol, Stage
from mendel_authoring.types import Command


def _proto(nodes, edges):
    return Protocol(stages=(Stage(id="s", title="s"),), nodes=tuple(nodes), edges=tuple(edges))


def _node(id, **kw):
    return Node(id=id, stage="s", actor=p.Actor.ENGINE, label=id, phase=Phase.GATHERING,
                built=True, **kw)


def test_two_arrows_out_of_one_node_cannot_answer_to_the_same_name():
    with pytest.raises(ValueError, match="twice"):
        _proto([_node("a", acts=True), _node("b"), _node("c")],
               [Edge(source="a", target="b", on="yes", built=True),
                Edge(source="a", target="c", on="yes", built=True)])


def test_a_waiting_node_is_left_only_by_a_declared_command():
    with pytest.raises(ValueError, match="not a command"):
        _proto([_node("a", waits=True), _node("b")],
               [Edge(source="a", target="b", on="whatever", built=True)])
    _proto([_node("a", waits=True), _node("b")],
           [Edge(source="a", target="b", on=Command.CONTINUE.value, built=True)])


def test_a_node_has_at_most_one_way_straight_through():
    with pytest.raises(ValueError, match="straight through"):
        _proto([_node("a", waits=True), _node("b"), _node("c")],
               [Edge(source="a", target="b", built=True), Edge(source="a", target="c", built=True)])


def test_the_real_protocol_still_loads():
    assert p.PROTOCOL.nodes
```

The last test pins that the existing protocol, where no node is yet marked and no arrow named,
loads unchanged. A node that neither acts nor waits, with several unnamed arrows, is how the
protocol is drawn today. **So the *straight through* rule applies only once a node takes part**:
when it `acts` or `waits`, or any of its arrows has an `on`. 1b turns the rule on everywhere as it
marks each node.

- [ ] **Step 2: Run them; expected FAIL.**

- [ ] **Step 3: Implement**

`types.py`:

```python
class Command(StrEnum):
    """What a person (or, from 1b, a job) can do to a session: each is an arrow out of a
    waiting node (spec §3.2). Refused with MI0216 wherever no arrow names it."""

    DESCRIBE = "describe"
    ANSWER_GAP = "answer_gap"
    UPLOAD_SAMPLE = "upload_sample"
    CONFIRM_GOAL = "confirm_goal"
    REVISE_GOAL = "revise_goal"
    CHOOSE_PACING = "choose_pacing"
    CONTINUE = "continue"
    ANSWER_FACT = "answer_fact"
    CHOOSE = "choose"
    ASK = "ask"
    KEEP = "keep"
    RETRY = "retry"
```

`protocol.py`, `Node`:

```python
    acts: bool = False
    """A handler runs when a session enters this node (14.7.8.1). It returns the outcome that
    names the arrow on, or nothing, and the session rests here."""
    waits: bool = False
    """A session may rest here, until a command names an arrow out."""
```

`Edge`:

```python
    on: str | None = None
    """What takes this arrow: a `Command` out of a waiting node, an outcome out of an acting one;
    `None` for the one way straight on (14.7.8.1)."""
```

In `_consistent`, after the existing loop over edges:

```python
        commands = {c.value for c in Command}
        for node in self.nodes:
            out = [e for e in self.edges if e.source == node.id and e.built]
            named = [e.on for e in out if e.on is not None]
            twice = sorted({n for n in named if named.count(n) > 1})
            if twice:
                raise ValueError(f"{node.id}: {twice} names two arrows out — twice is ambiguous")
            if node.waits and not node.acts and node.built:
                # Only a command leaves a node that rests and does nothing: an outcome would
                # need a handler to return it.
                strays = sorted(set(named) - commands)
                if strays:
                    raise ValueError(f"{node.id} waits, and {strays} is not a command")
            takes_part = node.acts or node.waits or bool(named)
            if takes_part and sum(1 for e in out if e.on is None) > 1:
                raise ValueError(f"{node.id} has more than one way straight through")
        return self
```

- [ ] **Step 4: Run them; expected PASS**, and the whole `packages/mendel-authoring` suite.

- [ ] **Step 5: `make check`, then commit.** `feat(authoring): a node acts or waits, and an arrow names what takes it (#136)`

---

### Task 5: The interpreter

**Files:**
- Create: `packages/mendel-authoring/src/mendel_authoring/interpret.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (MI0216, after MI0215)
- Test: `packages/mendel-authoring/tests/test_interpret.py`

**Interfaces:**
- Produces:
  - `interpret.follow(protocol: Protocol, at: str, on: str | None) -> Edge`: the built arrow out of `at` that `on` names (`None`: the one way straight on). Raises `Refused` (a `ValueError` carrying MI0216) when there is none.
  - `interpret.run(protocol: Protocol, at: str, command: str, enter: Callable[[str], str | None], *, limit: int = 64) -> Ran`: follows `command` out of `at`, then, for each node entered, calls `enter(node_id)` if it `acts`, taking the arrow its outcome names, or resting there on `None`. A node that does not act is passed straight through if it has one way on and does not `wait`; otherwise the session rests there.
  - `interpret.Ran(at: str, path: list[str])`: where it rests, and every node entered, in order.

- [ ] **Step 1: Write the failing tests** (`test_interpret.py`)

```python
"""The interpreter: the protocol run as a program (14.7.8.1). Pure — `enter` is the shell's."""

import pytest
from mendel_authoring.interpret import Refused, run
from mendel_authoring.protocol import Actor, Edge, Node, Protocol, Stage
from mendel_authoring.types import Command, Phase


def _n(id, **kw):
    return Node(id=id, stage="s", actor=Actor.ENGINE, label=id, phase=Phase.GATHERING,
                built=True, **kw)


def _e(a, b, on=None):
    return Edge(source=a, target=b, on=on, built=True)


GATHER = Protocol(
    stages=(Stage(id="s", title="s"),),
    nodes=(
        _n("reply", waits=True), _n("said"), _n("next_gap", acts=True),
        _n("ask", acts=True, waits=True), _n("card", waits=True),
    ),
    edges=(
        _e("reply", "said", Command.ANSWER_GAP.value), _e("said", "next_gap"),
        _e("next_gap", "ask", "a_gap"), _e("next_gap", "card", "nothing_missing"),
        _e("ask", "reply", "phrased"),
    ),
)


def test_an_answer_runs_to_the_next_question_and_rests_there():
    entered = []

    def enter(node):
        entered.append(node)
        return {"next_gap": "a_gap"}.get(node)  # ask queues phrasing and rests

    ran = run(GATHER, "reply", Command.ANSWER_GAP.value, enter)
    assert ran.at == "ask" and ran.path == ["said", "next_gap", "ask"]
    assert entered == ["next_gap", "ask"], "only acting nodes are entered"


def test_the_last_answer_runs_to_the_goal_card():
    ran = run(GATHER, "reply", Command.ANSWER_GAP.value,
              lambda node: {"next_gap": "nothing_missing"}.get(node))
    assert ran.at == "card"


def test_a_command_no_arrow_names_is_refused_by_name():
    with pytest.raises(Refused, match="MI0216") as caught:
        run(GATHER, "card", Command.ANSWER_GAP.value, lambda node: None)
    assert "card" in str(caught.value) and "answer_gap" in str(caught.value)


def test_an_outcome_no_arrow_names_is_refused_by_name():
    with pytest.raises(Refused, match="MI0216") as caught:
        run(GATHER, "reply", Command.ANSWER_GAP.value, lambda node: "a_typo")
    assert "next_gap" in str(caught.value) and "a_typo" in str(caught.value)


def test_a_cycle_stops_at_the_limit_and_says_so():
    loop = Protocol(
        stages=(Stage(id="s", title="s"),),
        nodes=(_n("a", waits=True), _n("b", acts=True), _n("c", acts=True)),
        edges=(_e("a", "b", Command.CONTINUE.value), _e("b", "c", "on"), _e("c", "b", "on")),
    )
    with pytest.raises(Refused, match="MI0216.*64"):
        run(loop, "a", Command.CONTINUE.value, lambda node: "on")
```

- [ ] **Step 2: Run them; expected FAIL** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

`diagnostics.yml`, after MI0215:

```yaml
MI0216:
  emitted_by: api
  concern: workflow
  says: "that is not possible from here"
  fires_on: [authoring]
  refuses: true
  fix: |
    Read where the conversation is: the action named is not one of the ways on from there.
  explanation: |
    The authoring protocol is the program the builder runs (docs/design/diagrams/). From each
    place in it, only the arrows drawn lead on; an action or an outcome that names no arrow from
    where the session is, is refused here rather than half-done.
```

Run `uv run python tools/generate_diagnostics_doc.py`.

`interpret.py`:

```python
"""Run the protocol (14.7.8.1): where a session rests, and the nodes it passes on the way.

**Pure.** `enter` is the shell's: it runs an acting node's handler and returns its outcome, or
`None` to rest. Everything else — which arrow, when to stop, what to refuse — is here, read off
the protocol, so the diagram is the program and not a picture of it.
"""

from collections.abc import Callable
from typing import NamedTuple

from comeni_core.diagnostics import coded

from mendel_authoring.protocol import Edge, Node, Protocol


class Refused(ValueError):
    """MI0216: no arrow from here is named by what arrived."""


class Ran(NamedTuple):
    at: str
    path: list[str]


def follow(protocol: Protocol, at: str, on: str | None) -> Edge:
    found = [e for e in protocol.edges if e.built and e.source == at and e.on == on]
    if not found:
        named = "the way straight on" if on is None else repr(on)
        raise Refused(coded("MI0216", f"from {at!r}, nothing leads on by {named}"))
    return found[0]


def run(
    protocol: Protocol,
    at: str,
    command: str,
    enter: Callable[[str], str | None],
    *,
    limit: int = 64,
) -> Ran:
    nodes: dict[str, Node] = {n.id: n for n in protocol.nodes}
    node = nodes[follow(protocol, at, command).target]
    path = [node.id]
    while len(path) <= limit:
        if node.acts:
            outcome = enter(node.id)
            if outcome is None:
                return Ran(node.id, path)
            node = nodes[follow(protocol, node.id, outcome).target]
        elif not node.waits and _one_way_on(protocol, node.id):
            node = nodes[follow(protocol, node.id, None).target]
        else:
            return Ran(node.id, path)
        path.append(node.id)
    raise Refused(coded("MI0216", f"ran {limit} nodes from {at!r} without resting: a cycle"))


def _one_way_on(protocol: Protocol, at: str) -> bool:
    return sum(1 for e in protocol.edges if e.built and e.source == at and e.on is None) == 1
```

The cycle test expects the limit's number in the message: `{limit}` is there.

- [ ] **Step 4: Run them; expected PASS.** `uv run pytest packages/mendel-authoring -q`.

- [ ] **Step 5: `make check`, then commit.** `feat(authoring): the interpreter — the protocol run as a program (#136)`

---

### Task 6: The docs say so

**Files:** `CLAUDE.md` (invariant 1; *Packages*), `docs/design/invariants.md` §1, `ARCHITECTURE.md` (the package list), `docs/notes/now.md` only if a line there names `mendel_api/authoring/protocol.py`.

- [ ] **Step 1:** `git grep -n "mendel_api/authoring/protocol\|authoring/protocol.py\|dag-core\` do not" -- CLAUDE.md docs ARCHITECTURE.md`, and update each:
  - **Invariant 1:** *`comeni-core`, `mendel-resolver`, `mendel-compiler`, `mendel-authoring`, `wiener-core` and `dag-core` do not reach the network.*
  - **The *Packages* paragraph:** `mendel-authoring` (the authoring protocol, the diagram the builder runs, and its interpreter; pure).
  - **Every pointer to `mendel_api/authoring/protocol.py`** becomes `mendel_authoring/protocol.py`, including the diagram page's banner (it is generated: regenerate).
- [ ] **Step 2:** `make check` (including `doc-paths` and `doc-sizes`), then commit. `docs: mendel-authoring joins invariant 1; the protocol's new home (#136)`

---

## Execution record

*(Filled in while executing.)*
