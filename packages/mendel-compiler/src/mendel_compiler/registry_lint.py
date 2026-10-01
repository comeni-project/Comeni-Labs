"""Is this layer arranged the way it says it is?

**The loader stays free and this is not part of it.** Invariant 11 says a file declares its own
kind, so `layers.load` reads one flat folder as happily as a tree, and an overlay a laboratory
assembled by hand keeps that freedom entirely. What the *curated* registry does is hold itself
to a layout **its own CI** enforces — which is nixpkgs's `pkgs/by-name` move, and Homebrew's,
and conda-forge's: the index is not the filesystem, and the filesystem is still made regular so
that a human can navigate it and a reviewer can see what a diff touches.

**A layer with no `layout:` in its manifest is unenforced**, which is every private overlay.
The rule and the enforcement are different things and this file is only the second.

`comeni-registry#1` removed the guarantee that a misfiled document was impossible *by
construction* — a contract used to live in `contracts/` and a misspelled `contract/` was caught
because nothing read it. A `declares:` line can only be *detected*, which is `MD0011`. This is
the other half of that trade: what a directory used to prevent, a lint now refuses.
"""

from collections.abc import Iterable
from pathlib import Path

from comeni_core import yaml_strict
from comeni_core.declared.layer import LayerManifest
from comeni_core.declared.layered import _KIND_OF, MANIFEST, MODULE_DIR, declared_kind
from comeni_core.diagnostics import coded

from mendel_compiler.conformance import Diagnostic

_SINGULAR = {kind: singular for singular, kind in _KIND_OF.items()}
"""Inverted from the map a `declares:` line reads, rather than written out again — two
spellings of one mapping is how they come to disagree, and `vocabularies` is not
`vocabularys`."""


def _at(where: Path, root: Path) -> str:
    """The path a person opens, relative to the layer — never absolute.

    An absolute path names the machine it was found on, which is the defect issue #46 found in
    `digest_of_directory` and the forge found in its own locators. A finding has to name a file
    a reviewer on another machine can open.
    """
    try:
        return str(where.relative_to(root))
    except ValueError:
        return str(where)


def lint(root: Path) -> list[Diagnostic]:
    """Every way this layer's arrangement disagrees with its own manifest.

    Sorted by path, because these are printed and a stable order is what makes a CI log
    diffable against yesterday's.
    """
    manifest = LayerManifest.of(root)
    if manifest is None or not manifest.layout:
        return []

    found: list[Diagnostic] = []
    found += _misfiled(root, manifest)
    found += _named_for_its_id(root)
    found += _one_role_per_file(root)
    found += _modules_are_declared(root)
    found += _tool_types_are_namespaced(root)
    found += _one_version_per_module(root)
    found += _nothing_reaches_out_of_its_tool(root)
    # **Opt-in by manifest** (#216): a layer that has not moved to one folder per tool, and
    # every private overlay, lints exactly as before.
    if "tool" in manifest.layout:
        found += _path_is_the_id(root)
        found += _every_tool_says_what_it_is(root)
        found += _tool_types_in_types(root)
    return sorted(found, key=lambda f: (f.where, f.code))


def _declared_files(root: Path) -> Iterable[tuple[Path, str]]:
    """Every file that declares a kind, with the singular it declares.

    Skips anything under a `module/` — that is upstream's tree, is not layer data, and ships
    its own `meta.yml` with no `declares:` line.
    """
    for path in sorted({*root.rglob("*.yml"), *root.rglob("*.yaml")}):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts) or MODULE_DIR in rel.parts:
            continue
        if path.name == MANIFEST and path.parent == root:
            continue
        yield path, _SINGULAR[declared_kind(path)]


def _misfiled(root: Path, manifest: LayerManifest) -> list[Diagnostic]:
    """A file whose kind is not under one of the directories its manifest names.

    **This is the check the directory used to make unnecessary.** A contract in `measurements/`
    loads perfectly — the loader reads `declares:` — and is invisible to everyone reading the
    tree, which is the guarantee comeni-registry#1 traded away.
    """
    found = []
    for path, singular in _declared_files(root):
        allowed = manifest.layout.get(singular)
        if allowed is None:
            continue
        rel = path.relative_to(root)
        if any(rel.is_relative_to(Path(one)) for one in allowed):
            continue
        found.append(
            Diagnostic(
                code="MD0013",
                where=_at(path, root),
                summary=(
                    f"declares `{singular}` and this layer keeps those under "
                    f"{', '.join(allowed)}"
                ),
                detail="",
                fix=f"move it under {allowed[0]}, or widen `layout.{singular}` in {MANIFEST}",
            )
        )
    return found


