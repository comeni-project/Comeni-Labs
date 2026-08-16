# Registry CI and generated tool documentation — implementation plan

> **REQUIRED SUB-SKILL:** `superpowers:executing-plans`. Task by task, in a worktree.
> `CLAUDE.md` forbids farming implementation tasks out to subagents; drive this yourself.

**Goal:** `mendel docs` generates one Markdown page per tool from a registry layer, and
`comeni-registry` gains the CI that validates its data and keeps those pages honest.

**Architecture:** A pure renderer (`mendel_compiler/tool_docs.py`) turns loaded layers into
`{page name: markdown}`; a thin verb (`cli/layer_verbs.py`) is the only thing that touches disk,
which is what keeps the golden-file tests possible. The registry then installs the engine from
git — proven in the spec §2 — and runs the verb.

**Tech Stack:** Python 3.12+, Pydantic v2, argparse, pytest, GitHub Actions.

**Spec:** [`notes/specs/2026-08-16-registry-ci-and-tool-docs.md`](../specs/2026-08-16-registry-ci-and-tool-docs.md)

## Global Constraints

- **Two repositories.** Tasks 1–5 are `Comeni-Labs`; Task 6 is `comeni-registry`. Task 6 cannot
  run until Tasks 1–5 have **merged**, because it installs the verb from git.
- **The emitted artifacts must not move.** This adds a verb and touches no emission path.
  Recorded before Task 1 and checked at Task 5. `main.nf` is `76355bbf9f10d6e6` and
  `nextflow.config` is `72ddb081638edf76`.
- **A tool is the first two segments of the module key** (spec §3.1), never the directory.
- **A new diagnostic code must be declared in `diagnostics.yml` AND emitted through `coded()`.**
  Both directions are tested. This plan introduces **no** new code — see the self-review.
- **`make check` after every task; `make verify` at Task 5.** No test may pass `--gate` to
  `mendel build` (CI has no Nextflow).
- **Line length 100.** `ruff check .` is a gate.

### Deviation from the spec, decided here

The spec §3 writes `mendel docs <layer>`, taking the layer as a positional argument. **This plan
uses repeated `--registry` instead**, uniform with `build`, `profile` and `upgrade`.

Two reasons. There is then one way to name a layer rather than two. And a private overlay usually
cannot load alone — it references types the base declares, and `layers.load()` enforces
vocabulary closure — so the spec's own "a laboratory can document its own overlay" argument needs
stacking to work at all. Pages cover every tool in the loaded stack.

The registry's command becomes `mendel docs --registry . --out docs/tools`.

---

## Task 1: grouping contracts into tools

**Files:**
- Create: `packages/mendel-compiler/src/mendel_compiler/tool_docs.py`
- Test: `packages/mendel-compiler/tests/test_tool_docs.py`

**Interfaces:**
- Consumes: `mendel_resolver.layers.Layers` (fields `registry`, `vocabulary`, `rules`).
- Produces: `tool_docs.tools_of(registry) -> dict[str, list[ModuleContract]]`, keys sorted,
  each list sorted by contract id.

- [ ] **Step 1: Write the failing tests**

