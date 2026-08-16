# The Forge, Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` to implement
> this plan task by task. **Do not use `subagent-driven-development`** — `CLAUDE.md` forbids
> farming implementation out to subagents; they are for review and design only. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `mendel-forge` — a deterministic scaffold generator and verifier that turns a
tool source into registry files and the Nextflow module behind them, with everything it cannot
prove recorded as a typed hole, served identically over a CLI and an HTTP API.

**Architecture:** A pluggable `Source` ingests a tool into an `Observation` — facts that each
carry the file and line they were read from. A `Scaffold` pairs that observation with a list of
`Hole`s naming every field that could not be derived, together with the declared values that
would be legal there. A `ModuleContract` is constructed **only when the last hole is filled**, so
an invalid declared file is unrepresentable rather than merely rejected. A five-rung verification
ladder — complete, constructs, loads, conforms, routes — reuses the compiler's existing
conformance and loader machinery. One operations layer of typed functions is rendered by a CLI
and served by an ASGI app; neither transport holds logic.

**Tech Stack:** Python 3.12, pydantic v2, argparse, FastAPI + Starlette, pytest, uv workspace,
hatchling. No model is called anywhere in this plan.

**Spec:** [`notes/specs/2026-08-16-the-forge.md`](../specs/2026-08-16-the-forge.md) — read it
first. Every task argues from a section of it, cited in the task header.

---

## Global Constraints

Every task's requirements implicitly include all of these.

- **Python floor is 3.12**, matching every other package. Test on 3.12 and 3.13.
- **Line length 100.** `uv run ruff check .` is a gate; `ruff format` is not and must not be run
  across existing files.
- **`mendel-forge` is impure** — it may reach the network in later phases. It must be added to
  `IMPURE_PACKAGES` in `tests/test_purity.py`, and **nothing in `comeni-core`,
  `mendel-resolver` or `mendel-compiler` may import it.** The dependency arrow is
  `mendel-forge → the pure packages`, never the reverse.
- **No model is called in Phase 1.** `--no-ai` is not a flag; it is the only mode. A task that
  adds an LLM dependency is a task that has gone wrong.
- **Every diagnostic code is `MF`, `emitted_by: forge`,** declared in
  `packages/comeni-core/src/comeni_core/diagnostics.yml` **and emitted through `coded()` in the
  same commit.** `tests/test_diagnostics_ownership.py` holds both directions.
- **Never write a code into a string by hand.** `coded(code, message)` is the only way a code
  becomes text; `Diagnostic(code=...)` is the only way it becomes an object.
- **Determinism is a test.** Same source in → byte-identical `Scaffold` out, hole order included.
  `frozenset` has no stable order; anything serialising a set needs a `field_serializer` that
  sorts, as `IREdge.states` and `OutputPort.state` already do.
- **Reused diagnostics keep their existing prefix and owner.** A draft failing the load rung
  emits `MD0004` because that is what it is. Do not mint an `MF` twin for a condition that
  already has a code.
- **Import modules, not symbols, where tests monkeypatch.** `from x import f` binds past a later
  patch of `x.f`.
- **`make check` is the gate for this plan.** No task here touches `resolve.py`, `router.py`,
  `rules/`, `mendel_compiler/cli/`, `emit.py` or `artifact/pipeline.py`, so `make verify` is not
  required per task — but run it once at Checkpoint G before the branch is finished.
- **Commit after every task.** Frequent commits; the message says what changed and why.

---

## File Structure

Everything new lives under `packages/mendel-forge/`, following the existing package layout
(`src/<module>/`, `tests/`, `pyproject.toml`, `README.md`, `LICENSE`).

| File | Responsibility |
|---|---|
| `src/mendel_forge/__init__.py` | the public surface, re-exported so consumers import one name |
| `src/mendel_forge/observe.py` | `Excerpt`, `Fact`, `Observation` — what a source proved, and where from |
| `src/mendel_forge/scaffold.py` | `Filler`, `FilledValue`, `Candidate`, `Hole`, `Scaffold` |
| `src/mendel_forge/sources/__init__.py` | the `Source` protocol, `ToolRef`, the source registry |
| `src/mendel_forge/sources/nfcore.py` | the nf-core adapter, over `ModuleSpec` and `meta.yml` |
| `src/mendel_forge/candidates.py` | legal values for a hole, read off a loaded layer stack |
| `src/mendel_forge/assemble.py` | `Scaffold` → `ModuleContract`, refusing while holes remain |
| `src/mendel_forge/modulegen.py` | a skeleton `main.nf` for a source that ships none |
| `src/mendel_forge/verify.py` | the five-rung ladder |
| `src/mendel_forge/workspace.py` | drafts on disk: save, load, list |
| `src/mendel_forge/land.py` | the invariant-2 boundary — branch and commit into a registry |
| `src/mendel_forge/ops.py` | one typed function per verb; the only layer with logic |
| `src/mendel_forge/ports.py` | `HoleFiller` — the Phase 2 seam, with `NoFiller` (Task 15) |
| `src/mendel_forge/cli/__init__.py` | dispatch and refusal handling |
| `src/mendel_forge/cli/parse.py` | argparse only |
| `src/mendel_forge/cli/render.py` | result models → console text |
| `src/mendel_forge/http/__init__.py` | a mountable ASGI app; request in, result out |
| `tests/fixtures/opaque/` | the pegi3s-shaped fixture source's fake tool tree |

Modified: `pyproject.toml` (workspace member), `tests/test_purity.py` (impure classification),
`tests/test_diagnostics_ownership.py` (the `MD`-only regex), `comeni_core/diagnostics.yml`
(the `MF` band and its codes), `Makefile`, `ARCHITECTURE.md`, `CLAUDE.md`, `notes/README.md`.

---

## Checkpoints

Stop at each one, run the stated command, and report before continuing.

| # | After task | Gate |
|---|---|---|
| **A** | 2 | `make check` green with an empty package present and classified |
| **B** | 7 | two sources ingest, `uv run pytest packages/mendel-forge -v` green |
| **C** | 11 | a holeless scaffold assembles into a real `ModuleContract` |
| **D** | 13 | the ladder refuses and explains; `MF` codes visible to the ownership guard |
| **E** | 17 | a draft round-trips through the workspace and lands on a branch |
| **F** | 19 | CLI `--json` and HTTP return byte-identical payloads |
| **G** | 23 | `make verify` green; the guard has a ledger row |

---

# Checkpoint A — the survey, and a package that exists

### Task 1: Survey what a contract actually needs against what a module actually gives

**Spec:** §3.4, §9.1. **This task writes no forge code.** It replaces every estimate in this plan
with a measurement, and it is first because every later task's hole list depends on its answer.

**Files:**
- Create: `notes/audits/2026-08-16-forge-derivability.md`
- Create: `packages/mendel-compiler/tests/test_derivability_survey.py`

**Interfaces:**
- Consumes: `ModuleSpec.parse(main_nf: Path) -> ModuleSpec` from
  `mendel_compiler.modulespec`; `ModuleContract` from `comeni_core.declared.contract`;
  `layers.load` from `mendel_resolver.layers`.
- Produces: the derivability table that Task 6 implements literally. No code imported later.

- [ ] **Step 1: Write the survey script as a test that prints its findings**

Create `packages/mendel-compiler/tests/test_derivability_survey.py`:

```python
"""What can a contract's fields be read off its module, and what cannot?

Not a guard. This is the measurement behind the forge's hole list, kept as a test so it
re-runs and cannot quietly become false. If it fails, the derivability table in
notes/audits/2026-08-16-forge-derivability.md is stale and the forge's holes are wrong.
"""

from pathlib import Path

from comeni_core.declared.contract import ModuleContract
from mendel_compiler.modulespec import ModuleSpec
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "vendor"


def _pairs() -> list[tuple[ModuleContract, ModuleSpec]]:
    stack = layers.load(ROOT / "registry")
    found = []
    for contract in stack.registry.all():
        main_nf = VENDOR / f"{contract.nf_include}.nf"
        if main_nf.exists():
            found.append((contract, ModuleSpec.parse(main_nf)))
    return found


def test_the_survey_found_modules_to_survey():
    pairs = _pairs()
    assert len(pairs) >= 5, f"only {len(pairs)} contract/module pairs; the survey is not surveying"


def test_process_name_is_derivable():
    for contract, spec in _pairs():
        assert contract.nf_process == spec.process, contract.id


def test_container_is_derivable():
    missing = [c.id for c, s in _pairs() if c.container and s.container != c.container]
    assert missing == [], f"container disagrees with the module for: {missing}"


def test_output_port_names_come_from_emits():
    wrong = []
    for contract, spec in _pairs():
        for port in contract.produces:
            if port.name not in spec.emits:
                wrong.append(f"{contract.id}:{port.name} not in {spec.emits}")
    assert wrong == [], f"output port names are not module emits: {wrong}"


def test_input_channel_count_is_derivable():
    wrong = []
    for contract, spec in _pairs():
        if len(contract.input_signature()) != len(spec.inputs):
            wrong.append(f"{contract.id}: {len(contract.input_signature())} vs {len(spec.inputs)}")
    assert wrong == [], f"nf_inputs arity disagrees with the module: {wrong}"


def test_semantic_fields_are_not_in_the_module_at_all():
    """The negative half, and the one that justifies holes existing.

    A module declares no type_id, no state, no role. If this ever fails, the forge can
    derive more than it does and the hole list should shrink.
    """
    for contract, spec in _pairs():
        text = (VENDOR / f"{contract.nf_include}.nf").read_text()
        for port in contract.produces:
            assert port.type_id not in text, (
                f"{contract.id}: {port.type_id} appears in main.nf — it may be derivable"
            )
```

- [ ] **Step 2: Run it and read every failure as data, not as a bug**

Run: `uv run pytest packages/mendel-compiler/tests/test_derivability_survey.py -v`

Expected: some of these **will fail**, and that is the finding. A failure means the field is
*less* derivable than assumed. Do not weaken an assertion to make it pass — record the
disagreement, and if a shipped contract is genuinely wrong, that is a finding to report at the
checkpoint rather than fix here.

- [ ] **Step 3: Write the derivability table from what the run said**

Create `notes/audits/2026-08-16-forge-derivability.md`. Fill the **Verdict** column from Step 2's
actual output — `derived`, `hole`, or `partial` with a note. The rows are every field of
`ModuleContract`:

```markdown
# What the forge can derive, measured

**Method:** `packages/mendel-compiler/tests/test_derivability_survey.py`, run against every
contract in `registry/` whose module is vendored. Re-run it; do not trust this page alone.

| Contract field | Module source of truth | Verdict |
|---|---|---|
| `id` | directory path + version | |
| `nf_process` | `ModuleSpec.process` | |
| `nf_include` | path under `vendor/modules/` | |
| `consumes[].name` | `InputSlot.names` / `DocumentedInput.name` | |
| `consumes[].type_id` | nothing | |
| `consumes[].state_required` | nothing | |
| `consumes[].state_required_conventional` | nothing | |
| `produces[].name` | `ModuleSpec.emits` | |
| `produces[].type_id` | nothing | |
| `produces[].state` | nothing | |
| `params[].name` | nothing (a flag is a string in the script body) | |
| `params[].via` / `key` / `template` | `reads_ext_args`, `reads_ext_prefix`, `meta_reads` | |
| `params[].default` / `because` / `domain` | nothing | |
| `roles` | nothing | |
| `priority` / `priority_because` | nothing | |
| `container` | `ModuleSpec.container` | |
| `nf_inputs[].ports` | nothing (semantic grouping) | |
| `nf_inputs` arity | `len(ModuleSpec.inputs)` | |
| `nf_inputs[].empty` / `because` / `join` | nothing | |
| `ext_args` | nothing | |
| `provenance.source` / `drafted_by` | the ingestion itself | |
| `provenance.approved_by` / `approved_at` | the human, at land time | |

## What this changes about the plan

[Write what Step 2 actually showed. If a field assumed derivable is not, say so here — Task 6
implements this table literally.]
```

- [ ] **Step 4: Commit**

```bash
git add notes/audits/2026-08-16-forge-derivability.md \
  packages/mendel-compiler/tests/test_derivability_survey.py
git commit -m "survey: what a contract needs against what a module gives

The forge's hole list is only as good as this table, and every previous version of it
was an estimate. Kept as a test so it re-runs and cannot quietly go stale."
```

---

### Task 2: The package, classified impure, with nothing in it

**Spec:** §2, Global Constraints. A package that exists and is correctly classified, before any
logic lands in it — so the purity guard is watched failing on an empty target.

**Files:**
- Create: `packages/mendel-forge/pyproject.toml`, `README.md`, `LICENSE`,
  `src/mendel_forge/__init__.py`, `src/mendel_forge/py.typed`, `tests/__init__.py`
- Modify: `pyproject.toml` (root), `tests/test_purity.py:121`

**Interfaces:**
- Produces: the importable name `mendel_forge`, version `0.1.0`.

- [ ] **Step 1: Create the package skeleton**

`packages/mendel-forge/pyproject.toml` — copy `mendel-compiler`'s manifest and change these
fields only:

```toml
[project]
name = "mendel-forge"
version = "0.1.0"
description = "Scaffolding and verification for the Mendel registry"
dependencies = [
  "comeni-core>=0.1.0",
  "mendel-resolver>=0.1.0",
  "mendel-compiler>=0.1.0",
  "pydantic>=2.9",
  "pyyaml>=6.0",
]

[project.scripts]
forge = "mendel_forge.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/mendel_forge"]
```

Keep `requires-python`, `license`, `authors`, `keywords`, `classifiers`, `[project.urls]` and
`[build-system]` identical to `mendel-compiler`'s. Copy `LICENSE` from
`packages/mendel-compiler/LICENSE`. Write a short `README.md` naming the spec.

`src/mendel_forge/__init__.py`:

```python
"""The forge: scaffolding and verification for the registry.

`notes/specs/2026-08-16-the-forge.md` is the design. The one property everything here
serves: a scaffold is not a half-built contract, so the forge cannot emit an invalid
declared file — only a valid one, or something that says which fields it is missing.
"""

__all__: list[str] = []
```

Create empty `src/mendel_forge/py.typed` and `tests/__init__.py`.

- [ ] **Step 2: Watch the purity guard fail on the unclassified package**

Run: `uv run pytest tests/test_purity.py -v`

Expected: FAIL — a test asserts every directory under `packages/` is in `CLOSED_PACKAGES`,
`BANLIST_PACKAGES` or `IMPURE_PACKAGES`, and `mendel-forge` is in none of them. **Read the
message.** This is the guard doing its job, and it is the reason the package is created before
anything is written into it.

- [ ] **Step 3: Classify it impure, with the reason**

In `tests/test_purity.py`, change line 121:

```python
IMPURE_PACKAGES: list[str] = ["mendel-forge"]
"""Packages that may reach the network, and are therefore not scanned.

`mendel-forge` ingests tool sources and, from Phase 2, calls a model. Invariant 1 names
three packages and this is not one of them — the arrow points mendel-forge → the pure
packages, and `test_no_pure_package_imports_an_impure_one` is what holds that direction.
"""
```

- [ ] **Step 4: Add the workspace wiring**

In the root `pyproject.toml`, add to `dependencies` and `[tool.uv.sources]`:

```toml
dependencies = ["comeni-core", "mendel-resolver", "mendel-compiler", "mendel-forge"]

[tool.uv.sources]
mendel-forge = { workspace = true }
```

`[tool.uv.workspace] members = ["packages/*"]` already matches it. **The root must list it in
`dependencies` or `uv sync` installs nothing and every import fails** — that gotcha is in
`CLAUDE.md`.

- [ ] **Step 5: Add the reverse-direction guard**

Append to `tests/test_purity.py`:

```python
def test_no_pure_package_imports_an_impure_one():
    """The dependency arrow, asserted rather than assumed.

    `mendel-forge` importing `mendel-resolver` is the design. The reverse would put an
    impure package inside the purity boundary by transitivity, and the AST scan would
    not see it — it scans the pure packages' own imports, and `mendel_forge` is not on
    any banlist because it is not supposed to be reachable at all.
    """
    offenders = []
    for pkg in [*CLOSED_PACKAGES, *BANLIST_PACKAGES]:
        for path in sorted((ROOT / "packages" / pkg).rglob("src/**/*.py")):
            if "mendel_forge" in path.read_text():
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], (
        "a pure package references mendel_forge; the dependency arrow points the other "
        f"way: {offenders}"
    )
```

- [ ] **Step 6: Sync and verify**

```bash
uv sync
uv run python -c "import mendel_forge; print(mendel_forge.__doc__.splitlines()[0])"
make check
```

Expected: the import prints, `make check` is green.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-forge pyproject.toml uv.lock tests/test_purity.py
git commit -m "feat: mendel-forge, empty and classified impure

The package is created before anything is written into it so the purity guard is
watched failing on an unclassified target — IMPURE_PACKAGES was an empty list, and
the totality test is what caught it. Adds the reverse guard too: the arrow points
mendel-forge -> the pure packages, and nothing asserted that until now."
```

> ## ✅ Checkpoint A
>
> Run `make check`. Report: the derivability table's verdicts, anything in Step 2 of Task 1 that
> failed and what it means, and whether any shipped contract turned out to be wrong.
---

# Checkpoint B — the spine, and two sources

### Task 3: `Observation` — what was proven, and where from

**Spec:** §3.2. Facts with evidence, and no opinions.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/observe.py`
- Test: `packages/mendel-forge/tests/test_observe.py`

**Interfaces:**
- Produces: `Excerpt(locator: str, text: str)`, `Fact(value: Any, evidence: Excerpt)`,
  `Observation(source: str, ref_id: str, facts: dict[str, Fact], prose: list[Excerpt])`,
  and `Observation.fact(name: str) -> Any | None`.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pydantic import ValidationError

from mendel_forge.observe import Excerpt, Fact, Observation


def test_a_fact_carries_where_it_came_from():
    fact = Fact(value="FASTQC", evidence=Excerpt(locator="main.nf:12", text="process FASTQC {"))
    assert fact.value == "FASTQC"
    assert fact.evidence.locator == "main.nf:12"


def test_an_observation_looks_a_fact_up_and_returns_none_for_an_absent_one():
    obs = Observation(
        source="nf-core",
        ref_id="nf-core/fastqc",
        facts={"process": Fact(value="FASTQC", evidence=Excerpt(locator="main.nf:12", text="x"))},
    )
    assert obs.fact("process") == "FASTQC"
    assert obs.fact("container") is None


def test_evidence_is_mandatory_on_every_fact():
    """A fact with no locator is an assertion, which is what the forge exists not to make."""
    with pytest.raises(ValidationError):
        Fact(value="FASTQC")


def test_an_observation_serialises_with_its_facts_in_sorted_order():
    obs = Observation(
        source="s",
        ref_id="r",
        facts={
            "zebra": Fact(value=1, evidence=Excerpt(locator="a:1", text="t")),
            "alpha": Fact(value=2, evidence=Excerpt(locator="a:2", text="t")),
        },
    )
    assert list(obs.model_dump()["facts"]) == ["alpha", "zebra"]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_observe.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'mendel_forge.observe'`

- [ ] **Step 3: Implement**

```python
"""What a source proved about a tool, and where each fact was read from.

Source-neutral by construction: an `Observation` names facts by string, so an adapter
for a source nobody has written yet does not need this file changed. It holds no
opinions about contracts — turning facts into a contract's fields is `scaffold.py`'s
job, and keeping the two apart is what lets a second source exist at all.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

_NO_EXTRAS = ConfigDict(extra="forbid")


class Excerpt(BaseModel):
    """A span of source text and a resolvable pointer to it.

    `locator` is a `file:line` or a URL — never a bare claim. The rule drafter's §3.2
    makes the same demand of a citation for the same reason: a reviewer approving
    something is approving that the quoted text supports it, and they cannot do that
    without the text.
    """

    model_config = _NO_EXTRAS

    locator: str
    text: str


class Fact(BaseModel):
    """One thing the source says, with the evidence for it.

    `value` is `Any` because a fact is a process name, an arity, a list of emits or a
    container URI. This is not an egress payload — invariant 14's ban on `Any` covers
    what crosses a door, and an `Observation` never does.
    """

    model_config = _NO_EXTRAS

    value: Any
    evidence: Excerpt


class Observation(BaseModel):
    model_config = _NO_EXTRAS

    source: str
    ref_id: str
    facts: dict[str, Fact] = Field(default_factory=dict)
    prose: list[Excerpt] = Field(default_factory=list)
    """Documentation. Unused in Phase 1 beyond display; it is what Phase 2's filler reads."""

    @field_serializer("facts")
    def _sorted(self, facts: dict[str, Fact]) -> dict[str, Fact]:
        """Byte-identical output is a hard requirement, and a dict serialises in insertion
        order — which is parse order, which is not stable across a refactor."""
        return {name: facts[name] for name in sorted(facts)}

    def fact(self, name: str) -> Any | None:
        found = self.facts.get(name)
        return None if found is None else found.value
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/mendel-forge/tests/test_observe.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-forge/src/mendel_forge/observe.py \
  packages/mendel-forge/tests/test_observe.py
git commit -m "feat(forge): Observation — facts that carry where they came from"
```

---

### Task 4: `Scaffold` and `Hole` — a partial artifact that cannot pretend to be whole

**Spec:** §3.1, §3.2, §3.3. The load-bearing decision of the whole design.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/scaffold.py`
- Test: `packages/mendel-forge/tests/test_scaffold.py`

**Interfaces:**
- Consumes: `Excerpt`, `Observation` from `mendel_forge.observe`; `DeclaredKind` from
  `comeni_core.declared.layered`.
- Produces: `Filler` (StrEnum: `HAND`, `DERIVED`, `MODEL`), `FilledValue(value, filler, by,
  why)`, `Candidate(value: str, note: str)`, `Hole(field, what, why_open, candidates,
  evidence)`, `Scaffold(kind, target, observation, filled, holes)` with
  `Scaffold.is_complete() -> bool`, `Scaffold.hole(field) -> Hole | None`, and
  `Scaffold.fill(field, value, filler, by, why) -> Scaffold`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from comeni_core.declared.layered import DeclaredKind
from mendel_forge.observe import Excerpt, Observation
from mendel_forge.scaffold import Candidate, Filler, Hole, Scaffold


def _scaffold() -> Scaffold:
    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="tools/nf-core/fastqc/fastqc.contract.yml",
        observation=Observation(source="nf-core", ref_id="nf-core/fastqc"),
        filled={},
        holes=[
            Hole(
                field="produces[0].type_id",
                what="the semantic type this port emits",
                why_open="a module declares a filename pattern, never a type",
                candidates=[Candidate(value="qc.report", note="declared in registry/types")],
                evidence=[Excerpt(locator="meta.yml:31", text="FastQC report")],
            )
        ],
    )


def test_a_scaffold_with_holes_is_not_complete():
    assert _scaffold().is_complete() is False


def test_filling_the_last_hole_completes_it():
    filled = _scaffold().fill(
        "produces[0].type_id", "qc.report", Filler.HAND, by="rafael", why="it is a report"
    )
    assert filled.is_complete() is True
    assert filled.holes == []
    assert filled.filled["produces[0].type_id"].value == "qc.report"
    assert filled.filled["produces[0].type_id"].filler is Filler.HAND


def test_filling_is_not_in_place():
    """A scaffold is a value. Mutating one would make the workspace's saved copy lie."""
    original = _scaffold()
    original.fill("produces[0].type_id", "qc.report", Filler.HAND, by="r", why="w")
    assert original.is_complete() is False


def test_filling_a_field_that_is_not_a_hole_is_refused():
    with pytest.raises(ValueError, match="MF0002"):
        _scaffold().fill("roles", "qc_per_sample", Filler.HAND, by="r", why="w")


def test_a_value_outside_the_candidates_is_refused():
    """Invariant 7 at draft time. A closed candidate list that anything may ignore is not one."""
    with pytest.raises(ValueError, match="MF0003"):
        _scaffold().fill("produces[0].type_id", "invented.type", Filler.HAND, by="r", why="w")


def test_a_hole_with_no_candidates_accepts_free_text():
    """`priority_because` has no enumerable legal values, and demanding some would make
    every prose field unfillable."""
    scaffold = Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="t",
        observation=Observation(source="s", ref_id="r"),
        holes=[Hole(field="priority_because", what="why this ranks here", why_open="a judgement")],
    )
    assert scaffold.fill("priority_because", "it is the only aligner", Filler.HAND,
                         by="r", why="w").is_complete()


def test_holes_serialise_in_field_order():
    scaffold = Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="t",
        observation=Observation(source="s", ref_id="r"),
        holes=[
            Hole(field="zebra", what="w", why_open="o"),
            Hole(field="alpha", what="w", why_open="o"),
        ],
    )
    assert [h["field"] for h in scaffold.model_dump()["holes"]] == ["alpha", "zebra"]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_scaffold.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'mendel_forge.scaffold'`

- [ ] **Step 3: Declare the two codes this task emits**

In `packages/comeni-core/src/comeni_core/diagnostics.yml`, add the band comment to the header
block, after the `MD0400` line:

```yaml
#   MF0001-MF0099  the forge: a scaffold, its holes, and filling them
#   MF0100-MF0199  the forge: landing a draft into a registry
```

Then add the entries (keep the file's alphabetical-by-code ordering — `MF` sorts after `MD`):

```yaml
MF0002:
  emitted_by: forge
  concern: scaffolding
  says: "that field is not a hole in this scaffold"
  fires_on: [forge fill]
  refuses: true
  fix: |
    Run `forge show <draft>` for the fields that are open. A field already filled is
    changed with `forge fill --force`, which records the overwrite.
  explanation: |
    Filling a field that is not open would either overwrite something the source
    proved, or invent a field the target model does not have. Both are silent in a
    plain dictionary, which is why a scaffold refuses rather than accepts.

MF0003:
  emitted_by: forge
  concern: scaffolding
  says: "the value is not one this hole declares as legal"
  fires_on: [forge fill]
  refuses: true
  fix: |
    Run `forge show <draft>` for the candidates. If the value you want is genuinely
    absent, the declaration it would come from — a type, a role — does not exist yet,
    and it is a separate draft that must land first.
  explanation: |
    Invariant 7 says vocabularies are closed: a contract naming an undeclared state
    fails to load. A hole carrying its legal values enforces that when the value is
    written rather than when the file is read, which turns a load-time refusal a
    reviewer sees late into an immediate one. A hole with no candidates accepts free
    text — prose fields have no enumerable domain.
```

- [ ] **Step 4: Implement**

```python
"""A partial artifact with typed holes.

**A scaffold is not a half-built contract.** `ModuleContract` has validators and forbids
extras, so a half-contract is unrepresentable — and it must stay that way, because the
moment a partially-valid contract is constructible somebody will persist one. The forge
therefore holds an `Observation` plus a list of `Hole`s and constructs the real model only
when the last hole is filled (`assemble.py`).

The consequence is the property the whole design rests on: **the forge cannot emit an
invalid declared file.** It emits either a valid one, or something that is honestly not one
yet and says which fields it is missing and why.
"""

from enum import StrEnum
from typing import Any

from comeni_core.declared.layered import DeclaredKind
from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from mendel_forge.observe import Excerpt, Observation

_NO_EXTRAS = ConfigDict(extra="forbid")


class Filler(StrEnum):
    """Who settled a value. `MODEL` exists before anything writes it, deliberately —
    the same argument as `ValueSource.MODEL`, which shipped a plan before its adapter."""

    DERIVED = "derived"
    HAND = "hand"
    MODEL = "model"


class FilledValue(BaseModel):
    model_config = _NO_EXTRAS

    value: Any
    filler: Filler
    by: str
    """`nf-core` for a derived fact, a username for a hand fill, a model id for a model one.
    Copied verbatim into `Provenance.drafted_by` at land time."""
    why: str


class Candidate(BaseModel):
    model_config = _NO_EXTRAS

    value: str
    note: str = ""
    """Where this candidate is declared, so a reviewer can check it without a second lookup."""


class Hole(BaseModel):
    model_config = _NO_EXTRAS

    field: str
    what: str
    why_open: str
    candidates: list[Candidate] = Field(default_factory=list)
    """Empty means free text. Non-empty means a closed choice, enforced by `fill`."""
    evidence: list[Excerpt] = Field(default_factory=list)

    def legal(self, value: Any) -> bool:
        return not self.candidates or any(c.value == value for c in self.candidates)


class Scaffold(BaseModel):
    model_config = _NO_EXTRAS

    kind: DeclaredKind
    target: str
    observation: Observation
    filled: dict[str, FilledValue] = Field(default_factory=dict)
    holes: list[Hole] = Field(default_factory=list)

    @field_serializer("filled")
    def _sorted_filled(self, filled: dict[str, FilledValue]) -> dict[str, FilledValue]:
        return {name: filled[name] for name in sorted(filled)}

    @field_serializer("holes")
    def _sorted_holes(self, holes: list[Hole]) -> list[dict[str, Any]]:
        """Determinism: ingestion order is parse order, and parse order moves under a
        refactor that changes nothing anybody asked to change."""
        return [hole.model_dump() for hole in sorted(holes, key=lambda h: h.field)]

    def is_complete(self) -> bool:
        return not self.holes

    def hole(self, field: str) -> Hole | None:
        return next((h for h in self.holes if h.field == field), None)

    def fill(self, field: str, value: Any, filler: Filler, *, by: str, why: str) -> "Scaffold":
        """Returns a new scaffold. A scaffold is a value; mutating one would make the
        workspace's saved copy disagree with the one in hand."""
        found = self.hole(field)
        if found is None:
            raise ValueError(
                coded("MF0002", f"{field} is not a hole in {self.target}")
                + f"\n  open: {', '.join(h.field for h in sorted(self.holes, key=lambda h: h.field))}"
            )
        if not found.legal(value):
            legal = ", ".join(c.value for c in found.candidates)
            raise ValueError(
                coded("MF0003", f"{value!r} is not legal for {field}") + f"\n  candidates: {legal}"
            )
        return self.model_copy(
            update={
                "filled": {**self.filled, field: FilledValue(
                    value=value, filler=filler, by=by, why=why
                )},
                "holes": [h for h in self.holes if h.field != field],
            }
        )
```

- [ ] **Step 5: Run the tests and the ownership guard**

Run: `uv run pytest packages/mendel-forge/tests/test_scaffold.py tests/test_diagnostics_ownership.py -v`
Expected: the scaffold tests pass. **The ownership tests also pass, and that is wrong** — Task 11
is where that is fixed. Note the result now so the contrast is visible then.

- [ ] **Step 6: Regenerate the diagnostics page**

```bash
uv run python tools/generate_diagnostics_doc.py
make check
```

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-forge packages/comeni-core/src/comeni_core/diagnostics.yml \
  docs/reference/diagnostics.md
git commit -m "feat(forge): Scaffold and Hole, and the two codes filling one can refuse

A scaffold is not a half-built contract: ModuleContract forbids extras and validates,
so a half-contract is unrepresentable and stays that way. MF0003 is invariant 7 moved
from load time to fill time — a closed candidate list that anything may ignore is not
a closed list."
```

---

### Task 5: The `Source` protocol and the source registry

**Spec:** §3.2, §3.4. Pluggable, per the operator's decision on 2026-08-16.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/sources/__init__.py`
- Test: `packages/mendel-forge/tests/test_sources.py`