def _named_for_its_id(root: Path) -> list[Diagnostic]:
    """A vocabulary or measurement whose filename is not its `id:`.

    Their identity is the `id:` since `MD0012`, so the filename is free — and a file called
    one thing that declares another is a file nobody can find by searching for what it
    declares. The contract and module kinds are exempt: a contract is `contract.yml` beside
    the `module.yml` it binds to, which is this layer's convention and is checked elsewhere.
    """
    found = []
    for path, singular in _declared_files(root):
        if singular not in ("vocabulary", "measurement"):
            continue
        declared = (yaml_strict.load(path) or {}).get("id")
        stem = path.name.removesuffix(".yaml").removesuffix(".yml")
        if declared and stem != declared:
            found.append(
                Diagnostic(
                    code="MD0014",
                    where=_at(path, root),
                    summary=f"declares `id: {declared}` and is named {stem!r}",
                    detail="",
                    fix=f"rename it to {declared}{path.suffix}",
                )
            )
    return found


def _one_role_per_file(root: Path) -> list[Diagnostic]:
    """`roles.yml` held all nine at the layer root — one of the granularities §4.1 counts.

    The *format* permits several and always will: an overlay may keep them however it likes,
    because invariant 11 says the layout is the author's business. What this refuses is a
    layer that declared a `layout:` and then put nine roles in one file anyway.
    """
    found = []
    for path, singular in _declared_files(root):
        if singular != "role":
            continue
        declared = list((yaml_strict.load(path) or {}).get("roles", []))
        stem = path.name.removesuffix(".yaml").removesuffix(".yml")
        if len(declared) > 1:
            found.append(
                Diagnostic(
                    code="MD0015",
                    where=_at(path, root),
                    summary=f"declares {len(declared)} roles in one file: {', '.join(declared)}",
                    detail="",
                    fix="one role per file, named for the role — a diff should say which job "
                    "changed",
                )
            )
        elif declared and declared[0] != stem:
            found.append(
                Diagnostic(
                    code="MD0014",
                    where=_at(path, root),
                    summary=f"declares role {declared[0]!r} and is named {stem!r}",
                    detail="",
                    fix=f"rename it to {declared[0]}{path.suffix}",
                )
            )
    return found


def _modules_are_declared(root: Path) -> list[Diagnostic]:
    """A `module/` with no `module.yml` beside it.

    **The code would be invisible.** Nothing under `module/` is read as layer data, so a
    directory with no declaration is not in the stack's modules at all — and `MD0100` would
    report every contract binding to it as *unverified* while the source sat right there.
    """
    found = []
    for directory in sorted(root.rglob(MODULE_DIR)):
        if not directory.is_dir() or MODULE_DIR in directory.parent.relative_to(root).parts:
            continue
        if not (directory.parent / "module.yml").exists():
            found.append(
                Diagnostic(
                    code="MD0016",
                    where=_at(directory, root),
                    summary="holds a tool's source and nothing declares it",
                    detail="",
                    fix="add a `module.yml` beside it — `comeni-vendor add` writes both",
                )
            )
    return found


def _tool_types_are_namespaced(root: Path) -> list[Diagnostic]:
    """A type filed under a tool whose id is not namespaced by that tool.

    `genome.index.star` lives under `tools/nf-core/star/` because only STAR's own modules
    touch it. A type called `alignment.bam` filed there would be a *shared* type hidden inside
    one tool's directory, which is the arrangement the tool/subtool layout exists to prevent.
    """
    found = []
    tools = root / "tools"
    for path, singular in _declared_files(root):
        if singular != "vocabulary" or not path.is_relative_to(tools):
            continue
        declared = (yaml_strict.load(path) or {}).get("id", "")
        # `tools/nf-core/star/types/genome.index.star.yml` -> the tool is `star`.
        parts = path.parent.relative_to(tools).parts
        if len(parts) < 2:
            continue
        tool = parts[1]
        if tool not in str(declared).split("."):
            found.append(
                Diagnostic(
                    code="MD0017",
                    where=_at(path, root),
                    summary=(
                        f"declares `{declared}`, which is not namespaced by the tool it "
                        f"sits under ({tool})"
                    ),
                    detail="",
                    fix=f"move it to types/ if several tools touch it, or name it for {tool}",
                )
            )
    return found


def _one_version_per_module(root: Path) -> list[Diagnostic]:
    """Two contract versions for one module key, in one layer.

    **Bounded rather than designed around** (spec §9.3). One `module/` directory cannot hold
    two commits, so a layer carrying `star/align@1.11.0` and `@2.0.0` has one of them checked
    against source that is not its own — which is the drift `MD0104` exists to catch, arriving
    by a route it cannot see. Pinning a version is what a *higher layer* is for.
    """
    seen: dict[str, list[Path]] = {}
    for path, singular in _declared_files(root):
        if singular != "contract":
            continue
        declared = str((yaml_strict.load(path) or {}).get("id", ""))
        seen.setdefault(declared.split("@")[0], []).append(path)
    return [
        Diagnostic(
            code="MD0018",
            where=_at(sorted(paths)[1], root),
            summary=(
                f"a second contract for module {key!r} in one layer: "
                f"{', '.join(sorted(str(p.relative_to(root)) for p in paths))}"
            ),
            detail="",
            fix="one `module/` cannot hold two commits — pin a version in a higher layer",
        )
        for key, paths in sorted(seen.items())
        if len(paths) > 1
    ]