```python
"""One page per tool, and a tool is what the ids say it is — not what the folders say.

comeni-registry#1 removed the directory's meaning on purpose. Grouping documentation by
folder would put path-as-meaning straight back in, one layer up.
"""

from pathlib import Path

from mendel_compiler import tool_docs
from mendel_resolver import layers

ROOT = Path(__file__).parent.parent.parent.parent


def _layers():
    return layers.load([ROOT / "registry"])


def test_a_three_segment_id_groups_under_its_first_two():
    """`nf-core/star/align` and `nf-core/star/genomegenerate` are one tool."""
    tools = tool_docs.tools_of(_layers().registry)
    assert "nf-core/star" in tools
    assert [c.id for c in tools["nf-core/star"]] == [
        "nf-core/star/align@1.11.0",
        "nf-core/star/genomegenerate@1.11.0",
    ]


def test_a_two_segment_id_is_its_own_tool():
    """`nf-core/fastqc` has no third segment. Dropping the last one would say `nf-core`,
    which would collapse every nf-core module into a single page."""
    tools = tool_docs.tools_of(_layers().registry)
    assert [c.id for c in tools["nf-core/fastqc"]] == ["nf-core/fastqc@0.12.1"]


def test_a_one_segment_key_is_its_own_page_rather_than_a_refusal(tmp_path):
    """No contract has one today, and an in-house `sortmerna@4.3.6` is not obviously wrong,
    so this forbids nothing. Spec §3.1."""
    assert tool_docs._tool_of("sortmerna@4.3.6") == "sortmerna"


def test_the_registry_groups_into_the_eight_pages_the_spec_names():
    tools = tool_docs.tools_of(_layers().registry)
    assert sorted(tools) == [
        "comeni/profile",
        "nf-core/fastqc",
        "nf-core/hisat2",
        "nf-core/multiqc",
        "nf-core/samtools",
        "nf-core/star",
        "nf-core/subread",
        "nf-core/trimgalore",
    ]
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest packages/mendel-compiler/tests/test_tool_docs.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'mendel_compiler.tool_docs'`

- [ ] **Step 3: Write the module**

```python
"""One Markdown page per tool, rendered from declared data and nothing else.

**Pure.** Takes loaded layers, returns strings. `cli/layer_verbs.py` is the only thing that
touches disk, which is what makes these tests golden-file tests rather than filesystem
tests — the same split `cli/__init__.py` describes.

comeni-registry#2.
"""

from collections import defaultdict

from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.registry import Registry


def _tool_of(contract_id: str) -> str:
    """`nf-core/star/align@1.11.0` -> `nf-core/star`.

    The **module key** — the id minus `@version` — is what shadowing already keys on, so a
    version bump never splits a page. The first two segments, because the ids are not
    uniformly shaped: `nf-core/star/align` has three and `nf-core/fastqc` has two, and
    "drop the last segment" turns the second into `nf-core` and collapses every nf-core
    module onto one page.

    Fewer than two segments returns the key itself rather than refusing. No contract has one
    today, and a laboratory's in-house `sortmerna@4.3.6` is not obviously wrong — inventing a
    rule for a case that does not exist is how a vocabulary comes to forbid something
    legitimate.
    """
    key = contract_id.split("@")[0]
    return "/".join(key.split("/")[:2])


def tools_of(registry: Registry) -> dict[str, list[ModuleContract]]:
    """Every contract in the stack, grouped into the page it belongs on.

    Sorted at both levels: a generated file that reorders itself between runs is a file
    whose `--check` fails for no reason anybody can act on.
    """
    grouped: dict[str, list[ModuleContract]] = defaultdict(list)
    for contract_id in sorted(registry.contracts):
        grouped[_tool_of(contract_id)].append(registry.contracts[contract_id])
    return dict(sorted(grouped.items()))
```

- [ ] **Step 4: Run them and watch them pass**

Run: `uv run pytest packages/mendel-compiler/tests/test_tool_docs.py -v`
Expected: 4 passed.

- [ ] **Step 5: Watch the grouping rule fail on purpose**

Change `[:2]` to `[:-1]` and rerun. Expected: `test_a_two_segment_id_is_its_own_tool` fails
because `nf-core/fastqc` groups under `nf-core`. Restore it, and **clear `__pycache__`** —
restoring a file byte-for-byte can reproduce its size and mtime, so CPython reuses the cached
bytecode and the reverted code keeps running:

```bash
find packages -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; true
```

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-compiler/src/mendel_compiler/tool_docs.py \
        packages/mendel-compiler/tests/test_tool_docs.py
git commit -m "feat: a tool is the first two segments of its module key (comeni-registry#2)"
```

---

## Task 2: rendering one page

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/tool_docs.py`
- Test: `packages/mendel-compiler/tests/test_tool_docs.py`

