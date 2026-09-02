import subprocess
import sys

from support.paths import ROOT

STUB = ROOT / "packages/comeni-core/src/comeni_core/goal/profile.pyi"


def test_the_committed_stub_matches_the_declarations():
    """Staleness is safe — a stale stub costs autocomplete, never correctness — which is
    exactly why nobody would notice it rotting. CI notices."""
    result = subprocess.run(
        [sys.executable, "tools/generate_types.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_stub_types_each_declared_measurement():
    stub = STUB.read_text()
    assert 'Literal["read_length"]' in stub
    assert "-> int | None" in stub
    assert 'Literal["forward", "reverse", "unstranded"] | None' in stub


def test_the_stub_keeps_a_fallback_for_an_undeclared_id():
    """A laboratory's own measurement is not in this repository's declarations, and
    `get` still has to type-check for it."""
    assert "def get(self, measurement_id: str)" in STUB.read_text()


def test_the_stub_is_valid_python():
    """The first version wrapped a long overload onto a line starting `-> ...`.

    It read fine and was a syntax error, which a type checker reports as "cannot parse"
    and then silently ignores the whole module — so the stub would have been worse than
    absent while every other test here passed.
    """
    import ast

    ast.parse(STUB.read_text())


def test_the_stub_declares_the_whole_module():
    """A `.pyi` replaces its module rather than adding to it.

    Stubbing only `DataProfile` would make `Measured` invisible to every type checker,
    which is a correctness cost, not an autocomplete one — and would void the reason
    generation is safe here at all.
    """
    import comeni_core.goal.profile as module

    stub = STUB.read_text()
    public = [
        name
        for name, obj in vars(module).items()
        if not name.startswith("_") and getattr(obj, "__module__", None) == module.__name__
    ]
    missing = [name for name in public if f"class {name}(" not in stub]
    assert missing == [], f"{STUB.name} does not declare: {', '.join(missing)}"


def test_comeni_core_is_marked_as_typed():
    """PEP 561: without `py.typed`, an installed package's stubs are ignored outright."""
    assert (ROOT / "packages/comeni-core/src/comeni_core/py.typed").exists()
