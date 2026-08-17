# Forge Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task, sequentially, driven by the primary agent. **Do NOT use
> `subagent-driven-development`** — `CLAUDE.md` forbids farming implementation out to subagents in
> this repository; subagents are for review and design only. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Put a model behind `mendel-forge`'s `HoleFiller` seam, and create `mendel-ai` — the
package every later AI subsystem will call.

**Architecture:** `mendel-ai` exposes one primitive, `generate(instruction, shape, evidence)`,
which validates model output against a declared Pydantic shape before any caller sees it;
`choose_one`/`choose_many` are helpers over it for closed-choice holes. `mendel-forge` gains
`ModelFiller`, which attempts only candidate-bearing holes and validates every answer twice.
Before either, `ModuleSpec` starts recording line numbers so the evidence a model reads quotes
real source instead of naming a file.

**Tech Stack:** Python 3.12+, Pydantic v2, LiteLLM, argparse, FastAPI (optional extra), pytest,
`uv` workspace.

**Spec:** [`notes/specs/2026-08-17-forge-phase-2.md`](../specs/2026-08-17-forge-phase-2.md) —
read it before Task 1. The plan argues from the spec and does not repeat its reasoning.

**Worktree:** `.worktrees/forge-phase-2`, branch `forge-phase-2`. Already created, with the
`registry/` submodule initialised.

---

## Global Constraints

- **Python floor is 3.12.** Every new `pyproject.toml` says `requires-python = ">=3.12"`.
- **Line length 100.** `uv run ruff check .` is a gate; `ruff format` is not — do not reformat
  files you are not otherwise changing.
- **Dependencies are lower bounds, no caps** — copy the style in
  `packages/mendel-forge/pyproject.toml`.
- **A new workspace member needs three edits, not one.** Its own `pyproject.toml`, plus the root
  `pyproject.toml`'s `dependencies` list *and* `[tool.uv.sources]`. `uv sync` installs nothing you
  do not depend on — a member listed only in `[tool.uv.sources]` is never installed and its
  imports fail.
- **A diagnostic code is DECLARED in `comeni_core/diagnostics.yml` and EMITTED through
  `coded()`.** Both directions are tested (`tests/test_diagnostics_ownership.py`), so **never
  declare a code in an earlier task than the one that raises it**. Never write a code into a
  string by hand. Run `make docs` after touching `diagnostics.yml`; CI checks the generated page.
- **`emitted_by` for new codes is `ai`** for anything raised in `mendel-ai`, `forge` for anything
  raised in `mendel-forge`.
- **No test may call a live model.** Task 7 builds the guard that enforces it; until then, every
  test uses an injected fake.
- **`make check` (~1 min) is the CI gate. `make verify` (~2 min, needs Docker) is what Tasks 1
  and 2 need** — they change how a vendored module is parsed, which feeds `conformance.py` and
  therefore a real build.
- **Never pass `--gate` to `mendel build` in a test** unless the test is about gates. CI has no
  Nextflow; it passes locally and fails in CI.
- **Import modules, not symbols, where tests monkeypatch.** `from x import f` binds past a later
  patch of `x.f`.
- **Determinism is not claimed for model fills.** The golden scaffold test
  (`packages/mendel-forge/tests/test_golden.py`) stays pinned to the `NoFiller` path. Do not add a
  golden file for a model-filled draft.
- **Expect to correct this plan while executing it.** Phase 1's plan needed five corrections and
  two were found only by running the loop by hand. Record each correction in the commit message
  that makes it, and run the documented loop end to end before believing the tests.

---

## File Structure

**Created:**

| Path | Responsibility |
|---|---|
| `packages/mendel-ai/pyproject.toml` | the new workspace member |
| `packages/mendel-ai/src/mendel_ai/__init__.py` | the package's public surface, re-exported |
| `packages/mendel-ai/src/mendel_ai/access.py` | `ModelAccess` — the three lanes, as config |
| `packages/mendel-ai/src/mendel_ai/client.py` | `Client.generate` — the one primitive |
| `packages/mendel-ai/src/mendel_ai/choice.py` | `choose_one` / `choose_many`, over `generate` |
| `packages/mendel-ai/src/mendel_ai/recorded.py` | record/replay transport for tests |
| `packages/mendel-ai/tests/` | unit tests plus committed fixtures |
| `packages/mendel-forge/src/mendel_forge/filler.py` | `ModelFiller`, implementing `HoleFiller` |

**Modified:**

| Path | Change |
|---|---|
| `packages/mendel-compiler/src/mendel_compiler/modulespec.py` | record a line per parsed fact |
| `packages/mendel-forge/src/mendel_forge/sources/nfcore.py` | one excerpt per fact, quoting source |
| `packages/mendel-forge/src/mendel_forge/ops.py` | `fill_with_model` op |
| `packages/mendel-forge/src/mendel_forge/cli/parse.py` | `--model` on the `fill` verb |
| `packages/mendel-forge/src/mendel_forge/cli/render.py` | render model fills, and mark them in `show` |
| `packages/mendel-forge/src/mendel_forge/http/__init__.py` | the model-fill route |
| `packages/mendel-forge/pyproject.toml` | depend on `mendel-ai` |
| `pyproject.toml` | the new member, in two places |
| `tests/test_purity.py` | `IMPURE_PACKAGES` gains `mendel-ai` |
| `packages/comeni-core/src/comeni_core/diagnostics.yml` | `MA` codes, each with its emitter |
| `CLAUDE.md`, `ARCHITECTURE.md`, `docs/design/clinical-data-protection.md` | invariant 14's scope, `--no-ai` |
| `docs/guides/driving-the-forge.md` | the `--model` step |
| `notes/journal/` | a new entry |

---

### Task 1: `ModuleSpec` records where each fact was read

**Why first:** every fact an `Observation` carries today shares one excerpt reading
`"FASTQC in main.nf"`. A human clicks through; a model learns nothing. Spec §3.3.

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/modulespec.py`
- Test: `packages/mendel-compiler/tests/test_modulespec_lines.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ModuleSpec.lines: dict[str, int]` — a 1-indexed line per parsed fact. Keys are
  `"process"`, `"container"`, `"inputs"`, `"outputs"`, `"reads_ext_args"`, `"reads_ext_prefix"`,
  `f"emits.{name}"`, `f"inputs.{position}"`, `f"meta_reads.{variable}.{key}"`. A fact the module
  does not have has no key. Task 2 is its only consumer.

**Design note for the implementer.** A parallel `lines` map is used rather than a `line` field on
`InputSlot`/`MetaRead` and a `Positions` model, because `emits` is a `list[str]` read by
`conformance.py` and `verify.py` — changing its element type is a breaking change across two
packages for no gain. One additive field breaks nothing. The cost is stringly-typed keys, which
is acceptable for a provenance side-table and is why the key convention is written above.

- [ ] **Step 1: Write the failing test**

Create `packages/mendel-compiler/tests/test_modulespec_lines.py`:

```python
"""`ModuleSpec` records where it read each fact.

Without this every `Fact` in an `Observation` cites the same location, which is enough for a
human to find the file and not enough for anyone — or anything — to read the evidence.
"""

from pathlib import Path

import pytest

from mendel_compiler.modulespec import ModuleSpec

ROOT = Path(__file__).resolve().parents[3]
FASTQC = ROOT / "vendor" / "modules" / "nf-core" / "fastqc" / "main.nf"


@pytest.fixture(scope="module")
def spec() -> ModuleSpec:
    return ModuleSpec.parse(FASTQC)


def _line(text: str, number: int) -> str:
    return text.splitlines()[number - 1]


def test_the_process_line_holds_the_process_declaration(spec: ModuleSpec) -> None:
    source = FASTQC.read_text()
    assert "process" in _line(source, spec.lines["process"])
    assert spec.process in _line(source, spec.lines["process"])


def test_every_recorded_line_is_within_the_file(spec: ModuleSpec) -> None:
    total = len(FASTQC.read_text().splitlines())
    assert spec.lines, "no positions were recorded at all"
    for key, number in spec.lines.items():
        assert 1 <= number <= total, f"{key} points at line {number} of a {total}-line file"


def test_every_emit_has_a_line_naming_it(spec: ModuleSpec) -> None:
    source = FASTQC.read_text()
    assert spec.emits, "fixture has no emits; pick a different module"
    for name in spec.emits:
        assert name in _line(source, spec.lines[f"emits.{name}"])


def test_the_container_line_holds_the_container(spec: ModuleSpec) -> None:
    assert spec.container is not None
    assert "container" in _line(FASTQC.read_text(), spec.lines["container"])


def test_a_fact_the_module_lacks_has_no_key(spec: ModuleSpec) -> None:
    """`reads_ext_prefix` is absent from three of the ten vendored modules — MD0108's
    real negatives. An absent fact must have no position rather than a zero."""
    if not spec.reads_ext_prefix:
        assert "reads_ext_prefix" not in spec.lines
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-compiler/tests/test_modulespec_lines.py -v
```

Expected: every test errors with `AttributeError` or a Pydantic validation error — `ModuleSpec`
has no `lines`.

- [ ] **Step 3: Add the field and a line helper**

In `modulespec.py`, beside the other module-level helpers:

```python
def _line_of(source: str, offset: int) -> int:
    """1-indexed line containing `offset`. `str.count` over a slice is exact and cheap."""
    return source.count("\n", 0, offset) + 1
```

On `ModuleSpec`, after `documented`:

```python
    lines: dict[str, int] = Field(default_factory=dict)
    """Where each fact was read, 1-indexed, keyed by fact.

    `"process"`, `"container"`, `"inputs"`, `"outputs"`, `"reads_ext_args"`,
    `"reads_ext_prefix"`, `f"emits.{name}"`, `f"inputs.{position}"`,
    `f"meta_reads.{variable}.{key}"`. **A fact the module does not have has no key** — an
    absent position must not read as line zero.

    A parallel map rather than a `line` on `InputSlot` and `MetaRead`, because `emits` is a
    `list[str]` that `conformance.py` and the forge both read; changing its element type is a
    breaking change for no gain. Added for the forge, whose evidence excerpts were citing one
    location for every fact — but a conformance diagnostic naming a line is the larger prize
    and is deliberately left for its own change.
    """
```

- [ ] **Step 4: Populate it in `parse`**

Replace the body of `ModuleSpec.parse` so the positions are collected as the facts are. Keep
every existing extraction exactly as it is — this task adds positions and changes nothing else.

```python
    @classmethod
    def parse(cls, main_nf: Path) -> "ModuleSpec":
        source = main_nf.read_text()

        process = _PROCESS.search(source)
        if process is None:
            raise ValueError(f"{main_nf}: no `process NAME {{` declaration")

        slots = _slots(source, main_nf)
        emits = _emits(source)
        meta_reads = [MetaRead(variable=v, key=k) for v, k in dict.fromkeys(_META.findall(source))]

        return cls(
            process=process.group(1),
            inputs=slots,
            emits=emits,
            container=_container(source),
            meta_reads=meta_reads,
            reads_ext_args="task.ext.args" in source,
            reads_ext_prefix="task.ext.prefix" in source,
            documented=_documented(main_nf.parent / "meta.yml"),
            lines=_positions(source, process, slots, emits, meta_reads),
        )
```

- [ ] **Step 5: Write `_positions`**

Below `_container` in the same module:

```python
def _positions(
    source: str,
    process: re.Match[str],
    slots: list[InputSlot],
    emits: list[str],
    meta_reads: list[MetaRead],
) -> dict[str, int]:
    """Where each fact was read. Absent facts get no key — see `ModuleSpec.lines`."""
    found = {"process": _line_of(source, process.start())}

    for key, pattern in (
        ("inputs", _INPUT_BLOCK),
        ("outputs", _OUTPUT_BLOCK),
        ("container", _CONTAINER),
    ):
        match = pattern.search(source)
        if match is not None:
            found[key] = _line_of(source, match.start())

    for key, needle in (
        ("reads_ext_args", "task.ext.args"),
        ("reads_ext_prefix", "task.ext.prefix"),
    ):
        at = source.find(needle)
        if at != -1:
            found[key] = _line_of(source, at)

    for name in emits:
        match = re.search(rf"\bemit:\s*{re.escape(name)}\b", source)
        if match is not None:
            found[f"emits.{name}"] = _line_of(source, match.start())

    for slot in slots:
        for name in slot.names:
            if not name:
                continue
            match = re.search(rf"\b(?:val|path|eval|env|stdout)\s*\(\s*{re.escape(name)}\b", source)
            if match is not None:
                found[f"inputs.{slot.position}"] = _line_of(source, match.start())
                break

    for read in meta_reads:
        match = re.search(rf"\b{re.escape(read.variable)}\.{re.escape(read.key)}\b", source)
        if match is not None:
            found[f"meta_reads.{read.variable}.{read.key}"] = _line_of(source, match.start())

    return found
```

- [ ] **Step 6: Run the new test**

```bash
uv run pytest packages/mendel-compiler/tests/test_modulespec_lines.py -v
```

Expected: all pass.

- [ ] **Step 7: Prove nothing else moved**

`modulespec.py` feeds `conformance.py`, which `mendel build` runs against every contract. It is
not one of the six files `CLAUDE.md` names, but it is upstream of a real build, so run the full
set rather than the fast one.

```bash
make verify
```

Expected: green, and no change to any golden file. **If a golden `.nf` digest moved, stop** —
this task must not change what is parsed, only what is recorded about where.

- [ ] **Step 8: Commit**

```bash
git add packages/mendel-compiler/src/mendel_compiler/modulespec.py \
        packages/mendel-compiler/tests/test_modulespec_lines.py
git commit -m "feat(compiler): ModuleSpec records where it read each fact

Every Fact in an Observation cited the same location — the file, and the
process name. Enough for a human to find the evidence, and nothing for
anyone reading the citation itself.

