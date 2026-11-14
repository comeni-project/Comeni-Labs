"""MD0027: a measurer piece imports and calls only what pieces may (#487).

The check the inspector-pieces guard ran, as a lint rule: the forge's draft layer, its publish
check and the registry's CI hold drafted parser code to it too.
"""

from mendel_compiler.registry_lint import lint, piece_problems


def test_allowed_code_has_no_problems():
    assert piece_problems("from comeni_inspect.outcome import Value\nimport re\n") == []


def test_each_reach_is_named():
    code = "import os\nopen('x')\nfrom . import y\n"
    assert piece_problems(code) == ["<open()>", "<relative import>", "os"]


def test_a_syntax_error_is_a_problem():
    found = piece_problems("def (")
    assert len(found) == 1 and found[0].startswith("syntax error")


def test_lint_reports_md0027_without_a_layout(tmp_path):
    (tmp_path / "registry.yml").write_text("name: forge-draft\nrequires_format: 2\n")
    piece = tmp_path / "measurers" / "measures" / "x" / "piece"
    piece.mkdir(parents=True)
    (piece / "x.py").write_text("import socket\n")
    (piece / "test_x.py").write_text("import os\n")  # tests are not piece code
    found = lint(tmp_path)
    assert [d.code for d in found] == ["MD0027"]
    assert "socket" in found[0].summary


def test_the_gaps_the_tripwire_had_are_closed():
    """Issue 489: builtins through `globals()`, files through `FileIO` and `GzipFile(path)`, and
    the calls that corrupt or stall the step's JSON report."""
    code = ("import io, gzip\nglobals()\nlocals()\nio.FileIO('x')\ngzip.GzipFile('x')\n"
            "print(1)\ninput()\nbreakpoint()\n")
    assert piece_problems(code) == ["<FileIO()>", "<GzipFile(path)>", "<breakpoint()>",
                                    "<globals()>", "<input()>", "<locals()>", "<print()>"]


def test_a_gzip_stream_wrapped_by_its_fileobj_is_allowed():
    assert piece_problems("import gzip\ndef open(stream):\n"
                          "    return gzip.GzipFile(fileobj=stream)\n") == []