**Interfaces:**
- Consumes: `Observation` from `mendel_forge.observe`.
- Produces: `ToolRef(source: str, ident: str)` with `ToolRef.parse(text: str) -> ToolRef`
  (spelled `<source>:<ident>`), the `Source` protocol
  (`name: str`, `discover(root: Path) -> list[ToolRef]`, `ingest(ref: ToolRef, root: Path) ->
  Observation`), `register(source: Source) -> None`, `get(name: str) -> Source`,
  `names() -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from mendel_forge import sources
from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.sources import ToolRef


class _Fake:
    name = "fake"

    def discover(self, root: Path) -> list[ToolRef]:
        return [ToolRef(source="fake", ident="tool-b"), ToolRef(source="fake", ident="tool-a")]

    def ingest(self, ref: ToolRef, root: Path) -> Observation:
        return Observation(
            source="fake",
            ref_id=ref.ident,
            facts={"n": Fact(value=1, evidence=Excerpt(locator="x:1", text="t"))},
        )


def test_a_ref_round_trips_through_its_text_form():
    assert ToolRef.parse("nf-core:fastqc") == ToolRef(source="nf-core", ident="fastqc")
    assert str(ToolRef(source="nf-core", ident="fastqc")) == "nf-core:fastqc"


def test_a_ref_without_a_source_is_refused():
    with pytest.raises(ValueError, match="MF0001"):
        ToolRef.parse("fastqc")


def test_a_registered_source_is_retrievable_by_name(monkeypatch):
    monkeypatch.setattr(sources, "_REGISTERED", {})
    sources.register(_Fake())
    assert sources.names() == ["fake"]
    assert sources.get("fake").ingest(ToolRef.parse("fake:x"), Path(".")).ref_id == "x"


def test_an_unknown_source_names_the_ones_that_exist(monkeypatch):
    monkeypatch.setattr(sources, "_REGISTERED", {})
    sources.register(_Fake())
    with pytest.raises(ValueError, match="MF0001") as caught:
        sources.get("pegi3s")
    assert "fake" in str(caught.value)


def test_discover_is_sorted(monkeypatch):
    """Two sources listing tools in filesystem order would make `forge discover` output
    depend on the machine. Determinism is not only about emitted files."""
    monkeypatch.setattr(sources, "_REGISTERED", {})
    sources.register(_Fake())
    found = sources.discover_all(Path("."))
    assert [r.ident for r in found] == ["tool-a", "tool-b"]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_sources.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Declare `MF0001`**

Add to `diagnostics.yml`:

```yaml
MF0001:
  emitted_by: forge
  concern: scaffolding
  says: "no such source, or a tool reference that does not name one"
  fires_on: [forge discover, forge draft]
  refuses: true
  fix: |
    Run `forge sources` for the registered names, and spell a reference
    `<source>:<tool>` — `nf-core:fastqc`, not `fastqc`.
  explanation: |
    A reference without a source is ambiguous the moment a second source exists, and a
    second source is the reason the ingestion layer is a protocol at all. Refusing the
    bare form now costs one colon and prevents a reference that means different things
    on two machines.
```

- [ ] **Step 4: Implement**

```python
"""Where a tool comes from, and how one is read.

**Pluggable by decision, not by prediction.** nf-core is what is vendored and what
`modulespec.py` parses; pegi3s is issue #65 and is designed for rather than built. A
protocol with one implementation is a protocol designed against imagination, so the test
suite ships a second — `tests/fixtures/opaque` — whose shape is pegi3s's: no module, almost
everything a hole.

A `Source` returns an `Observation` and nothing contract-shaped. Keeping the two apart is
what lets a source for something nobody has written yet need no change here.
"""

from pathlib import Path
from typing import Protocol

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.observe import Observation


class ToolRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    ident: str

    def __str__(self) -> str:
        return f"{self.source}:{self.ident}"

    @classmethod
    def parse(cls, text: str) -> "ToolRef":
        source, sep, ident = text.partition(":")
        if not sep or not source or not ident:
            raise ValueError(
                coded("MF0001", f"{text!r} does not name a source")
                + f"\n  spell it <source>:<tool> — known sources: {', '.join(names())}"
            )
        return cls(source=source, ident=ident)


class Source(Protocol):
    """One place tools are read from."""

    name: str

    def discover(self, root: Path) -> list[ToolRef]:
        """Every tool this source can ingest under `root`. Sorted."""
        ...

    def ingest(self, ref: ToolRef, root: Path) -> Observation:
        """What can be proven about one tool. Never a guess: a fact with no evidence
        does not belong in an `Observation`."""
        ...


_REGISTERED: dict[str, Source] = {}


def register(source: Source) -> None:
    _REGISTERED[source.name] = source


def names() -> list[str]:
    return sorted(_REGISTERED)


def get(name: str) -> Source:
    if name not in _REGISTERED:
        raise ValueError(
            coded("MF0001", f"{name!r} is not a registered source")
            + f"\n  known: {', '.join(names()) or '(none)'}"
        )
    return _REGISTERED[name]


def discover_all(root: Path) -> list[ToolRef]:
    found = [ref for name in names() for ref in _REGISTERED[name].discover(root)]
    return sorted(found, key=lambda r: (r.source, r.ident))
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/mendel-forge/tests/test_sources.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-forge packages/comeni-core/src/comeni_core/diagnostics.yml docs/reference/diagnostics.md
git commit -m "feat(forge): the Source protocol, a registry of them, and MF0001"
```

---

### Task 6: The nf-core source — `ModuleSpec` read forwards

**Spec:** §3.4, and **Task 1's derivability table, implemented literally.** Where the table and
this task disagree, the table is right and this task is wrong.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/sources/nfcore.py`
- Test: `packages/mendel-forge/tests/test_source_nfcore.py`

**Interfaces:**
- Consumes: `ModuleSpec.parse` from `mendel_compiler.modulespec`; `Excerpt`, `Fact`,
  `Observation`; `ToolRef`, `Source`, `register`.
- Produces: `NfCoreSource` with `name = "nf-core"`, registered at import of
  `mendel_forge.sources.nfcore`. Fact names it sets, which Task 8 reads:
  `process`, `container`, `emits`, `input_arity`, `input_names`, `meta_reads`,
  `reads_ext_args`, `reads_ext_prefix`, `nf_include`, `documented_inputs`.

- [ ] **Step 1: Write the failing test against a real vendored module**

```python
from pathlib import Path

from mendel_forge.sources import ToolRef
from mendel_forge.sources.nfcore import NfCoreSource

ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "vendor"


def test_discover_finds_every_vendored_module():
    found = NfCoreSource().discover(VENDOR)
    idents = [r.ident for r in found]
    assert "fastqc" in idents
    assert "samtools/sort" in idents
    assert found == sorted(found, key=lambda r: r.ident), "discover must be sorted"


def test_ingest_derives_the_process_name_with_evidence():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), VENDOR)
    assert obs.fact("process") == "FASTQC"
    assert obs.facts["process"].evidence.locator.endswith("main.nf")


def test_ingest_derives_the_container_the_module_actually_declares():
    """Take the LAST quoted string in the container ternary — nf-core 4.x mostly uses
    community.wave.seqera.io, and reading the first gives the singularity URI."""
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), VENDOR)
    assert obs.fact("container") is not None


def test_ingest_derives_the_emit_names():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), VENDOR)
    assert "zip" in obs.fact("emits")


def test_ingest_derives_the_channel_count_not_the_port_count():
    """A contract port is not a process argument. `nf_inputs` arity is what Nextflow
    matches, and a 2-tuple in a 3-tuple slot dies on 'Path value cannot be null'."""
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:samtools/sort"), VENDOR)
    assert obs.fact("input_arity") == 3


def test_ingest_carries_meta_yml_prose_when_present():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), VENDOR)
    assert obs.prose, "meta.yml documentation should reach the observation"


def test_the_source_registers_itself_on_import():
    from mendel_forge import sources

    assert "nf-core" in sources.names()
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_source_nfcore.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""nf-core modules: the source that ships its own Nextflow.

Largely `ModuleSpec` read **forwards**. The same regex parser `conformance.py` uses to check
a contract against a module is used here to propose one — one parser, so a syntax nf-core
adopts that this cannot read fails loudly in both directions rather than in one.

**What it does not derive is the point.** A module declares an output as `type: file` with a
filename pattern; "sorted" exists only in an English description. The semantic overlay —
`type_id`, `state`, `roles` — is the missing ~40% and is every hole this source produces.
"""

from pathlib import Path

from comeni_core import yaml_strict
from mendel_compiler.modulespec import ModuleSpec

from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.sources import ToolRef, register


class NfCoreSource:
    name = "nf-core"

    def discover(self, root: Path) -> list[ToolRef]:
        found = [
            ToolRef(
                source=self.name,
                ident=str(main_nf.parent.relative_to(root / "modules" / "nf-core")),
            )
            for main_nf in (root / "modules" / "nf-core").rglob("main.nf")
        ]
        return sorted(found, key=lambda r: r.ident)

    def ingest(self, ref: ToolRef, root: Path) -> Observation:
        module_dir = root / "modules" / "nf-core" / ref.ident
        main_nf = module_dir / "main.nf"
        spec = ModuleSpec.parse(main_nf)
        at = str(main_nf)

        def fact(value: object) -> Fact:
            return Fact(value=value, evidence=Excerpt(locator=at, text=f"{spec.process} in main.nf"))

        facts = {
            "process": fact(spec.process),
            "emits": fact(list(spec.emits)),
            "input_arity": fact(len(spec.inputs)),
            "input_names": fact([slot.names for slot in spec.inputs]),
            "meta_reads": fact(sorted({read.key for read in spec.meta_reads})),
            "reads_ext_args": fact(spec.reads_ext_args),
            "reads_ext_prefix": fact(spec.reads_ext_prefix),
            "nf_include": fact(f"modules/nf-core/{ref.ident}/main"),
        }
        if spec.container:
            facts["container"] = fact(spec.container)
        if spec.documented:
            facts["documented_inputs"] = fact([d.name for d in spec.documented])

        return Observation(
            source=self.name, ref_id=str(ref), facts=facts, prose=_prose(module_dir)
        )


def _prose(module_dir: Path) -> list[Excerpt]:
    """`meta.yml` is a scaffold, not a contract — it declares outputs as `type: file` with a
    filename pattern. Its English is still the best evidence a reviewer has for what a port
    *means*, which is exactly the judgement a hole asks for."""
    meta = module_dir / "meta.yml"
    if not meta.exists():
        return []
    data = yaml_strict.load(meta)
    if not isinstance(data, dict):
        return []
    found = []
    if isinstance(data.get("description"), str):
        found.append(Excerpt(locator=f"{meta}:description", text=data["description"]))
    for key in ("input", "output"):
        entry = data.get(key)
        if entry is not None:
            found.append(Excerpt(locator=f"{meta}:{key}", text=str(entry)))
    return found


register(NfCoreSource())
```

- [ ] **Step 4: Run and reconcile against Task 1's table**

Run: `uv run pytest packages/mendel-forge/tests/test_source_nfcore.py -v`
Expected: 7 passed. If `test_ingest_derives_the_channel_count_not_the_port_count` fails with a
number other than 3, **check `vendor/modules/nf-core/samtools/sort/main.nf` and fix the test to
what the module says** — the module is ground truth, not this plan.

- [ ] **Step 5: Import the source from the package root so registration happens**

In `src/mendel_forge/__init__.py`:

```python
from mendel_forge.sources import nfcore as _nfcore  # noqa: F401  — registers "nf-core"
```

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-forge
git commit -m "feat(forge): the nf-core source, ModuleSpec read forwards

One parser for both directions: the regexes that check a contract against a module now
also propose one, so a syntax nf-core adopts that this cannot read fails in both places
rather than silently in one."
```

---

### Task 7: The fixture source — the phantom limb, load-tested

**Spec:** §3.4, §9.3, and issue #65. **A protocol with one implementation is designed against
imagination.**

**Files:**
- Create: `packages/mendel-forge/tests/fixtures/opaque/tools/widget/tool.yml`
- Create: `packages/mendel-forge/tests/opaque_source.py`
- Test: `packages/mendel-forge/tests/test_source_opaque.py`

**Interfaces:**
- Produces: `OpaqueSource` with `name = "opaque"`. **Test-suite only** — it is not registered at
  package import and does not ship in the wheel.

- [ ] **Step 1: Create the fake tool**

`packages/mendel-forge/tests/fixtures/opaque/tools/widget/tool.yml`:

```yaml
name: widget
container: docker.io/example/widget:1.4.0
description: |
  Widget counts things in a file and writes a table. It reads one input file and
  writes one output table. There is no Nextflow module for it.
```

- [ ] **Step 2: Write the failing test**

```python
from pathlib import Path

from mendel_forge.sources import ToolRef

from .opaque_source import OpaqueSource

FIXTURES = Path(__file__).parent / "fixtures" / "opaque"


def test_it_discovers_the_fake_tool():
    assert [str(r) for r in OpaqueSource().discover(FIXTURES)] == ["opaque:widget"]


def test_it_derives_a_container_and_a_name_and_nothing_else():
    obs = OpaqueSource().ingest(ToolRef.parse("opaque:widget"), FIXTURES)
    assert obs.fact("container") == "docker.io/example/widget:1.4.0"
    assert obs.fact("process") is None, "a source with no module cannot know a process name"
    assert obs.fact("emits") is None
    assert obs.fact("nf_include") is None


def test_it_carries_the_documentation_as_prose():
    obs = OpaqueSource().ingest(ToolRef.parse("opaque:widget"), FIXTURES)
    assert any("counts things" in e.text for e in obs.prose)


def test_it_satisfies_the_same_protocol_as_nf_core():
    """The whole reason this file exists. If `Source` grows a member only nf-core can
    supply, this stops type-checking and the seam has quietly closed."""
    from mendel_forge.sources import Source

    def takes_any_source(source: Source) -> str:
        return source.name

    assert takes_any_source(OpaqueSource()) == "opaque"
```

- [ ] **Step 3: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_source_opaque.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named '...opaque_source'`

- [ ] **Step 4: Implement**

`packages/mendel-forge/tests/opaque_source.py`:

```python
"""A source shaped like pegi3s, so the protocol has two implementations from day one.

**Not a pegi3s adapter** — that is issue #65, and it needs a container registry and a
decision about what may honestly be read out of documentation prose. This is the *shape*:
a container, a name, no Nextflow module, and everything else a hole.

It lives in `tests/` and is never registered at package import, so it cannot reach a user.
Its job is to fail loudly if `Source` ever grows a member only nf-core can supply — which
is how a pluggable seam quietly becomes a single-implementation one.
"""

from pathlib import Path

from comeni_core import yaml_strict
from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.sources import ToolRef


class OpaqueSource:
    name = "opaque"

    def discover(self, root: Path) -> list[ToolRef]:
        found = [
            ToolRef(source=self.name, ident=path.parent.name)
            for path in (root / "tools").rglob("tool.yml")
        ]
        return sorted(found, key=lambda r: r.ident)

    def ingest(self, ref: ToolRef, root: Path) -> Observation:
        path = root / "tools" / ref.ident / "tool.yml"
        data = yaml_strict.load(path)
        at = str(path)
        facts = {}
        if isinstance(data, dict) and isinstance(data.get("container"), str):
            facts["container"] = Fact(
                value=data["container"],
                evidence=Excerpt(locator=f"{at}:container", text=data["container"]),
            )
        prose = []
        if isinstance(data, dict) and isinstance(data.get("description"), str):
            prose.append(Excerpt(locator=f"{at}:description", text=data["description"]))
        return Observation(source=self.name, ref_id=str(ref), facts=facts, prose=prose)
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/mendel-forge/tests/test_source_opaque.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-forge
git commit -m "test(forge): a pegi3s-shaped fixture source (#65)

Planned for rather than built. What it buys is that the Source protocol has two
implementations from the first commit, so it cannot quietly become nf-core-shaped —
the rule drafter's argument about designing a format before the rules exist, applied
one layer over."
```

