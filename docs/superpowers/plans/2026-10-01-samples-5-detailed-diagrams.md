# Samples 5 — one general diagram, and detailed ones — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The protocol diagram splits into a general one and detailed ones, all generated into `docs/design/diagrams/`; the first detailed diagram, *Inspecting a sample*, draws every step and every way out of an upload, all on our server; and the upload branch of the general diagram turns solid.

**Architecture:** A `Node` in `PROTOCOL` may carry a `detail`: a nested `Protocol` checked when it loads like the main one, whose steps sit inside the parent node's phase and carry no events, so `state.TRANSITIONS` is unchanged. `tools/generate_protocol_doc.py` writes the whole folder — the general diagram, one file per detail, and a README index — and `--check` fails on a stale, missing or orphaned file. The general diagram marks a node that has a detail.

**Tech Stack:** pydantic 2, Mermaid (rendered by GitHub), pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-samples-and-inspectors-design.md` §11. Part 14.7.6.5 of #134. Depends on part 4 (the upload is built, so its nodes may be).

## Global Constraints

- **The protocol object is the only definition** (consultant spec §5): the state machine is derived from it and the diagrams are generated from it. Nothing here is hand-drawn.
- **A detail cannot move the session:** its edges carry no events and its built nodes share the parent node's phase.
- **Generated files are whole files**, never blocks spliced into hand-written pages (`generate_diagnostics_doc.py` records why).
- Planned parts stay dashed; a node is built only if what it draws exists after parts 1–4.
- Comments and docstrings match the repository's style. A loop is not an assertion.

## Review Focus

1. **A detail whose node is built while its parent is planned**: refused, like a built edge touching a planned node. Pinned in Task 1.
2. **A stray file in `docs/design/diagrams/`** (a diagram whose detail was deleted): `--check` fails naming it. Pinned in Task 2.
3. **Node ids that collide between the general diagram and a detail** (`admit` in both): each diagram is its own Mermaid document, so this is legal; a test pins that both render. Pinned in Task 2.
4. **An old link to `docs/design/authoring-protocol-diagram.md`** anywhere outside the journal and archives: `make links` fails on it. Pinned in Task 3.
5. **The derived state machine**: identical before and after (the upload's edges carry `FACT_ADDED` only where a click already did). Pinned in Task 3.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `packages/mendel-api/src/mendel_api/authoring/protocol.py` | `Node.detail`, `Protocol.title`/`slug`, the checks, `to_mermaid` marks a detailed node, `INSPECTING`, the upload branch built |
| Modify `tools/generate_protocol_doc.py` | write the folder: general, details, README; `--check` over the folder |
| Create `docs/design/diagrams/README.md`, `authoring-protocol.md`, `inspecting-a-sample.md` | generated |
| Delete `docs/design/authoring-protocol-diagram.md` | moved |
| Modify `docs/design/authoring-protocol.md`, `protocol.py` docstring, `Makefile:105` | the new paths |
| Test: `packages/mendel-api/tests/test_authoring_protocol.py`, `tests/repo/test_protocol_doc.py` (create) | |

---

### Task 1: A node may carry a detail

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/protocol.py:50-130`
- Test: `packages/mendel-api/tests/test_authoring_protocol.py`

**Interfaces:**
- Produces: `Protocol.title: str = "The authoring protocol"`, `Protocol.slug: str = "authoring-protocol"`; `Node.detail: Protocol | None = None`; `Protocol.details() -> list[Protocol]` (every detail, depth-first, declaration order).

- [x] **Step 1: Write the failing tests**