**Interfaces:**
- Consumes: `tools_of` from Task 1.
- Produces: `tool_docs.render(tool: str, contracts: list[ModuleContract], loaded: Layers) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_page_names_every_contract_and_its_process():
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert page.startswith("# nf-core/star\n")
    assert "`nf-core/star/align@1.11.0`" in page
    assert "STAR_ALIGN" in page
    assert "`nf-core/star/genomegenerate@1.11.0`" in page


def test_a_page_records_ports_with_their_states():
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/samtools", tools["nf-core/samtools"], loaded)
    assert "alignment.bam" in page
    assert "coordinate_sorted" in page


def test_a_page_carries_the_citation_rather_than_dropping_it():
    """Contracts cite papers and the data is CC-BY. A generated page that drops attribution
    is the one thing this registry's licence exists to prevent."""
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert "approved_by" in page or "Provenance" in page


def test_a_page_says_when_a_tool_declares_no_parameters():
    """An empty section is a fact — 'this tool settles nothing' — and a page that silently
    omits it reads as though the generator forgot."""
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/multiqc", tools["nf-core/multiqc"], loaded)
    assert "no parameters" in page.lower() or "Parameters" in page


def test_rendering_is_stable_across_two_calls():
    """`--check` compares bytes. A frozenset iterated without sorting is how byte-identical
    output stops being byte-identical — `IREdge.states` already carries a field_serializer
    for exactly this."""
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    first = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    second = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert first == second
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest packages/mendel-compiler/tests/test_tool_docs.py -v`
Expected: FAIL, `AttributeError: module 'mendel_compiler.tool_docs' has no attribute 'render'`

- [ ] **Step 3: Implement `render`**

Add to `tool_docs.py`:

```python
_GENERATED = (
    "<!-- Generated by `mendel docs`. Do not edit: `--check` refuses a hand edit. -->\n"
)


def _states(states) -> str:
    """Sorted, because a frozenset has no stable order and `--check` compares bytes."""
    return ", ".join(f"`{s}`" for s in sorted(states)) if states else "—"


def _ports(contract: ModuleContract) -> list[str]:
    lines = ["| Direction | Port | Type | States |", "|---|---|---|---|"]
    for port in contract.consumes:
        type_id = port.type_id or " / ".join(sorted(port.accepts or []))
        lines.append(
            f"| consumes | `{port.name}` | `{type_id}` | {_states(port.state_required)} |"
        )
    for port in contract.produces:
        lines.append(
            f"| produces | `{port.name}` | `{port.type_id}` | {_states(port.state)} |"
        )
    return lines


def _params(contract: ModuleContract) -> list[str]:
    if not contract.params:
        return ["This contract declares no parameters."]
    lines = ["| Parameter | Tier hint | Route | Default |", "|---|---|---|---|"]
    for param in sorted(contract.params, key=lambda p: p.name):
        via = f"`{param.via.value}`" if param.via is not None else "—"
        default = f"`{param.default}`" if param.default is not None else "—"
        lines.append(f"| `{param.name}` | {param.tier_hint} | {via} | {default} |")
    return lines


def _contract_section(contract: ModuleContract) -> list[str]:
    provenance = contract.provenance
    lines = [
        f"### `{contract.id}`",
        "",
        f"- **Process:** `{contract.nf_process}`",
        f"- **Include:** `{contract.nf_include}`",
        f"- **Roles:** {', '.join(f'`{r}`' for r in sorted(contract.roles)) or '—'}",
        f"- **Container:** `{contract.container}`" if contract.container else "- **Container:** —",
        f"- **Priority:** {contract.priority}",
        "",
        "#### Ports",
        "",
        *_ports(contract),
        "",
        "#### Parameters",
        "",
        *_params(contract),
        "",
        "#### Provenance",
        "",
        f"- source: `{provenance.source}`",
        f"- drafted_by: `{provenance.drafted_by}`",
        f"- approved_by: `{provenance.approved_by}`",
        f"- approved_at: `{provenance.approved_at}`",
        "",
    ]
    return lines


def render(tool: str, contracts: list[ModuleContract], loaded) -> str:
    """One page. Every line traces to a field of a declared file.

    No hand-written sections and no splice markers: issue #41 found that a generator writing
    into a partly hand-edited page compares the hand-written half against itself and can
    never see an edit.
    """
    lines = [
        _GENERATED.rstrip("\n"),
        "",
        f"# {tool}",
        "",
        f"{len(contracts)} contract(s) in this layer stack.",
        "",
    ]
    for contract in contracts:
        lines += _contract_section(contract)
    return "\n".join(lines).rstrip("\n") + "\n"
```

