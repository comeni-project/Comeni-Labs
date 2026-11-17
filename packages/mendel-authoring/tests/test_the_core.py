"""`mendel-authoring` is the builder's pure core, and the shell's arrow points at it."""


def test_the_package_imports():
    import mendel_authoring

    assert mendel_authoring.__doc__


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
