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


def test_each_generated_page_contains_a_diagram():
    pages = _generator().pages()
    assert pages, "no diagram pages: the loop below would assert nothing"
    for content in pages.values():
        assert "```mermaid\nflowchart" in content


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
    (tmp_path / "gone.md").write_text(gen.BANNER + "# A detail that was deleted\n")
    assert gen.main([]) == 0
    assert not (tmp_path / "gone.md").exists()


def test_a_hand_written_page_is_never_deleted(tmp_path, monkeypatch):
    """Review of #134: writing deleted any page it did not generate, a hand-written one too."""
    gen = _generator()
    monkeypatch.setattr(gen, "DIAGRAMS", tmp_path)
    (tmp_path / "notes.md").write_text("# my notes\n")
    assert gen.main([]) == 1
    assert (tmp_path / "notes.md").exists()


def test_one_diagram_with_sections():
    """14.7.8.1: the sample's inside is a section of the one diagram, not a page of its own.
    One page per declared flow: the builder's, and the forge's (#364)."""
    pages = _generator().pages()
    assert set(pages) == {"authoring-protocol.md", "forging-protocol.md"}
    assert 'subgraph sample ["②a Inside: reading a sample"]' in pages["authoring-protocol.md"]
    assert "mendel_authoring/protocol.py" in pages["authoring-protocol.md"]
