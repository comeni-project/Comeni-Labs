"""Protect the deprecated exports and prevent new repository consumers of the shim."""

import ast
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
"""Repository root resolved locally so the package test also runs on its own."""

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
"""Historical public surface, independent of the module under test."""


def test_the_shim_exports_the_pre_rename_surface() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import mendel_ai

    assert set(mendel_ai.__all__) == PRE_RENAME
    for name in PRE_RENAME:
        assert hasattr(mendel_ai, name), f"{name} is in __all__ and not on the module"


def test_the_shim_hands_back_the_same_objects() -> None:
    """Re-exports retain identity so cross-package ``isinstance`` checks remain valid."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import mendel_ai

    import comeni_ai

    for name in PRE_RENAME:
        assert getattr(mendel_ai, name) is getattr(comeni_ai, name), name


def test_importing_it_warns() -> None:
    """Reload the cached module to observe its import-time deprecation warning."""
    import importlib

    import mendel_ai

    with pytest.warns(DeprecationWarning, match="comeni_ai"):
        importlib.reload(mendel_ai)


def test_the_shim_carries_no_implementation() -> None:
    """Keep behavior in ``comeni-ai`` by allowing only exports, the warning, and ``__all__``."""
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
    """Require repository code to import the replacement package directly."""
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
