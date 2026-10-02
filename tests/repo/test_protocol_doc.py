"""The protocol diagram is generated from `protocol.py`, and a stale one fails the build."""

import subprocess
import sys

from support.paths import ROOT


def test_the_protocol_diagram_is_fresh():
    run = subprocess.run(
        [sys.executable, "tools/generate_protocol_doc.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def _generator():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen", ROOT / "tools/generate_protocol_doc.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_one_page_per_diagram_and_an_index():
    pages = _generator().pages()
    assert {"README.md", "authoring-protocol.md"} <= set(pages)
    diagrams = [name for name in pages if name != "README.md"]
    assert diagrams, "no diagram pages: the loop below would assert nothing"
    for name in diagrams:
        assert f"({name})" in pages["README.md"], f"{name} is not listed in the index"
        assert "```mermaid\nflowchart" in pages[name]


def test_check_fails_on_an_orphan(tmp_path, monkeypatch):
    """Review focus 2: a diagram whose detail was deleted is refused, named."""
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


def test_writing_removes_a_page_nothing_generates(tmp_path, monkeypatch):
    gen = _generator()
    monkeypatch.setattr(gen, "DIAGRAMS", tmp_path)
    (tmp_path / "gone.md").write_text("x")
    gen.main([])
    assert not (tmp_path / "gone.md").exists()