```python
from mendel_api.authoring.protocol import Actor, Edge, Node, Protocol, Stage
from mendel_api.authoring.types import Event, Phase


def _detail(phase=Phase.GATHERING, built=True, event=None):
    return Protocol(
        title="Inside", slug="inside",
        stages=(Stage(id="s", title="On our server"),),
        nodes=(
            Node(id="a", stage="s", actor=Actor.ENGINE, label="A", phase=phase, built=built),
            Node(id="b", stage="s", actor=Actor.ENGINE, label="B", phase=phase, built=built),
        ),
        edges=(Edge(source="a", target="b", event=event, built=built),),
    )


def _with(detail, parent_built=True):
    return Protocol(
        stages=(Stage(id="g", title="G"),),
        nodes=(Node(id="p", stage="g", actor=Actor.ENGINE, label="P",
                    phase=Phase.GATHERING if parent_built else None, built=parent_built, detail=detail),),
        edges=(),
    )


def test_a_node_may_carry_a_detail():
    assert _with(_detail()).details()[0].slug == "inside"


def test_a_detail_edge_cannot_move_the_session():
    with pytest.raises(ValueError, match="cannot move the session"):
        _with(_detail(event=Event.FACT_ADDED))


def test_a_detail_step_is_in_its_parents_phase():
    with pytest.raises(ValueError, match="phase"):
        _with(_detail(phase=Phase.BUILDING))


def test_a_built_detail_under_a_planned_node_is_refused():
    with pytest.raises(ValueError, match="planned"):
        _with(_detail(phase=None, built=True), parent_built=False)


def test_the_machine_ignores_details():
    assert _with(_detail()).transitions() == {}
```

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest packages/mendel-api/tests/test_authoring_protocol.py -q`
Expected: FAIL — `Protocol` has no `title`/`slug`; `Node` has no `detail`.

- [x] **Step 3: Implement**

`Node.detail: "Protocol | None" = None` (and `Node.model_rebuild()` after `Protocol` is defined). `Protocol.title`, `Protocol.slug` with the defaults above. In `_consistent`, after the existing checks:

```python
        for node in self.nodes:
            if node.detail is None:
                continue
            for step in node.detail.nodes:
                if step.built and not node.built:
                    raise ValueError(f"{node.id}'s detail has built step {step.id!r} under a planned node")
                if step.built and step.phase is not node.phase:
                    raise ValueError(f"{node.id}'s detail step {step.id!r} is not in its phase {node.phase}")
            for edge in node.detail.edges:
                if edge.event is not None:
                    raise ValueError(f"{node.id}'s detail edge {edge.source}→{edge.target} cannot move the session")
```

```python
    def details(self) -> list["Protocol"]:
        """Every detail, depth first, in declaration order: what the generator writes."""
        found = []
        for node in self.nodes:
            if node.detail is not None:
                found += [node.detail, *node.detail.details()]
        return found
```

The detail's own `_consistent` runs when it is constructed, so its stages, nodes and edges are checked by the same code.

- [x] **Step 4: Run them to see them pass**

Run: `uv run pytest packages/mendel-api/tests/test_authoring_protocol.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add packages/mendel-api/src/mendel_api/authoring/protocol.py packages/mendel-api/tests/test_authoring_protocol.py
git commit -m "feat(protocol): a node may carry a detailed diagram of its own steps (#134)"
```

---

### Task 2: The diagrams folder

**Files:**
- Modify: `tools/generate_protocol_doc.py`
- Modify: `packages/mendel-api/src/mendel_api/authoring/protocol.py` (`to_mermaid` marks a detailed node)
- Create (generated): `docs/design/diagrams/README.md`, `docs/design/diagrams/authoring-protocol.md`
- Delete: `docs/design/authoring-protocol-diagram.md`
- Test: `tests/repo/test_protocol_doc.py`

**Interfaces:**
- Produces: `generate_protocol_doc.pages() -> dict[str, str]` (file name → content: `README.md`, `<slug>.md` for the main protocol and every detail); `DIAGRAMS = docs/design/diagrams/`.

- [x] **Step 1: Write the failing tests**

```python
# tests/repo/test_protocol_doc.py
"""The diagrams folder is generated whole, and checked whole."""

import importlib.util

from support.paths import ROOT


