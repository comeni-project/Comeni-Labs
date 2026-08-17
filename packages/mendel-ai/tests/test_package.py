"""The package exists, is importable, and is typed.

`uv sync` installs nothing you do not depend on: a workspace member listed only in
`[tool.uv.sources]` is never installed and its imports fail at the first use rather than at
sync. This test is what turns that into a fast failure.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_package_imports() -> None:
    import mendel_ai  # noqa: F401


def test_the_package_ships_a_py_typed_marker() -> None:
    assert (ROOT / "packages" / "mendel-ai" / "src" / "mendel_ai" / "py.typed").exists()


def test_the_root_project_depends_on_it() -> None:
    """Not just `[tool.uv.sources]` — that says where a member comes from, not that we want it."""
    manifest = (ROOT / "pyproject.toml").read_text()
    assert '"mendel-ai"' in manifest
    assert "mendel-ai = { workspace = true }" in manifest


def test_it_is_findable_as_an_installed_distribution() -> None:
    assert importlib.util.find_spec("mendel_ai") is not None
