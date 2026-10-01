# Samples 1 — the registry, one folder per tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The registry reads as five things (tools, profilers, inspectors, vocabulary, rules), the path of every tool file is its id, every tool says what it is in a `tool.yml` with its docs beside it, and the API stops hashing the whole registry on every request.

**Architecture:** The engine learns the new layout first, behind the manifest: the new lint checks run only when `registry.yml`'s `layout:` declares the `tool` kind, so the engine lands green against today's registry. A new declared kind, `tool`, joins `DeclaredKind` and `Layers`. `mendel docs --in-place` writes each tool's page as `README.md` in that tool's own folder. The API keys its cache on a file-metadata signature and computes the exact digest only when the signature changes. Then the registry moves, on a branch in `comeni-registry`, and this repository bumps the submodule.

**Tech Stack:** Python 3.12, pydantic 2, pytest, git (submodule `registry/` → `comeni-project/comeni-registry`).

**Spec:** `docs/superpowers/specs/2026-10-01-samples-and-inspectors-design.md` §2, §3. Issue #216, part 14.7.6.1 of #134.

## Global Constraints

- **Invariant 11 holds:** the loader ignores folders; a file declares its own kind. Only `mendel lint` (and only when `layout:` asks) cares where a file sits. A private overlay with no `layout:` is unenforced.
- **No id changes.** Contract, module, type and measurement ids stay exactly as they are; `pipeline.yml` pins contracts by id and digest. Only paths move.
- **The exact layer digest is unchanged in meaning:** `digest_of_directory` still covers every declared byte, and is still what a pipeline pins and what `registry.digest()` returns.
- Diagnostics are declared in `comeni_core/diagnostics.yml` and emitted with `coded()`; `uv run python tools/generate_diagnostics_doc.py` regenerates the page.
- **Never push `main`** of either repository. `comeni-registry` changes go on a branch; pushing it is asked of the operator first (spec §15).
- `registry/` is a submodule at a detached HEAD: make the registry commits on a named branch inside it, never `git submodule deinit`.
- Comments and docstrings match the repository's style: say why, in full sentences, bold lead-in where a choice was made. A loop is not an assertion: assert the collection is non-empty first.

## Review Focus

1. **A lab overlay with no `layout:`** (or an old `layout:` without `tool`) must lint clean exactly as today: the new checks are opt-in through the manifest. Pinned in Task 2.
2. **An edit that keeps a file's size** (a one-character change) must still invalidate the API cache: the signature includes the modification time in nanoseconds. Pinned in Task 4.
3. **A tool with a module but no contract** (`bedtools`, `picard` today) still needs a `tool.yml`, but gets no generated page: `--in-place --check` must not demand a README for it, nor call one orphaned. Pinned in Task 3.
4. **A deleted tool's README** left behind must fail `--in-place --check` (the orphan case `--out` already catches). Pinned in Task 3.
5. **`forge land` into a layer whose manifest has the new layout** must write a new type under `vocabulary/types/`, not the old `types/`, or the next lint refuses the landing it just made. Pinned in Task 5.

---

## File structure

| File | Responsibility |
|---|---|
| Create `packages/comeni-core/src/comeni_core/declared/tools.py` | `Tool`, `ToolCatalogue`: the `tool` kind |
| Modify `packages/comeni-core/src/comeni_core/declared/layered.py` | `DeclaredKind.TOOLS`, `_KIND_OF["tool"]` |
| Modify `packages/mendel-resolver/src/mendel_resolver/layers.py` | `Layers.tools`, stacked and displaced like the rest |
| Create `packages/comeni-core/tests/test_tools.py` | the kind |
| Modify `packages/mendel-compiler/src/mendel_compiler/registry_lint.py` | path is the id (MD0021), every tool has a `tool.yml` (MD0022), a tool's own types sit in its `types/` (MD0023) |
| Modify `packages/comeni-core/src/comeni_core/diagnostics.yml` | MD0021–MD0023, and the header range |
| Modify `tests/registry/test_registry_lint.py` | the new checks, opt-in |
| Modify `packages/mendel-compiler/src/mendel_compiler/cli/layer_verbs.py`, `cli/parse.py`, `tool_docs.py` | `mendel docs --in-place`, the tool's description at the top of its page |
| Modify `tests/registry/test_docs_verb.py` | in-place pages, orphans, tools with no contract |
| Modify `packages/mendel-api/src/mendel_api/services/registry.py` | `signature()`; `digest()` cached on it |
| Modify `packages/mendel-api/tests/test_registry_cache.py` | the signature reloads on an edit and not otherwise |
| Modify `packages/mendel-forge/src/mendel_forge/land.py` | new types go where the layer's `layout:` keeps vocabulary |
| Modify `packages/mendel-forge/tests/test_land.py` | that |
| In `registry/` (branch `one-folder-per-tool`) | the move, nine `tool.yml`, top-level READMEs, `registry.yml` `layout:`, CI, pages in place |
| Modify paths in `tests/artifact/test_publish.py`, `tests/regressions/test_overlays.py`, `CLAUDE.md`, `.github/CONTRIBUTING.md`, `.github/pull_request_template.md`, `docs/design/invariants.md`, `docs/handbook/reference/cli.md`, `tools/generate_types.py`, `packages/comeni-core/src/comeni_core/goal/profile.pyi` | names of moved registry paths |

