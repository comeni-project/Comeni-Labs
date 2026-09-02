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


def test_the_tools_book_is_generated_not_committed():
    """Spec §6: a generated page in the repository is a page that can disagree with its source.

    `index.md` is the one hand-written file under `docs/tools/`; everything else arrives from
    `mendel docs` at build time and is ignored.
    """
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/docs/tools/*.md" in ignore
    assert "!/docs/tools/index.md" in ignore, (
        "index.md is authored and must be negated out of the ignore rule"
    )


def test_building_the_wiki_generates_the_catalogue_first():
    """`make wiki` must not be able to publish a stale or absent catalogue."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "wiki: wiki-tools" in makefile, (
        "make wiki must depend on wiki-tools, or the catalogue can go stale"
    )
