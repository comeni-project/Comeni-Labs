"""A `DataProfile` is built in exactly one place, and that place validates it.

Validation needs the measurement registry, which the model cannot hold, so it cannot live
in `__init__`. That makes an unvalidated profile constructible — and an unvalidated profile
with a nonsense measurement flows straight into routing.

**This scan is belt and braces, and saying so is load-bearing.** A2's fix re-checks every
measurement inside `resolve()`, so any profile that reaches resolution is validated
*regardless of how it was constructed*; that is the enforcement. This file raises the cost
of the mistake and makes it visible in review — which is a real job, and a different one.
Treating a spelling-matcher as the guarantee is exactly how A18 was written: `if name ==
"DataProfile"`, no alias resolution, one construction form, and
`from … import DataProfile as _DP; _DP.model_construct(...)` walked straight past it.
"""

import ast
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_purity import _imported_names  # noqa: E402  — the one alias resolver, reused

ALLOWED = {
    # the one validated constructor
    "packages/comeni-core/src/comeni_core/measurement.py",
    # the model's own module, where the class is defined
    "packages/comeni-core/src/comeni_core/profile.py",
}

BYPASSES = ("model_construct", "model_validate", "model_validate_json")
"""Pydantic's other constructors. `model_construct` skips validation entirely, and the two
`model_validate` forms build one from data a stranger may have written — a bundle, a goal
file. A18: the scan knew about `DataProfile(...)` and nothing else."""


def _aliases_of(tree: ast.AST) -> set[str]:
    """Every local name that resolves to `DataProfile` in this file.

    `import ... as` is the whole of A18: the guard compared a spelling, so renaming the
    import at the point of use was enough to disappear from it.
    """
    names = {"DataProfile"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "DataProfile":
                    names.add(alias.asname or alias.name)
    return names


def _constructions(tree: ast.AST, aliases: set[str], modules: set[str]) -> list[int]:
    """Every line that builds a `DataProfile`, by any spelling this scan can see."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # `DataProfile(...)`, or `_DP(...)` after an aliased import.
        if isinstance(func, ast.Name) and func.id in aliases:
            found.append(node.lineno)
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            # `DataProfile.model_construct(...)` or `_DP.model_validate_json(...)` — a
            # bypass on a name that resolves to the model.
            bypass = func.value.id in aliases and func.attr in BYPASSES
            # `profile.DataProfile(...)` — the model reached through its module.
            through_module = func.attr in aliases and func.value.id in modules
            if bypass or through_module:
                found.append(node.lineno)
    return found


def test_data_profile_is_constructed_in_one_place():
    root = pathlib.Path(__file__).parent.parent
    offenders = []
    for package in ("comeni-core", "mendel-resolver", "mendel-compiler"):
        for py in sorted((root / "packages" / package / "src").rglob("*.py")):
            if str(py.relative_to(root)) in ALLOWED:
                continue
            tree = ast.parse(py.read_text())
            aliases = _aliases_of(tree)
            modules = _imported_names(tree)
            for line in _constructions(tree, aliases, modules):
                offenders.append(f"{py.relative_to(root)}:{line}")
    assert offenders == [], (
        "build a profile through MeasurementRegistry.profile(), which validates it; "
        "these construct one directly: " + ", ".join(offenders)
    )
