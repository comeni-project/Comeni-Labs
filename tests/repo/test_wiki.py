"""The wiki's structure is a claim the build checks, not a convention anybody remembers.

`mkdocs.yml`'s `nav:` is the one place book order is declared — the folder layout mirrors it
so the two cannot drift, and this file is what says so.
"""

import pathlib

import yaml

ROOT = pathlib.Path(__file__).parent.parent.parent
CONFIG = ROOT / "mkdocs.yml"

BOOKS = ["Start here", "Handbook", "Tools", "Registry", "Internals"]


def _config() -> dict:
    """Parse `mkdocs.yml`, tolerating the `!!python/name:` tags Material uses."""
    text = CONFIG.read_text(encoding="utf-8")
    return yaml.safe_load(
        "\n".join(line for line in text.splitlines() if "!!python/" not in line)
    )


def _nav_titles(nav: list) -> list[str]:
    return [next(iter(entry)) for entry in nav if isinstance(entry, dict)]


def test_the_five_books_are_the_top_level_nav_in_order():
    nav = _config()["nav"]
    assert _nav_titles(nav) == BOOKS, (
        "mkdocs.yml's top-level nav is the book order and it is a spec decision (§4). "
        f"Expected {BOOKS}."
    )


def test_every_book_has_a_landing_page():
    for slug in ["start", "handbook", "tools", "registry", "internals"]:
        index = ROOT / "docs" / slug / "index.md"
        assert index.is_file(), f"{index.relative_to(ROOT)} is missing"


def test_provenance_is_excluded_from_the_site():
    """`notes/` and `superpowers/` are read on GitHub, never in a sidebar. Spec §7."""
    excluded = _config().get("exclude_docs", "")
    for prefix in ["notes/", "superpowers/"]:
        assert prefix in excluded, (
            f"{prefix} must be in exclude_docs — a file that is not in a book "
            "must not be silently published"
        )


def test_the_stage_stamp_is_declared_once():
    """Spec §6.1: stamp the stage, do not version the books."""
    extra = _config().get("extra", {})
    assert extra.get("stage") == "Alpha · pre-MVP"
