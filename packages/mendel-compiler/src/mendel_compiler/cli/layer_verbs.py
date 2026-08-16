"""Verbs that act on a **layer** rather than on a pipeline.

`cli/__init__.py` splits by what a verb does to a pipeline — `resolve_verbs` produces one,
`artifact_verbs` acts on one that exists, `report` prints. `docs` does none of those: there is
no pipeline anywhere in its execution, and it never resolves. That is a third category, and it
gets its own module rather than being wedged into `report` because both happen to write text.
Wedging is how `cli.py` reached the 851 lines issue #41 had to split.

comeni-registry#2.
"""

from pathlib import Path

from mendel_resolver import layers

from mendel_compiler import tool_docs


def _pages(registries: list[Path]) -> dict[Path, str]:
    """Relative page path -> its content.

    Separated from the writing so the decision *what the pages are* can be tested without a
    filesystem, which is the same split that makes the emitter's golden-file tests possible.
    """
    loaded = layers.load(list(registries))
    return {
        Path(f"{tool}.md"): tool_docs.render(tool, contracts, loaded)
        for tool, contracts in tool_docs.tools_of(loaded.registry).items()
    }


def _docs_verb(registries: list[Path], out: Path, check: bool) -> int:
    """Write a page per tool, or with `--check` report the ones that disagree.

    **`--check` writes nothing at all.** A check that repairs what it measures reports success
    the second time it is run and can therefore never fail twice — which is how `make drift`
    printed "skipped" over twelve edited contracts while `make verify` stayed green.

    Three ways a page can disagree, and all three exit 1: it is stale, it is **missing**, and
    it describes a tool the registry no longer ships. The third is the one nothing else would
    catch — a contract is deleted, its page is not, and the page goes on documenting something
    that is gone.
    """
    pages = _pages(registries)
    if check:
        wrong = [
            path
            for path, content in pages.items()
            if not (out / path).exists() or (out / path).read_text() != content
        ]
        orphaned = [
            page.relative_to(out)
            for page in sorted(out.rglob("*.md"))
            if page.relative_to(out) not in pages
        ]
        for path in sorted(wrong) + sorted(orphaned):
            print(f"{out / path} disagrees with the registry")
        if wrong or orphaned:
            print(f"  run: mendel docs --registry <layer> --out {out}")
            return 1
        return 0

    for path, content in pages.items():
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    print(f"mendel: wrote {len(pages)} tool page(s) to {out}")
    return 0
