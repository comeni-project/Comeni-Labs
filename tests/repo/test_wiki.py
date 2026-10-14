"""Documentation navigation preserves reader paths, catalogue access and existing URLs.

Diátaxis paths organize navigation independently of the physical page directories.
Historical notes and plans remain outside the published site.
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

PATHS = ["Tutorials", "How-to guides", "Reference", "Explanation"]


def _config() -> dict:
    """Parse `mkdocs.yml`, tolerating the `!!python/name:` tags Material uses."""
    text = CONFIG.read_text(encoding="utf-8")
    return yaml.safe_load(
        "\n".join(line for line in text.splitlines() if "!!python/" not in line)
    )


def _nav_titles(nav: list) -> list[str]:
    return [next(iter(entry)) for entry in nav if isinstance(entry, dict)]


def test_the_four_reader_paths_are_the_top_level_nav_in_order():
    nav = _config()["nav"]
    assert _nav_titles(nav) == PATHS, f"Expected documentation paths {PATHS}."


def test_every_reader_path_has_a_landing_page():
    nav = _config()["nav"]
    for title, slug in zip(PATHS, ["tutorials", "how-to", "reference", "explanation"], strict=True):
        relative = f"{slug}/index.md"
        index = ROOT / "docs" / relative
        assert index.is_file(), f"{index.relative_to(ROOT)} is missing"
        assert next(entry[title] for entry in nav if title in entry)[0] == relative


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
    """Generated tool pages are ignored; their authored introduction is outside that tree."""
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/docs/reference/tools/*.md" in ignore
    assert (ROOT / "docs/reference/tools.md").is_file()
    assert not (ROOT / "docs/tools").exists()


def test_building_the_wiki_generates_the_catalogue_first():
    """`make wiki` must not be able to publish a stale or absent catalogue."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "wiki: wiki-tools" in makefile, (
        "make wiki must depend on wiki-tools, or the catalogue can go stale"
    )


def test_the_catalogue_is_reachable_by_clicking_not_only_searching():
    """Reference navigation exposes the authored introduction and generated catalogue."""
    nav = _config()["nav"]
    reference = next(entry["Reference"] for entry in nav if "Reference" in entry)
    tools = next(entry["Available tools"] for entry in reference
                 if isinstance(entry, dict) and "Available tools" in entry)
    assert "reference/tools.md" in tools and "reference/tools/catalogue.md" in tools, (
        "Reference must expose both the tool introduction and generated catalogue"
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


CANONICAL_PAGES = {
    "tutorials/first-pipeline.md",
    "explanation/decision-tiers.md",
    "explanation/tool-selection.md",
    "how-to/development/local-stack.md",
    "reference/pipelines/cli.md",
    "reference/pipelines/pipeline-schema.md",
    "reference/pipelines/goal-schema.md",
    "reference/pipelines/diagnostics.md",
    "reference/pipelines/glossary.md",
    "how-to/registry/add-tool.md",
    "how-to/registry/write-rule.md",
    "how-to/registry/add-layer.md",
    "reference/registry/contract-schema.md",
    "reference/registry/rule-schema.md",
    "reference/registry/vocabulary-schema.md",
    "reference/registry/measurement-schema.md",
    "how-to/development/release.md",
}

RETIRED = [
    "concepts", "guides", "reference/cli.md", "tutorial.md", "README.md",
    "design", "handbook", "internals", "registry", "start", "tools", "status.md",
]


@pytest.mark.parametrize("rel", sorted(CANONICAL_PAGES))
def test_maintained_pages_have_their_canonical_destinations(rel: str):
    assert (ROOT / "docs" / rel).is_file(), f"docs/{rel} is missing"


@pytest.mark.parametrize("rel", RETIRED)
def test_the_old_layout_is_gone(rel: str):
    """Retired locations stay absent; reference/index.md is now a reader-path entry."""
    assert not (ROOT / "docs" / rel).exists(), f"docs/{rel} should have been moved or deleted"


def test_no_shipped_message_points_at_a_deleted_guide():
    """`docs/guides/contributing.md` has not existed since the file moved to `.github/`.

    Both of these are user-facing: one is printed when the registry submodule is missing, the
    other when a layer fails to load. A message naming a path that 404s is worse than no
    message, because the reader goes looking.
    """
    for rel in ["Makefile", "packages/mendel-resolver/src/mendel_resolver/layers.py"]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "docs/guides/contributing.md" not in text, (
            f"{rel} names a file that does not exist; it is .github/CONTRIBUTING.md"
        )


def test_specs_are_excluded_from_the_link_check():
    """`docs/superpowers/` is provenance like `docs/notes/`, and its links point at plans
    that may not exist yet."""
    text = (ROOT / "tools" / "check_links.py").read_text(encoding="utf-8")
    assert "superpowers" in text


CERTAINTY = {
    "--undecided": "the `Not built yet` marker, and a tier-4 question",
    "--measured": "a derived version stamp, and a tier-3 rule",
}


@pytest.mark.parametrize("token", sorted(CERTAINTY))
def test_the_theme_declares_the_certainty_tokens(token: str):
    """The wiki borrows the product's certainty colours rather than inventing docs colours,
    so a reader who has seen a tier-4 question on the canvas already knows what red means."""
    css = (ROOT / "docs" / "assets" / "comeni.css").read_text(encoding="utf-8")
    assert token in css, f"{token} missing — it is {CERTAINTY[token]}"


def test_the_theme_does_not_load_a_serif_display_face():
    """`--font-display` was a Georgia serif with no webfont loaded, and that was most of why
    the built front door did not look like the artboard it came from. Never again silently."""
    css = (ROOT / "docs" / "assets" / "comeni.css").read_text(encoding="utf-8")
    assert "Georgia" not in css and "serif;" not in css.replace("sans-serif;", "")