- [ ] **Step 4: Run them and watch them pass**

Run: `uv run pytest packages/mendel-compiler/tests/test_tool_docs.py -v`
Expected: 9 passed.

- [ ] **Step 5: Watch the stability guard fail**

In `_states`, change `sorted(states)` to `states`. Rerun
`test_rendering_is_stable_across_two_calls` **repeatedly**:

```bash
for i in 1 2 3 4 5; do uv run pytest \
  packages/mendel-compiler/tests/test_tool_docs.py::test_rendering_is_stable_across_two_calls \
  -q 2>&1 | tail -1; done
```

Expected: it passes within one process because a frozenset's order is stable *per process* —
which is the point. Instead confirm the guard by comparing across processes:

```bash
uv run python -c "
from pathlib import Path
from mendel_compiler import tool_docs
from mendel_resolver import layers
l = layers.load([Path('registry')])
t = tool_docs.tools_of(l.registry)
print(hash(tool_docs.render('nf-core/star', t['nf-core/star'], l)))" 
```

Run that twice. With `sorted` removed the two hashes differ between runs (PYTHONHASHSEED
varies); with `sorted` restored they are equal. Record both in
`notes/audits/guard-ledger.md`. Then restore and clear `__pycache__`.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-compiler/
git commit -m "feat: render a tool page from declared data alone (comeni-registry#2)"
```

---

## Task 3: the two cross-references

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/tool_docs.py`
- Test: `packages/mendel-compiler/tests/test_tool_docs.py`

**Interfaces:**
- Produces: `tool_docs.sole_types(loaded) -> dict[str, list[str]]` (tool -> type ids only that
  tool produces) and `tool_docs.rules_naming(loaded) -> dict[str, list[str]]` (tool -> decision
  descriptions). Both consumed by `render`.

**Why these two and not the file path.** The spec §3.2 says "types the tool declares". A loaded
`Vocabulary` maps `type_id -> frozenset[state]` and **does not retain which file declared it**, so
that phrasing is not answerable from loaded data. The answerable and more useful fact is *which
types only this tool produces* — `genome.index.star` has exactly one producer, which is the fact
the old layout hid.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_type_with_one_producer_is_listed_on_that_tools_page():
    loaded = _layers()
    assert tool_docs.sole_types(loaded)["nf-core/star"] == ["genome.index.star"]
    assert tool_docs.sole_types(loaded)["nf-core/subread"] == ["counts.matrix"]


def test_a_type_two_tools_produce_is_listed_on_neither():
    """`alignment.bam` comes from both star and hisat2, so it is not either one's to claim."""
    loaded = _layers()
    for tool in ("nf-core/star", "nf-core/hisat2"):
        assert "alignment.bam" not in tool_docs.sole_types(loaded).get(tool, [])


def test_a_tool_a_rule_pins_says_so():
    """A contract selected by a tier-3 implementation rule is one whose selection is not
    free, and a reader deciding whether to use it should be told."""
    loaded = _layers()
    assert tool_docs.rules_naming(loaded)["nf-core/star"]


def test_a_tool_no_rule_names_has_no_entry():
    loaded = _layers()
    assert tool_docs.rules_naming(loaded).get("nf-core/multiqc") in (None, [])


