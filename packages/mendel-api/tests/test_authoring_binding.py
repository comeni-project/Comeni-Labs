"""The diagram and the shell agree (spec §3.2, §9): every acting node has one handler, every
handler an acting node; and nothing but the dispatcher moves a session."""

import ast
from pathlib import Path

from mendel_api.services import session
from mendel_authoring.protocol import PROTOCOL

SRC = Path(__file__).resolve().parents[1] / "src" / "mendel_api"


def test_every_acting_node_has_a_handler_and_every_handler_a_node():
    bound = session._bound()
    acting = {n.id for n in PROTOCOL.nodes if n.built and n.acts}
    assert acting, "no acting node: the comparison would hold vacuously"
    assert set(bound) == acting


def _outside_move(tree: ast.Module, path: Path) -> list[ast.AST]:
    """Every node of `tree`, except inside `services/authoring.py`'s `move`: the test-setup
    function (ruling 5) is the one place a session still moves by event."""
    skipped: set[int] = set()
    if path.relative_to(SRC).as_posix() == "services/authoring.py":
        for fn in tree.body:
            if isinstance(fn, ast.FunctionDef) and fn.name == "move":
                skipped |= {id(n) for n in ast.walk(fn)}
    return [n for n in ast.walk(tree) if id(n) not in skipped]


def _calls(name: str) -> list[str]:
    found = []
    files = sorted(SRC.rglob("*.py"))
    assert files, "no source found: the scan reads the wrong folder"
    for path in files:
        for node in _outside_move(ast.parse(path.read_text()), path):
            if isinstance(node, ast.Call):
                f = node.func
                called = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if called == name:
                    found.append(f"{path.relative_to(SRC)}:{node.lineno}")
    return found


def test_nothing_in_the_shell_calls_advance():
    """Outside the test-setup `move`: the diagram, not a hand-written event, moves a session."""
    assert _calls("advance") == []


def test_nothing_in_the_shell_moves_a_session_by_event():
    """Ruling 5 of 14.7.8.1b: `authoring.move` is setup for tests. Its own definition is not a
    call; `forge_state.move` moves a forge adaptation, not a session."""
    assert [c for c in _calls("move") if c.startswith("services/authoring")] == []


_WRITES = {"values", "PipelineAuthoringSession", "_swap"}
"""The three ways a row's columns are written: an `update(...).values(...)`, the row's
constructor, and `_swap`. A `phase=` on anything else (`AuthoringDecided(phase=…)`) is a
reply carrying the phase, not a write."""


def test_only_the_dispatcher_writes_the_phase():
    writers = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            called = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if called in _WRITES and any(k.arg == "phase" for k in node.keywords):
                writers.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert writers, "no writer at all: the scan reads the wrong thing"
    # The dispatcher; `open_session`'s constructor (stage ①, plan 1c); `move`'s `.values()`
    # (test setup, ruling 5 of 1b).
    assert {w.split(":")[0] for w in writers} == {"services/session.py",
                                                   "services/authoring.py",
                                                   "stages/describe.py"}, writers
    assert len([w for w in writers if w.startswith("services/authoring.py")]) == 1, writers
