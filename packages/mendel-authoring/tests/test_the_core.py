"""`mendel-authoring` is the protocol's core: pure, and the shell's arrow points at it."""


def test_the_package_imports():
    import mendel_authoring

    assert mendel_authoring.__doc__



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
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    tree = ast.parse((root / "tools" / "generate_protocol_doc.py").read_text())
    imported = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported, "the generator imports nothing: the test reads the wrong file"
    assert not any(m.startswith("mendel_api") for m in imported)