---

### Task 1: The `tool` kind

**Files:**
- Create: `packages/comeni-core/src/comeni_core/declared/tools.py`
- Modify: `packages/comeni-core/src/comeni_core/declared/layered.py` (`DeclaredKind`, `_KIND_OF`)
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py` (`Layers`, `load`)
- Test: `packages/comeni-core/tests/test_tools.py`, `tests/registry/test_declared_loading.py`

**Interfaces:**
- Produces: `comeni_core.declared.tools.Tool(id: str, name: str, description: str, homepage: str | None, cite: str | None)`; `ToolCatalogue(tools: dict[str, Tool])` with `.kind()`, `.of(stacked)`, `.load(layers)`; `DeclaredKind.TOOLS = "tools"`; `Layers.tools: ToolCatalogue`.

- [x] **Step 1: Write the failing tests**

```python
# packages/comeni-core/tests/test_tools.py
"""The `tool` kind: what a tool is, in one file beside its contracts (#216).

Stacked like every kind (invariant 11): an overlay may describe a tool the base lacks, or
replace the base's description. One tool per file, `declares: tool`.
"""

import pytest
from pydantic import ValidationError

from comeni_core.declared.tools import Tool, ToolCatalogue


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


SAMTOOLS = (
    "declares: tool\nid: nf-core/samtools\nname: SAMtools\n"
    "description: Reads, writes, sorts and indexes alignments.\n"
    "homepage: https://www.htslib.org\n"
)


def test_a_tool_file_loads_keyed_on_its_id(tmp_path):
    _write(tmp_path, "tools/nf-core/samtools/tool.yml", SAMTOOLS)
    catalogue = ToolCatalogue.load(tmp_path)
    assert list(catalogue.tools) == ["nf-core/samtools"]
    assert catalogue.tools["nf-core/samtools"].name == "SAMtools"


def test_a_higher_layer_replaces_a_description(tmp_path):
    base, lab = tmp_path / "base", tmp_path / "lab"
    _write(base, "tools/nf-core/samtools/tool.yml", SAMTOOLS)
    _write(lab, "samtools.yml", SAMTOOLS.replace("Reads, writes", "Our lab's samtools; reads"))
    catalogue = ToolCatalogue.load([base, lab])
    assert catalogue.tools["nf-core/samtools"].description.startswith("Our lab's")


@pytest.mark.parametrize("missing", ["id", "name", "description"])
def test_a_tool_says_what_it_is_or_fails(missing):
    fields = {"id": "nf-core/x", "name": "X", "description": "Does x."}
    del fields[missing]
    with pytest.raises(ValidationError):
        Tool.model_validate(fields)


def test_an_unknown_field_is_refused():
    with pytest.raises(ValidationError):
        Tool.model_validate({"id": "a/b", "name": "B", "description": "d.", "licence": "MIT"})
```

Add to `tests/registry/test_declared_loading.py`:

```python
def test_the_shipped_registry_loads_its_tools():
    """Empty until the registry moves (Task 6); every tool directory has one after."""
    from mendel_resolver import layers

    loaded = layers.load(REGISTRY)
    assert isinstance(loaded.tools.tools, dict)
```

(`REGISTRY` is the module's existing constant for the shipped layer; reuse it.)

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest packages/comeni-core/tests/test_tools.py tests/registry/test_declared_loading.py -q`
Expected: FAIL — `ModuleNotFoundError: comeni_core.declared.tools`, and `Layers` has no `tools`.

- [x] **Step 3: Implement the kind**

```python
# packages/comeni-core/src/comeni_core/declared/tools.py
"""Tools: what each tool is, in one file beside its contracts (#216).

A contract says how a tool is called; nothing said what the tool *is*. `tool.yml` does: a name, a
one-paragraph description, a homepage and a citation. It is also where the declared
descriptions the consultant explains from live (protocol rule 12): the forge drafts one and a
person approves it (invariant 2).

**Stacked** (invariant 11) like every other kind: an overlay may describe a tool the base lacks,
or replace a description the base wrote. One tool per file, `declares: tool`.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from comeni_core import yaml_strict
from comeni_core.declared.layered import DeclaredKind, Kind, Policy, Stacked, layers_of, stack


class Tool(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=128)
    """The module key's first two segments, `nf-core/samtools`: the same key `mendel docs`
    groups a page by, so a tool, its folder and its page are one name."""
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=600)
    homepage: str | None = None
    cite: str | None = None


def _parse_tool(path: Path) -> list[Tool]:
    """One tool file. `declares:` is accepted and ignored, as `_parse_family` does."""
    data = yaml_strict.load(path) or {}
    data.pop("declares", None)
    return [Tool.model_validate(data)]


class ToolCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tools: dict[str, Tool]

    @staticmethod
    def kind() -> Kind[str, Tool]:
        """Keyed on the tool id; a higher layer replaces a lower one's description."""
        return Kind(DeclaredKind.TOOLS, parse=_parse_tool, key=lambda t: t.id, policy=Policy.REPLACE)

    @classmethod
    def of(cls, stacked: Stacked[str, Tool]) -> "ToolCatalogue":
        return cls(tools=dict(stacked.entries))

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "ToolCatalogue":
        """Load the tools across a layer stack. **Layer roots**, as for every kind."""
        return cls.of(stack(layers_of(layers), cls.kind()))
```