def test_the_page_shows_both_cross_references():
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert "genome.index.star" in page
    assert "alignment" in page  # the role the rule decides
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest packages/mendel-compiler/tests/test_tool_docs.py -v`
Expected: FAIL, `AttributeError: ... has no attribute 'sole_types'`

- [ ] **Step 3: Implement both, and wire them into `render`**

```python
def sole_types(loaded) -> dict[str, list[str]]:
    """Types exactly one tool produces.

    The spec asked for "types the tool declares", which loaded data cannot answer: a
    `Vocabulary` maps `type_id -> frozenset[state]` and keeps no file path — deliberately,
    since comeni-registry#1 made the path meaningless. Sole production is the answerable
    fact, and it is the one the old layout hid: `genome.index.star` exists for `star` alone.
    """
    producers: dict[str, set[str]] = defaultdict(set)
    for contract_id, contract in loaded.registry.contracts.items():
        for port in contract.produces:
            producers[port.type_id].add(_tool_of(contract_id))
    owned: dict[str, list[str]] = defaultdict(list)
    for type_id, tools in producers.items():
        if len(tools) == 1:
            owned[next(iter(tools))].append(type_id)
    return {tool: sorted(types) for tool, types in sorted(owned.items())}


def rules_naming(loaded) -> dict[str, list[str]]:
    """Decisions whose rows select a contract belonging to each tool.

    `row.then` on an `implementation` decision is a contract id. A `param` decision names a
    parameter rather than a contract and is not a claim about this tool, so it is skipped.
    """
    named: dict[str, list[str]] = defaultdict(list)
    for decision in loaded.rules.decisions:
        target = decision.decides
        if target.effect.value != "implementation":
            continue
        for row in decision.rows:
            if not isinstance(row.then, str) or "@" not in row.then:
                continue
            entry = f"`{target.effect.value}` of role `{target.of}` — {decision.because}"
            tool = _tool_of(row.then)
            if entry not in named[tool]:
                named[tool].append(entry)
    return {tool: sorted(entries) for tool, entries in sorted(named.items())}
```

In `render`, after the contract sections, append:

```python
    owned = sole_types(loaded).get(tool, [])
    lines += ["## Types only this tool produces", ""]
    lines += [f"- `{t}`" for t in owned] if owned else ["None."]
    lines += [""]

    pinned = rules_naming(loaded).get(tool, [])
    lines += ["## Rules that select this tool", ""]
    lines += [f"- {entry}" for entry in pinned] if pinned else ["No rule names it."]
    lines += [""]
```

`render`'s signature does not change, so Task 2's tests still hold.

- [ ] **Step 4: Run them and watch them pass**

Run: `uv run pytest packages/mendel-compiler/tests/test_tool_docs.py -v`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-compiler/
git commit -m "feat: a tool page carries the two facts no single file holds (comeni-registry#2)"
```

---

## Task 4: the `mendel docs` verb

**Files:**
- Create: `packages/mendel-compiler/src/mendel_compiler/cli/layer_verbs.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli/parse.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli/__init__.py`
- Test: `tests/test_docs_verb.py`

**Interfaces:**
- Consumes: `tool_docs.tools_of`, `tool_docs.render`.
- Produces: `layer_verbs._docs_verb(registries: list[Path], out: Path, check: bool) -> int`.
  Returns `0` on success, `1` when `--check` finds a page stale or missing.

- [ ] **Step 1: Write the failing tests**