> ## ✅ Checkpoint B
>
> Run `uv run pytest packages/mendel-forge -v` and `make check`. Report: how many vendored
> modules `discover` found, and whether any assertion in Task 6 had to be changed to match what
> a module actually says.
---

# Checkpoint C — from an observation to a real contract

### Task 8: Candidates — what the registry already declares

**Spec:** §3.3. The hint mechanism, and invariant 7 enforced at draft time.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/candidates.py`
- Test: `packages/mendel-forge/tests/test_candidates.py`

**Interfaces:**
- Consumes: `layers.load(paths) -> Layers` from `mendel_resolver.layers`, whose fields are
  `measurements`, `vocabulary` (`.types: dict[str, frozenset[str]]`), `registry`,
  `roles` (`.names: frozenset[str]`), `rules`, `paths`.
- Produces: `for_field(field: str, stack: Layers) -> list[Candidate]`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from mendel_forge.candidates import for_field
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]


def _stack():
    return layers.load(ROOT / "registry")


def test_a_type_id_hole_offers_every_declared_type():
    found = [c.value for c in for_field("produces[0].type_id", _stack())]
    assert "qc.report" in found
    assert "alignment.bam" in found
    assert found == sorted(found), "candidates must be sorted; output is compared byte-for-byte"


def test_a_roles_hole_offers_every_declared_role():
    found = [c.value for c in for_field("roles", _stack())]
    assert "qc_per_sample" in found


def test_a_state_hole_offers_only_the_states_of_its_own_type():
    """`state` is meaningless without the type it qualifies, and offering every state in
    the vocabulary would invite `coordinate_sorted` on a FASTQ."""
    found = [c.value for c in for_field("produces[0].state", _stack(), type_id="alignment.bam")]
    assert "coordinate_sorted" in found
    assert "trimmed" not in found


def test_a_prose_field_has_no_candidates():
    assert for_field("priority_because", _stack()) == []


def test_an_unknown_field_has_no_candidates_rather_than_raising():
    """A hole for a field nobody anticipated is free text, not a crash. The forge must keep
    working when a contract gains a field before this file knows about it."""
    assert for_field("some_future_field", _stack()) == []


def test_every_candidate_says_where_it_is_declared():
    for candidate in for_field("roles", _stack()):
        assert candidate.note, f"{candidate.value} has no note saying where it comes from"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_candidates.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""What a hole will accept, read off the layer stack rather than hard-coded.

**This is invariant 7 moved earlier.** Vocabularies are closed: a contract naming an
undeclared state fails to load. A hole carrying its legal values turns that load-time
refusal into a fill-time one — and, from Phase 2, turns an open prompt into a closed
choice. A model asked *"which of these nine types"* cannot invent a tenth.

**An unknown field yields no candidates rather than raising.** A contract gaining a field
before this module knows about it must degrade to free text, not to a crash: the forge is
the thing that keeps working while the registry moves.
"""

import re

from mendel_resolver.layers import Layers

from mendel_forge.scaffold import Candidate

_INDEX = re.compile(r"\[\d+\]")


def _base(field: str) -> str:
    """`produces[0].type_id` and `consumes[2].type_id` ask the same question."""
    return _INDEX.sub("[]", field)


def for_field(field: str, stack: Layers, *, type_id: str | None = None) -> list[Candidate]:
    base = _base(field)

    if base.endswith("type_id"):
        return [
            Candidate(value=name, note="declared type")
            for name in sorted(stack.vocabulary.types)
        ]

    if base == "roles":
        return [Candidate(value=name, note="declared role") for name in sorted(stack.roles.names)]

    if base.endswith("state") or base.endswith("state_required"):
        if type_id is None:
            return []
        return [
            Candidate(value=state, note=f"state of {type_id}")
            for state in sorted(stack.vocabulary.states_for(type_id))
        ]

    return []
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/mendel-forge/tests/test_candidates.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-forge
git commit -m "feat(forge): candidates for a hole, read off the layer stack

The same list three ways: printed by the CLI, a picker in the GUI, and a closed choice
for Phase 2's filler. An unknown field degrades to free text rather than raising —
the forge has to keep working while the registry moves under it."
```

---

### Task 9: `scaffold_for` — an observation becomes holes

**Spec:** §3.1, §3.4, and **Task 1's derivability table**. Every `derived` row becomes a
`filled` entry; every `hole` row becomes a `Hole`.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/assemble.py`
- Test: `packages/mendel-forge/tests/test_assemble_scaffold.py`

**Interfaces:**
- Consumes: `Observation`; `Scaffold`, `Hole`, `FilledValue`, `Filler`; `candidates.for_field`;
  `Layers`.
- Produces: `scaffold_for(obs: Observation, stack: Layers, *, ident: str, version: str) ->
  Scaffold`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from mendel_forge.assemble import scaffold_for
from mendel_forge.scaffold import Filler
from mendel_forge.sources import ToolRef
from mendel_forge.sources.nfcore import NfCoreSource
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]


def _scaffold():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), ROOT / "vendor")
    return scaffold_for(obs, layers.load(ROOT / "registry"), ident="nf-core/fastqc",
                        version="0.12.1")


def test_the_process_name_arrives_filled_and_derived():
    filled = _scaffold().filled["nf_process"]
    assert filled.value == "FASTQC"
    assert filled.filler is Filler.DERIVED
    assert filled.by == "nf-core"
    assert filled.why, "a derived value still has to say why — the evidence locator"


def test_semantic_fields_arrive_as_holes():
    open_fields = {h.field for h in _scaffold().holes}
    assert "roles" in open_fields
    assert any(f.endswith("type_id") for f in open_fields)


def test_every_hole_says_why_it_is_open():
    for hole in _scaffold().holes:
        assert hole.why_open, f"{hole.field} is open with no stated reason"


def test_a_type_id_hole_carries_the_declared_types_as_candidates():
    hole = next(h for h in _scaffold().holes if h.field.endswith("type_id"))
    assert "qc.report" in [c.value for c in hole.candidates]


def test_a_hole_carries_the_prose_that_bears_on_it():
    hole = next(h for h in _scaffold().holes if h.field == "produces[0].type_id")
    assert hole.evidence, "meta.yml's description of the output should reach the hole"


def test_the_target_path_follows_the_registry_convention():
    assert _scaffold().target == "tools/nf-core/fastqc/fastqc.contract.yml"


def test_a_source_with_no_module_holes_everything_the_module_would_have_given():
    from .opaque_source import OpaqueSource

    fixtures = Path(__file__).parent / "fixtures" / "opaque"
    obs = OpaqueSource().ingest(ToolRef.parse("opaque:widget"), fixtures)
    scaffold = scaffold_for(obs, layers.load(ROOT / "registry"), ident="opaque/widget",
                            version="1.4.0")
    open_fields = {h.field for h in scaffold.holes}
    assert "nf_process" in open_fields
    assert "container" not in open_fields, "the container WAS derivable from tool.yml"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_assemble_scaffold.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
"""Observation in, scaffold out — and scaffold in, contract out.

Two directions of one mapping, kept in one file because they must agree: a field this
module fills must be a field the other reads, and splitting them is how the two halves of
a serialiser drift apart.

**The mapping is `notes/audits/2026-08-16-forge-derivability.md`, implemented literally.**
That table was measured against every vendored module rather than reasoned about. Where
this file and the table disagree, the table is right.
"""

from typing import Any

from mendel_resolver.layers import Layers

from mendel_forge import candidates
from mendel_forge.observe import Observation
from mendel_forge.scaffold import Filler, FilledValue, Hole, Scaffold
from comeni_core.declared.layered import DeclaredKind

_WHY_OPEN = {
    "roles": "a module declares no role — a role is the job it does in a pipeline, "
             "which is a judgement about the registry rather than a fact about the tool",
    "type_id": "nf-core declares an output as `type: file` with a filename pattern; the "
               "semantic type exists only in the English description",
    "state": "the same — `sorted` is in the prose, never in the declaration",
    "priority_because": "why this contract ranks where it does is a judgement, and a bare "
                        "integer with no reason is the gap audit A128 is about",
    "nf_process": "this source ships no Nextflow module, so the process name is whatever "
                  "the generated one is called",
}


def _derived(value: Any, obs: Observation, name: str) -> FilledValue:
    evidence = obs.facts[name].evidence
    return FilledValue(
        value=value, filler=Filler.DERIVED, by=obs.source, why=f"read from {evidence.locator}"
    )


def _hole(field: str, stack: Layers, obs: Observation, *, why: str, type_id: str | None = None
          ) -> Hole:
    return Hole(
        field=field,
        what=f"a value for {field}",
        why_open=why,
        candidates=candidates.for_field(field, stack, type_id=type_id),
        evidence=list(obs.prose),
    )


def scaffold_for(obs: Observation, stack: Layers, *, ident: str, version: str) -> Scaffold:
    filled: dict[str, FilledValue] = {}
    holes: list[Hole] = []

    filled["id"] = FilledValue(
        value=f"{ident}@{version}", filler=Filler.DERIVED, by=obs.source,
        why=f"the tool's path and version under {obs.source}",
    )
    filled["provenance.source"] = FilledValue(
        value=obs.source, filler=Filler.DERIVED, by=obs.source, why="the source it was read from"
    )

    for name, field in (
        ("process", "nf_process"),
        ("nf_include", "nf_include"),
        ("container", "container"),
    ):
        if obs.fact(name) is not None:
            filled[field] = _derived(obs.fact(name), obs, name)
        else:
            holes.append(_hole(field, stack, obs, why=_WHY_OPEN.get(field, "not derivable")))

    emits = obs.fact("emits") or []
    for index, emit in enumerate(emits):
        filled[f"produces[{index}].name"] = _derived(emits, obs, "emits").model_copy(
            update={"value": emit}
        )
        holes.append(_hole(f"produces[{index}].type_id", stack, obs, why=_WHY_OPEN["type_id"]))

    arity = obs.fact("input_arity")
    if arity is not None:
        filled["nf_inputs.arity"] = _derived(arity, obs, "input_arity")

    holes.append(_hole("roles", stack, obs, why=_WHY_OPEN["roles"]))
    holes.append(_hole("priority_because", stack, obs, why=_WHY_OPEN["priority_because"]))

    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target=_target(ident),
        observation=obs,
        filled=filled,
        holes=sorted(holes, key=lambda h: h.field),
    )


def _target(ident: str) -> str:
    """Where the file lands, following the convention the public registry already uses.

    A layer's layout is free — invariant 11 says a file declares its own kind, so nothing
    reads the path. The convention groups a tool's files together, and it is **not uniform**:

        nf-core/fastqc         -> tools/nf-core/fastqc/fastqc.contract.yml
        nf-core/samtools/sort  -> tools/nf-core/samtools/sort.contract.yml

    A single-segment tool doubles its name to get a directory of its own; a multi-segment
    one already has one. Read off the shipped registry rather than invented — every id in
    it was checked when this was written.
    """
    source, _, tool = ident.partition("/")
    tail = tool if "/" in tool else f"{tool}/{tool}"
    return f"tools/{source}/{tail}.contract.yml"
```

- [ ] **Step 4: Add the second target-path case to the test**

`_target` has two branches and the test above exercises one. Add:

```python
def test_a_multi_segment_tool_does_not_double_its_name():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:samtools/sort"), ROOT / "vendor")
    scaffold = scaffold_for(obs, layers.load(ROOT / "registry"),
                            ident="nf-core/samtools/sort", version="1.21.0")
    assert scaffold.target == "tools/nf-core/samtools/sort.contract.yml"
```

- [ ] **Step 5: Run the tests, and reconcile against the table**

Run: `uv run pytest packages/mendel-forge/tests/test_assemble_scaffold.py -v`
Expected: 8 passed. If a target path disagrees, **the shipped registry is right** — every id
and path in it was read when this plan was written, and the convention is not uniform.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-forge
git commit -m "feat(forge): an observation becomes filled fields and typed holes

Implements notes/audits/2026-08-16-forge-derivability.md literally. A derived value
still records why — the evidence locator — because 'derived' with no pointer is the
same unsourced assertion the semantic fields are holes for."
```

---

### Task 10: `contract_from` — a scaffold becomes a real contract, or refuses

**Spec:** §3.1. The property the design rests on, made executable.

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/assemble.py`
- Test: `packages/mendel-forge/tests/test_assemble_contract.py`

**Interfaces:**
- Consumes: `ModuleContract`, `Provenance`, `InputPort`, `OutputPort`, `NfInput` from
  `comeni_core.declared.contract`.
- Produces: `contract_from(scaffold: Scaffold, *, approved_by: str, approved_at: str) ->
  ModuleContract`, and `to_yaml(scaffold, *, approved_by, approved_at) -> str`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.layered import DeclaredKind
from mendel_forge.assemble import contract_from, to_yaml
from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.scaffold import Filler, FilledValue, Hole, Scaffold


def _complete() -> Scaffold:
    def derived(value):
        return FilledValue(value=value, filler=Filler.DERIVED, by="nf-core", why="main.nf")

    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="tools/nf-core/fastqc/fastqc.contract.yml",
        observation=Observation(
            source="nf-core",
            ref_id="nf-core:fastqc",
            facts={"process": Fact(value="FASTQC", evidence=Excerpt(locator="m:1", text="t"))},
        ),
        filled={
            "id": derived("nf-core/fastqc@0.12.1"),
            "nf_process": derived("FASTQC"),
            "nf_include": derived("modules/nf-core/fastqc/main"),
            "container": derived("quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0"),
            "produces[0].name": derived("zip"),
            "produces[0].type_id": FilledValue(
                value="qc.report", filler=Filler.HAND, by="rafael", why="it is a report"
            ),
            "roles": FilledValue(
                value=["qc_per_sample"], filler=Filler.HAND, by="rafael", why="it QCs a sample"
            ),
            "priority_because": FilledValue(
                value="the only QC tool", filler=Filler.HAND, by="rafael", why="no alternative"
            ),
        },
        holes=[],
    )


def test_a_complete_scaffold_becomes_a_real_contract():
    contract = contract_from(_complete(), approved_by="rafael", approved_at="2026-08-20")
    assert isinstance(contract, ModuleContract)
    assert contract.nf_process == "FASTQC"
    assert contract.produces[0].type_id == "qc.report"
    assert contract.roles == ["qc_per_sample"]


def test_provenance_carries_the_filler_forward():
    """`drafted_by` is where Phase 2's model id lands, and the field already exists."""
    contract = contract_from(_complete(), approved_by="rafael", approved_at="2026-08-20")
    assert contract.provenance.source == "nf-core"
    assert contract.provenance.approved_by == "rafael"
    assert contract.provenance.drafted_by == "hand", "no model was involved, so say so"


def test_a_scaffold_with_a_hole_refuses_rather_than_defaulting():
    """The property everything rests on. A default here would be the forge inventing a
    value with a straight face, which is what a hole exists to prevent."""
    incomplete = _complete().model_copy(
        update={"holes": [Hole(field="roles", what="w", why_open="o")]}
    )
    with pytest.raises(ValueError, match="MF0004") as caught:
        contract_from(incomplete, approved_by="r", approved_at="2026-08-20")
    assert "roles" in str(caught.value)


def test_the_yaml_declares_its_own_kind():
    text = to_yaml(_complete(), approved_by="rafael", approved_at="2026-08-20")
    assert text.startswith("declares: contract\n")