In `layered.py`, add the member after `FAMILIES` with a one-line docstring, and the singular:

```python
    TOOLS = "tools"
    """What each tool is — `comeni_core.declared.tools` (#216)."""
```

```python
_KIND_OF = {
    ...
    "family": DeclaredKind.FAMILIES,
    "tool": DeclaredKind.TOOLS,
}
```

In `layers.py`, import `ToolCatalogue`, add the field to `Layers` after `families`:

```python
    tools: ToolCatalogue
    """What each tool is (#216). Read by the docs and, from 14.7.8, by explanations."""
```

and in `load()`, beside `declared_families`:

```python
    declared_tools = stack(stacked, ToolCatalogue.kind(), buckets=buckets)
```

pass `tools=ToolCatalogue.of(declared_tools)` to `Layers(...)`, and add `*declared_tools.displaced` to the displacement list.

- [x] **Step 4: Run them to see them pass, and the kind count wherever it is pinned**

Run: `uv run pytest packages/comeni-core/tests/test_tools.py tests/registry/ -q && grep -rn "len(DeclaredKind)" tests packages | head`
Expected: PASS. If a test pins `len(DeclaredKind)`, it now fails by one: update its number in this step (the count lives in `DeclaredKind`, never in prose).

- [x] **Step 5: Commit**

```bash
git add packages/comeni-core/src/comeni_core/declared/tools.py packages/comeni-core/src/comeni_core/declared/layered.py packages/mendel-resolver/src/mendel_resolver/layers.py packages/comeni-core/tests/test_tools.py tests/registry/test_declared_loading.py
git commit -m "feat(core): the tool kind — what a tool is, beside its contracts (#216)"
```

---

### Task 2: The lint learns the layout, opt-in

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/registry_lint.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`
- Test: `tests/registry/test_registry_lint.py`

**Interfaces:**
- Consumes: `DeclaredKind.TOOLS`, singular `"tool"` (Task 1).
- Produces: lint codes **MD0021** (a tool file's path is not its id), **MD0022** (a tool folder with no `tool.yml`), **MD0023** (a type under a tool sits outside that tool's `types/`). All three run only when `manifest.layout` has a `"tool"` key.

The rule *path is the id*, exactly: for a `contract` or `module` under `tools/` or `profilers/`, the id minus `@version` must equal the file's folder relative to that root (`tools/nf-core/samtools/sort/contract.yml` ↔ `nf-core/samtools/sort`). A **tool folder** is `tools/<org>/<tool>/` — the first two segments of any module key under `tools/`.

- [x] **Step 1: Write the failing tests**

Add to `tests/registry/test_registry_lint.py` (the module already has a `copy` fixture of the shipped layer; these tests build small layers in `tmp_path` so they do not depend on whether the registry has moved yet):

```python
def _layer(root, files: dict[str, str], layout_has_tool: bool = True):
    layout = {
        "contract": ["tools/", "profilers/"], "module": ["tools/"],
        "vocabulary": ["vocabulary/types/", "tools/"], "measurement": ["vocabulary/measurements/"],
        "role": ["vocabulary/roles/"], "family": ["vocabulary/families/"], "rule": ["rules/"],
    }
    if layout_has_tool:
        layout["tool"] = ["tools/"]
    import yaml

    (root / "registry.yml").write_text(yaml.safe_dump({
        "name": "t", "version": "0.1.0", "requires_format": 2, "licence": "CC-BY-4.0",
        "description": "t", "layout": layout,
    }))
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


TOOL = "declares: tool\nid: nf-core/x\nname: X\ndescription: Does x.\n"
MODULE = "declares: module\nid: {id}\nlicence: MIT\nupstream: {{repo: r, sha: s, path: p}}\ndigest: sha256:0\n"


def _codes(root):
    return sorted({f.code for f in lint(root)})


def test_a_module_whose_folder_is_not_its_id_is_refused(tmp_path):
    root = _layer(tmp_path, {
        "tools/nf-core/x/tool.yml": TOOL,
        "tools/nf-core/x/other/module.yml": MODULE.format(id="nf-core/x/sort"),
    })
    assert "MD0021" in _codes(root)


def test_a_tool_folder_without_tool_yml_is_refused(tmp_path):
    root = _layer(tmp_path, {"tools/nf-core/x/sort/module.yml": MODULE.format(id="nf-core/x/sort")})
    assert "MD0022" in _codes(root)


def test_a_tools_own_type_outside_its_types_folder_is_refused(tmp_path):
    root = _layer(tmp_path, {
        "tools/nf-core/x/tool.yml": TOOL,
        "tools/nf-core/x/genome.index.x.yml": "declares: vocabulary\nid: genome.index.x\nstates: []\n",
    })
    assert "MD0023" in _codes(root)


def test_the_arranged_layer_is_clean(tmp_path):
    root = _layer(tmp_path, {
        "tools/nf-core/x/tool.yml": TOOL,
        "tools/nf-core/x/types/genome.index.x.yml": "declares: vocabulary\nid: genome.index.x\nstates: []\n",
        "tools/nf-core/x/sort/module.yml": MODULE.format(id="nf-core/x/sort"),
    })
    assert not {"MD0021", "MD0022", "MD0023"} & set(_codes(root))