A parallel lines map rather than a line field on InputSlot and MetaRead:
emits is a list[str] that conformance.py and the forge both read, so
changing its element type breaks two packages for no gain. An absent fact
has no key, because a position that reads as line zero is worse than none.

Task 2 is the consumer. A conformance diagnostic naming a line is the
larger prize and is left for its own change."
```

---

### Task 2: one excerpt per fact, quoting the line

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/sources/nfcore.py`
- Test: `packages/mendel-forge/tests/test_nfcore_evidence.py` (create)

**Interfaces:**
- Consumes: `ModuleSpec.lines` from Task 1.
- Produces: an `Observation` whose `Fact.evidence` differs per fact — `locator` is
  `"<relative path>:<line>"` and `text` is that source line, stripped.

- [ ] **Step 1: Write the failing test**

Create `packages/mendel-forge/tests/test_nfcore_evidence.py`:

```python
"""Evidence a reader can read — including a reader that cannot open the file.

Before this, every fact in an Observation carried `locator="…/main.nf"` and
`text="FASTQC in main.nf"`. Nine facts, one citation, no line.
"""

from pathlib import Path

import pytest

from mendel_forge.sources import nfcore
from mendel_forge.sources import ToolRef

ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "vendor"
REF = ToolRef(source="nf-core", ident="fastqc")


@pytest.fixture(scope="module")
def observation():
    return nfcore.NfCoreSource().ingest(REF, VENDOR)


def test_facts_do_not_all_share_one_locator(observation) -> None:
    locators = {fact.evidence.locator for fact in observation.facts.values()}
    assert len(locators) > 1, f"every fact still cites {locators}"


def test_a_source_read_locator_names_a_line(observation) -> None:
    assert ":" in observation.facts["process"].evidence.locator
    path, _, line = observation.facts["process"].evidence.locator.rpartition(":")
    assert path.endswith("main.nf")
    assert line.isdigit()


def test_the_text_is_the_line_the_locator_names(observation) -> None:
    """The whole point: the citation quotes the evidence, rather than describing it."""
    for key in ("process", "emits", "container"):
        evidence = observation.facts[key].evidence
        path, _, line = evidence.locator.rpartition(":")
        actual = (ROOT / path).read_text().splitlines()[int(line) - 1]
        assert evidence.text == actual.strip()


def test_no_locator_is_an_absolute_path(observation) -> None:
    """Held already for the old locators; a line suffix must not reintroduce it."""
    for fact in observation.facts.values():
        assert not fact.evidence.locator.startswith("/")
    for excerpt in observation.prose:
        assert not excerpt.locator.startswith("/")


def test_a_derived_fact_says_so_rather_than_citing_a_line(observation) -> None:
    """`nf_include` is computed from the ref, not read from the module. Citing a line for it
    would be a false citation, which is worse than a vague one."""
    assert ":" not in observation.facts["nf_include"].evidence.locator
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-forge/tests/test_nfcore_evidence.py -v
```

Expected: `test_facts_do_not_all_share_one_locator` fails with one locator in the set; the
locator and text tests fail too.

- [ ] **Step 3: Replace the `fact` helper in `ingest`**

In `nfcore.py`, replace the single `fact` closure with one that takes a position key:

```python
        at = str(main_nf.relative_to(root))
        source_lines = main_nf.read_text().splitlines()

        def fact(value: object, position: str | None = None) -> Fact:
            """`position` is a key into `ModuleSpec.lines`. `None` means derived rather than
            read — citing a line for a computed value would be a false citation."""
            line = spec.lines.get(position) if position else None
            if line is None:
                return Fact(value=value, evidence=Excerpt(locator=at, text=f"read from {at}"))
            return Fact(
                value=value,
                evidence=Excerpt(locator=f"{at}:{line}", text=source_lines[line - 1].strip()),
            )
```

- [ ] **Step 4: Point each fact at its position**

```python
        facts = {
            "process": fact(spec.process, "process"),
            "emits": fact(list(spec.emits), "outputs"),
            "input_arity": fact(len(spec.inputs), "inputs"),
            "input_names": fact([slot.names for slot in spec.inputs], "inputs"),
            "meta_reads": fact(sorted({read.key for read in spec.meta_reads}), "inputs"),
            "reads_ext_args": fact(spec.reads_ext_args, "reads_ext_args"),
            "reads_ext_prefix": fact(spec.reads_ext_prefix, "reads_ext_prefix"),
            "nf_include": fact(f"modules/nf-core/{ref.ident}/main"),
        }
        if spec.container:
            facts["container"] = fact(spec.container, "container")
        if spec.documented:
            facts["documented_inputs"] = fact([d.name for d in spec.documented])
```

Note `meta_reads` cites the input block rather than a single read: the fact is the *set* of keys,
and citing the first one would claim the others came from there.

- [ ] **Step 5: Run the new test**

```bash
uv run pytest packages/mendel-forge/tests/test_nfcore_evidence.py -v
```

Expected: all pass.

- [ ] **Step 6: Regenerate the golden scaffolds and read the diff**

The golden scaffold fixtures embed evidence, so they move. **Read the diff before accepting it** —
that is what caught the absolute-path defect in Phase 1.

```bash
uv run pytest packages/mendel-forge/tests/test_golden.py -v
# then, only after reading why it failed:
FORGE_GOLDEN=update uv run pytest packages/mendel-forge/tests/test_golden.py -v
```

If it fails on changed evidence, regenerate with `FORGE_GOLDEN=update`, then:

```bash
git diff packages/mendel-forge/tests/
```

Expected in the diff: locators gaining `:<line>`, and text becoming real source lines. **Not
expected:** any absolute path, any changed `value`, any changed hole.

- [ ] **Step 7: Full verification**

```bash
make verify
```

- [ ] **Step 8: Commit**

```bash
git add packages/mendel-forge/src/mendel_forge/sources/nfcore.py \
        packages/mendel-forge/tests/
git commit -m "feat(forge): each fact cites the line it was read from

Every fact in an Observation carried locator=<file> and text='FASTQC in
main.nf'. Excerpt's own docstring called this out: enough to find the
evidence, not enough to read it.

A derived fact — nf_include, computed from the ref — deliberately keeps a
file-level locator. Citing a line for a value nothing read from that line
is a false citation, and worse than a vague one.

Golden scaffolds move, and the diff was read rather than accepted: locators
gain a line, text becomes real source, and no value or hole changed."
```

---

### Task 3: the `mendel-ai` package, and its classification

**Why this shape:** `test_every_package_is_classified` fails the moment a package directory exists
and is unlisted in `tests/test_purity.py` — that is A67/#31's guard, and it makes this task
self-forcing. `IMPURE_PACKAGES`'s docstring currently says `mendel-ai` is *deliberately* absent;
that sentence is edited here rather than deleted.

**Files:**
- Create: `packages/mendel-ai/pyproject.toml`, `packages/mendel-ai/README.md`,
  `packages/mendel-ai/LICENSE`, `packages/mendel-ai/src/mendel_ai/__init__.py`,
  `packages/mendel-ai/src/mendel_ai/py.typed`, `packages/mendel-ai/tests/test_package.py`
- Modify: `pyproject.toml` (two places), `tests/test_purity.py:121`

**Interfaces:**
- Consumes: nothing.
- Produces: an importable `mendel_ai` package. Tasks 4–7 add its contents.

- [ ] **Step 1: Write the failing test**

Create `packages/mendel-ai/tests/test_package.py`:

```python
"""The package exists, is importable, and is typed.

`uv sync` installs nothing you do not depend on: a workspace member listed only in
`[tool.uv.sources]` is never installed and its imports fail at the first use rather than at
sync. This test is what turns that into a fast failure.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_package_imports() -> None:
    import mendel_ai  # noqa: F401


def test_the_package_ships_a_py_typed_marker() -> None:
    assert (ROOT / "packages" / "mendel-ai" / "src" / "mendel_ai" / "py.typed").exists()


def test_the_root_project_depends_on_it() -> None:
    """Not just `[tool.uv.sources]` — that says where a member comes from, not that we want it."""
    manifest = (ROOT / "pyproject.toml").read_text()
    assert '"mendel-ai"' in manifest
    assert "mendel-ai = { workspace = true }" in manifest


def test_it_is_findable_as_an_installed_distribution() -> None:
    assert importlib.util.find_spec("mendel_ai") is not None
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-ai/tests/test_package.py -v
```

Expected: collection error — no such directory. That is the correct failure; create the files.

- [ ] **Step 3: Create the package manifest**

`packages/mendel-ai/pyproject.toml` — copy `mendel-forge`'s and change what differs:

```toml
[project]
name = "mendel-ai"
version = "0.1.0"
requires-python = ">=3.12"
description = "Model access for Mendel — one primitive, validated against a declared shape"
license = "Apache-2.0"
license-files = ["LICENSE"]
readme = "README.md"
authors = [{name = "Rafael Correia"}]
keywords = ["bioinformatics", "nextflow", "workflow", "reproducibility", "pipeline"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Science/Research",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Bio-Informatics",
    "Typing :: Typed",
]

# Lower bounds, no caps — see mendel-resolver's manifest and docs/guides/releasing.md.
# comeni-core is here for `coded()` and nothing else: this package holds no Mendel domain
# types, which is what lets a second consumer reuse it unchanged.
dependencies = [
  "comeni-core>=0.1.0",
  "litellm>=1.50",
  "pydantic>=2.9",
]

[project.urls]
Homepage = "https://github.com/comeni-project/Comeni-Labs"
Documentation = "https://github.com/comeni-project/Comeni-Labs/tree/main/docs"
Repository = "https://github.com/comeni-project/Comeni-Labs"
Issues = "https://github.com/comeni-project/Comeni-Labs/issues"
Changelog = "https://github.com/comeni-project/Comeni-Labs/blob/main/CHANGELOG.md"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mendel_ai"]
```

- [ ] **Step 4: Create the package body**

```bash
mkdir -p packages/mendel-ai/src/mendel_ai packages/mendel-ai/tests
touch packages/mendel-ai/src/mendel_ai/py.typed
cp packages/mendel-forge/LICENSE packages/mendel-ai/LICENSE
```

`packages/mendel-ai/src/mendel_ai/__init__.py`:

```python
"""Model access for Mendel.

**One primitive.** `generate(instruction, shape, evidence)` asks a model for something and
validates the answer against a declared Pydantic shape before any caller sees it. Closed
choice — `choose_one`, `choose_many` — is a helper over it, for the case where the shape is
*one of these values*.

That is the boundary, and it is the one the rest of the system already enforces: not that a
model may not speak, but that nothing it says is taken on trust. A drafted rule has the rule
validator; a `Goal` is a Pydantic model. **A module's script body has no shape**, which is why
`MF0005` refuses it and why nothing here will fill one.

**This package holds no Mendel domain types.** It speaks in strings and shapes its caller
declares, which is what lets the tier-4 ambiguity resolver reuse it unchanged when Plan 3
arrives (`notes/README.md` row 17). `comeni-core` is imported for `coded()` and nothing else.

**It is impure and classified as such** in `tests/test_purity.py`. The arrow points
`mendel-ai -> comeni-core`, never back.
"""
```

`packages/mendel-ai/README.md`:

```markdown
# mendel-ai

Model access for Mendel. One primitive — `generate(instruction, shape, evidence)` — which
validates model output against a declared Pydantic shape before returning it. `choose_one` and
`choose_many` are helpers over it for closed choices.

Impure by design: this is where the network lives. `comeni-core`, `mendel-resolver` and
`mendel-compiler` do not reach it, and `tests/test_purity.py` holds that direction.

See [`notes/specs/2026-08-17-forge-phase-2.md`](../../notes/specs/2026-08-17-forge-phase-2.md) §4.
```

- [ ] **Step 5: Register it in the workspace**

In the root `pyproject.toml`, two edits:

```toml
dependencies = ["comeni-core", "mendel-resolver", "mendel-compiler", "mendel-forge", "mendel-ai"]
```

```toml
[tool.uv.sources]
comeni-core = { workspace = true }
mendel-resolver = { workspace = true }
mendel-compiler = { workspace = true }
mendel-forge = { workspace = true }
mendel-ai = { workspace = true }
```

- [ ] **Step 6: Classify it**

In `tests/test_purity.py`, change line 121 and the docstring paragraph that names it:

```python
IMPURE_PACKAGES: list[str] = ["mendel-forge", "mendel-ai"]
```

In that docstring, replace the paragraph beginning `mendel-ai` and `mendel-api` are still
absent` with:

```
`mendel-ai` arrived with forge Phase 2 and is where the network lives — it is the package the
purity guards exist to keep the pure three away from. `mendel-api` is still absent, and is
deliberately *not* listed ahead of time: a name in a classification list that matches no
directory is a guard nobody is running, and `test_every_package_is_classified` refuses that too.
```

- [ ] **Step 7: Sync and run**

```bash
uv sync
uv run pytest packages/mendel-ai/tests/test_package.py -v
uv run pytest tests/test_purity.py -v
```

Expected: all pass. If `test_every_package_is_classified` fails, Step 6 was missed — that is the
guard working.

- [ ] **Step 8: Full check and commit**

```bash
make check
git add packages/mendel-ai pyproject.toml uv.lock tests/test_purity.py
git commit -m "feat(ai): the mendel-ai package, classified impure

Where the network lives. It holds no Mendel domain types — it speaks in
strings and shapes its caller declares, which is what lets the tier-4
ambiguity resolver reuse it unchanged in Plan 3. comeni-core is imported
for coded() and nothing else.

Registered in three places, not one: uv sync installs nothing you do not
depend on, so a member named only in [tool.uv.sources] is never installed
and fails at first import rather than at sync.