def test_the_yaml_round_trips_through_the_real_loader(tmp_path):
    """The strongest assertion available: what the forge writes is what the registry reads."""
    from pathlib import Path

    from mendel_resolver import layers

    root = Path(__file__).resolve().parents[3]
    stack = layers.load(root / "registry")
    path = tmp_path / "fastqc.contract.yml"
    path.write_text(to_yaml(_complete(), approved_by="rafael", approved_at="2026-08-20"))
    assert ModuleContract.load(path, stack.vocabulary).id == "nf-core/fastqc@0.12.1"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_assemble_contract.py -v`
Expected: FAIL, `ImportError: cannot import name 'contract_from'`

- [ ] **Step 3: Declare `MF0004`**

```yaml
MF0004:
  emitted_by: forge
  concern: scaffolding
  says: "the scaffold still has open holes and cannot become a declared file"
  fires_on: [forge verify, forge land]
  refuses: true
  fix: |
    Run `forge show <draft>` for the open fields and `forge fill` for each. Every hole
    names why it is open and what values are legal there.
  explanation: |
    A scaffold is not a half-built contract — the model it becomes validates and forbids
    extras, so a partially-valid one is unrepresentable. Defaulting the missing fields
    would let the forge invent a value with a straight face, which is the thing a hole
    exists to prevent. The refusal is the design working, not a failure.
```

- [ ] **Step 4: Implement, appending to `assemble.py`**

```python
def _require_complete(scaffold: Scaffold) -> None:
    if scaffold.is_complete():
        return
    open_fields = ", ".join(h.field for h in sorted(scaffold.holes, key=lambda h: h.field))
    raise ValueError(
        coded("MF0004", f"{scaffold.target} has {len(scaffold.holes)} open hole(s)")
        + f"\n  open: {open_fields}"
    )


def _drafted_by(scaffold: Scaffold) -> str:
    """`hand` when a person filled every non-derived hole; the model id when one did.

    Phase 2 needs no change here: `Filler.MODEL` already exists and `by` already carries
    the id, so a model-filled scaffold lands with its model named in the file.
    """
    fillers = {v.filler: v.by for v in scaffold.filled.values()}
    return fillers.get(Filler.MODEL, "hand")


def contract_from(scaffold: Scaffold, *, approved_by: str, approved_at: str) -> ModuleContract:
    _require_complete(scaffold)
    value = {field: filled.value for field, filled in scaffold.filled.items()}

    produces = []
    for index in range(len({k for k in value if k.startswith("produces[")} and
                           {k.split("]")[0] for k in value if k.startswith("produces[")})):
        produces.append(
            OutputPort(
                name=value[f"produces[{index}].name"],
                type_id=value[f"produces[{index}].type_id"],
                state=frozenset(value.get(f"produces[{index}].state", [])),
            )
        )

    consumes = []
    for index in range(len({k.split("]")[0] for k in value if k.startswith("consumes[")})):
        consumes.append(
            InputPort(
                name=value[f"consumes[{index}].name"],
                type_id=value.get(f"consumes[{index}].type_id", ""),
                state_required=frozenset(value.get(f"consumes[{index}].state_required", [])),
            )
        )

    return ModuleContract(
        id=value["id"],
        nf_process=value["nf_process"],
        nf_include=value["nf_include"],
        consumes=consumes,
        produces=produces,
        roles=value.get("roles", []),
        priority=value.get("priority", 0),
        priority_because=value.get("priority_because", ""),
        container=value.get("container"),
        provenance=Provenance(
            source=value["provenance.source"],
            drafted_by=_drafted_by(scaffold),
            approved_by=approved_by,
            approved_at=approved_at,
        ),
    )


def to_yaml(scaffold: Scaffold, *, approved_by: str, approved_at: str) -> str:
    """The file as it will land. `declares: contract` first, because that is the line the
    loader reads to know what the file is — comeni-registry#1 retired the directory that
    used to say it, and a misspelled `declares:` is MD0011 rather than an impossibility."""
    contract = contract_from(scaffold, approved_by=approved_by, approved_at=approved_at)
    body = contract.model_dump(mode="json", exclude_defaults=True)
    return "declares: contract\n" + yaml.safe_dump(body, sort_keys=False, width=100)
```

Add the imports at the top of `assemble.py`:

```python
import yaml
from comeni_core.declared.contract import InputPort, ModuleContract, OutputPort, Provenance
from comeni_core.diagnostics import coded
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/mendel-forge/tests/test_assemble_contract.py -v`
Expected: 5 passed. The index-counting expression in `contract_from` is deliberately ugly —
**simplify it** to a helper that groups `filled` keys by their `produces[N]` / `consumes[N]`
prefix, and keep the tests green while you do.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-forge packages/comeni-core/src/comeni_core/diagnostics.yml docs/reference/diagnostics.md
git commit -m "feat(forge): a complete scaffold becomes a contract; an incomplete one refuses

MF0004 is the design working rather than failing. The round-trip test is the strongest
assertion available here: what the forge writes is loaded back by the real loader with
the real vocabulary, so 'it produces valid YAML' is not taken on trust."
```

---

### Task 11: A skeleton `main.nf` for a source that ships none

**Spec:** §4. What makes a module-less source reachable at all.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/modulegen.py`
- Test: `packages/mendel-forge/tests/test_modulegen.py`

**Interfaces:**
- Consumes: `Scaffold`.
- Produces: `skeleton(scaffold: Scaffold) -> str`, and `needs_module(obs: Observation) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
from mendel_forge.modulegen import needs_module, skeleton
from mendel_forge.observe import Excerpt, Fact, Observation


def _obs_without_a_module() -> Observation:
    return Observation(
        source="opaque",
        ref_id="opaque:widget",
        facts={
            "container": Fact(
                value="docker.io/example/widget:1.4.0",
                evidence=Excerpt(locator="tool.yml:container", text="x"),
            )
        },
    )


def test_a_source_with_no_include_needs_a_module():
    assert needs_module(_obs_without_a_module()) is True


def test_a_source_that_ships_one_does_not():
    obs = _obs_without_a_module().model_copy(
        update={
            "facts": {
                "nf_include": Fact(
                    value="modules/nf-core/fastqc/main",
                    evidence=Excerpt(locator="m:1", text="t"),
                )
            }
        }
    )
    assert needs_module(obs) is False


def test_the_skeleton_declares_the_process_the_contract_names(widget_scaffold):
    assert "process WIDGET {" in skeleton(widget_scaffold)


def test_the_skeleton_has_a_stub_block(widget_scaffold):
    """-stub-run is the fast validation tier, and a module with no stub cannot use it.
    nf-core modules all define one, which is why the whole DAG executes in seconds."""
    text = skeleton(widget_scaffold)
    assert "\n    stub:\n" in text
    assert "touch " in text.split("stub:")[1]


def test_the_script_body_is_a_marked_hole_not_a_guess(widget_scaffold):
    """The one field that is honestly not derivable. A plausible command line here would be
    the exact failure mode this project exists to be an alternative to."""
    from mendel_forge.modulegen import SCRIPT_HOLE

    text = skeleton(widget_scaffold)
    assert SCRIPT_HOLE in text
    assert "MF0005" in SCRIPT_HOLE
    script = text.split("script:")[1].split("stub:")[0]
    assert "--" not in script, "the skeleton must not invent flags for a tool it cannot read"


def test_the_skeleton_declares_the_container_it_was_given(widget_scaffold):
    assert 'container "docker.io/example/widget:1.4.0"' in skeleton(widget_scaffold)


def test_the_skeleton_parses_back_through_ModuleSpec(tmp_path, widget_scaffold):
    """The generated module must be readable by the parser conformance uses, or rung 4
    cannot run against it at all. If this raises, the skeleton is wrong, not the parser:
    ModuleSpec reads four shapes and raises rather than guessing on a fifth."""
    from mendel_compiler.modulespec import ModuleSpec

    path = tmp_path / "main.nf"
    path.write_text(skeleton(widget_scaffold))
    spec = ModuleSpec.parse(path)
    assert spec.process == "WIDGET"
    assert spec.container == "docker.io/example/widget:1.4.0"
    assert "out" in spec.emits
    assert spec.reads_ext_args is True
```

Add a `widget_scaffold` fixture to `packages/mendel-forge/tests/conftest.py` — Task 10's
`_complete()` with `nf_process` set to `WIDGET` and `container` to
`docker.io/example/widget:1.4.0`. **It is a separate fixture from `complete_scaffold`**, which
stays FASTQC-shaped because Tasks 13 and 17 check it against the real vendored module.

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_modulegen.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Declare `MF0005`**

```yaml
MF0005:
  emitted_by: forge
  concern: scaffolding
  says: "the generated module's script body has not been written"
  fires_on: [forge verify]
  refuses: true
  fix: |
    Open the generated `main.nf` and replace the marked line with the tool's command,
    reading its arguments from `task.ext.args` as every nf-core module does. Then
    `forge verify` again.
  explanation: |
    A source that ships no Nextflow module gives the forge a container and a name. The
    process declaration, the stub block and the versions block follow from those; the
    command line does not. Writing a plausible one would produce a module that launches
    and does the wrong thing — a green run with wrong results, which is the failure this
    project is built to avoid. So it is a hole, and the marker refuses until it is filled.
```

- [ ] **Step 4: Implement**

```python
"""A Nextflow module for a source that does not ship one.

Everything here follows from the container and the process name. **The script body does
not, and it is a hole** — `MF0005`. A plausible command line would produce a module that
launches and does the wrong thing, and `-stub-run` cannot see a hollow input, so nothing
downstream would catch it either.

Deliberately a template string rather than Jinja: `mendel-compiler` owns the Jinja
templates for pipelines, and one module skeleton is not worth a second template loader
in a second package. If this grows a third shape, move it to Jinja and match
`emit.py`'s conventions — `{% endfor %}`, never `{%- endfor %}`.
"""

from mendel_forge.observe import Observation
from mendel_forge.scaffold import Scaffold

SCRIPT_HOLE = "// MF0005: write the tool's command here, reading flags from task.ext.args"


def needs_module(obs: Observation) -> bool:
    return obs.fact("nf_include") is None


def skeleton(scaffold: Scaffold) -> str:
    process = scaffold.filled["nf_process"].value
    container = scaffold.filled["container"].value
    tool = process.lower()
    return f"""process {process} {{
    tag "$meta.id"
    label 'process_medium'

    container "{container}"

    input:
    tuple val(meta), path(input)

    output:
    tuple val(meta), path("*.out"), emit: out
    path "versions.yml",           emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${{meta.id}}"
    \"\"\"
    {SCRIPT_HOLE}

    cat <<-END_VERSIONS > versions.yml
    "${{task.process}}":
        {tool}: \\$(echo "unknown")
    END_VERSIONS
    \"\"\"

    stub:
    def prefix = task.ext.prefix ?: "${{meta.id}}"
    \"\"\"
    touch ${{prefix}}.out

    cat <<-END_VERSIONS > versions.yml
    "${{task.process}}":
        {tool}: \\$(echo "unknown")
    END_VERSIONS
    \"\"\"
}}
"""
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/mendel-forge/tests/test_modulegen.py -v`
Expected: 6 passed. `test_the_skeleton_parses_back_through_ModuleSpec` is the one that matters —
if `ModuleSpec.parse` raises, the generated module is not in the four shapes its regexes read,
and **the skeleton is wrong, not the parser**.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-forge packages/comeni-core/src/comeni_core/diagnostics.yml docs/reference/diagnostics.md
git commit -m "feat(forge): a skeleton main.nf, with the script body as MF0005

Everything follows from the container and the process name except the command line.
Guessing it would give a module that launches and does the wrong thing — and -stub-run
cannot see a hollow input, so nothing downstream would catch it either."
```

> ## ✅ Checkpoint C
>
> Run `uv run pytest packages/mendel-forge -v` and `make check`. Report: whether the generated
> skeleton parses back through `ModuleSpec`, and whether the target-path convention in Task 9
> matched the real registry layout or had to be corrected.

---

# Checkpoint D — verification, and codes the guard can see

### Task 12: Make `MF` codes visible to the ownership guard

**Spec:** §8, Global Constraints. **Do this before writing another code.** Five `MF` codes have
been declared and emitted, and the guard that is supposed to hold both directions has been
green throughout without looking at any of them.

**Files:**
- Modify: `tests/test_diagnostics_ownership.py:37`
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli/__init__.py:35`
- Test: `tests/test_diagnostics_ownership.py`

**Interfaces:**
- Produces: nothing importable. This task changes two regexes and adds one test.

- [ ] **Step 1: Watch the guard fail to notice a deliberately broken code**

In `packages/mendel-forge/src/mendel_forge/sources/__init__.py`, temporarily change
`coded("MF0001", ...)` to `coded("MF9999", ...)`. Then:

```bash
uv run pytest tests/test_diagnostics_ownership.py -v
```

Expected: **PASS.** That is the bug. `MF9999` is not declared anywhere, and
`test_every_emitted_code_is_declared` cannot see it. Revert the change before continuing.

- [ ] **Step 2: Write the failing test**

Add to `tests/test_diagnostics_ownership.py`:

```python
def test_the_scan_sees_every_declared_prefix():
    """A prefix the pattern does not match is a whole subsystem the guard is blind to.

    `MF` codes were declared and emitted for five tasks while both ownership directions
    stayed green, because `EMISSION` matched `MD` alone. The prefixes are a closed set —
    `EmittedBy` names the subsystems and the header of `diagnostics.yml` names the
    letters — so the pattern is checked against the registry rather than maintained by
    hand.
    """
    declared = {code[:2] for code in REGISTRY}
    seen = {code[:2] for code in _emitted()}
    missing = sorted(declared - seen)
    assert missing == [], (
        f"codes with these prefixes are declared but the emission scan matches none of "
        f"them; widen EMISSION: {missing}"
    )
```

- [ ] **Step 3: Run it and watch it fail**

Run: `uv run pytest tests/test_diagnostics_ownership.py::test_the_scan_sees_every_declared_prefix -v`
Expected: FAIL — `['MF']`

- [ ] **Step 4: Widen the pattern**

In `tests/test_diagnostics_ownership.py`:

```python
EMISSION = re.compile(r"""(?:coded\(\s*|code=)["']([A-Z]{2}\d{4})["']""")
"""The two shapes an emission can take, and there are only two.

`coded("MD0001", …)` builds a message; `Diagnostic(code="MD0100", …)` builds an object that
carries the code as a field and validates it there. `\\s*` because wrapping a long call puts
the code on its own line.

**`[A-Z]{2}`, not `MD`.** This read `MD\\d{4}` until the forge landed, so five `MF` codes were
declared and emitted while both ownership directions reported green. A guard scoped to one
prefix is a guard that goes blind the day a second subsystem appears —
`test_the_scan_sees_every_declared_prefix` is what makes that failure loud instead.
"""
```

- [ ] **Step 5: Widen the CLI's `mendel explain` pointer too, in its own package**

`mendel_compiler/cli/__init__.py` has `_CODE = re.compile(r"\bMD0\d{3}\b")`. Leave it —
`mendel` emits no `MF` codes. Instead, note it in Task 18: the forge CLI gets its own
`_CODE = re.compile(r"\bMF\d{4}\b")` for `forge explain`.

Add a comment where `_CODE` is defined recording why it stays narrow:

```python
_CODE = re.compile(r"\bMD0\d{3}\b")
"""Deliberately `MD` only: `mendel` raises no forge code, and matching one here would
point a reader at `mendel explain` for a refusal `forge` produced. The forge CLI has its
own, over `MF`."""
```

- [ ] **Step 6: Run the whole ownership suite, and re-run Step 1's experiment**

```bash
uv run pytest tests/test_diagnostics_ownership.py -v
```
Expected: all pass, including the new test.

Now redo Step 1: change `MF0001` to `MF9999` and run again.
Expected: **FAIL**, `emitted in source but absent from diagnostics.yml: ['MF9999']`. Revert.

- [ ] **Step 7: Commit**

```bash
git add tests/test_diagnostics_ownership.py packages/mendel-compiler/src/mendel_compiler/cli/__init__.py
git commit -m "fix: the diagnostics ownership guard was blind to every non-MD prefix