def test_a_layout_without_the_tool_kind_is_not_held_to_it(tmp_path):
    """Opt-in: today's registry, and any overlay that has not moved, lints as before."""
    root = _layer(tmp_path, {
        "tools/nf-core/x/other/module.yml": MODULE.format(id="nf-core/x/sort"),
    }, layout_has_tool=False)
    assert not {"MD0021", "MD0022", "MD0023"} & set(_codes(root))
```

- [x] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/registry/test_registry_lint.py -q -k "folder or tool_yml or types_folder or arranged or without_the_tool"`
Expected: FAIL on the three refusals (codes absent); the two clean cases pass.

- [x] **Step 3: Declare the codes**

In `diagnostics.yml`, change the header line `#   MD0013-MD0019  a layer is not arranged …` to `#   MD0013-MD0019, MD0021-MD0023  a layer is not arranged the way its own manifest says`, and add after `MD0020`, copying `MD0019`'s shape:

```yaml
MD0021:
  emitted_by: compiler
  concern: layout
  says: "a tool's file sits in a folder that is not its id"
  fires_on: [registry lint]
  refuses: true
  explain: >-
    In a layer whose `layout:` declares the `tool` kind, the path is the id: the contract or
    module `nf-core/samtools/sort` lives in `tools/nf-core/samtools/sort/`, and a profiler's in
    `profilers/<its id>/`. Finding a file is then never a search, and `forge land` writes straight
    to it. Move the file, or fix the id if it is the id that is wrong.
MD0022:
  emitted_by: compiler
  concern: layout
  says: "a tool folder has no tool.yml saying what the tool is"
  fires_on: [registry lint]
  refuses: true
  explain: >-
    Every `tools/<org>/<tool>/` folder carries a `tool.yml` (`declares: tool`) with the tool's
    name and a description. The description is what an explanation is allowed to quote, so a
    tool without one cannot be explained from a source.
MD0023:
  emitted_by: compiler
  concern: layout
  says: "a type only one tool uses sits outside that tool's types/ folder"
  fires_on: [registry lint]
  refuses: true
  explain: >-
    A type only one tool touches lives with that tool, in `tools/<org>/<tool>/types/`, so the
    tool's folder reads as subtools plus its own words. A type several tools touch belongs in
    `vocabulary/types/`.
```

Copy any further keys `MD0019` carries (for example `fix:` or `see:`) so the file's own schema check passes; read `MD0019` first.

- [x] **Step 4: Implement the three checks**

In `registry_lint.py`, in `lint()` after the existing checks:

```python
    if "tool" in manifest.layout:
        found += _path_is_the_id(root)
        found += _every_tool_says_what_it_is(root)
        found += _tool_types_in_types(root)
```

and the functions, after `_nothing_reaches_out_of_its_tool`:

```python
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
```

`_tool_types_are_namespaced` (MD0017) keeps working unchanged: it reads `parts[1]` of the path below `tools/`, which is still the tool.

- [x] **Step 5: Run the lint tests and regenerate the diagnostics page**

Run: `uv run python tools/generate_diagnostics_doc.py && uv run pytest tests/registry/test_registry_lint.py tests/ -q -k "lint or diagnostic" -p no:randomly`
Expected: PASS, including `test_the_shipped_layer_lints_clean` against today's registry (its `layout:` has no `tool`).

- [x] **Step 6: Watch each new guard fail (A14)**

For each of MD0021–MD0023, delete the `found += …` line, run its test, see it FAIL, restore. Record the three reverts in `tests/fixtures/guard-ledger.md` in the table's existing format.

- [x] **Step 7: Commit**

```bash
git add packages/mendel-compiler/src/mendel_compiler/registry_lint.py packages/comeni-core/src/comeni_core/diagnostics.yml docs/handbook/reference/diagnostics.md tests/registry/test_registry_lint.py tests/fixtures/guard-ledger.md
git commit -m "feat(lint): the path is the id, every tool says what it is — opt-in by layout (#216)"
```

---

### Task 3: `mendel docs --in-place`

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli/layer_verbs.py` (`_pages`, `_docs_verb`)
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli/parse.py` (the `docs` arguments)
- Modify: `packages/mendel-compiler/src/mendel_compiler/tool_docs.py` (`render`)
- Test: `tests/registry/test_docs_verb.py`

**Interfaces:**
- Consumes: `Layers.tools` (Task 1).
- Produces: `mendel docs --registry <one layer> --in-place [--check]` writes `README.md` in the folder holding each tool's contracts: `tools/<key>/` if it exists in the layer, else `profilers/<key>/`, where `<key>` is `tool_docs._tool_of(id)`. A page opens with the tool's `name` and `description` when a `tool.yml` declares it.

- [x] **Step 1: Read the existing tests and parser**

Run: `sed -n 1,80p tests/registry/test_docs_verb.py && sed -n 20,90p packages/mendel-compiler/src/mendel_compiler/cli/parse.py`
Note how the tests invoke the verb (directly through `_docs_verb`, or through `main([...])`) and follow the same style below.