```python
"""`mendel docs` writes a page per tool, and `--check` refuses a stale one."""

import pathlib

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent


def test_docs_writes_one_page_per_tool(tmp_path):
    code = main(["docs", "--registry", str(ROOT / "registry"), "--out", str(tmp_path)])
    assert code == 0
    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.md"))
    assert written == [
        "comeni/profile.md",
        "nf-core/fastqc.md",
        "nf-core/hisat2.md",
        "nf-core/multiqc.md",
        "nf-core/samtools.md",
        "nf-core/star.md",
        "nf-core/subread.md",
        "nf-core/trimgalore.md",
    ]


def test_check_passes_against_pages_just_written(tmp_path):
    main(["docs", "--registry", str(ROOT / "registry"), "--out", str(tmp_path)])
    assert main(["docs", "--registry", str(ROOT / "registry"),
                 "--out", str(tmp_path), "--check"]) == 0


def test_check_refuses_a_hand_edited_page(tmp_path, capsys):
    main(["docs", "--registry", str(ROOT / "registry"), "--out", str(tmp_path)])
    page = tmp_path / "nf-core" / "star.md"
    page.write_text(page.read_text() + "\nhand written\n")
    assert main(["docs", "--registry", str(ROOT / "registry"),
                 "--out", str(tmp_path), "--check"]) == 1
    assert "star.md" in capsys.readouterr().out


def test_check_refuses_a_missing_page(tmp_path, capsys):
    main(["docs", "--registry", str(ROOT / "registry"), "--out", str(tmp_path)])
    (tmp_path / "nf-core" / "star.md").unlink()
    assert main(["docs", "--registry", str(ROOT / "registry"),
                 "--out", str(tmp_path), "--check"]) == 1
    assert "star.md" in capsys.readouterr().out


def test_check_writes_nothing(tmp_path):
    """`--check` is a question. A check that repairs what it measures cannot fail twice."""
    main(["docs", "--registry", str(ROOT / "registry"), "--out", str(tmp_path)])
    page = tmp_path / "nf-core" / "star.md"
    page.write_text("hand written\n")
    main(["docs", "--registry", str(ROOT / "registry"), "--out", str(tmp_path), "--check"])
    assert page.read_text() == "hand written\n"


def test_docs_needs_an_out(capsys):
    """Every other writing verb says so; this one must not silently write into cwd."""
    try:
        main(["docs", "--registry", str(ROOT / "registry")])
    except SystemExit as exit_:
        assert exit_.code == 2
    assert "--out" in capsys.readouterr().err
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_docs_verb.py -v`
Expected: FAIL — argparse rejects `docs` as an invalid choice.

- [ ] **Step 3: Write the verb**

Create `cli/layer_verbs.py`:

```python
"""Verbs that act on a **layer** rather than on a pipeline.

`cli/__init__.py` splits by what a verb does to a pipeline — `resolve_verbs` produces one,
`artifact_verbs` acts on one that exists. `docs` does neither: there is no pipeline anywhere
in its execution. That is a third category, and it gets its own module rather than being
wedged into `report` because both happen to write text — wedging is how `cli.py` reached the
851 lines issue #41 had to split.

comeni-registry#2.
"""

from pathlib import Path

from mendel_resolver import layers

from mendel_compiler import tool_docs


def _pages(registries: list[Path]) -> dict[Path, str]:
    """Relative page path -> its content. Pure enough to test without a filesystem."""
    loaded = layers.load(list(registries))
    grouped = tool_docs.tools_of(loaded.registry)
    return {
        Path(f"{tool}.md"): tool_docs.render(tool, contracts, loaded)
        for tool, contracts in grouped.items()
    }


def _docs_verb(registries: list[Path], out: Path, check: bool) -> int:
    """Write a page per tool, or with `--check` report the ones that disagree.

    `--check` writes nothing at all. A check that repairs what it measures reports success
    the second time it is run and can never fail twice, which is how `make drift`'s
    "skipped" managed to stay green over twelve edited contracts.
    """
    pages = _pages(registries)
    if check:
        stale = [
            path
            for path, content in pages.items()
            if not (out / path).exists() or (out / path).read_text() != content
        ]
        extra = [
            p.relative_to(out)
            for p in sorted(out.rglob("*.md"))
            if p.relative_to(out) not in pages
        ]
        for path in sorted(stale) + sorted(extra):
            print(f"{out / path} is stale — run: mendel docs --registry <layer> --out {out}")
        return 1 if stale or extra else 0

    for path, content in pages.items():
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    print(f"mendel: wrote {len(pages)} tool page(s) to {out}")
    return 0
```

In `parse.py`, add `"docs"` to the `command` choices and add the flag:

```python
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "`docs` only: write nothing and exit 1 if any page disagrees with the data. "
            "A check that repaired what it measured could never fail twice."
        ),
    )
```

In `cli/__init__.py`, import `layer_verbs` alongside the others, and add — **after** the
`explain` branch and **before** the `--dry-run` check, since `docs` accepts neither `--dry-run`
nor `--force` nor `--gate`:

```python
    # `docs` acts on a layer and produces no pipeline, so it returns before every flag
    # below, all of which describe a pipeline this verb never makes.
    if args.command == "docs":
        if args.out is None:
            parser.error("docs needs --out")
        if not args.registry:
            parser.error("docs needs at least one --registry")
        return layer_verbs._docs_verb(args.registry, args.out, args.check)
```