EMISSION matched MD\\d{4}, so the five MF codes added in the tasks before this were
declared and emitted with both ownership directions reporting green. Watched failing:
MF0001 renamed to MF9999 passed before and fails after.

The new test checks the pattern against the registry's own prefixes rather than
against a hand-maintained list, so the next subsystem does not repeat this."
```

---

### Task 13: The five-rung ladder

**Spec:** §5. Four of the five rungs are machinery that already exists.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/verify.py`
- Test: `packages/mendel-forge/tests/test_verify.py`

**Interfaces:**
- Consumes: `Diagnostic` from `mendel_compiler.conformance`; `conformance.check`;
  `layers.load`; `Registry`; `assemble.contract_from`; `Scaffold`.
- Produces: `Rung` (StrEnum: `COMPLETE`, `CONSTRUCTS`, `LOADS`, `CONFORMS`, `ROUTES`),
  `Verdict(rung: Rung, diagnostics: list[Diagnostic], refused: bool)`,
  `verify(scaffold, *, registry_root: Path, source_root: Path) -> list[Verdict]`,
  `refuses(verdicts) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from mendel_forge.verify import Rung, refuses, verify

ROOT = Path(__file__).resolve().parents[3]


def test_an_incomplete_scaffold_stops_at_the_first_rung(incomplete_scaffold):
    verdicts = verify(incomplete_scaffold, registry_root=ROOT / "registry",
                      source_root=ROOT / "vendor")
    assert verdicts[0].rung is Rung.COMPLETE
    assert verdicts[0].refused is True
    assert len(verdicts) == 1, "the ladder is cheapest-first; a failed rung stops it"
    assert verdicts[0].diagnostics[0].code == "MF0004"


def test_a_complete_scaffold_reaches_the_conformance_rung(complete_scaffold):
    verdicts = verify(complete_scaffold, registry_root=ROOT / "registry",
                      source_root=ROOT / "vendor")
    assert Rung.CONFORMS in [v.rung for v in verdicts]


def test_a_wrong_process_name_is_caught_by_the_existing_conformance_code(complete_scaffold):
    """MD0101, reused rather than twinned. A draft failing this fails it for exactly the
    reason a built pipeline would, and a runbook citing MD0101 covers both."""
    broken = complete_scaffold.model_copy(
        update={"filled": {**complete_scaffold.filled,
                           "nf_process": complete_scaffold.filled["nf_process"].model_copy(
                               update={"value": "FASTQCC"})}}
    )
    verdicts = verify(broken, registry_root=ROOT / "registry", source_root=ROOT / "vendor")
    codes = [d.code for v in verdicts for d in v.diagnostics]
    assert "MD0101" in codes


def test_every_diagnostic_carries_a_fix(complete_scaffold):
    verdicts = verify(complete_scaffold, registry_root=ROOT / "registry",
                      source_root=ROOT / "vendor")
    for verdict in verdicts:
        for diagnostic in verdict.diagnostics:
            assert diagnostic.fix, f"{diagnostic.code} has no fix; that is half a diagnostic"


def test_a_contract_nothing_can_route_to_is_reported_but_does_not_refuse(orphan_scaffold):
    """The inert case. Worth telling a reviewer before they land it, and not worth
    blocking on — a lab may legitimately add a tool nothing reaches yet."""
    verdicts = verify(orphan_scaffold, registry_root=ROOT / "registry",
                      source_root=ROOT / "vendor")
    routes = next(v for v in verdicts if v.rung is Rung.ROUTES)
    assert routes.diagnostics
    assert routes.refused is False
    assert refuses(verdicts) is False


def test_verdicts_are_ordered_cheapest_first(complete_scaffold):
    verdicts = verify(complete_scaffold, registry_root=ROOT / "registry",
                      source_root=ROOT / "vendor")
    order = [v.rung for v in verdicts]
    assert order == sorted(order, key=list(Rung).index)
```

Add `incomplete_scaffold` and `orphan_scaffold` to `conftest.py` beside `complete_scaffold`:
the first is `complete_scaffold` with one `Hole` put back, the second is `complete_scaffold`
with `produces[0].type_id` filled to a declared type no other contract consumes.

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_verify.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Declare `MF0006`**

```yaml
MF0006:
  emitted_by: forge
  concern: verification
  says: "nothing in the layer can route to this contract — **warns, never blocks**"
  fires_on: [forge verify]
  refuses: false
  fix: |
    Check the output `type_id` and `state` against what other contracts consume. If
    nothing consumes them, the contract is a leaf — legitimate for a terminal reporting
    step, and worth a second look for anything else.
  explanation: |
    A contract nothing reaches changes no pipeline. It is the inert case the rule
    drafter's impact analysis is about, one level down: a mechanism that runs and
    changes nothing. It warns rather than refuses because a laboratory adding a tool
    before the goal that needs it is doing something reasonable, and because a leaf step
    that only produces reports is genuinely unreachable-from-below.
```

- [ ] **Step 4: Implement**

```python
"""Does this draft hold up? Five questions, cheapest first.

**Four of the five rungs are machinery that already exists**, pointed at a draft instead of
at a build. That is the argument for this shape over a bespoke validator: a second
implementation of *"is this contract sound"* would disagree with the first one inside a plan.

Two weaknesses, recorded rather than left to be found:

- **Rung 4 is a transcription check for a generated module, not an independent one.** The
  contract and the module descend from one `Observation`, so agreement proves the two code
  paths match, not that either is right. It is still worth running — it catches real bugs —
  and it is not the guarantee it is for a vendored nf-core module, where the module is
  foreign ground truth.
- **Rung 5 warns rather than refuses**, because a tool added before the goal that needs it
  is a reasonable thing to do.
"""

from enum import StrEnum
from pathlib import Path

from comeni_core.declared.registry import Registry
from mendel_compiler import conformance
from mendel_compiler.conformance import Diagnostic
from mendel_resolver import layers
from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError

from mendel_forge import assemble
from mendel_forge.scaffold import Scaffold


class Rung(StrEnum):
    COMPLETE = "complete"
    CONSTRUCTS = "constructs"
    LOADS = "loads"
    CONFORMS = "conforms"
    ROUTES = "routes"


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rung: Rung
    diagnostics: list[Diagnostic] = []
    refused: bool = False


def refuses(verdicts: list[Verdict]) -> bool:
    return any(v.refused for v in verdicts)


def verify(scaffold: Scaffold, *, registry_root: Path, source_root: Path) -> list[Verdict]:
    verdicts: list[Verdict] = []

    complete = _complete(scaffold)
    verdicts.append(complete)
    if complete.refused:
        return verdicts

    stack = layers.load(registry_root)
    constructs = _constructs(scaffold)
    verdicts.append(constructs)
    if constructs.refused:
        return verdicts

    contract = assemble.contract_from(scaffold, approved_by="(unapproved)", approved_at="")
    verdicts.append(_loads(contract, stack))
    verdicts.append(_conforms(contract, source_root))
    verdicts.append(_routes(contract, stack))
    return verdicts
```

Write `_complete`, `_constructs`, `_loads`, `_conforms` and `_routes` as follows:

- `_complete` — `Verdict(rung=Rung.COMPLETE)` if `scaffold.is_complete()`, else catch the
  `ValueError` from `assemble._require_complete` and turn it into a `Diagnostic(code="MF0004",
  where=scaffold.target, summary=…, detail=…, fix=…)` with `refused=True`.
- `_constructs` — call `assemble.contract_from`, catch `ValidationError`, and emit
  `Diagnostic(code="MF0007", …)` naming each `loc` and `msg` Pydantic reported. Declare
  `MF0007` in `diagnostics.yml` alongside `MF0006` in Step 3.
- `_loads` — call `contract.check_against(stack.vocabulary)`,
  catching `UnknownTypeError` / `UnknownStateError` / `UnknownRoleError` and re-raising them as
  `Diagnostic`s carrying **the code the loader already uses**, not a new one.
- `_conforms` — `conformance.check` takes a `Registry`, so build one holding this contract
  alone. **Check how `Registry` is constructed before writing this**: it exposes `load()` and
  `of(stacked, layers)` rather than a plain constructor, and `of` wants a `Stacked`. If neither
  fits a single in-memory contract, call the private `_against(contract, ModuleSpec.parse(path),
  path)` — and if you do, **make it public in `conformance.py` in the same commit**, with a
  docstring saying the forge checks one draft where a build checks a whole registry. Do not
  reach into another package's underscore.
  `refused=True` if any diagnostic has `diagnostics.spec_for(d.code).refuses`.
- `_routes` — for each `produces[].type_id`, ask `stack.registry.producers_of` and the inverse:
  if no other contract's `consumes` matches the type, emit `MF0006` with `refused=False`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/mendel-forge/tests/test_verify.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-forge packages/comeni-core/src/comeni_core/diagnostics.yml docs/reference/diagnostics.md
git commit -m "feat(forge): the five-rung verification ladder

Reuses MD0001-MD0009 and MD0100-MD0108 rather than minting MF twins: a draft failing
the load rung fails it for exactly the reason a build would, and one code means one
runbook entry. Both weaknesses are in the module docstring rather than discovered —
rung 4 over a generated module is a transcription check, and rung 5 warns."
```

> ## ✅ Checkpoint D
>
> Run `make check`. Report: the Step 1 experiment in Task 12 — did `MF9999` pass before the fix
> and fail after? That contrast is the whole value of the task and belongs in the report.
---

# Checkpoint E — a workspace, the verbs, and the boundary

### Task 14: The workspace — drafts on disk

**Spec:** §7. The queue, and what the Plan 3 GUI reads.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/workspace.py`
- Test: `packages/mendel-forge/tests/test_workspace.py`

**Interfaces:**
- Consumes: `Scaffold`.
- Produces: `Draft(name: str, scaffold: Scaffold, module: str | None)`,
  `Workspace(root: Path)` with `save(draft) -> Path`, `load(name) -> Draft`,
  `names() -> list[str]`, `delete(name) -> None`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from mendel_forge.workspace import Draft, Workspace