- [x] **Step 2: Write the failing tests**

```python
def _arranged(tmp_path):
    """A copy of the shipped layer with fastqc arranged and described."""
    import shutil

    root = tmp_path / "layer"
    shutil.copytree(REGISTRY, root, ignore=shutil.ignore_patterns(".git"))
    (root / "tools/nf-core/fastqc/tool.yml").write_text(
        "declares: tool\nid: nf-core/fastqc\nname: FastQC\n"
        "description: A quality report for sequencing reads.\n"
    )
    return root


def test_in_place_writes_a_readme_beside_the_tool(tmp_path):
    root = _arranged(tmp_path)
    assert layer_verbs._docs_verb([root], out=None, check=False, in_place=True) == 0
    page = (root / "tools/nf-core/fastqc/README.md").read_text()
    assert "# FastQC" in page
    assert "A quality report for sequencing reads." in page


def test_in_place_check_passes_after_a_write_and_fails_on_an_edit(tmp_path):
    root = _arranged(tmp_path)
    layer_verbs._docs_verb([root], out=None, check=False, in_place=True)
    assert layer_verbs._docs_verb([root], out=None, check=True, in_place=True) == 0
    readme = root / "tools/nf-core/fastqc/README.md"
    readme.write_text(readme.read_text() + "\nhand edit\n")
    assert layer_verbs._docs_verb([root], out=None, check=True, in_place=True) == 1


def test_in_place_check_fails_on_an_orphaned_readme(tmp_path):
    root = _arranged(tmp_path)
    layer_verbs._docs_verb([root], out=None, check=False, in_place=True)
    (root / "tools/nf-core/gone").mkdir(parents=True)
    (root / "tools/nf-core/gone/README.md").write_text("<!-- Generated by `mendel docs`. -->\n")
    assert layer_verbs._docs_verb([root], out=None, check=True, in_place=True) == 1


def test_a_tool_with_no_contract_needs_no_page(tmp_path):
    """bedtools and picard carry modules and no contract: no page, and not an orphan."""
    root = _arranged(tmp_path)
    layer_verbs._docs_verb([root], out=None, check=False, in_place=True)
    assert not (root / "tools/nf-core/bedtools/README.md").exists()
    assert layer_verbs._docs_verb([root], out=None, check=True, in_place=True) == 0


def test_in_place_refuses_a_stack(tmp_path):
    root = _arranged(tmp_path)
    assert layer_verbs._docs_verb([root, root], out=None, check=False, in_place=True) == 2
```

An orphan is a `README.md` **beginning with the generated banner** under `tools/` or `profilers/` that is not in the page set: a hand-written top-level `README.md` (`tools/README.md`) is never an orphan, because it lacks the banner.

- [x] **Step 3: Run them to see them fail**

Run: `uv run pytest tests/registry/test_docs_verb.py -q`
Expected: FAIL — `_docs_verb() got an unexpected keyword argument 'in_place'`.

- [x] **Step 4: Implement**

In `tool_docs.render`, after the banner, when `loaded.tools.tools.get(tool)` exists, title the page with its `name` and put its `description` (and `homepage`/`cite` lines when set) under the title; otherwise keep `# {tool}`. Keep the rest of the page as it is.

In `layer_verbs.py`:

```python
def _folder_of(root: Path, tool: str) -> Path:
    """Where a tool's page goes in place: the folder that holds its contracts (#216)."""
    for base in ("tools", "profilers"):
        if (root / base / tool).is_dir():
            return Path(base) / tool
    return Path("tools") / tool


def _in_place_pages(root: Path) -> dict[Path, str]:
    return {
        _folder_of(root, Path(page).with_suffix("").as_posix()) / "README.md": content
        for page, content in _pages([root]).items()
    }


def _generated_readmes(root: Path) -> list[Path]:
    return sorted(
        p.relative_to(root)
        for base in ("tools", "profilers")
        for p in (root / base).rglob("README.md")
        if p.read_text().startswith(tool_docs._BANNER)
    )
```

Change `_docs_verb(registries, out, check)` to `_docs_verb(registries, out, check, in_place=False)`. With `in_place`: refuse anything but one layer (`print("mendel: --in-place writes into one layer; pass exactly one --registry")`, return 2); the pages are `_in_place_pages(root)` and their base is `root`; orphans are `_generated_readmes(root)` not in the pages. Without it, behave exactly as today (`out` required). Write and check through the same code path, so `--check` writes nothing.

In `parse.py`, add `--in-place` to `docs` (help: "`docs` only: write each tool's page as README.md in that tool's own folder, in the one layer given") and make `--out` optional when `--in-place` is given; pass it through where `_docs_verb` is called.

- [x] **Step 5: Run them to see them pass, and the existing docs tests**

Run: `uv run pytest tests/registry/test_docs_verb.py tests/repo/test_wiki.py -q`
Expected: PASS. `make wiki-tools` (`--out docs/tools/`) is unchanged.

- [x] **Step 6: Commit**

```bash
git add packages/mendel-compiler/src/mendel_compiler/cli/layer_verbs.py packages/mendel-compiler/src/mendel_compiler/cli/parse.py packages/mendel-compiler/src/mendel_compiler/tool_docs.py tests/registry/test_docs_verb.py
git commit -m "feat(docs): mendel docs --in-place — a tool's page lives in its folder (#216)"
```