Guard `--check` against the other verbs, beside the existing `--dry-run` and `--force` guards:

```python
    if args.check and args.command != "docs":
        parser.error("--check is for `docs`; it asks whether the pages match the data")
```

- [ ] **Step 4: Run them and watch them pass**

Run: `uv run pytest tests/test_docs_verb.py -v`
Expected: 6 passed.

- [ ] **Step 5: Watch `--check` fail for the right reason**

Delete the `extra` list and its use, rerun `test_check_refuses_a_missing_page`. It still passes
(deletion is caught by `stale`), so instead delete the `not (out / path).exists()` clause and
rerun: expected FAIL with a `FileNotFoundError` rather than a clean exit 1 — which is the
message a registry contributor would have seen. Restore, clear `__pycache__`, and add the row
to `notes/audits/guard-ledger.md`.

- [ ] **Step 6: Run the full suite and commit**

```bash
make check
git add packages/mendel-compiler/ tests/test_docs_verb.py
git commit -m "feat: mendel docs — a verb that documents a layer (comeni-registry#2)"
```

---

## Task 5: the documents, and the canary

**Files:**
- Modify: `docs/reference/cli.md`
- Modify: `docs/guides/registry-layers.md`
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md` (the commands block)

- [ ] **Step 1: Record the canary**

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/canary
sha256sum /tmp/canary/main.nf /tmp/canary/nextflow.config
```

Expected: `76355bbf9f10d6e6…` and `72ddb081638edf76…`, unchanged. This task and the three
before it touch no emission path; if either moves, stop and find out why.

- [ ] **Step 2: `docs/reference/cli.md`**

Add a `## docs` section after `explain`, with the synopsis, both flags, and one worked example:

```bash
mendel docs --registry registry/ --out docs/tools          # write the pages
mendel docs --registry registry/ --out docs/tools --check   # fail if any is stale
```

State that the page set is derived from contract ids, not from directories, and that `--check`
writes nothing.

- [ ] **Step 3: `docs/guides/registry-layers.md`**

Add a short `## Documenting a layer` section after "Starting a layer": one command, and the note
that a private overlay is documented by stacking it over the base, because an overlay alone
usually cannot satisfy vocabulary closure.

- [ ] **Step 4: `CLAUDE.md` commands block**

Add beneath the `mendel profile` example:

```bash
# one Markdown page per tool, from the registry data alone
uv run mendel docs --registry registry/ --out /tmp/tool-docs
```

- [ ] **Step 5: `CHANGELOG.md`**

Under `[Unreleased]` → `### mendel-compiler`:

```markdown
- **`mendel docs`** — one Markdown page per tool, rendered from a layer's declared data.
  A tool is the first two segments of a contract's module key, never its directory, since
  comeni-registry#1 made the path meaningless. `--check` writes nothing and exits 1 on a
  stale page, which is what `comeni-registry`'s CI runs.
```

- [ ] **Step 6: `make verify`, canary, commit**

```bash
make verify
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/canary2
diff <(sha256sum < /tmp/canary/main.nf) <(sha256sum < /tmp/canary2/main.nf)
make links && make docs
git add -A
git commit -m "docs: mendel docs, in the CLI reference and the layer guide (comeni-registry#2)"
```

Then open the pull request. **Task 6 cannot start until this merges.**

---

## Task 6: `comeni-registry` — the workflows and the pages

**Repository:** `comeni-project/comeni-registry`. Work in a clone, not in the submodule
checkout — a detached HEAD inside `registry/` is not a branch.

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/compat.yml`
- Create: `docs/tools/**/*.md` (generated)
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Clone and branch**

```bash
git clone https://github.com/comeni-project/comeni-registry /tmp/comeni-registry
cd /tmp/comeni-registry && git checkout -b ci-and-tool-docs
```

- [ ] **Step 2: Generate the pages and read one before committing**

```bash
uv tool install --from "git+https://github.com/comeni-project/Comeni-Labs@main#subdirectory=packages/mendel-compiler" mendel
mendel docs --registry . --out docs/tools
cat docs/tools/nf-core/star.md
```

Read it. A generated file committed unread is the failure the Jinja golden-file gotcha records.

- [ ] **Step 3: `ci.yml`**

```yaml
name: check

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

