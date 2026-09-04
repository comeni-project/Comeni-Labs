"""The shim re-exports what it used to implement, and nothing in this repository uses it.

Two halves, and the second is the one that matters. A compatibility shim's failure mode is not
that it stops working — it is that it keeps working so well that new code is written against
it, and the window never closes.
"""

import ast
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
"""`support.paths` is only importable once `tests/` has been collected, and this file must
pass when `packages/mendel-ai` is run alone. Every other package-local test counts the same
way; `tests/README.md`'s rule is about files under `tests/`."""

PRE_RENAME = {
    "WHY_LIMIT",
    "Choice",
    "Choices",
    "Client",
    "ModelAccess",
    "ModelUnavailableError",
    "NoModelError",
    "Option",
    "Transport",
    "choose_many",
    "choose_one",
}
"""`mendel_ai.__all__` as it stood at 0.1.0, spelled out rather than imported from the module
under test — a test that reads its subject's own answer checks nothing."""


def test_the_shim_exports_the_pre_rename_surface() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import mendel_ai

    assert set(mendel_ai.__all__) == PRE_RENAME
    for name in PRE_RENAME:
        assert hasattr(mendel_ai, name), f"{name} is in __all__ and not on the module"


def test_the_shim_hands_back_the_same_objects() -> None:
    """Identity, not merely a name that resolves.

    A shim that re-implemented `Client` would satisfy `hasattr` and give a caller a second
    class — so `isinstance` against the real one would fail, which is the confusing shape.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import mendel_ai

    import comeni_ai

    for name in PRE_RENAME:
        assert getattr(mendel_ai, name) is getattr(comeni_ai, name), name


def test_importing_it_warns() -> None:
    """A silent deprecation is a deprecation nobody acts on.

    Reimported through `importlib` because the module is almost certainly already in
    `sys.modules` by the time this runs — the warning fires at import, once.
    """
    import importlib

    import mendel_ai

    with pytest.warns(DeprecationWarning, match="comeni_ai"):
        importlib.reload(mendel_ai)


def test_the_shim_carries_no_implementation() -> None:
    """One file, and every statement in it is an import, a warning or `__all__`.

    This is what stops the window from being reopened: a fix applied here rather than in
    `comeni-ai` would be a fix released consumers get and current ones do not.
    """
    src = ROOT / "packages" / "mendel-ai" / "src" / "mendel_ai"
    files = sorted(p.name for p in src.glob("*.py"))
    assert files == ["__init__.py"], f"the shim grew modules: {files}"

    tree = ast.parse((src / "__init__.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Expr | ast.Import | ast.ImportFrom):
            continue
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "__all__":
            continue
        if isinstance(node, ast.Expr | ast.Call):
            continue
        assert isinstance(node, ast.Expr), (
            f"line {node.lineno} is {type(node).__name__} — the shim must only re-export"
        )


def test_no_in_repo_module_imports_the_shim() -> None:
    """The half that closes the window.

    Every caller in this repository moved to `comeni_ai` in the same change that created this
    shim. A new one reaching for the old name has to fail here, in the suite, rather than in a
    year when somebody asks why `mendel-ai` is still shipped.
    """
    roots = [ROOT / "packages", ROOT / "tests", ROOT / "tools"]
    exempt = {
        (ROOT / "packages" / "mendel-ai" / "src" / "mendel_ai" / "__init__.py").resolve(),
        (ROOT / "packages" / "mendel-ai" / "tests" / "test_shim.py").resolve(),
    }
    offenders: list[str] = []
    scanned = 0
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if path.resolve() in exempt or ".venv" in path.parts:
                continue
            scanned += 1
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                    "mendel_ai"
                ):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
                if isinstance(node, ast.Import) and any(
                    alias.name.startswith("mendel_ai") for alias in node.names
                ):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert scanned > 50, f"the scan read only {scanned} files"
    assert offenders == [], (
        "these import the deprecated shim; import `comeni_ai` instead:\n  "
        + "\n  ".join(offenders)
    )