def test_a_draft_round_trips_byte_identically(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    path = workspace.save(Draft(name="fastqc", scaffold=complete_scaffold, module=None))
    first = path.read_text()
    workspace.save(workspace.load("fastqc"))
    assert path.read_text() == first, "save(load(x)) must not move a byte"


def test_names_are_sorted(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    for name in ("zebra", "alpha"):
        workspace.save(Draft(name=name, scaffold=complete_scaffold, module=None))
    assert workspace.names() == ["alpha", "zebra"]


def test_loading_an_absent_draft_names_the_ones_that_exist(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    workspace.save(Draft(name="fastqc", scaffold=complete_scaffold, module=None))
    with pytest.raises(ValueError, match="MF0008") as caught:
        workspace.load("multiqc")
    assert "fastqc" in str(caught.value)


def test_a_draft_carrying_a_generated_module_keeps_it(tmp_path, complete_scaffold):
    workspace = Workspace(root=tmp_path)
    workspace.save(Draft(name="widget", scaffold=complete_scaffold, module="process WIDGET {}\n"))
    assert workspace.load("widget").module == "process WIDGET {}\n"


def test_a_draft_name_cannot_escape_the_workspace(tmp_path, complete_scaffold):
    """A name reaching the filesystem is a name that can contain `../`."""
    workspace = Workspace(root=tmp_path)
    with pytest.raises(ValueError, match="MF0008"):
        workspace.save(Draft(name="../escape", scaffold=complete_scaffold, module=None))
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_workspace.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Declare `MF0008`**

```yaml
MF0008:
  emitted_by: forge
  concern: workspace
  says: "no such draft, or a draft name that is not a plain name"
  fires_on: [forge show, forge fill, forge verify, forge land]
  refuses: true
  fix: |
    Run `forge list` for the drafts that exist. A name is a plain identifier — letters,
    digits, hyphens and underscores — because it becomes a directory.
  explanation: |
    A draft name reaches the filesystem, so a name containing a path separator would let
    a draft be written outside the workspace. Restricting the name is prevention by
    construction; validating the resolved path afterwards is detection, and the two are
    not the same guarantee.
```

- [ ] **Step 4: Implement**

```python
"""Drafts on disk — the queue, and the boundary's near side.

**The workspace lives outside the registry.** A `proposals/` directory inside a layer
would put non-declared files where the loader globs and the digest allowlist walks, and
would make every draft a commit in the registry's history. Here, a draft is a directory
of ordinary JSON that the CLI reads, the HTTP layer serves and the Plan 3 GUI renders,
and `land.py` is the only thing that turns one into registry data.

JSON rather than YAML: this is machine state, not something a human hand-edits, and
`model_dump_json` round-trips a pydantic model exactly where a YAML dump has to be told
how to spell a frozenset.
"""

import json
import re
from pathlib import Path

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.scaffold import Scaffold

_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    scaffold: Scaffold
    module: str | None = None
    """The generated `main.nf`, for a source that ships none. `None` when the source did."""


class Workspace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: Path

    def _dir(self, name: str) -> Path:
        if not _NAME.match(name):
            raise ValueError(
                coded("MF0008", f"{name!r} is not a plain draft name")
                + "\n  letters, digits, hyphens and underscores only — it becomes a directory"
            )
        return self.root / name

    def save(self, draft: Draft) -> Path:
        directory = self._dir(draft.name)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "draft.json"
        path.write_text(draft.model_dump_json(indent=2) + "\n")
        return path

    def load(self, name: str) -> Draft:
        path = self._dir(name) / "draft.json"
        if not path.exists():
            raise ValueError(
                coded("MF0008", f"no draft named {name!r}")
                + f"\n  drafts: {', '.join(self.names()) or '(none)'}"
            )
        return Draft.model_validate(json.loads(path.read_text()))

    def names(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if (p / "draft.json").exists())

    def delete(self, name: str) -> None:
        path = self._dir(name) / "draft.json"
        path.unlink(missing_ok=True)
        path.parent.rmdir()
```

- [ ] **Step 5: Run the tests and commit**

```bash
uv run pytest packages/mendel-forge/tests/test_workspace.py -v
git add packages/mendel-forge packages/comeni-core/src/comeni_core/diagnostics.yml docs/reference/diagnostics.md
git commit -m "feat(forge): the workspace — drafts outside the registry, not inside it

A proposals/ directory in a layer would put non-declared files where the loader globs
and the digest allowlist walks, and make every draft a commit in the registry's
history. MF0008 restricts a draft name by construction rather than validating the
resolved path afterwards; those are different guarantees."
```

---

### Task 15: The operations layer, and the Phase 2 port

**Spec:** §6, §10.1. **The only layer with logic.** Both transports are adapters over this.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/ops.py`, `ports.py`
- Test: `packages/mendel-forge/tests/test_ops.py`

**Interfaces:**
- Produces, one request/result pair per verb, all `BaseModel` with `extra="forbid"`:
  `sources_() -> SourcesResult`, `discover(DiscoverRequest) -> DiscoverResult`,
  `draft(DraftRequest) -> DraftResult`, `show(ShowRequest) -> ShowResult`,
  `fill(FillRequest) -> FillResult`, `verify_(VerifyRequest) -> VerifyResult`.
  Also `HoleFiller` protocol and `NoFiller` in `ports.py`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from mendel_forge import ops

ROOT = Path(__file__).resolve().parents[3]


def _ctx(tmp_path):
    return {"registry_root": ROOT / "registry", "source_root": ROOT / "vendor",
            "workspace_root": tmp_path}


def test_sources_lists_the_registered_ones():
    assert "nf-core" in ops.sources_().names


def test_draft_ingests_and_saves(tmp_path):
    result = ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    assert result.name == "fastqc"
    assert result.holes, "a fresh nf-core draft has semantic holes"
    assert (tmp_path / "fastqc" / "draft.json").exists()


def test_show_returns_holes_with_their_candidates(tmp_path):
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    shown = ops.show(ops.ShowRequest(name="fastqc", **_ctx(tmp_path)))
    hole = next(h for h in shown.holes if h.field.endswith("type_id"))
    assert hole.candidates


def test_fill_persists(tmp_path):
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    ops.fill(ops.FillRequest(name="fastqc", field="roles", value=["qc_per_sample"],
                             by="rafael", why="it QCs a sample", **_ctx(tmp_path)))
    shown = ops.show(ops.ShowRequest(name="fastqc", **_ctx(tmp_path)))
    assert "roles" not in {h.field for h in shown.holes}
    assert shown.filled["roles"].value == ["qc_per_sample"]


def test_every_result_is_json_serialisable(tmp_path):
    """The whole point of the layer: the CLI's --json and the HTTP body are one payload."""
    result = ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    assert result.model_dump_json()


def test_a_refusal_is_raised_not_returned(tmp_path):
    """Both transports need one place to turn a refusal into an exit code or a 4xx, and a
    result object carrying a maybe-error means both would have to remember to check."""
    with pytest.raises(ValueError, match="MF0001"):
        ops.draft(ops.DraftRequest(ref="nonesuch:x", name="x", **_ctx(tmp_path)))


def test_the_default_filler_declines_every_hole():
    from mendel_forge.ports import NoFiller

    from mendel_forge.observe import Observation
    from mendel_forge.scaffold import Hole

    hole = Hole(field="roles", what="w", why_open="o")
    assert NoFiller().fill(hole, Observation(source="s", ref_id="r")) is None
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-forge/tests/test_ops.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Write `ports.py`**

```python
"""The Phase 2 seam, built now and left empty.

`HoleFiller` is the only place a model may enter the forge. Phase 1 ships `NoFiller`,
which declines everything, and **`--no-ai` is therefore not a flag — it is the only
mode.** That is honest by construction rather than by discipline: there is nothing to
switch off, so there is nothing to leave accidentally on.

**A filler returns the same `FilledValue` a human's `forge fill` produces**, differing
only in `filler` and `by`. `land` copies `by` verbatim into `Provenance.drafted_by`, a
field every contract has carried since the first one — so wiring a model needs no change
to the artifact's provenance design at all.

**`None` must stay legal.** A filler that always answers is a filler that invents, and a
hole a model declines is a hole a human still sees.

Before implementing this in Phase 2, read §10.3 of the spec: a forge model call is a
fifth egress door, and invariant 14 says there are four.
"""

from typing import Protocol

from mendel_forge.observe import Observation
from mendel_forge.scaffold import FilledValue, Hole


class HoleFiller(Protocol):
    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None: ...


class NoFiller:
    """Phase 1's only implementation."""

    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None:
        return None
```

- [ ] **Step 4: Write `ops.py`**

One request model and one result model per verb. **Not every verb needs every path** —
a `Context` mixin holding all three would make `CheckRequest` demand a workspace it never
writes to, so give each request exactly the fields it uses:

| Request | Fields |
|---|---|
| `DiscoverRequest` | `source: str \| None = None`, `source_root` |
| `DraftRequest` | `ref`, `name`, `version: str = "0.0.0"`, `registry_root`, `source_root`, `workspace_root` |
| `ShowRequest`, `VerifyRequest` | `name`, `registry_root`, `source_root`, `workspace_root` |
| `FillRequest` | `name`, `field`, `value: Any`, `by`, `why`, `workspace_root` |
| `CheckRequest` | `registry_root`, `source_root` — **no workspace**, it writes nothing |
| `UpdateRequest` | `contract_id`, `name`, `registry_root`, `source_root`, `workspace_root` |
| `LandRequest` | `name`, `registry`, `branch`, `approved_by`, `approved_at`, `workspace_root` |

`version` defaults because a source may not know one — nf-core carries it in the container
tag and a bare tool directory does not. A default that is obviously wrong (`0.0.0`) is
better than one that looks right.

`_ident(ref: ToolRef) -> str` is a two-line helper in `ops.py`: `f"{ref.source}/{ref.ident}"`,
which is the contract-id namespace the shipped registry already uses (`nf-core/fastqc`).

Each function:

1. builds a `Workspace(root=req.workspace_root)`,
2. does the one thing,
3. returns a result model — **never a tuple, never a dict**.

`draft` is the shape to copy:

```python
def draft(req: DraftRequest) -> DraftResult:
    ref = ToolRef.parse(req.ref)
    observation = sources.get(ref.source).ingest(ref, req.source_root)
    stack = layers.load(req.registry_root)
    scaffold = assemble.scaffold_for(
        observation, stack, ident=_ident(ref), version=req.version
    )
    module = modulegen.skeleton(scaffold) if modulegen.needs_module(observation) else None
    saved = Draft(name=req.name, scaffold=scaffold, module=module)
    Workspace(root=req.workspace_root).save(saved)
    return DraftResult(
        name=req.name, target=scaffold.target, holes=scaffold.holes,
        filled=scaffold.filled, generated_module=module is not None,
    )
```

**Refusals raise.** A result carrying a maybe-error means both transports have to remember
to check it, and one of them will not.

- [ ] **Step 5: Run the tests and commit**

```bash
uv run pytest packages/mendel-forge/tests/test_ops.py -v
git add packages/mendel-forge
git commit -m "feat(forge): the operations layer, and the HoleFiller seam

One function per verb, pydantic in and pydantic out, so the CLI and the HTTP app are
adapters rather than implementations. ports.py ships NoFiller and nothing else:
--no-ai is not a flag in Phase 1, it is the only mode, which is honest by construction.
Its docstring names the fifth-door question Phase 2 must answer first."
```

---

### Task 16: `check` and `update` — the maintain half

**Spec:** §6.1. Offline; upstream is #64.

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/ops.py`
- Test: `packages/mendel-forge/tests/test_ops_maintain.py`

**Interfaces:**
- Produces: `check(CheckRequest) -> CheckResult` with
  `CheckResult.drift: list[Drift]` where `Drift(contract_id, field, registry_says, source_says)`,
  and `update(UpdateRequest) -> DraftResult`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from mendel_forge import ops

ROOT = Path(__file__).resolve().parents[3]


def test_the_shipped_registry_has_no_drift_against_the_vendored_modules():
    """If this fails on a clean checkout, a shipped contract disagrees with its module and
    the finding is real — do not weaken the test."""
    result = ops.check(ops.CheckRequest(registry_root=ROOT / "registry",
                                        source_root=ROOT / "vendor"))
    assert result.drift == [], f"{len(result.drift)} disagreements: {result.drift}"


def _broken_registry(tmp_path) -> Path:
    """A copy of the shipped registry with one contract made to disagree with its module."""
    import shutil

    copy = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", copy, ignore=shutil.ignore_patterns(".git"))
    contract = copy / "tools" / "nf-core" / "fastqc" / "fastqc.contract.yml"
    contract.write_text(contract.read_text().replace("nf_process: FASTQC", "nf_process: WRONG"))
    return copy


def test_drift_is_found_when_a_contract_is_edited(tmp_path):
    result = ops.check(ops.CheckRequest(registry_root=_broken_registry(tmp_path),
                                        source_root=ROOT / "vendor"))
    assert len(result.drift) == 1
    drift = result.drift[0]
    assert drift.field == "nf_process"
    assert drift.registry_says == "WRONG"
    assert drift.source_says == "FASTQC"
    assert drift.contract_id.startswith("nf-core/fastqc")


def test_update_turns_a_drift_into_a_draft(tmp_path):
    registry = _broken_registry(tmp_path)
    result = ops.update(ops.UpdateRequest(
        contract_id="nf-core/fastqc@0.12.1", name="fastqc",
        registry_root=registry, source_root=ROOT / "vendor",
        workspace_root=tmp_path / "workspace",
    ))
    from mendel_forge.workspace import Workspace

    draft = Workspace(root=tmp_path / "workspace").load(result.name)
    assert draft.scaffold.filled["nf_process"].value == "FASTQC"


def test_update_does_not_touch_the_registry(tmp_path):
    """`update` produces a draft. Only `land` writes, and Task 22 is the guard for it."""
    registry = _broken_registry(tmp_path)
    before = (registry / "tools" / "nf-core" / "fastqc" / "fastqc.contract.yml").read_text()
    ops.update(ops.UpdateRequest(
        contract_id="nf-core/fastqc@0.12.1", name="fastqc",
        registry_root=registry, source_root=ROOT / "vendor",
        workspace_root=tmp_path / "workspace",
    ))
    assert (registry / "tools" / "nf-core" / "fastqc" / "fastqc.contract.yml").read_text() == before
```

- [ ] **Step 2: Run it and watch it fail**, then implement `check` as: for every contract in the
stack whose module is present, re-ingest through the source that matches its `provenance.source`,
and compare each **derived** field against what the contract declares. Report a `Drift` per
disagreement. `update` re-drafts that one contract and saves it to the workspace.

- [ ] **Step 3: Commit**

```bash
git add packages/mendel-forge
git commit -m "feat(forge): check and update — does the registry still match the source

Offline by decision (#64 is the upstream half). The first test asserts the shipped
registry is clean against the vendored modules, so a real disagreement shows up as a
finding rather than as a test somebody weakened."
```

---

### Task 17: `land` — the invariant-2 boundary

**Spec:** §7. **The narrowest surface in the package, and the only thing that writes to a
registry.**

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/land.py`
- Modify: `packages/mendel-forge/src/mendel_forge/ops.py`
- Test: `packages/mendel-forge/tests/test_land.py`

**Interfaces:**
- Produces: `land(draft: Draft, *, registry: Path, branch: str, approved_by: str,
  approved_at: str) -> LandResult` with `LandResult(branch, files: list[str], commit: str)`.

- [ ] **Step 1: Write the failing test**

```python
import subprocess

import pytest

from mendel_forge.land import land
from mendel_forge.workspace import Draft


def _repo(tmp_path):
    root = tmp_path / "registry"
    root.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    (root / "registry.yml").write_text("name: test\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
                   cwd=root, check=True, capture_output=True)
    return root


def test_landing_writes_the_contract_on_a_new_branch(tmp_path, complete_scaffold):
    repo = _repo(tmp_path)
    result = land(Draft(name="fastqc", scaffold=complete_scaffold, module=None),
                  registry=repo, branch="forge/fastqc", approved_by="rafael",
                  approved_at="2026-08-20")
    assert result.branch == "forge/fastqc"
    head = subprocess.run(["git", "branch", "--show-current"], cwd=repo,
                          capture_output=True, text=True).stdout.strip()
    assert head == "forge/fastqc"
    assert (repo / complete_scaffold.target).exists()


def test_it_refuses_to_land_on_the_default_branch(tmp_path, complete_scaffold):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError, match="MF0100"):
        land(Draft(name="f", scaffold=complete_scaffold, module=None), registry=repo,
             branch="main", approved_by="r", approved_at="2026-08-20")


def test_it_refuses_a_dirty_tree(tmp_path, complete_scaffold):
    repo = _repo(tmp_path)
    (repo / "stray.txt").write_text("x")
    with pytest.raises(ValueError, match="MF0101"):
        land(Draft(name="f", scaffold=complete_scaffold, module=None), registry=repo,
             branch="forge/f", approved_by="r", approved_at="2026-08-20")


def test_it_refuses_an_incomplete_draft(tmp_path, incomplete_scaffold):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError, match="MF0004"):
        land(Draft(name="f", scaffold=incomplete_scaffold, module=None), registry=repo,
             branch="forge/f", approved_by="r", approved_at="2026-08-20")


def test_it_does_not_open_a_pull_request(tmp_path, complete_scaffold):
    """Invariant 13: a lab landing into a private local overlay gets the identical path.
    Making GitHub the approval mechanism would make self-hosted a degraded tier."""
    repo = _repo(tmp_path)
    result = land(Draft(name="f", scaffold=complete_scaffold, module=None), registry=repo,
                  branch="forge/f", approved_by="r", approved_at="2026-08-20")
    assert not hasattr(result, "pull_request_url")


def test_a_generated_module_lands_beside_the_contract(tmp_path, complete_scaffold):
    repo = _repo(tmp_path)
    result = land(Draft(name="w", scaffold=complete_scaffold, module="process W {}\n"),
                  registry=repo, branch="forge/w", approved_by="r", approved_at="2026-08-20")
    assert any(f.endswith("main.nf") for f in result.files)
```

- [ ] **Step 2: Run it and watch it fail.** Then declare `MF0100` (landing on the default
branch) and `MF0101` (a dirty tree) in the `MF0100`–`MF0199` band, with `emitted_by: forge`.

- [ ] **Step 3: Implement.** `land` must, in order: call `assemble.contract_from` (which raises
`MF0004` while holes remain), refuse the default branch, refuse a dirty tree, create the branch,
write the files, `git add` exactly those paths, and commit. **Nothing else in the package may
write under a registry root** — Task 22 is the guard that holds it.

- [ ] **Step 4: Run the tests and commit**

```bash
uv run pytest packages/mendel-forge/tests/test_land.py -v
git add packages/mendel-forge packages/comeni-core/src/comeni_core/diagnostics.yml docs/reference/diagnostics.md
git commit -m "feat(forge): land — a branch in a registry checkout, and nothing wider

Invariant 2 across a repository boundary. It refuses the default branch and a dirty
tree, and it does not open a pull request: invariant 13 says self-hosted is not a
degraded tier, and making GitHub the approval mechanism would break that."
```

> ## ✅ Checkpoint E
>
> Run `make check`. Report: whether `test_the_shipped_registry_has_no_drift_against_the_vendored_modules`
> passed on a clean checkout. If it did not, **that is a finding about the registry** and it
> needs a decision before Checkpoint F.

---

# Checkpoint F — two transports, one payload

### Task 18: The CLI

**Spec:** §6. argv → request, result → renderer. No logic.

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/cli/__init__.py`, `parse.py`, `render.py`
- Test: `packages/mendel-forge/tests/test_cli.py`

**Interfaces:**
- Produces: `main(argv: list[str] | None = None) -> int`, entry point `forge`.

- [ ] **Step 1: Write the failing test**

```python
import json

from mendel_forge.cli import main


def test_sources_lists_nf_core(capsys):
    assert main(["sources"]) == 0
    assert "nf-core" in capsys.readouterr().out


def test_json_output_is_the_result_model_verbatim(capsys, tmp_path):
    code = main(["draft", "nf-core:fastqc", "--name", "fastqc", "--version", "0.12.1",
                 "--workspace", str(tmp_path), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "fastqc"
    assert isinstance(payload["holes"], list)


def test_a_refusal_exits_nonzero_and_points_at_forge_explain(capsys, tmp_path):
    code = main(["draft", "nonesuch:x", "--name", "x", "--workspace", str(tmp_path)])
    assert code == 1
    err = capsys.readouterr().err
    assert "MF0001" in err
    assert "forge explain MF0001" in err


def test_explain_prints_the_long_form(capsys):
    assert main(["explain", "MF0004"]) == 0
    assert "open holes" in capsys.readouterr().out


def test_show_renders_every_hole_with_its_reason(capsys, tmp_path):
    main(["draft", "nf-core:fastqc", "--name", "f", "--version", "0.12.1",
          "--workspace", str(tmp_path)])
    main(["show", "f", "--workspace", str(tmp_path)])
    out = capsys.readouterr().out
    assert "roles" in out
    assert "a module declares no role" in out, "a hole prints why it is open, not just its name"
```

- [ ] **Step 2: Run it and watch it fail.** Then implement, following
`mendel_compiler/cli/`'s split exactly: `parse.py` holds argparse and nothing else,
`render.py` turns result models into text, `__init__.py` dispatches and catches `ValueError`
to print `forge: <message>` on stderr and return 1.

`_CODE = re.compile(r"\bMF\d{4}\b")` here, and the pointer line is `run: forge explain MF0004` —
`mendel explain` would be the wrong verb for a forge refusal.

- [ ] **Step 3: Run the tests and commit**

```bash
uv run pytest packages/mendel-forge/tests/test_cli.py -v
git add packages/mendel-forge
git commit -m "feat(forge): the CLI — argv in, result models rendered out"
```

---

### Task 19: The HTTP app

**Spec:** §6. **The same request models, the same result models.**

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/http/__init__.py`
- Modify: `packages/mendel-forge/pyproject.toml` (add `fastapi>=0.115` under an optional
  `[project.optional-dependencies] http` group, and to the dev group so tests can import it)
- Test: `packages/mendel-forge/tests/test_http.py`

**Interfaces:**
- Produces: `app` — a mountable `FastAPI` instance. Routes: `GET /sources`,
  `GET /discover`, `POST /drafts`, `GET /drafts`, `GET /drafts/{name}`,
  `POST /drafts/{name}/fill`, `POST /drafts/{name}/verify`, `POST /drafts/{name}/land`.

- [ ] **Step 1: Write the failing test — and make it the equivalence test**

```python
import json

from fastapi.testclient import TestClient

from mendel_forge.cli import main
from mendel_forge.http import app

client = TestClient(app)


def test_sources_over_http_matches_the_cli_json(capsys):
    """The claim the whole two-transport split rests on. If these ever differ, one of them
    has grown logic, and the GUI in Plan 3 will be built against the wrong one."""
    main(["sources", "--json"])
    from_cli = json.loads(capsys.readouterr().out)
    from_http = client.get("/sources").json()
    assert from_cli == from_http


def test_drafting_over_http_matches_the_cli_json(capsys, tmp_path):
    body = {"ref": "nf-core:fastqc", "name": "a", "version": "0.12.1",
            "workspace_root": str(tmp_path / "a")}
    from_http = client.post("/drafts", json=body).json()

    main(["draft", "nf-core:fastqc", "--name", "b", "--version", "0.12.1",
          "--workspace", str(tmp_path / "b"), "--json"])
    from_cli = json.loads(capsys.readouterr().out)

    from_http.pop("name"), from_cli.pop("name")
    assert from_cli == from_http


def test_a_refusal_becomes_a_422_carrying_the_code():
    response = client.post("/drafts", json={"ref": "nonesuch:x", "name": "x",
                                            "workspace_root": "/tmp/x"})
    assert response.status_code == 422
    assert "MF0001" in response.json()["detail"]


def test_the_app_is_mountable():
    """Plan 3's mendel-api mounts this rather than reimplementing it."""
    from fastapi import FastAPI

    parent = FastAPI()
    parent.mount("/forge", app)
    assert TestClient(parent).get("/forge/sources").status_code == 200
```

- [ ] **Step 2: Run it and watch it fail.** Then implement: each route is three lines — build the
request model from the body, call the `ops` function, return the result model. One exception
handler turns `ValueError` into a 422 whose `detail` is the message. **No route may contain an
`if`** — a branch in a transport is logic that the other transport does not have.

- [ ] **Step 3: Run the tests and commit**

```bash
uv run pytest packages/mendel-forge/tests/test_http.py -v
git add packages/mendel-forge
git commit -m "feat(forge): a mountable HTTP app over the same request and result models

The equivalence test is the point: CLI --json and the HTTP body are compared directly,
so a transport that grows logic fails rather than drifts. Plan 3's mendel-api mounts
this app instead of reimplementing it."
```

> ## ✅ Checkpoint F
>
> Run `make check`. Report: the equivalence test's result, and whether any route needed a branch
> — if one did, the logic belongs in `ops.py` and the route is wrong.

---

# Checkpoint G — the guards, the big test, and the documentation

### Task 20: Re-derive the shipped registry

**Spec:** §9.1. **The strongest test available to this subsystem.**

**Files:**
- Test: `packages/mendel-forge/tests/test_rederive_registry.py`

- [ ] **Step 1: Write it**

```python
"""Ingest every vendored nf-core module and compare against the contract we ship.

Real ground truth, and the only test here with any. A disagreement is a finding either
way: the ingester is wrong, or a shipped contract is. Do not weaken an assertion to make
this pass — bring the disagreement to the checkpoint.

The count is derived from the tree rather than written down. Two numbers in CLAUDE.md
were stale for three plans because nothing counted them (A71, A72).
"""

from pathlib import Path

import pytest

from mendel_forge.assemble import scaffold_for
from mendel_forge.sources import ToolRef
from mendel_forge.sources.nfcore import NfCoreSource
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]
STACK = layers.load(ROOT / "registry")
PAIRS = [
    (contract, ToolRef(source="nf-core", ident=contract.id.split("@")[0].removeprefix("nf-core/")))
    for contract in STACK.registry.all()
    if contract.id.startswith("nf-core/")
    and (ROOT / "vendor" / f"{contract.nf_include}.nf").exists()
]


def test_there_are_pairs_to_compare():
    assert len(PAIRS) >= 5, f"only {len(PAIRS)} pairs; this test is not testing"


@pytest.mark.parametrize("contract,ref", PAIRS, ids=lambda x: getattr(x, "id", str(x)))
def test_the_derived_fields_match_what_we_ship(contract, ref):
    obs = NfCoreSource().ingest(ref, ROOT / "vendor")
    scaffold = scaffold_for(obs, STACK, ident=contract.id.split("@")[0],
                            version=contract.id.split("@")[1])
    assert scaffold.filled["nf_process"].value == contract.nf_process
    assert scaffold.filled["nf_include"].value == contract.nf_include
    if contract.container:
        assert scaffold.filled["container"].value == contract.container


@pytest.mark.parametrize("contract,ref", PAIRS, ids=lambda x: getattr(x, "id", str(x)))
def test_every_shipped_output_port_appears_as_a_derived_name(contract, ref):
    obs = NfCoreSource().ingest(ref, ROOT / "vendor")
    scaffold = scaffold_for(obs, STACK, ident=contract.id.split("@")[0],
                            version=contract.id.split("@")[1])
    derived = {v.value for k, v in scaffold.filled.items() if k.endswith("].name")}
    for port in contract.produces:
        assert port.name in derived, f"{contract.id}: {port.name} was not derived"
```

- [ ] **Step 2: Run it and read the failures as findings**

Run: `uv run pytest packages/mendel-forge/tests/test_rederive_registry.py -v`

**Every failure is a decision, not a bug to patch.** For each: is the ingester wrong, or is the
shipped contract wrong? Record both kinds in the checkpoint report. Fix the ingester; **file an
issue for a wrong contract** rather than editing the registry submodule from this branch.

- [ ] **Step 3: Commit**

```bash
git add packages/mendel-forge
git commit -m "test(forge): re-derive every shipped nf-core contract from its module

The count comes from the tree, not from this message (A71, A72)."
```

---

### Task 21: Golden scaffolds and determinism

**Spec:** §9.2.

**Files:**
- Create: `packages/mendel-forge/tests/golden/nf-core-fastqc.scaffold.json`
- Test: `packages/mendel-forge/tests/test_golden.py`

- [ ] **Step 1: Write the test, generate the golden file, read it before committing**

```python
import json
import os
from pathlib import Path

from mendel_forge.assemble import scaffold_for
from mendel_forge.sources import ToolRef
from mendel_forge.sources.nfcore import NfCoreSource
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = Path(__file__).parent / "golden" / "nf-core-fastqc.scaffold.json"


def _scaffold():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), ROOT / "vendor")
    return scaffold_for(obs, layers.load(ROOT / "registry"), ident="nf-core/fastqc",
                        version="0.12.1")


def test_the_scaffold_matches_the_golden_file():
    """A change in what the forge derives shows up as a reviewable diff, the same way a
    change in generated Nextflow does. Regenerate with FORGE_GOLDEN=update, and READ the
    diff before committing it — reading the golden file is what caught the Jinja
    `{%- endfor %}` collision that put every loop iteration on one line."""
    produced = _scaffold().model_dump_json(indent=2) + "\n"
    if os.environ.get("FORGE_GOLDEN") == "update":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(produced)
    assert produced == GOLDEN.read_text()


def test_the_same_source_twice_is_byte_identical():
    """Determinism is a test here too. A dict serialises in insertion order, which is parse
    order, which moves under a refactor that changed nothing anybody asked to change."""
    assert _scaffold().model_dump_json(indent=2) == _scaffold().model_dump_json(indent=2)


def test_hole_order_does_not_depend_on_construction_order():
    """`Scaffold` sorts holes on serialisation. Build one with the holes reversed and the
    output must not move — otherwise the golden file records an accident of parse order."""
    scaffold = _scaffold()
    shuffled = scaffold.model_copy(update={"holes": list(reversed(scaffold.holes))})
    assert shuffled.model_dump_json(indent=2) == scaffold.model_dump_json(indent=2)


def test_the_golden_file_is_not_empty():
    """A golden test comparing two empty strings passes and asserts nothing."""
    assert len(json.loads(GOLDEN.read_text())["holes"]) > 0
```

Generate it with `FORGE_GOLDEN=update uv run pytest packages/mendel-forge/tests/test_golden.py`,
then **read the JSON before committing it.**

- [ ] **Step 2: Commit**

```bash
git add packages/mendel-forge
git commit -m "test(forge): golden scaffolds, and determinism as an assertion"
```

---

### Task 22: The write-boundary guard, watched failing

**Spec:** §9.4, and A14's standard.

**Files:**
- Create: `tests/test_forge_write_boundary.py`
- Modify: `notes/audits/guard-ledger.md`

- [ ] **Step 1: Write the guard**

```python
"""Nothing in mendel-forge writes to a registry except `land`.

Invariant 2 says a person approves; nothing writes to the registry automatically. That is
a claim about the whole package, and a claim about a whole package needs a scan rather
than a review.

**A static scan, deliberately.** A runtime check would only cover the paths a test
happens to execute, which is the exact weakness `test_purity_runtime.py` documents about
itself. This is the cheap half of the same union.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORGE = ROOT / "packages" / "mendel-forge" / "src" / "mendel_forge"

WRITES = {"write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir", "rename", "replace"}
ALLOWED = {"land.py", "workspace.py"}
"""`land.py` is the boundary. `workspace.py` writes drafts, which are never inside a
registry — `test_the_workspace_is_never_a_registry_path` is what holds that separately."""


def test_the_scan_reached_the_sources():
    assert len(list(FORGE.rglob("*.py"))) > 5, "the scan is not scanning"


def test_only_land_and_the_workspace_write_to_disk():
    offenders = []
    for path in sorted(FORGE.rglob("*.py")):
        if path.name in ALLOWED:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in WRITES:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} .{node.attr}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "open" and len(node.args) > 1:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} open(…, mode)")
    assert offenders == [], (
        "only land.py may write to a registry and only workspace.py may write a draft; "
        "these write somewhere:\n    " + "\n    ".join(offenders)
    )
```

- [ ] **Step 2: Watch it fail — this is the whole point of the task**

Add a `Path("x").write_text("y")` line to `mendel_forge/verify.py`, run the guard, and **read
the message it prints**. Then remove the line.

```bash
uv run pytest tests/test_forge_write_boundary.py -v
```

- [ ] **Step 3: Record the revert in the ledger**

Append a row to `notes/audits/guard-ledger.md` in the file's existing format: the guard's path,
what was broken, the date, and **the message it printed, verbatim**. A guard never watched
failing may be inert rather than merely weak, and the ledger is the only record that this one
is not.

- [ ] **Step 4: Commit**

```bash
git add tests/test_forge_write_boundary.py notes/audits/guard-ledger.md
git commit -m "guard: only land.py writes to a registry, watched failing

Ledger row records the revert and the message it printed. A14's standard: a guard
nobody has broken on purpose may be inert rather than merely weak."
```

---

### Task 23: Documentation, and the journal

**Spec:** all of it. **The plan is not finished until a stranger can find this.**

**Files:**
- Modify: `ARCHITECTURE.md`, `CLAUDE.md`, `Makefile`, `notes/README.md`, `docs/README.md`
- Create: `docs/guides/driving-the-forge.md`, `notes/journal/2026-08-<dd>.md`

- [ ] **Step 1: `ARCHITECTURE.md`** — add `mendel-forge` to the package tree with its
subpackages, and a section on the scaffold/hole model and the five-rung ladder, written against
the types that now exist.

- [ ] **Step 2: `CLAUDE.md`** — three edits, and no counts:
  - the architecture block: `mendel-forge` is no longer in the "does not exist" list. **Rewrite
    the "Nothing AI-shaped is built" paragraph** — the forge exists and is deterministic, which
    is a different statement from the one there now.
  - **Commands**: replace the `--- arrives with Plan 2; these do not exist yet ---` block with
    the real verbs.
  - the open-issues table: add #64 and #65.

- [ ] **Step 3: `Makefile`** — a `forge` target that drafts one nf-core module into a scratch
workspace and shows it, so the loop is one command for a newcomer.

- [ ] **Step 4: `docs/guides/driving-the-forge.md`** — the loop end to end, in the register of
`driving-mendel.md`: discover → draft → show → fill → verify → land. Add it to `docs/README.md`'s
table.

- [ ] **Step 5: `notes/README.md`** — change row 14's status from "the spec, not yet a plan" to
name this plan and its outcome.

- [ ] **Step 6: The journal entry** — dated, append-only. What shipped, what the derivability
survey actually found, what the re-derivation test found about the shipped registry, and **what a
fresh reader gets wrong.** Name Phase 2's first task explicitly: the fifth egress door.

- [ ] **Step 7: The full verification, and only then the claim**

```bash
make links
make docs
make verify
```

`make verify` takes about two minutes and needs Docker. **Report its output rather than
summarising it.**

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: the forge in ARCHITECTURE, CLAUDE.md, a guide, and the journal"
```

> ## ✅ Checkpoint G — the last one
>
> Report, with the actual command output:
> 1. `make verify` — green or not.
> 2. What Task 20 found about the shipped registry, and any issue filed.
> 3. The guard-ledger row's verbatim message.
> 4. Anything in this plan that turned out to be wrong. **Expect several** — this plan was
>    written against the code, and Plan 1.7's own README says to expect to correct a plan you
>    are executing. Corrections belong inline in this file, as every other plan here records
>    them.

---

## Self-review notes

Run before starting, and again at Checkpoint D.

- [ ] **Spec coverage.** §3.1 → Tasks 4, 10. §3.2 → Tasks 3, 4, 5. §3.3 → Task 8. §3.4 → Tasks
  6, 7. §4 → Task 11. §5 → Task 13. §6 → Tasks 15, 18, 19. §6.1 → Task 16. §7 → Tasks 14, 17.
  §8 → Task 12. §9.1 → Task 20. §9.2 → Task 21. §9.3 → Task 7. §9.4 → Task 22. §10.1 → Task 15.
  §10.2 → Task 10 (`_drafted_by`). §10.3 → documented in Task 15's `ports.py`, implemented never.
- [ ] **Known soft spots in this plan**, flagged rather than hidden:
  - Task 9's `scaffold_for` derives `consumes[]` names weakly — `ModuleSpec.inputs` gives slot
    names, not port names, and the two are not the same thing. Expect this to need correcting
    against Task 1's table.
  - Task 10's index-counting expression is deliberately marked for simplification; do not ship
    it as written.
  - Task 11's skeleton is one hard-coded shape. The moment a second is needed, move to Jinja.
  - Task 13's `_routes` is the least-specified rung. If it proves noisy, narrowing it is
    legitimate — say so in the checkpoint rather than silently loosening the assertion.