IMPURE_PACKAGES gains it, and the docstring sentence saying it was
deliberately absent is edited rather than deleted — mendel-api is still
absent and still deliberately unlisted, because a name matching no
directory is a guard nobody runs (A67, #31)."
```

---

### Task 4: `ModelAccess` — the three lanes as config

**Spec §4.4.** Invariant 13: self-hosted is not a degraded tier, so the lanes are one code path
with different config. Invariant 12: no subscription OAuth — enforced by the config having
nowhere to put one.

**Files:**
- Create: `packages/mendel-ai/src/mendel_ai/access.py`,
  `packages/mendel-ai/tests/test_access.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ModelAccess(model: str, api_key: str | None = None, base_url: str | None = None,
    timeout_seconds: float = 60.0)` — frozen, `extra="forbid"`.
  - `ModelAccess.from_env(env: Mapping[str, str]) -> ModelAccess | None` — `None` when
    `MENDEL_MODEL` is unset, which is the honest spelling of "no model was configured".

- [ ] **Step 1: Write the failing test**

Create `packages/mendel-ai/tests/test_access.py`:

```python
"""The three lanes, and the invariants they carry.

Invariant 13 — self-hosted is not a degraded tier — means the lanes differ by configuration
and not by code path. Invariant 12 — no subscription OAuth — is enforced by there being
nowhere to put a subscription token.
"""

import pytest
from pydantic import ValidationError

from mendel_ai.access import ModelAccess


def test_no_model_configured_is_none_rather_than_a_default() -> None:
    """A default model would make an unconfigured install quietly reach a provider."""
    assert ModelAccess.from_env({}) is None


def test_the_byo_key_lane() -> None:
    access = ModelAccess.from_env({"MENDEL_MODEL": "anthropic/claude-x", "MENDEL_API_KEY": "k"})
    assert access is not None
    assert access.model == "anthropic/claude-x"
    assert access.api_key == "k"
    assert access.base_url is None


def test_the_local_lane_needs_no_key() -> None:
    """Ollama and vLLM behind an OpenAI-compatible endpoint. Invariant 13: identical path."""
    access = ModelAccess.from_env(
        {"MENDEL_MODEL": "ollama/llama3", "MENDEL_BASE_URL": "http://localhost:11434"}
    )
    assert access is not None
    assert access.api_key is None
    assert access.base_url == "http://localhost:11434"


def test_there_is_nowhere_to_put_a_subscription_token() -> None:
    """Invariant 12. Enforced by shape: a field that does not exist cannot be filled."""
    assert "oauth" not in ModelAccess.model_fields
    assert "token" not in ModelAccess.model_fields
    with pytest.raises(ValidationError):
        ModelAccess(model="m", oauth_token="whatever")


def test_it_is_frozen() -> None:
    """What was configured is what is used — the same argument EgressPayload makes."""
    access = ModelAccess(model="m")
    with pytest.raises(ValidationError):
        access.model = "other"


def test_a_blank_model_is_not_a_model() -> None:
    assert ModelAccess.from_env({"MENDEL_MODEL": "   "}) is None
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-ai/tests/test_access.py -v
```

Expected: `ModuleNotFoundError: No module named 'mendel_ai.access'`.

- [ ] **Step 3: Write `access.py`**

```python
"""How a laboratory reaches a model. Three lanes, one code path.

**Invariant 13 — self-hosted is not a degraded tier.** BYO key, a local model behind an
OpenAI-compatible endpoint (Ollama and vLLM both qualify), and the hosted lane differ by what
is in this object and by nothing else. A branch per lane would be the design error that
invariant names.

**Invariant 12 — no subscription OAuth.** Claude Pro/Max tokens in third-party tools violate
Anthropic's Consumer ToS. There is no field here to put one in, and `extra="forbid"` refuses
an attempt. A ban enforced by having nowhere to write the value is worth more than one
enforced by a check somebody can forget to call.

**`from_env` returns `None` rather than a default.** A default model would make an
unconfigured install quietly reach a provider on somebody's first `forge fill --model`, which
is the opposite of what `--no-ai`-by-default means.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

MODEL = "MENDEL_MODEL"
API_KEY = "MENDEL_API_KEY"
BASE_URL = "MENDEL_BASE_URL"
TIMEOUT = "MENDEL_TIMEOUT_SECONDS"


class ModelAccess(BaseModel):
    """What is needed to reach one model. Frozen: what was configured is what is used."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    api_key: str | None = None
    """`None` is legal — a local endpoint needs no key, and requiring one would make the
    self-hosted lane the awkward one."""
    base_url: str | None = None
    """Set for a local or self-hosted OpenAI-compatible endpoint; `None` for a provider."""
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "ModelAccess | None":
        """`None` when no model is configured. Takes a mapping rather than reading `os.environ`
        so a test needs no monkeypatching and cannot leak the developer's own configuration."""
        model = env.get(MODEL, "").strip()
        if not model:
            return None
        timeout = env.get(TIMEOUT, "").strip()
        return cls(
            model=model,
            api_key=env.get(API_KEY) or None,
            base_url=env.get(BASE_URL) or None,
            timeout_seconds=float(timeout) if timeout else 60.0,
        )
```

- [ ] **Step 4: Run the test**

```bash
uv run pytest packages/mendel-ai/tests/test_access.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-ai/src/mendel_ai/access.py packages/mendel-ai/tests/test_access.py
git commit -m "feat(ai): ModelAccess — three lanes, one code path

Invariant 13 says self-hosted is not a degraded tier, so BYO key, a local
OpenAI-compatible endpoint and the hosted lane differ by configuration and
by nothing else.

Invariant 12 is enforced by shape rather than by a check: there is no field
to put a subscription token in, and extra='forbid' refuses an attempt.

from_env takes a mapping rather than reading os.environ, so a test cannot
leak the developer's own configuration into an assertion, and returns None
rather than a default — a default model makes an unconfigured install reach
a provider on somebody's first --model."
```

---

### Task 5: `generate` — the one primitive

**Spec §4.2, §4.3.** Model output validated against a declared Pydantic shape before any caller
sees it. Closed choice is Task 6's helper over this.

**Files:**
- Create: `packages/mendel-ai/src/mendel_ai/client.py`,
  `packages/mendel-ai/tests/test_generate.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`,
  `docs/reference/diagnostics.md` (generated)

**Interfaces:**
- Consumes: `ModelAccess` from Task 4.
- Produces:
  - `Transport` — a `Protocol` with `send(access: ModelAccess, prompt: str) -> str`.
  - `LiteLLMTransport` — the real one.
  - `Client(access: ModelAccess, transport: Transport | None = None)`; `transport=None` means
    `LiteLLMTransport`.
  - `Client.generate(instruction: str, shape: type[T], evidence: list[str]) -> T | None`.
  - `NoModelError` — raised by `Client.for_env` when nothing is configured.
  - `Client.for_env(env: Mapping[str, str]) -> Client` — raises `NoModelError` with `MA0001`.

**Design note.** The transport is a seam for the same reason `HoleFiller` is: it lets every test
in Tasks 5–9 run with no network and no fixtures, and it is what Task 7's record/replay plugs
into. JSON is requested in the prompt and validated with Pydantic rather than relying on a
provider's structured-output mode — invariant 13 says a local model must work identically, and
schema support varies by provider. A provider that *does* support it is an optimisation, not a
second code path, and is out of scope here.

- [ ] **Step 1: Declare the diagnostics**

In `packages/comeni-core/src/comeni_core/diagnostics.yml`, after the last `MF` entry:

```yaml
MA0001:
  emitted_by: ai
  concern: model-access
  says: "no model is configured, and something asked for one"
  fires_on: [forge fill --model]
  refuses: true
  fix: |
    Set `MENDEL_MODEL`, and either `MENDEL_API_KEY` for a provider or `MENDEL_BASE_URL`
    for a local endpoint:

        export MENDEL_MODEL=anthropic/claude-sonnet-4-5
        export MENDEL_API_KEY=sk-...

    Or drop `--model` — every forge verb works without one, and that is the lane CI runs.
  explanation: |
    There is deliberately no default model. A default would make an unconfigured install
    reach a provider the first time somebody typed `--model`, which is the opposite of
    what a no-AI default means. Refusing here costs one environment variable and makes
    "did this build talk to anybody" answerable by reading the configuration.
MA0002:
  emitted_by: ai
  concern: model-access
  says: "the provider refused the credentials"
  fires_on: [forge fill --model]
  refuses: true
  fix: |
    Check `MENDEL_API_KEY`. For a local endpoint set `MENDEL_BASE_URL` and leave the key
    unset — a local model needs no credential, and sending an empty one looks like a
    credential to a provider that wanted none.
  explanation: |
    Separated from a generic transport failure because the two have different fixes and
    a retry helps neither. An authentication failure is a configuration error and is
    reported as one.
MA0003:
  emitted_by: ai
  concern: model-access
  says: "the model did not answer within the timeout"
  fires_on: [forge fill --model]
  refuses: false
  fix: |
    Raise `MENDEL_TIMEOUT_SECONDS`, or use a smaller model. A local endpoint on a cold
    cache is the common cause — the first call loads weights.

        export MENDEL_TIMEOUT_SECONDS=180
  explanation: |
    Not a refusal, because a hole nobody answered is a hole a person still sees. The
    fill that timed out is reported as declined and the draft keeps every fill made
    before it — a flaky network must not cost a draft.
MA0006:
  emitted_by: ai
  concern: model-output
  says: "the model's answer was longer than the field allows"
  fires_on: [forge fill --model]
  refuses: false
  fix: |
    Nothing — the answer is discarded whole and the hole stays open for a person. The limit
    is in the schema the model was given, so a model that overruns was told the number and
    did not keep to it.
  explanation: |
    Separated from MA0004 on purpose. "The answer did not match the shape" is true of an
    overlong rationale and useless for it: this is the one shape violation with an obvious
    cause, and a refusal that cannot say why it refused is a refusal somebody guesses at.

    The rationale is capped because it is the one free-text field a model writes here. The
    cap does not close that side channel — it makes it the wrong shape for the things worth
    smuggling through it, a script body or a priority_because essay. **Refused rather than
    truncated:** a silently shortened rationale is a reviewer reading half a sentence and not
    knowing it.
MA0004:
  emitted_by: ai
  concern: model-output
  says: "the model's answer did not match the shape it was asked for"
  fires_on: [forge fill --model]
  refuses: false
  fix: |
    Nothing, usually — the hole is left open and a person answers it. If it happens for
    every hole, the model is too small for structured output; try a larger one.
  explanation: |
    **This is the guard, working.** The whole reason `generate` takes a shape is that a
    model's answer is checked against a declaration before any caller sees it. An answer
    that will not validate is discarded rather than repaired, because a half-built value
    is worse than an open hole: the hole is visible and the half-built value is not.
```

Then regenerate the page:

```bash
make docs
```

- [ ] **Step 2: Write the failing test**

Create `packages/mendel-ai/tests/test_generate.py`:

```python
"""`generate` validates before it returns, and declines rather than repairs.

Every test here injects a transport. No test in this repository may call a live model —
Task 7 builds the guard that enforces it.
"""

import pytest
from pydantic import BaseModel

from mendel_ai.access import ModelAccess
from mendel_ai.client import Client, NoModelError, Transport

ACCESS = ModelAccess(model="test/model")


class Answer(BaseModel):
    value: str
    why: str


class Fixed:
    """A transport that always returns the same body."""

    def __init__(self, body: str) -> None:
        self.body = body
        self.prompts: list[str] = []

    def send(self, access: ModelAccess, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.body


def test_a_well_shaped_answer_is_returned() -> None:
    client = Client(ACCESS, transport=Fixed('{"value": "qc", "why": "it QCs"}'))
    assert client.generate("pick one", Answer, ["evidence"]) == Answer(value="qc", why="it QCs")


def test_an_answer_that_does_not_validate_is_declined_not_repaired() -> None:
    """A half-built value is worse than an open hole: the hole is visible."""
    client = Client(ACCESS, transport=Fixed('{"value": "qc"}'))  # no `why`
    assert client.generate("pick one", Answer, []) is None


def test_a_non_json_answer_is_declined() -> None:
    client = Client(ACCESS, transport=Fixed("I think it should be qc, probably."))
    assert client.generate("pick one", Answer, []) is None


def test_json_inside_a_fenced_block_is_accepted() -> None:
    """Models fence JSON constantly. Refusing that is refusing a right answer for its wrapper."""
    client = Client(ACCESS, transport=Fixed('```json\n{"value": "qc", "why": "w"}\n```'))
    assert client.generate("pick one", Answer, []) == Answer(value="qc", why="w")


def test_the_evidence_reaches_the_prompt() -> None:
    transport = Fixed('{"value": "qc", "why": "w"}')
    Client(ACCESS, transport=transport).generate("pick one", Answer, ["FASTQC in main.nf:3"])
    assert "FASTQC in main.nf:3" in transport.prompts[0]


def test_the_shape_reaches_the_prompt() -> None:
    """A model asked for a shape it was never shown cannot produce it."""
    transport = Fixed('{"value": "qc", "why": "w"}')
    Client(ACCESS, transport=transport).generate("pick one", Answer, [])
    assert "why" in transport.prompts[0] and "value" in transport.prompts[0]


def test_no_model_configured_raises_a_coded_refusal() -> None:
    with pytest.raises(NoModelError) as raised:
        Client.for_env({})
    assert "MA0001" in str(raised.value)


def test_a_configured_env_builds_a_client() -> None:
    assert isinstance(Client.for_env({"MENDEL_MODEL": "test/model"}), Client)


def test_transport_is_a_protocol_anything_can_satisfy() -> None:
    """The seam Task 7's record/replay plugs into, and the reason no test needs a network."""
    assert isinstance(Fixed("{}"), Transport)
```

- [ ] **Step 3: Run it and watch it fail**

```bash
uv run pytest packages/mendel-ai/tests/test_generate.py -v
```

Expected: `ModuleNotFoundError: No module named 'mendel_ai.client'`.

- [ ] **Step 4: Write `client.py`**

```python
"""The one primitive, and the transport under it.

`generate` asks a model for something and **validates the answer against a declared shape
before any caller sees it.** That is the boundary this package exists to hold — not that a
model may not speak, but that nothing it says is taken on trust.

**An answer that will not validate is declined, never repaired.** A half-built value is worse
than an open hole, because the hole is visible to a reviewer and the half-built value is not.
`None` is a legal, expected answer.

**JSON is requested and validated here rather than delegated to a provider's structured-output
mode.** Invariant 13 says a local model must work identically, and schema support varies by
provider; one code path that always validates is the honest shape. A provider that supports
schemas natively is an optimisation on top, not a second path.

**`Transport` is a seam for the same reason `HoleFiller` is.** It lets every test run with no
network, and it is what the recorded fixtures plug into.
"""

import json
import re
from collections.abc import Mapping
from typing import Protocol, TypeVar

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ValidationError

from mendel_ai.access import ModelAccess

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


class NoModelError(RuntimeError):
    """Nothing was configured and something asked for a model. `MA0001`."""


class ModelUnavailableError(RuntimeError):
    """The provider refused credentials. `MA0002`."""


class Transport(Protocol):
    def send(self, access: ModelAccess, prompt: str) -> str: ...


class Client:
    def __init__(self, access: ModelAccess, transport: "Transport | None" = None) -> None:
        self.access = access
        self._transport = transport if transport is not None else LiteLLMTransport()

    @classmethod
    def for_env(cls, env: Mapping[str, str]) -> "Client":
        access = ModelAccess.from_env(env)
        if access is None:
            raise NoModelError(
                coded("MA0001", "no model is configured")
                + "\n  set MENDEL_MODEL, and MENDEL_API_KEY or MENDEL_BASE_URL"
            )
        return cls(access)

    def generate(self, instruction: str, shape: type[T], evidence: list[str]) -> T | None:
        """Ask, then validate. `None` when the model declines or its answer will not fit."""
        try:
            body = self._transport.send(self.access, _prompt(instruction, shape, evidence))
        except TimeoutError:
            return None
        payload = _json_in(body)
        if payload is None:
            return None
        try:
            return shape.model_validate_json(payload)
        except ValidationError:
            return None


def _prompt(instruction: str, shape: type[BaseModel], evidence: list[str]) -> str:
    """The shape is shown, not described. A model asked for a shape it never saw cannot
    produce it, and the JSON Schema is the shape's own account of itself."""
    parts = [
        instruction,
        "",
        "Answer with JSON only, matching this schema exactly:",
        json.dumps(shape.model_json_schema(), indent=2, sort_keys=True),
    ]
    if evidence:
        parts += ["", "Evidence:", *(f"- {line}" for line in evidence)]
    return "\n".join(parts)


def _json_in(body: str) -> str | None:
    """The body, or the JSON inside a fenced block. Models fence constantly, and refusing a
    right answer for its wrapper is refusing a right answer."""
    fenced = _FENCE.search(body)
    candidate = (fenced.group(1) if fenced else body).strip()
    return candidate or None


class LiteLLMTransport:
    """The real one. Imported lazily so the package is importable without a provider
    configured, which is what lets `--no-ai` stay the default lane."""

    def send(self, access: ModelAccess, prompt: str) -> str:
        import litellm

        try:
            response = litellm.completion(
                model=access.model,
                messages=[{"role": "user", "content": prompt}],
                api_key=access.api_key,
                base_url=access.base_url,
                timeout=access.timeout_seconds,
            )
        except litellm.AuthenticationError as failure:
            raise ModelUnavailableError(
                coded("MA0002", "the provider refused the credentials")
            ) from failure
        except litellm.Timeout as failure:
            raise TimeoutError(
                coded("MA0003", f"no answer within {access.timeout_seconds}s")
            ) from failure
        return response.choices[0].message.content or ""
```

- [ ] **Step 5: Emit `MA0004` where it belongs**

`MA0004` is declared and must be *emitted*, or `test_every_declared_code_is_emitted` goes red.
It is not a raise — a declined answer is a return value — so it is reported. Change `generate`'s
validation arm to record it:

```python
        try:
            return shape.model_validate_json(payload)
        except ValidationError as failure:
            self.last_refusal = _why_refused(shape, failure)
            return None
```

and add the helper below `_json_in`:

```python
def _why_refused(shape: type[BaseModel], failure: ValidationError) -> str:
    """Which shape violation, not merely that there was one.

    **A refusal that cannot say why it refused is a refusal somebody guesses at.** An overlong
    rationale is the one violation with an obvious cause and an obvious fix, so it gets its own
    code; reading Pydantic's own error types rather than checking a field by name means any
    capped field in any shape reports itself, not just the one this was written for.
    """
    too_long = [e for e in failure.errors() if e["type"] == "string_too_long"]
    if too_long:
        fields = ", ".join(".".join(str(part) for part in e["loc"]) for e in too_long)
        return coded("MA0006", f"{fields} was longer than the field allows")
    return coded("MA0004", f"the answer did not match {shape.__name__}")
```

and initialise `self.last_refusal: str | None = None` in `__init__`, with a docstring:

```python
        self.last_refusal: str | None = None
        """Why the most recent `generate` returned `None`, coded, for a caller that wants to
        report it. `None` when the last call succeeded or the model simply declined."""
```

Add a test for it in `test_generate.py`:

```python
import json

from pydantic import Field


class Capped(BaseModel):
    value: str
    why: str = Field(max_length=500)


def test_a_shape_mismatch_is_reported_with_its_code() -> None:
    client = Client(ACCESS, transport=Fixed('{"value": "qc"}'))
    assert client.generate("pick one", Answer, []) is None
    assert "MA0004" in (client.last_refusal or "")


def test_an_overlong_field_is_refused_with_its_own_code() -> None:
    """Not MA0004. The one shape violation with an obvious cause says so."""
    body = json.dumps({"value": "qc", "why": "x" * 5000})
    client = Client(ACCESS, transport=Fixed(body))
    assert client.generate("pick one", Capped, []) is None
    assert "MA0006" in (client.last_refusal or "")
    assert "MA0004" not in (client.last_refusal or "")


def test_the_overlong_refusal_names_the_field() -> None:
    """A code alone does not tell a reader which field overran."""
    body = json.dumps({"value": "qc", "why": "x" * 5000})
    client = Client(ACCESS, transport=Fixed(body))
    client.generate("pick one", Capped, [])
    assert "why" in (client.last_refusal or "")


def test_the_declared_limit_reaches_the_prompt() -> None:
    """A model told the number can keep to it; one punished for not guessing cannot."""
    transport = Fixed('{"value": "qc", "why": "w"}')
    Client(ACCESS, transport=transport).generate("pick one", Capped, [])
    assert "500" in transport.prompts[0]
```

- [ ] **Step 6: Run the tests**

```bash
uv run pytest packages/mendel-ai/tests/ -v
uv run pytest tests/test_diagnostics_ownership.py -v
```

Expected: all pass. If `test_every_declared_code_is_emitted` fails, a declared `MA` code has no
`coded()` call — that is the guard working, and the fix is to emit it or not to declare it yet.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-ai/src/mendel_ai/client.py packages/mendel-ai/tests/test_generate.py \
        packages/comeni-core/src/comeni_core/diagnostics.yml docs/reference/diagnostics.md
git commit -m "feat(ai): generate — ask, then validate against a declared shape

The boundary this package exists to hold. An answer that will not validate
is declined rather than repaired: a half-built value is worse than an open
hole, because the hole is visible to a reviewer and the value is not.

JSON is requested and validated here rather than delegated to a provider's
structured-output mode. Invariant 13 says a local model works identically,
and schema support varies by provider — one path that always validates is
the honest shape.

Transport is a seam for the same reason HoleFiller is: every test runs with
no network, and the recorded fixtures plug into it.

MA0001-MA0004, each emitted in this change. MA0003 and MA0004 do not refuse:
a hole nobody answered is a hole a person still sees."
```

---

### Task 6: `choose_one` and `choose_many`

**Spec §4.2.** Closed choice is a helper over `generate`, not the primitive. Two of them because
some holes are list-valued — `roles` and `produces[].state` take several members from one closed
set, which is why `Hole.legal` checks member by member.

**Files:**
- Create: `packages/mendel-ai/src/mendel_ai/choice.py`,
  `packages/mendel-ai/tests/test_choice.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`, `docs/reference/diagnostics.md`
- Modify: `packages/mendel-ai/src/mendel_ai/__init__.py` (re-export the surface)

**Interfaces:**
- Consumes: `Client.generate` from Task 5.
- Produces:
  - `Option(value: str, note: str = "")`
  - `Choice(value: str, why: str)`, `Choices(values: list[str], why: str)`
  - `choose_one(client: Client, question: str, options: list[Option], evidence: list[str])
    -> Choice | None`
  - `choose_many(...) -> Choices | None`

- [ ] **Step 1: Declare `MA0005`**

```yaml
MA0005:
  emitted_by: ai
  concern: model-output
  says: "the model picked a value it was not offered"
  fires_on: [forge fill --model]
  refuses: false
  fix: |
    Nothing — the answer is discarded and the hole stays open for a person. If it happens
    on every closed choice, the model is ignoring its options; try a larger one.
  explanation: |
    A closed choice is the half of model output that can be checked mechanically, and this
    is the check. Invariant 7 says vocabularies are closed: a contract naming an undeclared
    state fails to load, and refusing here moves that refusal earlier — to when the value is
    written rather than when the file is read.

    The same value is refused a second time by `Hole.legal` on the way into a scaffold. That
    is not redundant: it is the check that already existed for a person's fill, and routing
    a model's answer through it means one rule rather than two that can drift.
```

```bash
make docs
```

- [ ] **Step 2: Write the failing test**

Create `packages/mendel-ai/tests/test_choice.py`:

```python
"""Closed choice, over `generate`.

The value a model returns must be one it was offered. That is the half of model output that
can be checked mechanically, and it is why the forge attempts candidate-bearing holes only.
"""

from mendel_ai.access import ModelAccess
from mendel_ai.choice import WHY_LIMIT, Choice, Choices, Option, choose_many, choose_one
from mendel_ai.client import Client

ACCESS = ModelAccess(model="test/model")
OPTIONS = [Option(value="qc_per_sample", note="declared role"), Option(value="aligner")]


class Fixed:
    def __init__(self, body: str) -> None:
        self.body = body
        self.prompts: list[str] = []

    def send(self, access: ModelAccess, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.body


def _client(body: str) -> Client:
    return Client(ACCESS, transport=Fixed(body))


def test_choose_one_returns_the_picked_value() -> None:
    client = _client('{"value": "qc_per_sample", "why": "it QCs one sample"}')
    assert choose_one(client, "which role?", OPTIONS, []) == Choice(
        value="qc_per_sample", why="it QCs one sample"
    )


def test_a_value_outside_the_options_is_refused() -> None:
    client = _client('{"value": "invented_role", "why": "seemed right"}')
    assert choose_one(client, "which role?", OPTIONS, []) is None
    assert "MA0005" in (client.last_refusal or "")


def test_choose_many_returns_several() -> None:
    client = _client('{"values": ["qc_per_sample", "aligner"], "why": "both apply"}')
    assert choose_many(client, "which roles?", OPTIONS, []) == Choices(
        values=["qc_per_sample", "aligner"], why="both apply"
    )


def test_choose_many_refuses_if_any_member_was_not_offered() -> None:
    """Member by member, the same rule `Hole.legal` applies for the same reason."""
    client = _client('{"values": ["qc_per_sample", "invented"], "why": "w"}')
    assert choose_many(client, "which roles?", OPTIONS, []) is None
    assert "MA0005" in (client.last_refusal or "")


def test_choose_many_accepts_an_empty_answer() -> None:
    """'None of these' is a real answer to a closed choice, and it is not a refusal."""
    client = _client('{"values": [], "why": "none of these describe it"}')
    assert choose_many(client, "which roles?", OPTIONS, []) == Choices(values=[], why="none of these describe it")


def test_the_options_and_their_notes_reach_the_prompt() -> None:
    transport = Fixed('{"value": "qc_per_sample", "why": "w"}')
    choose_one(Client(ACCESS, transport=transport), "which role?", OPTIONS, [])
    assert "qc_per_sample" in transport.prompts[0]
    assert "declared role" in transport.prompts[0]


def test_a_declined_generate_stays_declined() -> None:
    assert choose_one(_client("not json at all"), "which role?", OPTIONS, []) is None


def test_an_overlong_rationale_is_refused_whole() -> None:
    """Refused rather than truncated: a shortened rationale is half a sentence a reviewer
    reads without knowing it was shortened."""
    import json

    body = json.dumps({"value": "qc_per_sample", "why": "x" * (WHY_LIMIT + 1)})
    client = _client(body)
    assert choose_one(client, "which role?", OPTIONS, []) is None
    assert "MA0006" in (client.last_refusal or "")


def test_a_rationale_at_the_limit_is_accepted() -> None:
    """An off-by-one here silently costs every long-but-legal answer."""
    import json

    body = json.dumps({"value": "qc_per_sample", "why": "x" * WHY_LIMIT})
    assert choose_one(_client(body), "which role?", OPTIONS, []) is not None


def test_no_options_is_none_rather_than_a_free_answer() -> None:
    """A hole with no candidates is free text, and #70 gates it. Asking anyway would be the
    one thing this design says it does not do."""
    assert choose_one(_client('{"value": "x", "why": "w"}'), "q", [], []) is None
```

- [ ] **Step 3: Run it and watch it fail**

```bash
uv run pytest packages/mendel-ai/tests/test_choice.py -v
```

Expected: `ModuleNotFoundError: No module named 'mendel_ai.choice'`.

- [ ] **Step 4: Write `choice.py`**

```python
"""Closed choice, as a helper over `generate`.

**Not the primitive.** The first design of this package made closed choice the whole surface,
which was wrong twice: it drew the boundary at *choice versus generation* rather than at
*validated against a declared shape*, and it was designed against the tier-4 ambiguity
resolver while the next consumer — the rule drafter — does not fit a list of options. Spec
§4.3 records both.

**Two functions because some holes are list-valued.** `roles` and `produces[].state` take
several members from one closed set, which is why `Hole.legal` checks member by member and why
a single-value return cannot fill them. The future `AmbiguityResolver` uses `choose_one` only —
`Resolution.chosen` is singular.

**Membership is checked here and again by the caller.** `Hole.legal` refuses the same value on
the way into a scaffold. Not redundant: that is the check a person's fill already goes through,
and routing a model's answer through it means one rule rather than two that drift.
"""

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, Field

from mendel_ai.client import Client

_NO_EXTRAS = ConfigDict(extra="forbid")


class Option(BaseModel):
    model_config = _NO_EXTRAS

    value: str
    note: str = ""
    """Where this option is declared, so the answer can cite something a reviewer can check."""


WHY_LIMIT = 500
"""How long a rationale may be.

A sentence or two. **This is the only free-text field a model writes in this package**, and the
cap is what makes it the wrong shape for the things worth smuggling through it — a module's
script body, or a `priority_because` essay. It does not close the side channel and is not sold as
doing so (spec §4.3.1).

A first number, expected to move once there are real drafts to look at. `MA0006` is what a reader
sees when it bites, so moving it is a decision somebody makes with evidence rather than a silence
somebody discovers.
"""


class Choice(BaseModel):
    model_config = _NO_EXTRAS

    value: str
    why: str = Field(max_length=WHY_LIMIT)


class Choices(BaseModel):
    model_config = _NO_EXTRAS

    values: list[str]
    """May be empty. 'None of these' is a real answer to a closed choice."""
    why: str = Field(max_length=WHY_LIMIT)


def _question(question: str, options: list[Option]) -> str:
    lines = [question, "", "Choose only from these:"]
    lines += [f"- {o.value}" + (f"  ({o.note})" if o.note else "") for o in options]
    return "\n".join(lines)


def choose_one(
    client: Client, question: str, options: list[Option], evidence: list[str]
) -> Choice | None:
    if not options:
        return None
    answer = client.generate(_question(question, options), Choice, evidence)
    if answer is None:
        return None
    if answer.value not in {o.value for o in options}:
        client.last_refusal = coded("MA0005", f"{answer.value!r} was not offered")
        return None
    return answer


def choose_many(
    client: Client, question: str, options: list[Option], evidence: list[str]
) -> Choices | None:
    if not options:
        return None
    answer = client.generate(_question(question, options), Choices, evidence)
    if answer is None:
        return None
    offered = {o.value for o in options}
    outside = [v for v in answer.values if v not in offered]
    if outside:
        client.last_refusal = coded("MA0005", f"{outside!r} were not offered")
        return None
    return answer
```

- [ ] **Step 5: Re-export the surface**

Append to `packages/mendel-ai/src/mendel_ai/__init__.py`:

```python
from mendel_ai.access import ModelAccess
from mendel_ai.choice import Choice, Choices, Option, choose_many, choose_one
from mendel_ai.client import Client, ModelUnavailableError, NoModelError, Transport

__all__ = [
    "Choice",
    "Choices",
    "Client",
    "ModelAccess",
    "ModelUnavailableError",
    "NoModelError",
    "Option",
    "Transport",
    "choose_many",
    "choose_one",
]
```

- [ ] **Step 6: Run and commit**

```bash
uv run pytest packages/mendel-ai/tests/ -v
uv run pytest tests/test_diagnostics_ownership.py -v
make check
git add packages/mendel-ai packages/comeni-core/src/comeni_core/diagnostics.yml \
        docs/reference/diagnostics.md
git commit -m "feat(ai): choose_one and choose_many, over generate

Closed choice is a helper, not the primitive — spec §4.3 records why the
first design had that backwards. Two functions because roles and
produces[].state take several members from one closed set, which is the
same reason Hole.legal checks member by member.

An empty answer from choose_many is legal: 'none of these' is a real answer
to a closed choice and is not a refusal. No options at all returns None
rather than asking anyway — a hole with no candidates is free text, and #70
is what gates it.

MA0005 when a model picks something it was not offered. The same value is
refused again by Hole.legal on the way into a scaffold, which is one rule
applied twice rather than two rules that can drift."
```

---

### Task 7: recorded fixtures, and the guard that no test calls a model

**`CLAUDE.md`:** *"`mendel-ai`: contract tests against recorded fixtures committed to the repo"*
and *"no test may call a live model"*. The second is stated and, until now, unenforced — there
was no model to reach.

**Files:**
- Create: `packages/mendel-ai/src/mendel_ai/recorded.py`,
  `packages/mendel-ai/tests/fixtures/roles-fastqc.json`,
  `packages/mendel-ai/tests/test_recorded.py`,
  `tests/test_no_live_model.py`

**Interfaces:**
- Consumes: `Transport` from Task 5.
- Produces:
  - `RecordedTransport(path: Path)` — replays a committed fixture, keyed by a digest of the
    prompt; raises `KeyError` naming the missing key when a prompt has no recording.
  - `RecordingTransport(inner: Transport, path: Path)` — writes fixtures. **Never used by a
    test**; it is the tool a developer runs by hand to capture one.

- [ ] **Step 1: Write the failing test**

Create `packages/mendel-ai/tests/test_recorded.py`:

```python
"""Recorded fixtures, so a contract test can run offline and forever.

A recording is keyed by a digest of the prompt, not by call order: a test that adds a call at
the front must not silently re-point every later assertion at the wrong answer.
"""

import json
from pathlib import Path

import pytest

from mendel_ai.access import ModelAccess
from mendel_ai.client import Client
from mendel_ai.recorded import RecordedTransport, key_for

ACCESS = ModelAccess(model="test/model")
FIXTURES = Path(__file__).parent / "fixtures"


def test_a_recorded_prompt_replays(tmp_path: Path) -> None:
    prompt = "which role?"
    path = tmp_path / "f.json"
    path.write_text(json.dumps({key_for(ACCESS, prompt): "an answer"}))
    assert RecordedTransport(path).send(ACCESS, prompt) == "an answer"


def test_an_unrecorded_prompt_fails_loudly_naming_its_key(tmp_path: Path) -> None:
    """Silence here would mean a test passing against a fixture for a different question."""
    path = tmp_path / "f.json"
    path.write_text("{}")
    with pytest.raises(KeyError) as raised:
        RecordedTransport(path).send(ACCESS, "unrecorded")
    assert key_for(ACCESS, "unrecorded") in str(raised.value)


def test_the_key_depends_on_the_model_as_well_as_the_prompt() -> None:
    """The same question to two models is two recordings."""
    other = ModelAccess(model="other/model")
    assert key_for(ACCESS, "q") != key_for(other, "q")


def test_the_committed_fixture_drives_a_real_choose(  # contract test
) -> None:
    """The shipped fixture, through the real Client and the real choose_one."""
    from mendel_ai.choice import Option, choose_one

    client = Client(ACCESS, transport=RecordedTransport(FIXTURES / "roles-fastqc.json"))
    picked = choose_one(
        client,
        "Which role does this tool play?",
        [Option(value="qc_per_sample", note="declared role"), Option(value="aligner")],
        ["FASTQC in main.nf:3"],
    )
    assert picked is not None
    assert picked.value == "qc_per_sample"
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-ai/tests/test_recorded.py -v
```

Expected: `ModuleNotFoundError: No module named 'mendel_ai.recorded'`.

- [ ] **Step 3: Write `recorded.py`**

```python
"""Recorded model answers, so a contract test runs offline and forever.

**Keyed by a digest of the prompt, not by call order.** Order-keyed recordings break in the
worst way: a test that adds a call at the front re-points every later assertion at the wrong
answer, and every one of them still passes.

**An unrecorded prompt raises, naming the key.** A recorded transport that invented a default
would let a test assert against a fixture for a different question, which is the failure this
exists to prevent.

`RecordingTransport` is the tool a developer runs by hand to capture a fixture. **No test uses
it** — `tests/test_no_live_model.py` is what holds that.
"""

import hashlib
import json
from pathlib import Path

from mendel_ai.access import ModelAccess
from mendel_ai.client import Transport


def key_for(access: ModelAccess, prompt: str) -> str:
    """The model as well as the prompt: the same question to two models is two recordings."""
    digest = hashlib.sha256(f"{access.model}\n{prompt}".encode()).hexdigest()
    return digest[:16]


class RecordedTransport:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._answers: dict[str, str] = json.loads(path.read_text())

    def send(self, access: ModelAccess, prompt: str) -> str:
        key = key_for(access, prompt)
        if key not in self._answers:
            raise KeyError(
                f"no recording for {key} in {self.path.name}. "
                f"Capture one with RecordingTransport, or check the prompt has not moved.\n"
                f"--- prompt ---\n{prompt}"
            )
        return self._answers[key]


class RecordingTransport:
    """Wraps a real transport and writes what it returns. **Run by hand, never by a test.**"""

    def __init__(self, inner: Transport, path: Path) -> None:
        self.inner = inner
        self.path = path

    def send(self, access: ModelAccess, prompt: str) -> str:
        answer = self.inner.send(access, prompt)
        existing = json.loads(self.path.read_text()) if self.path.exists() else {}
        existing[key_for(access, prompt)] = answer
        self.path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")
        return answer
```

- [ ] **Step 4: Create the committed fixture**

The prompt is built by `_prompt` and `_question`, so the key must be computed rather than
guessed. Generate it:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

from mendel_ai.access import ModelAccess
from mendel_ai.choice import Choice, Option, _question
from mendel_ai.client import _prompt
from mendel_ai.recorded import key_for

access = ModelAccess(model="test/model")
options = [Option(value="qc_per_sample", note="declared role"), Option(value="aligner")]
prompt = _prompt(
    _question("Which role does this tool play?", options), Choice, ["FASTQC in main.nf:3"]
)
answer = json.dumps(
    {
        "value": "qc_per_sample",
        "why": "it reports per-sample read quality and produces no alignment",
    }
)
out = Path("packages/mendel-ai/tests/fixtures/roles-fastqc.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({key_for(access, prompt): answer}, indent=2, sort_keys=True) + "\n")
print("wrote", out)
PY
```

**The fixture is generated rather than hand-written on purpose.** The key is a digest of the
prompt that `_prompt` and `_question` actually build, so a hand-written key would be wrong the
first time either of them changed a word — and the test would then fail with "no recording"
rather than with anything pointing at the cause. Regenerating is the documented fix when a
prompt moves.

- [ ] **Step 5: Write the live-model guard**

Create `tests/test_no_live_model.py`:

```python
"""No test may call a live model. `CLAUDE.md` says so; until Phase 2 nothing enforced it.

A static scan, and it is deliberately narrow: it looks for the two things that actually reach
a provider — `LiteLLMTransport` and `RecordingTransport` — anywhere under a `tests/` directory
or in a file named `test_*.py`. It cannot see a dynamically built transport, and it is not
trying to; the point is that reaching a model from a test has to be *deliberate and visible*,
which is the same standing invariant 1's scan has (`cost-raising, not a proof`).
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {"LiteLLMTransport", "RecordingTransport"}

# This file names them in prose and in this set; it is the one file exempt from its own rule.
EXEMPT = {Path(__file__).resolve()}


def _test_files() -> list[Path]:
    found = [p for p in ROOT.rglob("test_*.py") if ".worktrees" not in p.parts]
    found += [p for p in ROOT.rglob("tests/**/*.py") if ".worktrees" not in p.parts]
    return sorted({p.resolve() for p in found} - EXEMPT)


def test_no_test_file_names_a_live_transport() -> None:
    offenders: list[str] = []
    for path in _test_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            name = getattr(node, "id", None) or getattr(node, "attr", None)
            if name in FORBIDDEN:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} names {name}")
    assert not offenders, "a test reaches a live model:\n  " + "\n  ".join(offenders)


def test_the_scan_sees_the_names_it_is_looking_for() -> None:
    """A scan that matches nothing passes vacuously. This is the same lesson as A67 — a guard
    over an empty list is a guard nobody is running."""
    tree = ast.parse("LiteLLMTransport()\nx.RecordingTransport\n")
    found = {
        getattr(n, "id", None) or getattr(n, "attr", None)
        for n in ast.walk(tree)
    }
    assert FORBIDDEN <= found
```

- [ ] **Step 6: Watch the guard fail on purpose, and record it**

**This is required, not optional.** `CLAUDE.md`: *"Guards must be watched failing"*, and A14 is
open precisely because guards without a recorded revert may be inert rather than weak.

```bash
# Add a line naming LiteLLMTransport to any test file, then:
uv run pytest tests/test_no_live_model.py -v
```

Expected: FAIL, printing the file, line and name. Copy the message, revert the change, and
append a row to `notes/audits/guard-ledger.md` in the format the existing rows use.

- [ ] **Step 7: Run and commit**

```bash
uv run pytest packages/mendel-ai/tests/ tests/test_no_live_model.py -v
make check
git add packages/mendel-ai tests/test_no_live_model.py notes/audits/guard-ledger.md
git commit -m "test(ai): recorded fixtures, and the guard that no test calls a model

Recordings are keyed by a digest of the prompt and the model, not by call
order. Order-keyed fixtures break in the worst way: adding a call at the
front re-points every later assertion at a different answer and they all
still pass. An unrecorded prompt raises, naming its key and printing the
prompt, rather than inventing a default.

CLAUDE.md has said no test may call a live model since before there was a
model to call. tests/test_no_live_model.py is now what holds it — a narrow
static scan for the two transports that actually reach a provider, with the
same standing as invariant 1's scan: cost-raising, not a proof.

Watched failing, and the message is in the guard ledger."
```

---

### Task 8: `ModelFiller` — the seam, filled

**Spec §5.** A hole with no candidates is declined. Every answer is validated twice.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/filler.py`,
  `packages/mendel-forge/tests/test_filler.py`
- Modify: `packages/mendel-forge/pyproject.toml` (depend on `mendel-ai`)

**Interfaces:**
- Consumes: `Client`, `Option`, `choose_one`, `choose_many` from Tasks 5–6; `Hole`,
  `FilledValue`, `Filler` from `mendel_forge.scaffold`; `Observation` from
  `mendel_forge.observe`.
- Produces: `ModelFiller(client: Client, model_id: str)` satisfying
  `mendel_forge.ports.HoleFiller` — `fill(hole, observation) -> FilledValue | None`.

**Design note.** Which holes are list-valued is decided by the field name, not by the candidates:
`roles` and anything ending `state` or `state_required` take several members. That mirrors
`candidates.for_field`'s own dispatch, and the plan puts the two lists beside each other so a
future field added to one is visibly missing from the other.

- [ ] **Step 1: Write the failing test**

Create `packages/mendel-forge/tests/test_filler.py`:

```python
"""A model fills a hole, or declines it. Nothing in between.

Every test injects a transport — no test in this repository may reach a live model, and
`tests/test_no_live_model.py` is what holds that.
"""

from mendel_ai.access import ModelAccess
from mendel_ai.client import Client

from mendel_forge.filler import ModelFiller
from mendel_forge.observe import Excerpt, Observation
from mendel_forge.ports import HoleFiller
from mendel_forge.scaffold import Candidate, Filler, Hole

ACCESS = ModelAccess(model="test/model")

OBSERVATION = Observation(
    source="nf-core",
    ref_id="nf-core:fastqc",
    facts={},
    prose=[Excerpt(locator="meta.yml:description", text="Runs FastQC on sequencing reads")],
)


class Fixed:
    def __init__(self, body: str) -> None:
        self.body = body
        self.prompts: list[str] = []

    def send(self, access: ModelAccess, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.body


def _filler(body: str) -> ModelFiller:
    return ModelFiller(Client(ACCESS, transport=Fixed(body)), model_id="test/model")


ROLES = Hole(
    field="roles",
    what="what this tool is for",
    why_open="a judgement",
    candidates=[Candidate(value="qc_per_sample", note="declared role")],
    evidence=[Excerpt(locator="main.nf:3", text="process FASTQC {")],
)

TYPE_ID = Hole(
    field="produces[0].type_id",
    what="what the port carries",
    why_open="not derivable",
    candidates=[Candidate(value="qc.report"), Candidate(value="alignment.bam")],
)

PROSE = Hole(field="priority_because", what="why it ranks", why_open="a judgement")


def test_it_satisfies_the_port() -> None:
    assert isinstance(_filler("{}"), HoleFiller)


def test_a_single_valued_hole_is_filled() -> None:
    filled = _filler('{"value": "qc.report", "why": "it emits a report"}').fill(
        TYPE_ID, OBSERVATION
    )
    assert filled is not None
    assert filled.value == "qc.report"
    assert filled.filler is Filler.MODEL
    assert filled.by == "test/model"
    assert filled.why == "it emits a report"


def test_a_list_valued_hole_gets_a_list() -> None:
    """`roles` takes several members from one closed set — the reason `choose_many` exists."""
    filled = _filler('{"values": ["qc_per_sample"], "why": "it QCs a sample"}').fill(
        ROLES, OBSERVATION
    )
    assert filled is not None
    assert filled.value == ["qc_per_sample"]


def test_a_hole_with_no_candidates_is_declined_without_asking() -> None:
    """#70 gates prose. Asking anyway is the one thing this design says it does not do."""
    transport = Fixed('{"value": "x", "why": "w"}')
    filler = ModelFiller(Client(ACCESS, transport=transport), model_id="test/model")
    assert filler.fill(PROSE, OBSERVATION) is None
    assert transport.prompts == [], "a prose hole was sent to a model"


def test_a_value_outside_the_candidates_is_declined() -> None:
    assert _filler('{"value": "invented", "why": "w"}').fill(TYPE_ID, OBSERVATION) is None


def test_a_declined_model_leaves_the_hole_open() -> None:
    assert _filler("not json").fill(TYPE_ID, OBSERVATION) is None


def test_the_evidence_and_prose_reach_the_prompt() -> None:
    transport = Fixed('{"values": ["qc_per_sample"], "why": "w"}')
    ModelFiller(Client(ACCESS, transport=transport), model_id="test/model").fill(
        ROLES, OBSERVATION
    )
    prompt = transport.prompts[0]
    assert "main.nf:3" in prompt
    assert "Runs FastQC on sequencing reads" in prompt


def test_the_answer_is_legal_for_the_hole() -> None:
    """The second validation. `hole.legal` is the check a person's fill already goes through."""
    filled = _filler('{"values": ["qc_per_sample"], "why": "w"}').fill(ROLES, OBSERVATION)
    assert filled is not None
    assert ROLES.legal(filled.value)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-forge/tests/test_filler.py -v
```

Expected: `ModuleNotFoundError: No module named 'mendel_ai'` — the dependency is not declared
yet — or `No module named 'mendel_forge.filler'` once it is.

- [ ] **Step 3: Declare the dependency**

In `packages/mendel-forge/pyproject.toml`, add to `dependencies`:

```toml
  "mendel-ai>=0.1.0",
```

Then `uv sync`.

- [ ] **Step 4: Write `filler.py`**

```python
"""A model, behind the `HoleFiller` seam.

**Candidate-bearing holes only.** A hole with candidates is checkable: the candidates come off
the layer stack, and `Hole.legal` refuses anything outside them. A hole without them is free
text, nothing can check it, and the one such value that reaches the registry —
`priority_because` — is gated by issue #70. This filler does not ask about them at all, which
is stronger than asking and discarding: no prose about them ever leaves.

**Validated twice, deliberately.** `choose_*` refuses a value the model was not offered, and
`hole.legal` refuses it again here. That is not redundancy — the second is the check a person's
fill already goes through, and routing a model's answer through it means one rule rather than
two that drift.

**`None` is a normal answer.** A hole a model declines is a hole a person still sees, which is
`ports.py`'s point and the reason the return type has always been optional.
"""

from mendel_ai.choice import Option, choose_many, choose_one
from mendel_ai.client import Client

from mendel_forge.observe import Observation
from mendel_forge.scaffold import FilledValue, Filler, Hole

_LIST_VALUED = ("roles",)
"""Fields holding several members of one closed set.

Kept beside `_LIST_SUFFIXES` and mirroring `candidates.for_field`'s dispatch, so a field added
to one is visibly missing from the other. `Hole.legal` checks these member by member, which is
why they need `choose_many` rather than `choose_one`.
"""

_LIST_SUFFIXES = ("state", "state_required")


def _is_list_valued(field: str) -> bool:
    base = field.rsplit(".", 1)[-1]
    return field in _LIST_VALUED or base in _LIST_VALUED or base.endswith(_LIST_SUFFIXES)


class ModelFiller:
    """Phase 2's implementation of `HoleFiller`."""

    def __init__(self, client: Client, model_id: str) -> None:
        self.client = client
        self.model_id = model_id

    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None:
        if not hole.candidates:
            return None

        options = [Option(value=c.value, note=c.note) for c in hole.candidates]
        evidence = [f"{e.locator}: {e.text}" for e in (*hole.evidence, *observation.prose)]
        question = f"{hole.what}\n\nThis is the field {hole.field} of a Mendel module contract."

        if _is_list_valued(hole.field):
            answer = choose_many(self.client, question, options, evidence)
            value: object | None = answer.values if answer else None
        else:
            picked = choose_one(self.client, question, options, evidence)
            answer = picked
            value = picked.value if picked else None

        if answer is None or value is None:
            return None
        if not hole.legal(value):
            return None
        return FilledValue(
            value=value, filler=Filler.MODEL, by=self.model_id, why=answer.why
        )
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest packages/mendel-forge/tests/test_filler.py -v
uv run pytest tests/test_purity.py -v
```

Expected: all pass. `test_no_pure_package_imports_an_impure_one` must stay green — the arrow is
`mendel-forge -> mendel-ai`, and both are impure.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-forge/src/mendel_forge/filler.py \
        packages/mendel-forge/tests/test_filler.py \
        packages/mendel-forge/pyproject.toml uv.lock
git commit -m "feat(forge): ModelFiller — the seam, filled

Candidate-bearing holes only. A prose hole is declined without being sent
at all, which is stronger than asking and discarding: no prose about it
ever leaves. #70 is what gates the other direction.

Validated twice on purpose. choose_* refuses a value the model was not
offered; hole.legal refuses it again here. The second is the check a
person's fill already goes through, so a model's answer meets one rule
rather than a second that can drift from it.

Which fields are list-valued mirrors candidates.for_field's dispatch, and
the two lists sit beside each other so a field added to one is visibly
missing from the other."
```

---

### Task 9: `ops.fill_with_model`

**Spec §5.1.** One op, persisting after every fill. A separate op from `fill` because
`FillRequest`'s `value`, `by` and `why` are all required and a model fill supplies none of them
up front — making them optional to share a request model would weaken the hand-fill path to suit
the model one.

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/ops.py`
- Test: `packages/mendel-forge/tests/test_ops_model_fill.py` (create)

**Interfaces:**
- Consumes: `ModelFiller` from Task 8; `Workspace`, `Draft` from `mendel_forge.workspace`.
- Produces:
  - `ModelFillRequest(name: str, field: str | None, workspace_root: Path, model: str,
    api_key: str | None, base_url: str | None)` — `field=None` means every candidate-bearing
    hole.
  - `ModelFillOutcome(field: str, filled: bool, value: Any | None, why: str | None,
    declined_because: str | None)`
  - `ModelFillResult(name: str, outcomes: list[ModelFillOutcome], remaining: list[str])`
  - `fill_with_model(req: ModelFillRequest, filler: HoleFiller | None = None) -> ModelFillResult`
    — `filler=None` builds a `ModelFiller` from the request; a test injects one.

- [ ] **Step 1: Write the failing test**

Create `packages/mendel-forge/tests/test_ops_model_fill.py`:

```python
"""The model-fill op: attempt, persist, report.

Persistence is per fill rather than per batch. A provider dying after eight of fifteen holes
must cost eight holes' worth of nothing — the draft is the thing the forge accumulates.
"""

from pathlib import Path

import pytest

from mendel_forge import ops
from mendel_forge.observe import Observation
from mendel_forge.scaffold import Candidate, FilledValue, Filler, Hole, Scaffold
from mendel_forge.workspace import Draft, Workspace

from comeni_core.declared import DeclaredKind


def _scaffold() -> Scaffold:
    return Scaffold(
        kind=DeclaredKind.CONTRACT,
        target="fastqc",
        observation=Observation(source="nf-core", ref_id="nf-core:fastqc", facts={}, prose=[]),
        filled={},
        holes=[
            Hole(
                field="produces[0].type_id",
                what="what the port carries",
                why_open="not derivable",
                candidates=[Candidate(value="qc.report")],
            ),
            Hole(field="priority_because", what="why it ranks", why_open="a judgement"),
        ],
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    Workspace(root=tmp_path).save(Draft(name="fastqc", scaffold=_scaffold(), module=None))
    return tmp_path


class Always:
    """Fills anything with candidates."""

    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None:
        if not hole.candidates:
            return None
        return FilledValue(
            value=hole.candidates[0].value, filler=Filler.MODEL, by="test/model", why="because"
        )


class Explodes:
    """Fills the first hole, then fails — the flaky-provider case."""

    def __init__(self) -> None:
        self.calls = 0

    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None:
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("provider went away")
        return FilledValue(
            value=hole.candidates[0].value, filler=Filler.MODEL, by="test/model", why="because"
        )


def _request(root: Path, field: str | None = None) -> ops.ModelFillRequest:
    return ops.ModelFillRequest(
        name="fastqc", field=field, workspace_root=root, model="test/model"
    )


def test_it_fills_every_candidate_bearing_hole(workspace: Path) -> None:
    result = ops.fill_with_model(_request(workspace), filler=Always())
    filled = {o.field for o in result.outcomes if o.filled}
    assert filled == {"produces[0].type_id"}


def test_a_prose_hole_is_reported_as_declined_rather_than_omitted(workspace: Path) -> None:
    """A hole nobody attempted must not look like a hole that does not exist."""
    result = ops.fill_with_model(_request(workspace), filler=Always())
    declined = {o.field for o in result.outcomes if not o.filled}
    assert declined == {"priority_because"}
    assert all(o.declined_because for o in result.outcomes if not o.filled)


def test_the_fill_is_persisted(workspace: Path) -> None:
    ops.fill_with_model(_request(workspace), filler=Always())
    found = Workspace(root=workspace).load("fastqc")
    assert found.scaffold.filled["produces[0].type_id"].filler is Filler.MODEL
    assert found.scaffold.filled["produces[0].type_id"].by == "test/model"


def test_one_named_field_attempts_only_that_field(workspace: Path) -> None:
    result = ops.fill_with_model(
        _request(workspace, field="produces[0].type_id"), filler=Always()
    )
    assert [o.field for o in result.outcomes] == ["produces[0].type_id"]


def test_a_provider_dying_mid_batch_keeps_what_was_filled(workspace: Path) -> None:
    """The reason persistence is per fill. Eight of fifteen must cost nothing."""
    with pytest.raises(RuntimeError):
        ops.fill_with_model(_request(workspace), filler=Explodes())
    found = Workspace(root=workspace).load("fastqc")
    assert "produces[0].type_id" in found.scaffold.filled


def test_remaining_lists_the_holes_still_open(workspace: Path) -> None:
    result = ops.fill_with_model(_request(workspace), filler=Always())
    assert result.remaining == ["priority_because"]
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-forge/tests/test_ops_model_fill.py -v
```

Expected: `AttributeError: module 'mendel_forge.ops' has no attribute 'ModelFillRequest'`.

- [ ] **Step 3: Add the models and the op**

In `ops.py`, after `FillResult`:

```python
class ModelFillRequest(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    field: str | None = None
    """`None` attempts every candidate-bearing hole."""
    workspace_root: Path
    model: str
    api_key: str | None = None
    base_url: str | None = None


class ModelFillOutcome(BaseModel):
    model_config = _NO_EXTRAS

    field: str
    filled: bool
    value: Any | None = None
    why: str | None = None
    declined_because: str | None = None
    """Why a hole was not filled. **Never `None` when `filled` is false** — a hole nobody
    attempted must not look like a hole that does not exist."""


class ModelFillResult(BaseModel):
    model_config = _NO_EXTRAS

    name: str
    outcomes: list[ModelFillOutcome]
    remaining: list[str]
```

And the op, after `fill`:

```python
def fill_with_model(
    req: ModelFillRequest, filler: "HoleFiller | None" = None
) -> ModelFillResult:
    """Attempt each hole, persisting after each one.

    **Per fill, not per batch.** A provider dying after eight of fifteen holes must cost
    nothing — the draft is what the forge accumulates, and an all-or-nothing batch makes a
    flaky network expensive.
    """
    workspace = Workspace(root=req.workspace_root)
    found = workspace.load(req.name)
    if filler is None:
        filler = ModelFiller(
            Client(
                ModelAccess(model=req.model, api_key=req.api_key, base_url=req.base_url)
            ),
            model_id=req.model,
        )

    targets = [h for h in found.scaffold.holes if req.field is None or h.field == req.field]
    if req.field is not None and not targets:
        raise ValueError(coded("MF0002", f"{req.field} is not a hole in {req.name}"))

    outcomes: list[ModelFillOutcome] = []
    for hole in targets:
        answer = filler.fill(hole, found.scaffold.observation)
        if answer is None:
            outcomes.append(
                ModelFillOutcome(
                    field=hole.field,
                    filled=False,
                    declined_because=(
                        "no candidates — free text, and a person answers it"
                        if not hole.candidates
                        else "the model declined or its answer did not validate"
                    ),
                )
            )
            continue
        found = found.model_copy(
            update={
                "scaffold": found.scaffold.fill(
                    hole.field, answer.value, Filler.MODEL, by=answer.by, why=answer.why
                )
            }
        )
        workspace.save(found)
        outcomes.append(
            ModelFillOutcome(
                field=hole.field, filled=True, value=answer.value, why=answer.why
            )
        )

    return ModelFillResult(
        name=req.name,
        outcomes=outcomes,
        remaining=sorted(h.field for h in found.scaffold.holes),
    )
```

Add the imports `ops.py` needs at the top, beside the existing ones:

```python
from mendel_ai.access import ModelAccess
from mendel_ai.client import Client

from mendel_forge.filler import ModelFiller
from mendel_forge.ports import HoleFiller
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest packages/mendel-forge/tests/test_ops_model_fill.py -v
make check
```

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-forge/src/mendel_forge/ops.py \
        packages/mendel-forge/tests/test_ops_model_fill.py
git commit -m "feat(forge): fill_with_model — attempt, persist, report

A separate op from fill rather than a mode on it: FillRequest's value, by
and why are all required and a model fill supplies none of them up front,
so sharing a request model would mean weakening the hand-fill path to suit
the model one.

Persistence is per fill, not per batch. A provider dying after eight of
fifteen holes costs nothing, because the draft is what the forge
accumulates and an all-or-nothing batch makes a flaky network expensive.

A declined hole is reported with a reason rather than omitted — a hole
nobody attempted must not look like a hole that does not exist."
```

---

### Task 10: `forge fill --model` on the CLI

**Spec §3.5.** The verb is extended, not added — a model fill *is* a fill, and the documented
loop stays six steps.

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/cli/parse.py`,
  `packages/mendel-forge/src/mendel_forge/cli/render.py`,
  `packages/mendel-forge/src/mendel_forge/cli/__init__.py`
- Test: `packages/mendel-forge/tests/test_cli_model_fill.py` (create)

**Interfaces:**
- Consumes: `ops.fill_with_model`, `ops.ModelFillRequest`, `ops.ModelFillResult` from Task 9.
- Produces: `forge fill <name> [field] --model` — `value`, `--by` and `--why` become optional
  and are refused *with* `--model`; `field` becomes optional and defaults to every hole.

- [ ] **Step 1: Write the failing test**

Create `packages/mendel-forge/tests/test_cli_model_fill.py`:

```python
"""The `--model` flag, and the argument combinations it forbids.

argparse cannot express "these three are required unless that flag is set", so the check is
explicit and its message names the flag — a usage error that does not say which argument was
wrong is a usage error somebody guesses at.
"""

import pytest

from mendel_forge.cli import parse


def test_a_hand_fill_still_requires_value_by_and_why() -> None:
    args = parse.parse(["fill", "fastqc", "roles", "qc_per_sample", "--by", "me", "--why", "w"])
    assert args.model is None
    assert args.value == "qc_per_sample"


def test_model_takes_no_value_by_or_why() -> None:
    args = parse.parse(["fill", "fastqc", "--model", "test/model"])
    assert args.model == "test/model"
    assert args.value is None
    assert args.field is None


def test_model_with_one_field() -> None:
    args = parse.parse(["fill", "fastqc", "roles", "--model", "test/model"])
    assert args.field == "roles"
    assert args.value is None


def test_a_hand_fill_without_by_is_refused() -> None:
    with pytest.raises(SystemExit):
        parse.parse(["fill", "fastqc", "roles", "qc_per_sample", "--why", "w"])


def test_model_and_by_together_are_refused() -> None:
    """`--by` on a model fill is a person claiming a model's answer."""
    with pytest.raises(SystemExit):
        parse.parse(["fill", "fastqc", "--model", "test/model", "--by", "me"])
```

Add a rendering test to the same file:

```python
from mendel_forge import ops
from mendel_forge.cli import render


def test_it_renders_both_outcomes() -> None:
    text = render.model_fill(
        ops.ModelFillResult(
            name="fastqc",
            outcomes=[
                ops.ModelFillOutcome(
                    field="roles", filled=True, value=["qc_per_sample"], why="it QCs"
                ),
                ops.ModelFillOutcome(
                    field="priority_because",
                    filled=False,
                    declined_because="no candidates — free text, and a person answers it",
                ),
            ],
            remaining=["priority_because"],
        )
    )
    assert "roles" in text and "qc_per_sample" in text
    assert "priority_because" in text
    assert "free text" in text


def test_a_declined_hole_is_visible_rather_than_omitted() -> None:
    text = render.model_fill(
        ops.ModelFillResult(
            name="fastqc",
            outcomes=[
                ops.ModelFillOutcome(
                    field="priority_because", filled=False, declined_because="a reason"
                )
            ],
            remaining=["priority_because"],
        )
    )
    assert "priority_because" in text
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-forge/tests/test_cli_model_fill.py -v
```

Expected: failures on the unknown `--model` argument and on `render.model_fill` not existing.

- [ ] **Step 3: Extend the parser**

In `cli/parse.py`, replace the `fill` block:

```python
    fill = verbs.add_parser("fill", help="answer one hole, by hand or with a model")
    fill.add_argument("name")
    fill.add_argument("field", nargs="?", help="omit with --model to attempt every hole")
    fill.add_argument("value", nargs="?")
    fill.add_argument("--by")
    fill.add_argument("--why")
    fill.add_argument("--list", action="store_true", help="the value is a comma-separated list")
    fill.add_argument("--model", help="a model id; attempts candidate-bearing holes only")
    fill.add_argument("--workspace", type=Path, default=_WORKSPACE)
```

Then, in whatever function `parse.parse` returns from, after parsing, validate the combination.
argparse cannot express *required unless another flag is set*, so it is explicit:

```python
    if args.verb == "fill":
        if args.model:
            offered = [n for n, v in (("value", args.value), ("--by", args.by), ("--why", args.why)) if v]
            if offered:
                parser.error(
                    f"--model settles a hole itself; drop {', '.join(offered)}. "
                    "The model id is recorded as the filler."
                )
        elif not (args.field and args.value and args.by and args.why):
            parser.error("a hand fill needs a field, a value, --by and --why (or use --model)")
```

- [ ] **Step 4: Add the renderer**

In `cli/render.py`, beside `fill`:

```python
def model_fill(result: ops.ModelFillResult) -> str:
    """Both outcomes, always. A hole the model declined is the one a person now has to
    answer, so hiding it would hide the work."""
    lines = [f"{result.name}:"]
    for outcome in result.outcomes:
        if outcome.filled:
            lines.append(f"  filled   {outcome.field} = {outcome.value!r}")
            lines.append(f"           {outcome.why}")
        else:
            lines.append(f"  open     {outcome.field}")
            lines.append(f"           {outcome.declined_because}")
    lines.append(f"  {len(result.remaining)} hole(s) still open")
    return "\n".join(lines)
```

- [ ] **Step 5: Route the verb**

In `cli/__init__.py`, where `fill` is dispatched, branch on `--model`:

```python
    if args.verb == "fill":
        if args.model:
            return render.model_fill(
                ops.fill_with_model(
                    ops.ModelFillRequest(
                        name=args.name,
                        field=args.field,
                        workspace_root=args.workspace,
                        model=args.model,
                        api_key=os.environ.get("MENDEL_API_KEY") or None,
                        base_url=os.environ.get("MENDEL_BASE_URL") or None,
                    )
                )
            )
        return render.fill(ops.fill(...))  # unchanged, existing construction
```

Import `os` at the top if it is not already imported.

- [ ] **Step 6: Run the tests, then run it by hand**

```bash
uv run pytest packages/mendel-forge/tests/test_cli_model_fill.py -v
make check
```

**Then run the documented loop by hand**, with no model configured, and read the output:

```bash
uv run forge draft nf-core:fastqc --name fastqc-tmp --version 0.12.1
uv run forge show fastqc-tmp
uv run forge fill fastqc-tmp --model test/model    # expect a clear MA-coded failure
```

Phase 1's two worst defects were found this way and by no test. **If the failure message does
not tell you what to do next, fix the message before moving on.**

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-forge/src/mendel_forge/cli/ \
        packages/mendel-forge/tests/test_cli_model_fill.py
git commit -m "feat(forge): forge fill --model

The verb is extended rather than added — a model fill is a fill, and the
documented loop stays six steps. field and value become optional; --model
with any of value, --by or --why is a usage error naming what to drop,
because --by on a model fill is a person claiming a model's answer.

argparse cannot express 'required unless that flag is set', so the check is
explicit. A usage error that does not name the wrong argument is one
somebody guesses at.

A declined hole is rendered, not hidden: it is precisely the hole a person
now has to answer."
```

---

### Task 11: the HTTP route

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/http/__init__.py`
- Test: `packages/mendel-forge/tests/test_http_model_fill.py` (create)

**Interfaces:**
- Consumes: `ops.fill_with_model`, `ops.ModelFillRequest`, `ops.ModelFillResult`.
- Produces: `POST /drafts/fill-with-model`.

**Note.** The module's docstring already says the two transports share request and result models
so they cannot drift in what they accept. That property is the reason this task is four lines —
if it needs more, something was put in a transport that belongs in `ops.py`.

- [ ] **Step 1: Write the failing test**

Create `packages/mendel-forge/tests/test_http_model_fill.py`:

```python
"""The HTTP transport over the same models the CLI uses.

If this test needs to construct anything the CLI does not, logic has leaked into a transport.
"""

from fastapi.testclient import TestClient

from mendel_forge.http import app


def test_the_route_exists_and_takes_the_shared_request_model() -> None:
    routes = {r.path for r in app.routes}
    assert "/drafts/fill-with-model" in routes


def test_a_bad_request_is_a_422_not_a_traceback() -> None:
    client = TestClient(app)
    assert client.post("/drafts/fill-with-model", json={"name": "x"}).status_code == 422
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-forge/tests/test_http_model_fill.py -v
```

Expected: the route is absent from the set.

- [ ] **Step 3: Add the route**

In `http/__init__.py`, beside `fill_draft`:

```python
@app.post("/drafts/fill-with-model")
def fill_draft_with_model(req: ops.ModelFillRequest) -> ops.ModelFillResult:
    return ops.fill_with_model(req)
```

- [ ] **Step 4: Run and commit**

```bash
uv run pytest packages/mendel-forge/tests/test_http_model_fill.py -v
make check
git add packages/mendel-forge/src/mendel_forge/http/ \
        packages/mendel-forge/tests/test_http_model_fill.py
git commit -m "feat(forge): the model-fill route

Four lines, over the same request and result models the CLI uses. That the
route is this small is the property the http module's docstring claims —
if it had needed more, something belonging in ops.py had leaked into a
transport."
```

---

### Task 12: `forge show` marks what a model filled

**Spec §3.2.** The honesty cost of landing a model fill as an answer is paid by display. A
reviewer must be able to see, without opening the file, which values a model settled.

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/cli/render.py`
- Test: `packages/mendel-forge/tests/test_cli_model_fill.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `packages/mendel-forge/tests/test_cli_model_fill.py`:

```python
from mendel_forge.scaffold import FilledValue, Filler


def test_show_marks_a_model_fill_distinctly() -> None:
    """Landing a model fill as an answer is only honest if a reviewer can see which it was."""
    text = render.show(
        ops.ShowResult(
            name="fastqc",
            target="fastqc",
            holes=[],
            filled={
                "roles": FilledValue(
                    value=["qc_per_sample"], filler=Filler.MODEL, by="test/model", why="w"
                ),
                "nf_process": FilledValue(
                    value="FASTQC", filler=Filler.DERIVED, by="nf-core", why="read from main.nf"
                ),
            },
            module=None,
        )
    )
    assert "test/model" in text
    assert "model" in text.lower()


def test_show_does_not_mark_a_derived_fill_as_a_model_one() -> None:
    text = render.show(
        ops.ShowResult(
            name="fastqc",
            target="fastqc",
            holes=[],
            filled={
                "nf_process": FilledValue(
                    value="FASTQC", filler=Filler.DERIVED, by="nf-core", why="read from main.nf"
                )
            },
            module=None,
        )
    )
    assert "test/model" not in text
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-forge/tests/test_cli_model_fill.py -v -k show
```

Expected: the model marker is absent from the rendered text.

- [ ] **Step 3: Mark it in `render.show`**

Find where `show` renders `filled` and include the filler and `by`. The existing line already
prints the field and value; add the provenance so the three fillers are distinguishable at a
glance — for example:

```python
        marker = {
            Filler.MODEL: f"[model: {value.by}]",
            Filler.HAND: f"[hand: {value.by}]",
            Filler.DERIVED: f"[derived: {value.by}]",
        }[value.filler]
```

and append `marker` to the line that field is rendered on. **Match the surrounding formatting
rather than the shape above** — `render.py` has an established column style, and this must read
like the rest of it.

- [ ] **Step 4: Run, eyeball, commit**

```bash
uv run pytest packages/mendel-forge/tests/ -v
uv run forge show fastqc-tmp     # read it — is the marker legible?
make check
git add packages/mendel-forge/src/mendel_forge/cli/render.py \
        packages/mendel-forge/tests/test_cli_model_fill.py
git commit -m "feat(forge): show marks who settled each value

Phase 2 lands a model fill as an answer rather than a proposal, and the
honesty cost of that is paid here: a reviewer must be able to see which
values a model settled without opening the file.

All three fillers are marked, not just the model one. Marking only the
model fill would make the absence of a marker mean two different things."
```

---

### Task 13: the documentation corrections

**Spec §1.1.** Three prose statements are wrong and one is about to become wrong. This is the
task that closes the fifth-door question in the files a reader actually meets.

**Files:**
- Modify: `CLAUDE.md` (invariant 14, and the `--no-ai` sentence)
- Modify: `ARCHITECTURE.md` (the egress section, and a `mendel-ai` entry)
- Modify: `docs/design/clinical-data-protection.md` §4.1
- Modify: `notes/specs/2026-08-16-the-forge.md` §10.3
- Modify: `docs/guides/driving-the-forge.md`

- [ ] **Step 1: `CLAUDE.md` invariant 14**

Its opening sentence is *"Data leaves through four declared doors and no others"*. Add the scope
the design document has always had, without weakening the enumeration:

> 14. **Pipeline data leaves through four declared doors and no others** — goal extraction,
>     tier-4 resolution, compiler repair, publication. **The doors track the prompt taint
>     path**, which is what `docs/design/clinical-data-protection.md` §4.2 states and what the
>     one-line summary here lost: free text enters at exactly one door, and the question for
>     anything else is whether it is downstream of it. The four are one path — prompt, goal,
>     build, pipeline, publish.
>
>     **The forge is not on that path** and is not a fifth door (decided 2026-08-17,
>     `notes/specs/2026-08-17-forge-phase-2.md` §1). It has no prompt, takes no `Goal` and
>     writes no `pipeline.yml`; it reads vendored modules and registry files and produces
>     registry data a build later consumes — the offline authoring half of invariant 2.
>     `AiPoint` corroborates this without being changed: invariant 3 declares three runtime AI
>     points and the forge is not one of them.

Keep the rest of invariant 14 — the ten free-text fields, the allowlist, `DOORS`, publication
being the door with no undo — exactly as it is. **`DOORS` and `tests/test_egress.py` do not
change in this task or any other.**

- [ ] **Step 2: `CLAUDE.md`'s `--no-ai` sentence**

It currently says *"The `--no-ai` flag itself arrives with Plan 2 — through Plan 1 there is no AI
path to switch off, so every build is already that lane."* Replace with:

> **`--no-ai` is still not a flag, and Phase 2 did not add one.** The forge's model path is
> opt-in through `forge fill --model`, so its default *is* the no-AI lane — the same argument
> that made `NoFiller` not-a-flag. `mendel build` has no AI path at all until the tier-4
> ambiguity resolver arrives with Plan 3. When it does, `--no-ai` becomes meaningful and must
> keep working forever: it is how the deterministic guarantee stays testable, and it is the
> mode CI runs.

Also correct the gotcha bullet that says the same thing.

- [ ] **Step 3: `clinical-data-protection.md` §4.1**

Its first line is *"Data leaves through exactly four paths."* Add, immediately after the table:

> **These four are one path, and that is what makes the list complete.** Prompt → goal → build →
> pipeline → publish. §4.2's taint rule is the reason: free text enters at exactly one door, and
> everything else is judged by whether it is downstream of it.
>
> **Offline authoring is outside this boundary.** `mendel-forge` reads vendored modules and
> registry files and produces registry data; it has no prompt and no `Goal`, and a laboratory can
> deploy Mendel and never run it. A model call it makes is not a fifth door — decided 2026-08-17,
> and argued in `notes/specs/2026-08-17-forge-phase-2.md` §1. Invariant 3's `AiPoint` list is the
> corroboration: three runtime AI points, and the forge is not one.

- [ ] **Step 4: `ARCHITECTURE.md`**

Two edits. In the egress section, the same scope qualifier as Step 3, in one sentence. In §10
(the forge), a subsection for Phase 2:

> **Phase 2 — a model behind the seam.** `mendel_forge.filler.ModelFiller` implements
> `HoleFiller` over `mendel-ai`. It attempts **candidate-bearing holes only**: those are the
> holes whose legal answers come off the layer stack, so an answer is checkable, and `Hole.legal`
> refuses one that is not. A hole with no candidates is free text and is declined without being
> sent — issue #70 is what gates the other direction. A model fill lands as an *answer* carrying
> `Filler.MODEL` and the model id, which `assemble._drafted_by` writes into
> `Provenance.drafted_by`; `forge show` marks it so a reviewer can see it without opening the
> file.

And a `mendel-ai` row in the package listing, marked impure.

- [ ] **Step 5: `notes/specs/2026-08-16-the-forge.md` §10.3**

That section poses the fifth-door question. Add its resolution at the top rather than rewriting
it — the question and its answer are both worth keeping:

> **Resolved 2026-08-17: there is no door 5.** See
> [`2026-08-17-forge-phase-2.md`](2026-08-17-forge-phase-2.md) §1. The argument below is
> preserved because it is the argument that got the question asked, and because the resolution
> turns on a distinction it did not draw — that the doors track the prompt taint path rather
> than all data.

- [ ] **Step 6: `docs/guides/driving-the-forge.md`**

Add `--model` to the loop, with real output from the hand-run in Task 10 Step 6. Cover: what it
attempts and what it will not, that a declined hole is a hole a person answers, what
`MENDEL_MODEL` and friends do, and that the default with no `--model` is unchanged.

**Use output you actually saw.** Phase 1's guide is written from real runs, and writing this one
from real runs is what found two of that phase's five corrections.

- [ ] **Step 7: `CLAUDE.md`'s protection-profile table**

The table's own line says *"Never configurable at any level: the four doors, typed payloads, an
`EgressRecord` per crossing, tier 4 always flagged…"*. Add, immediately below it:

> **None of this is implemented yet, and saying so is the point** — see
> [#71](https://github.com/comeni-project/Comeni-Labs/issues/71). Every row above describes a
> subsystem that does not exist: the prompt door, compiler repair and tier-4 resolution are all
> Plan 3 or later. The profiles govern the **build path**; offline authoring in `mendel-forge` is
> outside them, for the same reason it is not a fifth egress door.

- [ ] **Step 8: Check links and commit**

```bash
make links
make check
git add CLAUDE.md ARCHITECTURE.md docs/ notes/specs/2026-08-16-the-forge.md
git commit -m "docs: invariant 14's scope, and --no-ai

Invariant 14's one-line summary said data leaves through four doors and no
others; clinical-data-protection.md §4.2 has always said what that tracks —
free text enters at one door, and everything else is judged by whether it is
downstream of it. The summary lost the qualifier, and this restores it.

The four doors are one path: prompt, goal, build, pipeline, publish. The
forge is not on it, so a forge model call is not a fifth door. DOORS and
tests/test_egress.py are unchanged, here and everywhere — this is a scope
correction to prose, not a carve-out in the guard.

--no-ai still is not a flag. The forge's model path is opt-in, so its
default is the no-AI lane, and mendel build has no AI path until Plan 3."
```

---

### Task 14: the journal entry

**`CLAUDE.md`:** the journal is the handoff, and it is what a fresh reader is told to start with.

**Files:**
- Create: `notes/journal/2026-08-18-forge-phase-2.md` (or the date it is finished)
- Modify: `notes/README.md` row 15 — status from *next* to *done*, with the date

- [ ] **Step 1: Write it**

Cover, in this order:

1. **Where things stand.** `mendel-ai` exists and the forge can call a model. `make verify`
   green. **No counts in prose** — `make check` counts the tests, `make residue` counts guard
   coverage. Two numbers in `CLAUDE.md` were stale for three plans because nothing counted them.
2. **What a fresh reader gets wrong.** Candidate-bearing only, and why that is not timidity —
   it is the half that can be checked. `--no-ai` is still not a flag. The forge is not an egress
   door and §1 is the argument.
3. **Every correction to this plan**, with what caused it, and **which were found by running the
   loop rather than by reading it**. Phase 1 had five and two came from the hand-run; expect
   similar, and say so plainly if fewer.
4. **The guard.** `tests/test_no_live_model.py`, watched failing, with the message it printed
   and a row in `notes/audits/guard-ledger.md`.
5. **What is next** — the rule drafter (row 16), then Plan 3 with the ambiguity resolver, #69
   and the review screens. Write the handoff for someone who was not here.
6. **What Phase 2 deliberately did not do**, with the issue number beside each: #70 (prose
   holes), #69 (`AiProvenance`), conformance line numbers.

- [ ] **Step 2: Update the plan index**

`notes/README.md` row 15: status to **DONE**, with the date and a one-line summary of what
actually shipped versus what this plan predicted.

- [ ] **Step 3: Final verification, then commit**

```bash
make verify
make links
```

```bash
git add notes/
git commit -m "docs: forge Phase 2 in the journal, and the index"
```

- [ ] **Step 4: Open the pull request**

```bash
git push -u origin forge-phase-2
gh pr create --title "The forge, Phase 2: a model fills the holes" --body "..."
```

The body should say what shipped, what was corrected, what was deliberately left, and link the
spec. Follow the shape of #68.

---

## Self-Review

Run against the spec after the plan is written, before execution starts.

**Spec coverage — every section has a task:**

| Spec | Task |
|---|---|
| §1 no door 5, §1.1 the doc corrections | 13 |
| §2 what Phase 2 builds; §2.1 out of scope | 3–9 build it; #69/#70 filed already |
| §3.1 candidate-bearing only | 8 |
| §3.2 answer, marked model-filled | 8 (the fill), 12 (the marking) |
| §3.3 `ModuleSpec` line numbers first | 1, 2 |
| §3.4 `mendel-ai` holds the client | 3–7 |
| §3.5 `forge fill --model` | 10 |
| §3.6 `sealed` does not reach the forge | 13 (the argument), and the finding is issue #71 |
| §4.1 dependencies and the arrow | 3 |
| §4.2 the surface | 5, 6 |
| §4.3, §4.3.1 the guard and its limits | 5 (`MA0006` and `_why_refused`), 6 (`WHY_LIMIT`) |
| §4.4 the three lanes | 4 |
| §5 the forge side, §5.1 data flow | 8, 9 |
| §6 error handling | 5, 6 |
| §7 testing | 7 |
| §8 the two weaknesses | 14 (recorded in the journal) |

**Two gaps were found by this review, and both are now closed** — recorded here because a
review that finds nothing is a review nobody ran.

1. **§3.6 asserted a behaviour justified by the analogy §1 rejects.** It said `sealed` makes no
   forge model call, "the profile table's logic applied straight". But a search for
   `ProtectionProfile`, `SEALED` or `GUARDED` across every package returns **nothing** — the
   three profiles are documented and implemented in zero lines — and every row in their table
   describes the build path: a prompt door, a gate failure, a repair, a tier-4 decision. None is
   about offline authoring. So a profile has nothing to say about the forge, for exactly the
   reason it is not a fifth door. §3.6 is rewritten to argue that, Task 13 carries it into the
   documentation, and the finding that the profiles are wholly unimplemented is
   [#71](https://github.com/comeni-project/Comeni-Labs/issues/71) — larger than this phase, and
   to be designed once when doors 1–3 exist to be governed.

2. **§4.3.1 described a rationale cap with no task behind it.** Now `WHY_LIMIT` in Task 6, as
   `Field(max_length=...)` on both `Choice.why` and `Choices.why` — the cap lives in the declared
   shape, so the JSON Schema handed to the model states the limit and the model is told the
   constraint rather than punished for not guessing it. **It gets `MA0006` rather than folding
   into `MA0004`**: "the answer did not match the shape" is true of an overlong rationale and
   useless for it, and a refusal that cannot say why it refused is one somebody guesses at.
   `_why_refused` reads Pydantic's own `string_too_long` error type, so **any** capped field in
   **any** shape reports itself correctly — not just the one it was written for.

**Placeholder scan:** clean. Every code step carries the code; every test step carries the test.
The one `render.show` step (Task 12 Step 3) gives a shape and says explicitly to match the
surrounding style instead — that is a deliberate instruction, not a TODO, because `render.py`'s
column formatting is not reproducible from memory and guessing it would produce a worse diff
than reading it.

**Type consistency:** `Transport.send(access, prompt) -> str` is used identically in Tasks 5, 7
and the fakes in 6 and 8. `ModelFillOutcome.declined_because` is written in Task 9 and read in
Tasks 10 and 12. `key_for(access, prompt)` is defined in Task 7 and used in its own fixture
generator. `ModelFiller(client, model_id=...)` is constructed the same way in Tasks 8 and 9.
`_prompt(instruction, shape, evidence)` and `_question(question, options)` compose in exactly
one order, in Task 7's generator and inside `choose_one`.