---

### Task 4: A cheap "has it changed?" check

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/registry.py`
- Test: `packages/mendel-api/tests/test_registry_cache.py`

**Interfaces:**
- Produces: `registry.signature() -> tuple[tuple[str, int, int], ...]` (relative path, size, `st_mtime_ns`, over `declared_entries`); `registry.digest() -> str` unchanged in value, computed once per signature; `registry.stack()` unchanged.

- [x] **Step 1: Measure today**

Run:
```bash
uv run python -c "
import timeit
from mendel_api.services import registry
registry.stack()
print('per request ms', round(timeit.timeit(registry.stack, number=200) / 200 * 1000, 2))
"
```
Expected: a number around 5–12 ms. Write it into the plan's execution record.

- [x] **Step 2: Write the failing tests**

```python
def test_an_unchanged_registry_is_not_hashed_again(monkeypatch):
    """The per-request cost: reading every byte to learn nothing changed (#216)."""
    hashed = []
    real = registry.digest_of_directory

    def counting(root):
        hashed.append(root)
        return real(root)

    monkeypatch.setattr(registry, "digest_of_directory", counting)
    registry._digest_for.cache_clear()
    registry.stack()
    registry.stack()
    registry.digest()
    assert len(hashed) == 1


def test_an_edit_of_the_same_size_is_still_seen(monkeypatch, broken_registry_copy):
    """`FASTQC` → `FASTQX` keeps the size; the modification time still moves."""
    from mendel_api.settings import settings

    changed = broken_registry_copy(
        "tools/nf-core/fastqc/contract.yml", "nf_process: FASTQC", "nf_process: FASTQC"
    )
    monkeypatch.setattr(settings, "registry_root", changed)
    registry._digest_for.cache_clear()
    first = registry.digest()
    contract = changed / "tools/nf-core/fastqc/contract.yml"
    import os, time

    text = contract.read_text().replace("nf_process: FASTQC", "nf_process: FASTQX")
    time.sleep(0.01)
    contract.write_text(text)
    os.utime(contract)
    assert registry.digest() != first
```

(Read the `broken_registry_copy` fixture first: if its replacement must differ, copy the layer with `shutil.copytree` in the test instead.)

- [x] **Step 3: Run them to see them fail**

Run: `uv run pytest packages/mendel-api/tests/test_registry_cache.py -q`
Expected: FAIL — `registry` has no `_digest_for`.

- [x] **Step 4: Implement**

```python
from comeni_core.declared.layered import declared_entries


def signature() -> tuple[tuple[str, int, int], ...]:
    """Each declared file's size and modification time, never its bytes (#216).

    **What a request pays to learn nothing changed.** The digest read every byte of the layer,
    module sources included, on every request: 5–12 ms at 68 files and growing with each tool.
    `stat` is enough to know whether to look again; the exact digest is still what a pipeline
    pins, computed only when this moves.
    """
    root = settings.registry_root
    return tuple(
        (str(p.relative_to(root)), s.st_size, s.st_mtime_ns)
        for p in sorted(declared_entries(root))
        for s in (p.stat(),)
    )


@lru_cache(maxsize=4)
def _digest_for(_signature: tuple) -> str:
    return str(digest_of_directory(settings.registry_root))


def digest() -> str:
    """The cache key, borrowed as an ETag — exact, and recomputed only when the signature moves."""
    return _digest_for(signature())
```

Keep `_load(digest)` and `stack()` as they are. `declared_entries` already lists what the digest covers, so the two agree on what "the registry" is.

- [x] **Step 5: Run them to see them pass, then measure again**

Run: `uv run pytest packages/mendel-api/tests/test_registry_cache.py -q` then the Step 1 command.
Expected: PASS; the per-request number well under 1 ms. Write both numbers into the execution record and onto issue #216.

- [x] **Step 6: Commit**

```bash
git add packages/mendel-api/src/mendel_api/services/registry.py packages/mendel-api/tests/test_registry_cache.py
git commit -m "perf(api): know the registry changed from stat, hash it only when it has (#216)"
```

---

### Task 5: `forge land` writes types where the layer keeps them

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/land.py:154-168`
- Test: `packages/mendel-forge/tests/test_land.py`

**Interfaces:**
- Consumes: `LayerManifest.of(root).layout` (`comeni_core.declared.layer`).
- Produces: a new type lands at `<first directory of layout["vocabulary"] that is not under tools/>/<id>.yml`, or `types/<id>.yml` when the layer declares no layout.

- [x] **Step 1: Read how `stage()` (the function holding lines 154–168) learns the landing root**

Run: `sed -n 100,150p packages/mendel-forge/src/mendel_forge/land.py && grep -n "def test" packages/mendel-forge/tests/test_land.py | head -30`
If the function has no access to the layer root, add a `types_dir: Path = Path("types")` parameter and have its caller pass `_types_dir(registry_root)`.

- [x] **Step 2: Write the failing test**

