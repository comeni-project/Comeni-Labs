"""The two checks that keep CLAUDE.md short and its paths real (#118)."""

import sys
from pathlib import Path

from support.paths import ROOT

sys.path.insert(0, str(ROOT / "tools"))  # how test_architecture.py imports check_links
import check_doc_paths as cdp  # noqa: E402
import check_doc_sizes as cds  # noqa: E402


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "design").mkdir(parents=True)
    (tmp_path / "docs" / "design" / "here.md").write_text("x")
    (tmp_path / "packages" / "p" / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "packages" / "p" / "src" / "pkg" / "mod.py").write_text("x")
    return tmp_path


def test_a_dead_path_is_reported_with_its_line(tmp_path):
    root = _tree(tmp_path)
    text = "one\nsee `docs/design/gone.md`\nand `docs/design/here.md`\n"
    assert cdp.dead_paths(text, root) == [(2, "docs/design/gone.md")]


def test_a_package_module_path_resolves_under_src(tmp_path):
    root = _tree(tmp_path)
    assert cdp.dead_paths("`pkg/mod.py` and `pkg/mod.py:12`", root) == []


def test_what_is_not_a_path_is_not_reported(tmp_path):
    """A checker whose output is mostly noise stops being read (check_links.py's lesson)."""
    root = _tree(tmp_path)
    text = ("`uv run pytest tests/guards/` `https://x.org/a.md` `registry/tools/**/main.nf` "
            "`comeni_core.layered.stack()` `--registry X` `<package>-v<version>` "
            "`git show 83c873d^:docs/design/wiener.md`")
    assert cdp.dead_paths(text, root) == []


def test_it_finds_the_dead_paths_in_claude_md_as_it_was():
    """A regex matching nothing passes every file. Measured before the cleanup."""
    before = (ROOT / "tests" / "fixtures" / "claude-md-2026-09-28.md").read_text()
    assert len(cdp.dead_paths(before, ROOT)) >= 20


def test_a_bare_filename_is_live_if_the_repository_has_one_by_that_name(tmp_path):
    """`tokens.test.ts` names a real file without its directory; `wiener.md` names one that the
    2026-09-02 rework deleted. The first is a reference, the second is dead."""
    root = _tree(tmp_path)
    names = {"here.md", "mod.py"}
    assert cdp.dead_paths("`here.md` `mod.py` `gone.md`", root, names=names) == [(1, "gone.md")]


def test_a_bare_extension_is_not_a_path(tmp_path):
    assert cdp.dead_paths("the emitted `.nf` and a `.pyi`", _tree(tmp_path)) == []


def test_the_budget_names_the_file_and_says_compact(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x\n" * 301)
    assert cds.over_budget(tmp_path, {"CLAUDE.md": 300}) == [("CLAUDE.md", 301, 300)]


def test_the_budgets_are_the_specs():
    assert cds.BUDGETS == {"CLAUDE.md": 300, "docs/notes/now.md": 150}


def test_the_live_brief_and_its_companions_pass_both_checks():
    """CI runs pytest, not `make doc-paths`/`make doc-sizes`, so without this a pull request could
    push CLAUDE.md past its budget or add a dead path and merge green (review of #118). A missing
    file fails here too: a check over a file that is not there passes on nothing."""
    for name in cdp.FILES:
        assert (ROOT / name).exists(), f"{name} is missing; the checks would pass vacuously"
        assert cdp.dead_paths((ROOT / name).read_text(), ROOT) == [], name
    assert cds.over_budget(ROOT, cds.BUDGETS) == []
