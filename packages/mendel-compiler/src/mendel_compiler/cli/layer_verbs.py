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

from mendel_compiler import orchestrate, tool_docs


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


def _conformance_verb(registries: list[Path]) -> int:
    """Does every contract in this layer agree with the module it is a binding for?

    **This verb could not have existed before Plan 5A**, and its absence is the argument for
    that plan. `MD0104`, `MD0105` and container drift compare a contract against a `main.nf`,
    and until the modules moved into the layer that file lived in another repository on another
    release cadence — so the only way to run the check was to build a pipeline, with a goal, in
    a checkout that had both. `comeni-registry`'s own CI could not ask the question about its
    own data.

    It takes a layer stack and nothing else. `MD0100` — *no module source to check this against*
    — is reported and **does not fail the run**: a laboratory wrapping bare containers is
    legitimate, and refusing it here would make the check unusable by exactly the people who
    need the rest of it. Everything else exits 1.

    Deliberately not `mendel build --gate lint`: that resolves a goal, so it only ever checks
    the contracts that happen to route. This checks all of them.
    """
    found = orchestrate.diagnostics_for(registries)
    for diagnostic in found:
        print(diagnostic.render())
        print()
    blocking = [d for d in found if d.code != "MD0100"]
    unverified = [d for d in found if d.code == "MD0100"]
    checked = len(_contracts(registries)) - len(unverified)
    print(f"{checked} contract(s) checked against their modules, {len(unverified)} unverified")
    if blocking:
        print(f"mendel: {len(blocking)} contract(s) disagree with their modules")
        print(f"  run: mendel explain {blocking[0].code}")
        return 1
    return 0


def _contracts(registries: list[Path]):
    return layers.load(registries).registry.all()


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
