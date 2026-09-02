"""The wiki's structure is a claim the build checks, not a convention anybody remembers.

`mkdocs.yml`'s `nav:` is the one place book order is declared — the folder layout mirrors it
so the two cannot drift, and this file is what says so.
"""

import pathlib
import sys
import tempfile

import pytest
import yaml
from mendel_compiler import tool_docs
from mendel_resolver import layers

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


def test_the_catalogue_is_reachable_by_clicking_not_only_searching():
    """A reader must be able to browse into the tool pages, not only find one by search.

    `docs/tools/index.md` is the one authored file under `docs/tools/`; the catalogue itself
    is generated (`tools/generate_tools_catalogue.py`, run by `make wiki-tools`) and gitignored
    like every other page `mendel docs` writes — but the *entry point* to it is a real nav
    reference, not a pointer to the search box.
    """
    nav = _config()["nav"]
    tools_entry = next(entry for entry in nav if next(iter(entry)) == "Tools")
    assert "tools/catalogue.md" in tools_entry["Tools"], (
        "the Tools nav must reference the generated catalogue page, so a reader reaches the "
        "tool pages by clicking through it"
    )


def test_the_catalogue_links_to_real_tool_pages_not_an_empty_shell():
    """A nav entry pointing at the catalogue proves nothing about the catalogue's own content —
    it would pass this file's other test even if the generator wrote nothing or wrote nonsense.

    Runs the real registry through `mendel-compiler`'s `tool_docs` — the same pure, offline,
    no-network, no-Docker path `mendel docs` takes — to produce real tool pages in a temp
    directory, then asserts the generator both produces something (an empty catalogue over a
    real registry is itself a bug) and names a link to every tool page it sits beside.
    """
    loaded = layers.load([ROOT / "registry"])
    tools = tool_docs.tools_of(loaded.registry)
    assert tools, "the registry produced no tools — there is nothing here to catalogue"

    with tempfile.TemporaryDirectory(prefix="catalogue-test-") as tmp:
        tools_dir = pathlib.Path(tmp)
        for tool, contracts in tools.items():
            page = tools_dir / f"{tool}.md"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(tool_docs.render(tool, contracts, loaded), encoding="utf-8")

        sys.path.insert(0, str(ROOT / "tools"))
        import generate_tools_catalogue

        catalogue = generate_tools_catalogue.build_catalogue(tools_dir)

    assert catalogue, "the generator produced an empty catalogue against a real registry"

    missing = [tool for tool in tools if f"]({tool}.md)" not in catalogue]
    assert missing == [], f"catalogue is missing a link to: {missing}"


MOVED = {
    "handbook/your-first-pipeline.md",
    "handbook/the-four-tiers.md",
    "handbook/how-tools-get-chosen.md",
    "handbook/the-stack.md",
    "handbook/reference/cli.md",
    "handbook/reference/pipeline-schema.md",
    "handbook/reference/goal-schema.md",
    "handbook/reference/diagnostics.md",
    "handbook/reference/glossary.md",
    "registry/writing-a-contract.md",
    "registry/making-a-choice-depend-on-your-data.md",
    "registry/your-labs-own-layer.md",
    "registry/reference/contract-schema.md",
    "registry/reference/rule-schema.md",
    "registry/reference/vocabulary-schema.md",
    "registry/reference/measurement-schema.md",
    "internals/releasing.md",
}

RETIRED = ["concepts", "guides", "reference", "tutorial.md", "README.md"]


@pytest.mark.parametrize("rel", sorted(MOVED))
def test_every_surviving_page_landed_in_its_book(rel: str):
    assert (ROOT / "docs" / rel).is_file(), f"docs/{rel} is missing — see the spec §7 move table"


@pytest.mark.parametrize("rel", RETIRED)
def test_the_old_layout_is_gone(rel: str):
    """The books ARE the folders. A leftover `guides/` is a second answer to 'where does
    this go', which is how the old split drifted from its own index pages."""
    assert not (ROOT / "docs" / rel).exists(), f"docs/{rel} should have been moved or deleted"