```python
def test_a_new_type_lands_where_the_layer_keeps_types(tmp_path):
    from mendel_forge.land import _types_dir

    (tmp_path / "registry.yml").write_text(
        "name: t\nversion: 0.1.0\nrequires_format: 2\nlicence: CC-BY-4.0\ndescription: t\n"
        "layout: {vocabulary: [vocabulary/types/, tools/], tool: [tools/]}\n"
    )
    assert _types_dir(tmp_path) == Path("vocabulary/types")


def test_a_layer_with_no_layout_keeps_types_in_types(tmp_path):
    from mendel_forge.land import _types_dir

    assert _types_dir(tmp_path) == Path("types")
```

- [x] **Step 3: Run it to see it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_land.py -q -k "types_dir or keeps_types"`
Expected: FAIL — `cannot import name '_types_dir'`.

- [x] **Step 4: Implement**

```python
def _types_dir(root: Path) -> Path:
    """Where this layer keeps shared types: its `layout:` says, else `types/` (#216).

    The first vocabulary directory that is not a tool's own — a type the forge proposes is a
    shared one until a person moves it into a tool.
    """
    manifest = LayerManifest.of(root)
    for place in (manifest.layout.get("vocabulary", []) if manifest else []):
        if not place.startswith("tools"):
            return Path(place.rstrip("/"))
    return Path("types")
```

and replace `str(Path("types") / f"{type_id}.yml")` with `str(types_dir / f"{type_id}.yml")`, threading `types_dir` from the caller that knows the layer root.

- [x] **Step 5: Run the forge's tests**

Run: `uv run pytest packages/mendel-forge -q`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add packages/mendel-forge/src/mendel_forge/land.py packages/mendel-forge/tests/test_land.py
git commit -m "feat(forge): land a new type where the layer's layout keeps types (#216)"
```

---

### Task 6: The registry moves

**Files (all inside `registry/`, on branch `one-folder-per-tool`):** every move below, nine `tool.yml`, five top-level `README.md`, `registry.yml`, `.github/workflows/ci.yml`, generated `README.md` pages, `docs/tools/` deleted.

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: comeni-registry commit on `one-folder-per-tool`, which Task 7 pins.

- [x] **Step 1: Branch from the pinned commit**

```bash
cd registry && git switch -c one-folder-per-tool && git log --oneline -1
```
Expected: `c7208bd feat: families…` (the commit this repository pins; it is on the remote branch `families`, not yet merged to `main`).

- [x] **Step 2: Move the files**

```bash
mkdir -p vocabulary profilers/comeni/profile inspectors
git mv types vocabulary/types
git mv families vocabulary/families
git mv measurements vocabulary/measurements
git mv roles vocabulary/roles
git mv tools/comeni/profile-fastqc profilers/comeni/profile/fastqc
git mv tools/comeni/profile-collect profilers/comeni/profile/collect
mkdir -p tools/nf-core/star/types tools/nf-core/hisat2/types
git mv tools/nf-core/star/genome.index.star.yml tools/nf-core/star/types/
git mv tools/nf-core/hisat2/genome.index.hisat2.yml tools/nf-core/hisat2/types/
git rm -r -q docs/tools
rmdir tools/comeni 2>/dev/null; ls
```
Expected: top level `CODEOWNERS CONTRIBUTING.md LICENSE LICENSES README.md inspectors profilers registry.yml rules tools vocabulary` (plus `docs/` only if something other than `docs/tools/` was in it).

- [x] **Step 3: The new `layout:`**

Replace the `layout:` block in `registry.yml` (keep its comment style; rewrite the comments for the new places):

```yaml
layout:
  # Everything about one tool, together: what it is, its docs, its own types, and one folder
  # per subtool. The path is the id (MD0021).
  tool: [tools/]
  contract: [tools/, profilers/]
  module: [tools/]
  # A type many tools touch is shared and lives in the vocabulary; a type only one tool's
  # modules touch lives in that tool's types/ (MD0023), namespaced by the tool's name (MD0017).
  vocabulary: [vocabulary/types/, tools/]
  # Facts about data, true regardless of which tool or inspector measures them.
  measurement: [vocabulary/measurements/]
  # The jobs a contract can do. One file each, named for the role.
  role: [vocabulary/roles/]
  # The first level of the type choice: what kinds of data exist. One file each.
  family: [vocabulary/families/]
  # Decisions *between* tools, belonging to neither.
  rule: [rules/]
```

- [x] **Step 4: Write the nine `tool.yml`**

One per folder under `tools/nf-core/`: `bedtools`, `fastqc`, `hisat2`, `multiqc`, `picard`, `samtools`, `star`, `subread`, `trimgalore`. Each: `declares: tool`, `id: nf-core/<tool>`, `name`, a one-to-three-sentence `description` of what the tool does for a researcher, `homepage`, and `cite` (author year, doi) — taken from the tool's own homepage or paper and from `module/meta.yml`'s `description`/`homepage`/`doi` under that tool, never from memory. Example:

```yaml
declares: tool
id: nf-core/samtools
name: SAMtools
description: >-
  Reads, writes, sorts and indexes alignments in SAM, BAM and CRAM. Here it sorts and indexes
  the alignments the aligner produces, and indexes the genome.
homepage: https://www.htslib.org
cite: "Danecek et al. 2021, doi:10.1093/gigascience/giab008"
```