def _nothing_reaches_out_of_its_tool(root: Path) -> list[Diagnostic]:
    """A relative path in a tool's own file that climbs out of that tool's directory.

    **This is what makes "self-isolated" a checked property rather than a hope.** The whole
    argument for the tool/subtool layout is that everything about one tool is in one place and
    can be reviewed, moved or deleted as a unit. A `../../other-tool/thing` in a contract makes
    that false quietly, and the next person to move a directory finds out at build time.

    Deliberately a scan for `..` in *declared* files rather than a resolver of every path: the
    fields that hold paths are the author's to add, so a check that knew which fields to look
    at would go blind the day a new one arrives.
    """
    found = []
    tools = root / "tools"
    for path, _ in _declared_files(root):
        if not path.is_relative_to(tools):
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            body = line.split("#", 1)[0]
            if "../" not in body:
                continue
            found.append(
                Diagnostic(
                    code="MD0019",
                    where=_at(path, root),
                    summary=f"line {number} holds a relative path leaving this tool's directory",
                    detail="",
                    fix="a tool's files are self-isolated — reference a type by id, not by path",
                )
            )
            break
    return found


_ID_ROOTS = ("tools", "profilers")


def _path_is_the_id(root: Path) -> list[Diagnostic]:
    """MD0021. A contract or module whose folder is not its id.

    **The id is the address.** `nf-core/samtools/sort` is at `tools/nf-core/samtools/sort/`, so a
    lookup, a review and `forge land` all go straight to it. Only contracts and modules: their
    file names are fixed (`contract.yml`, `module.yml`), so the folder is the only place the id
    can be spelled.
    """
    found = []
    for path, singular in _declared_files(root):
        if singular not in ("contract", "module"):
            continue
        rel = path.parent.relative_to(root)
        if not rel.parts or rel.parts[0] not in _ID_ROOTS:
            continue
        key = str((yaml_strict.load(path) or {}).get("id", "")).split("@")[0]
        where = "/".join(rel.parts[1:])
        if key != where:
            found.append(
                Diagnostic(
                    code="MD0021",
                    where=_at(path, root),
                    summary=f"declares `{key}` and sits in {rel.parts[0]}/{where}/",
                    detail="",
                    fix=f"move it to {rel.parts[0]}/{key}/",
                )
            )
    return found


def _tool_folders(root: Path) -> set[Path]:
    """`tools/<org>/<tool>/` for every module key under `tools/`."""
    folders = set()
    for path, singular in _declared_files(root):
        if singular not in ("contract", "module"):
            continue
        rel = path.parent.relative_to(root)
        if len(rel.parts) >= 3 and rel.parts[0] == "tools":
            folders.add(root / Path(*rel.parts[:3]))
    return folders


def _every_tool_says_what_it_is(root: Path) -> list[Diagnostic]:
    """MD0022. A tool folder with no `tool.yml`."""
    return [
        Diagnostic(
            code="MD0022",
            where=_at(folder, root),
            summary="is a tool folder and has no tool.yml",
            detail="",
            fix="add tool.yml: `declares: tool`, its id, name and a description",
        )
        for folder in sorted(_tool_folders(root))
        if not (folder / "tool.yml").exists()
    ]


def _tool_types_in_types(root: Path) -> list[Diagnostic]:
    """MD0023. A vocabulary file under a tool, not in that tool's `types/`."""
    found = []
    for path, singular in _declared_files(root):
        if singular != "vocabulary":
            continue
        rel = path.relative_to(root)
        if rel.parts[0] != "tools" or len(rel.parts) < 4:
            continue
        if rel.parts[3] != "types":
            found.append(
                Diagnostic(
                    code="MD0023",
                    where=_at(path, root),
                    summary="is a type under a tool and not in that tool's types/",
                    detail="",
                    fix=f"move it to {'/'.join(rel.parts[:3])}/types/",
                )
            )
    return found


def report(root: Path) -> int:
    """Print the findings and return an exit code. `0` when the layer is arranged as declared."""
    found = lint(root)
    for finding in found:
        print(finding.render())
        print()
    manifest = LayerManifest.of(root)
    if manifest is None or not manifest.layout:
        print(f"{root}/{MANIFEST} declares no `layout:`, so there is nothing to enforce")
        return 0
    checked = sum(1 for _ in _declared_files(root))
    print(f"{checked} declared file(s) checked against `layout:` in {MANIFEST}")
    if found:
        print(coded("MD0013", f"{len(found)} file(s) are not where this layer says they go."))
        return 1
    return 0