def _generator():
    spec = importlib.util.spec_from_file_location("gen", ROOT / "tools/generate_protocol_doc.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_one_page_per_diagram_and_an_index():
    pages = _generator().pages()
    assert {"README.md", "authoring-protocol.md"} <= set(pages)
    for name in pages:
        if name != "README.md":
            assert f"({name})" in pages["README.md"], f"{name} is not listed in the index"


def test_check_fails_on_an_orphan(tmp_path, monkeypatch):
    gen = _generator()
    monkeypatch.setattr(gen, "DIAGRAMS", tmp_path)
    gen.main([])
    assert gen.main(["--check"]) == 0
    (tmp_path / "a-diagram-nobody-generates.md").write_text("x")
    assert gen.main(["--check"]) == 1


def test_check_fails_on_a_stale_page(tmp_path, monkeypatch):
    gen = _generator()
    monkeypatch.setattr(gen, "DIAGRAMS", tmp_path)
    gen.main([])
    (tmp_path / "authoring-protocol.md").write_text("stale")
    assert gen.main(["--check"]) == 1
```

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/repo/test_protocol_doc.py -q`
Expected: FAIL — no `pages`.

- [x] **Step 3: Implement the generator**

```python
DIAGRAMS = Path(__file__).parent.parent / "docs" / "design" / "diagrams"


def _page(protocol: Protocol) -> str:
    return f"{_header(protocol)}{FENCE}mermaid\n{to_mermaid(protocol)}{FENCE}\n"


def pages() -> dict[str, str]:
    every = [PROTOCOL, *PROTOCOL.details()]
    found = {f"{p.slug}.md": _page(p) for p in every}
    found["README.md"] = _index(every)
    return found


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    want = pages()
    if "--check" in argv:
        have = {p.name for p in DIAGRAMS.glob("*.md")} if DIAGRAMS.exists() else set()
        wrong = sorted(n for n, text in want.items() if not (DIAGRAMS / n).exists() or (DIAGRAMS / n).read_text() != text)
        orphaned = sorted(have - set(want))
        for name in wrong + orphaned:
            print(f"docs/design/diagrams/{name} disagrees with protocol.py — run: uv run python tools/generate_protocol_doc.py")
        return 1 if wrong or orphaned else 0
    DIAGRAMS.mkdir(parents=True, exist_ok=True)
    for name in sorted(set(p.name for p in DIAGRAMS.glob("*.md")) - set(want)):
        (DIAGRAMS / name).unlink()
    for name, text in want.items():
        (DIAGRAMS / name).write_text(text)
    return 0
```

`_header(p)`: the generated banner, `# {p.title}`, and the existing paragraph (built is solid, planned is dashed); for a detail, also *"A detail of [the authoring protocol](authoring-protocol.md). Everything here happens on our server."* when every stage title starts with *On our server* — otherwise say nothing about where. `_index(every)`: the banner, `# Diagrams`, one line per diagram: `- [Title](slug.md): <one line>` (the main one: *"the whole conversation, from what you want to what is built"*; a detail: *"the steps inside *<parent node label without <br/>>*"*).

In `to_mermaid`, a node with a detail gets `<br/>▸ detailed diagram: {detail.title}` appended to its label. (GitHub's Mermaid does not follow `click` links, so the marker plus the index is how a reader finds it.)

Run `uv run python tools/generate_protocol_doc.py`, `git rm docs/design/authoring-protocol-diagram.md`, and change `Makefile:105` to `uv run python tools/generate_protocol_doc.py --check` (unchanged command; confirm it still runs from `make docs`).

- [x] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/repo/test_protocol_doc.py -q && uv run python tools/generate_protocol_doc.py --check`
Expected: PASS, exit 0.

- [x] **Step 5: Commit**

```bash
git add tools/generate_protocol_doc.py packages/mendel-api/src/mendel_api/authoring/protocol.py docs/design/diagrams tests/repo/test_protocol_doc.py Makefile
git rm -q docs/design/authoring-protocol-diagram.md
git commit -m "docs(protocol): the diagrams live in one generated folder, with an index (#134)"
```

---

### Task 3: *Inspecting a sample*, and the upload branch built

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/protocol.py` (the gather stage's upload nodes and edges; `INSPECTING`)
- Modify: `docs/design/authoring-protocol.md:14` and any other link to the old diagram
- Regenerate: `docs/design/diagrams/`
- Test: `packages/mendel-api/tests/test_authoring_protocol.py`

**Interfaces:**
- Consumes: Task 1's `detail`; part 4's built behaviour (upload, protection, inspection, admission).
- Produces: `INSPECTING: Protocol` (slug `inspecting-a-sample`) on node `read_engine`; nodes `upload`, `safety`, `read_engine` built in `GATHERING`; `read_ai` stays planned.

- [ ] **Step 1: Write the failing tests**

```python
from mendel_api.authoring.protocol import PROTOCOL


def test_the_upload_branch_is_built_and_the_characteriser_is_not():
    nodes = {n.id: n for n in PROTOCOL.nodes}
    assert nodes["upload"].built and nodes["safety"].built and nodes["read_engine"].built
    assert not nodes["read_ai"].built


def test_reading_a_sample_has_its_detailed_diagram():
    detail = {n.id: n for n in PROTOCOL.nodes}["read_engine"].detail
    assert detail.slug == "inspecting-a-sample"
    labels = " ".join(n.label for n in detail.nodes)
    for step in ("4 MB", "protection", "extension", "unpack", "confirm", "measure", "undetermined", "admit"):
        assert step.lower() in labels.lower(), f"the detail does not draw {step!r}"
    assert all(s.title.startswith("On our server") for s in detail.stages)


def test_the_machine_did_not_change():
    from mendel_api.authoring import state as st

    assert st.TRANSITIONS == PROTOCOL.transitions()
    assert (Phase.GATHERING, Event.FACT_ADDED) in st.TRANSITIONS
```

Before Step 3, copy the current `PROTOCOL.transitions()` into the execution record (`uv run python -c "from mendel_api.authoring.protocol import PROTOCOL; print(sorted(PROTOCOL.transitions().items()))"`); after Step 3 it must print the same.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest packages/mendel-api/tests/test_authoring_protocol.py -q`
Expected: FAIL — `upload` is planned; `read_engine` has no detail.

- [ ] **Step 3: Implement**

The detail, declared above `PROTOCOL`:

```python
INSPECTING = Protocol(
    title="Inspecting a sample",
    slug="inspecting-a-sample",
    stages=(
        Stage(id="receive", title="On our server: receiving it"),
        Stage(id="process", title="On our server: in its own process, with limits"),
        Stage(id="admit", title="On our server: admitting what it measured"),
    ),
    nodes=(
        _built("got", "receive", _YOU, "You upload one file or a pair", _P.GATHERING, shape=Shape.ROUND),
        _built("head", "receive", _ENGINE, "Keep the first 4 MB of each<br/>(longer files are cut, never refused)", _P.GATHERING),
        _built("level", "receive", _SAFETY, "Does the protection level<br/>allow an upload?", _P.GATHERING, shape=Shape.GATE),
        _built("refused", "receive", _STOP, "Refused, and says why", _P.GATHERING),
        _built("claim", "receive", _ENGINE, "Which formats claim<br/>the extension?", _P.GATHERING, shape=Shape.CHOICE),
        _n("characterise", "receive", _AI, "The characteriser reads it<br/>(14.7.7)"),
        _built("unpack", "process", _ENGINE, "Unpack, capped at 16 MB", _P.GATHERING),
        _built("confirm", "process", _ENGINE, "Does the content<br/>confirm the format?", _P.GATHERING, shape=Shape.CHOICE),
        _built("unreadable", "process", _STOP, "Unreadable, with the reason<br/>(too large, too slow, not this format)", _P.GATHERING),
        _n("tie", "process", _YOU, "Several formats confirm:<br/>you choose", shape=Shape.CHOICE, border=Border.TIER4),
        _built("measure", "process", _ENGINE, "Measure: one pass,<br/>every measure fed", _P.GATHERING),
        _built("undetermined", "admit", _ENGINE, "Below its threshold:<br/>undetermined, left open", _P.GATHERING, border=Border.TIER4),
        _built("admit", "admit", _ENGINE, "Admit each value<br/>against the registry", _P.GATHERING),
        _built("stamped", "admit", _ENGINE, "Stamped: measured by<br/>its pieces and versions", _P.GATHERING, border=Border.TIER3),
        _built("back", "admit", _ENGINE, "Back to the next question", _P.GATHERING, shape=Shape.ROUND),
    ),
    edges=(
        _e("got", "head", built=True),
        _e("head", "level", built=True),
        _e("level", "refused", "no", built=True),
        _e("level", "claim", "level 0", built=True),
        _e("claim", "characterise", "none"),
        _e("claim", "unpack", "one or more", built=True),
        _e("unpack", "unreadable", "too large unpacked", built=True),
        _e("unpack", "confirm", built=True),
        _e("confirm", "unreadable", "no", built=True),
        _e("confirm", "tie", "several"),
        _e("confirm", "measure", "exactly one", built=True),
        _e("measure", "unreadable", "took too long", built=True),
        _e("measure", "undetermined", "not enough to say", built=True),
        _e("measure", "admit", "decided", built=True),
        _e("admit", "stamped", built=True),
        _e("stamped", "back", built=True),
        _e("undetermined", "back", built=True),
    ),
)
```

In `PROTOCOL`'s gather stage: `upload`, `safety` and `read_engine` become `_built(..., _P.GATHERING, ...)` (labels unchanged), `read_engine` gains `detail=INSPECTING`; the edges `reply → upload` (relabel *"upload a sample"*), `upload → safety`, `safety → read_engine` (*"level 0"*) and `read_engine → next_gap` gain `built=True` **without** events; `safety → read_ai` and `read_ai → next_gap` stay planned. Update the comment above them (*"built in 14.7.6; the characteriser stays planned (14.7.7)"*).

Regenerate: `uv run python tools/generate_protocol_doc.py`. Update `docs/design/authoring-protocol.md:14` to link `diagrams/authoring-protocol.md`, and add one sentence there: *"Detailed diagrams, beginning with [Inspecting a sample](diagrams/inspecting-a-sample.md), are listed in [the diagrams folder](diagrams/README.md)."* Fix the module docstring's path in `protocol.py`.

- [ ] **Step 4: Run them, the docs checks, and compare the machine**

Run: `uv run pytest packages/mendel-api/tests/test_authoring_protocol.py tests/repo/test_protocol_doc.py -q && make docs links doc-paths`
Expected: PASS; `make links` reports 0 broken; the transitions print matches the one recorded before Step 3.

- [ ] **Step 5: Look at it**

Open `docs/design/diagrams/inspecting-a-sample.md` rendered (GitHub preview, or `npx -y @mermaid-js/mermaid-cli -i <extracted .mmd> -o /tmp/claude-1000/inspect.png` and read the PNG). Check every arrow has its label, the stop nodes read red, planned parts are dashed, and the three stage boxes say *On our server*. Fix and regenerate if not.

- [ ] **Step 6: Commit, then `make check` separately**

```bash
git add packages/mendel-api/src/mendel_api/authoring/protocol.py packages/mendel-api/tests/test_authoring_protocol.py docs/design
git commit -m "feat(protocol): the upload is built, and inspecting a sample has its own diagram (#134)"
make check > /tmp/claude-1000/check.log 2>&1; tail -20 /tmp/claude-1000/check.log
```

---

## Execution record

*(Filled in while executing: rulings, measurements, deviations.)*

- **The machine:** `PROTOCOL.transitions()` printed identically before and after Task 3.
- **Rulings:** the protection level is asked before the head is kept (got → level → head), as part 4 built it; *no format claims it* is a built stop (*nothing reads this type yet*) beside the planned characteriser; a built *already said: your word stands* step under *admit*; a stage and a node may not share an id (found rendering: Mermaid refused `admit` as its own parent), so the detail's stages are `receiving`, `processing`, `admitting`; the general page links the protocol page as `../authoring-protocol.md`.
- **Looked at:** both diagrams rendered with mermaid-cli; every arrow labelled, stops red, planned dashed, the three stage boxes *On our server*, the detail marked on *Engine reads it exactly*.