- [ ] **Step 5: STOP — the operator approves the nine descriptions**

Print the nine files and ask the operator to approve or correct them (spec §3: *the migration writes one for each existing tool … for the operator to approve*). Invariant 2: a person approves what an explanation may quote. Do not continue until they answer; apply their corrections.

- [x] **Step 6: One-line README for each top-level folder**

`tools/README.md`, `profilers/README.md`, `inspectors/README.md`, `vocabulary/README.md`, `rules/README.md`, each one hand-written line (no generated banner), e.g. `profilers/README.md`: `Uses of a tool to measure the data, run in the lab's pipeline. One folder per profiler; the path is its id.` and `inspectors/README.md`: `Code that measures an uploaded sample on the server: codecs, formats and measures. Arrives in 14.7.6.2.`

- [x] **Step 7: Generate the pages in place, and run every gate the registry's CI runs**

```bash
uv run mendel docs --registry . --in-place
uv run mendel docs --registry . --in-place --check
uv run mendel lint --registry .
uv run mendel conformance --registry .
uv run comeni-vendor check --registry .
```
(Run from inside `registry/`, with this repository's engine: `uv run --project ..`.)
Expected: each exits 0; `lint` reports the declared files checked and no findings.

- [x] **Step 8: The registry's CI**

In `.github/workflows/ci.yml`, replace the step *The committed pages match the data* with:

```yaml
      - name: Each tool's page matches the data
        run: mendel docs --registry . --in-place --check
```

and leave `ENGINE_REF` for Step 10 (it must name a pushed Comeni-Labs commit that has Tasks 1–5).

- [ ] **Step 9: Commit in the registry**

```bash
git add -A && git commit -m "One folder per tool: tools, profilers, inspectors, vocabulary, rules (comeni-labs #216)

The path is the id; every tool says what it is in tool.yml; each tool's page is generated
into its own folder; profilers move out of tools; shared kinds move under vocabulary/."
```

- [ ] **Step 10: STOP — pushing**

Ask the operator to authorise: (a) pushing `living-pipeline-design` in Comeni-Labs (already authorised) so Tasks 1–5 have a SHA; (b) setting `ENGINE_REF` to that SHA in a second registry commit; (c) pushing `one-folder-per-tool` to `comeni-registry` (spec §15). Do only what they authorise.

---

### Task 7: This repository follows the registry

**Files:**
- Modify: `registry` (submodule pointer), `tests/artifact/test_publish.py:292`, `tests/regressions/test_overlays.py:307`, `CLAUDE.md:159,235`, `.github/CONTRIBUTING.md:73`, `.github/pull_request_template.md:41`, `docs/design/invariants.md:94`, `docs/handbook/reference/cli.md:129,258-259,354-355`, `tools/generate_types.py:35`, `packages/comeni-core/src/comeni_core/goal/profile.pyi:2`, `ARCHITECTURE.md` (wherever it describes the registry's folders)

- [ ] **Step 1: Find every path that moved**

Run: `git grep -n -e "registry/types/" -e "registry/measurements/" -e "registry/roles/" -e "registry/families/" -e "tools/comeni/profile" -e "genome.index.star.yml" -e "genome.index.hisat2.yml" -e "registry/docs/" -- ':!docs/notes/journal' ':!docs/superpowers/plans/archive' ':!docs/superpowers/specs/archive' ':!tests/fixtures/guard-ledger.md' ':!tests/fixtures/claude-md-*'`
Expected: a list close to the Files line above. History (journal, archives, the guard ledger, frozen fixtures) is not rewritten.

- [ ] **Step 2: Update each to the new path**

`registry/types/` → `registry/vocabulary/types/` (and the same for `measurements`, `roles`, `families`); `tools/comeni/profile-*` → `profilers/comeni/profile/*`. In `CLAUDE.md`'s *The registry* paragraph, say the five top-level things in one sentence; keep it within `make doc-sizes`. In `cli.md`, document `mendel docs --in-place` beside `--out`.

- [ ] **Step 3: Run the whole check**

Run: `make check > /tmp/claude-1000/check.log 2>&1; tail -20 /tmp/claude-1000/check.log`
Expected: PASS. The shipped layer now declares `tool:` in its layout, so `test_the_shipped_layer_lints_clean` runs the new checks against the moved registry and passes.

- [ ] **Step 4: Run `make verify`** (Task 1 touched `layers.py`, which feeds `resolve.py`)

Run: `make verify > /tmp/claude-1000/verify.log 2>&1; tail -20 /tmp/claude-1000/verify.log`
Expected: PASS. Same goal → byte-identical `.nf` (ids did not change, so pinned digests change only because bytes moved: if a golden pins the layer digest, regenerate it and say so in the execution record).

- [ ] **Step 5: Commit, separately from the checks**

```bash
git add registry tests CLAUDE.md .github docs tools packages/comeni-core/src/comeni_core/goal/profile.pyi ARCHITECTURE.md
git commit -m "chore(registry): follow the registry to one folder per tool (#216)"
```

- [ ] **Step 6: Close the loop on #216**

Comment on #216 with the before/after per-request numbers and the commits; it closes when the registry branch merges.

---

## Execution record

*(Filled in while executing: rulings, measurements, deviations.)*