env:
  # Comeni-Labs @ mendel-compiler 0.1.0. Pinned by SHA with the version in a trailing
  # comment — the convention Comeni-Labs applies to every Action, for the same reason:
  # a mutable ref can be repointed by whoever controls the other end. Bumping this is a
  # deliberate registry commit, and `docs/tools/` regenerates in the same diff.
  ENGINE_REF: <the merge commit of the Task 5 pull request>

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1

      - name: Install the engine at the pinned commit
        run: |
          uv tool install --from \
            "git+https://github.com/comeni-project/Comeni-Labs@${ENGINE_REF}#subdirectory=packages/mendel-compiler" \
            mendel

      # Every MD0001-MD0012 refusal, vocabulary closure, and rule validation against the
      # parameters contracts actually declare.
      #
      # NOT checked here, and it cannot be: conformance against module source (MD0104,
      # MD0105, container drift) compares a contract against a vendored main.nf, and this
      # repository has no vendor/ and should not — that copy is what issue #46 removed.
      # A contract naming a process no module defines merges here and is caught in the
      # Comeni-Labs pull request that bumps the pointer.
      - name: The layer loads
        run: mendel docs --registry . --out "$(mktemp -d)"

      - name: The committed pages match the data
        run: mendel docs --registry . --out docs/tools --check
```

- [ ] **Step 4: `compat.yml`**

Same install, against `main` rather than the pin, on `schedule: - cron: "0 6 * * 1"` plus
`workflow_dispatch`, with `permissions: issues: write`. On failure, open or update one tracking
issue. It must **fail** rather than skip when the install fails — `make drift` printed "skipped"
when its input was missing and stayed green over twelve edited contracts.

- [ ] **Step 5: `CONTRIBUTING.md`**

Where a new file goes (anywhere; it carries `declares:`), that `docs/tools/` is generated, and
the exact regeneration command. State plainly that regenerating needs the engine installed —
authoring registry data still needs no Python, but regenerating a page does.

- [ ] **Step 6: Watch CI fail on purpose**

Push a commit that edits `docs/tools/nf-core/star.md` by hand. Confirm the `--check` step fails
and names the file. Revert it. Record the row in `Comeni-Labs`' `notes/audits/guard-ledger.md`.

- [ ] **Step 7: Open the pull request**

---

## Self-review

**Spec coverage.** §3 → Tasks 1–4. §3.1 → Task 1. §3.2 → Tasks 2–3. §4 → Task 6 Step 3,
including the ungated conformance gap as a comment in the workflow. §5 → Task 6 Steps 3–4.
§6 → Task 6 Step 3's `ENGINE_REF`. §7 → the global constraint and Task 5's closing line.
§8 → nothing built, by construction.

**One spec requirement is deliberately not implemented as written**, and Task 3 says so inline:
§3.2's "types the tool declares" is not answerable from loaded data, because `Vocabulary` keeps
no file path. Task 3 implements "types only this tool produces", which is answerable and is the
fact the old layout actually hid. **Update the spec when this lands.**

**No new diagnostic code**, checked deliberately: the only new refusals are `parser.error` calls
(argparse, exit 2) and `--check`'s exit 1. Neither is a `coded()` site, so the
declared-but-never-emitted test stays green. If Task 4 grows a `raise ValueError`, it needs a
declared code first.

**Type consistency.** `_tool_of` (Task 1) is used by `sole_types` and `rules_naming` (Task 3).
`render(tool, contracts, loaded)` keeps one signature across Tasks 2 and 3. `_pages` and
`_docs_verb` (Task 4) consume `tools_of` and `render` unchanged.

**Placeholder scan.** One intentional placeholder: `ENGINE_REF` in Task 6 cannot be known until
Task 5 merges, and Step 3 says exactly what to put there.
