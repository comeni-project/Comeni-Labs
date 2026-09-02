"""A released package declares a version for every workspace package it imports.

In a `uv` workspace `dependencies = ["comeni-core"]` resolves to the checkout and is fine. As a
**released artifact** it is meaningless: a `mendel-compiler` tarball would accept any
`comeni-core`, including one predating a type it imports. Tags became per-package and versions
independent on 2026-08-16, and independent versions are only real if the constraints are.
"""

import pathlib
import re
import tomllib

from support.paths import ROOT

PYPROJECTS = sorted((ROOT / "packages").glob("*/pyproject.toml"))
WORKSPACE = {"comeni-core", "mendel-resolver", "mendel-compiler"}


def _dependencies(path: pathlib.Path) -> list[str]:
    return tomllib.loads(path.read_text())["project"].get("dependencies", [])


def _name_of(requirement: str) -> str:
    return re.split(r"[><=!~\[;\s]", requirement, maxsplit=1)[0].strip()


def test_there_are_packages_to_check():
    """A scan that reaches nothing reports nothing and passes."""
    assert len(PYPROJECTS) >= 3, f"only {len(PYPROJECTS)} package manifests found"


def test_every_workspace_dependency_carries_a_lower_bound():
    unbounded = []
    for path in PYPROJECTS:
        for requirement in _dependencies(path):
            if _name_of(requirement) in WORKSPACE and not re.search(r">=\s*\d", requirement):
                unbounded.append(f"{path.parent.name}: {requirement!r}")
    assert unbounded == [], (
        "these depend on a workspace package with no lower bound, so a released artifact "
        "would accept any version of it:\n    " + "\n    ".join(unbounded)
    )


def test_no_workspace_dependency_carries_an_upper_bound():
    """A cap on a package released from this same repository is a promise to bump in lockstep.

    Which is the thing independent versioning exists to avoid: `mendel-compiler` pinning
    `comeni-core<0.3` means every `comeni-core` minor release breaks the compiler until somebody
    edits a file, and that is lockstep wearing a different hat.
    """
    capped = []
    for path in PYPROJECTS:
        for requirement in _dependencies(path):
            if _name_of(requirement) in WORKSPACE and re.search(r"[<~]=?\s*\d", requirement):
                capped.append(f"{path.parent.name}: {requirement!r}")
    assert capped == [], (
        "these cap a workspace package, which is lockstep by another name:\n    "
        + "\n    ".join(capped)
    )


def test_every_package_declares_the_workspace_packages_it_imports():
    """The bound is worthless if the dependency is missing entirely.

    Derived from the source rather than listed here: a package importing `comeni_core` and not
    declaring `comeni-core` works in a workspace and fails the moment somebody installs the
    wheel alone.
    """
    missing = []
    for path in PYPROJECTS:
        declared = {_name_of(r) for r in _dependencies(path)}
        source = "\n".join(
            file.read_text() for file in sorted((path.parent / "src").rglob("*.py"))
        )
        for package in WORKSPACE:
            module = package.replace("-", "_")
            imported = re.search(rf"^\s*(?:from|import)\s+{module}\b", source, re.M)
            if imported and package not in declared and path.parent.name != package:
                missing.append(f"{path.parent.name} imports {module} but does not depend on it")
    assert missing == [], "\n    ".join(missing)
