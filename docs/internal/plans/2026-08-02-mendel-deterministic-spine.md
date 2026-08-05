# Mendel — Deterministic Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax for
> tracking. Do **not** farm the tasks out with subagent-driven-development — subagents are for
> review and design only. This matches the execution decision recorded in `CLAUDE.md`.

**Goal:** Build the deterministic core of Mendel — a typed goal in, runnable Nextflow out — with no AI anywhere in the path.

**Architecture:** Three pure Python packages. `comeni-core` holds the data model (module contracts, type vocabularies, pipeline IR, decision records) and a registry that indexes contracts by what they produce. `mendel-resolver` walks a four-tier ladder to turn a `Goal` into a `PipelineIR`, routing through the registry and inserting missing steps. `mendel-compiler` renders the IR to Nextflow DSL2 and runs validation gates. Ambiguity is reached through a `Protocol` port; this plan ships only the non-AI implementation, which flags rather than guesses.

**Tech Stack:** Python 3.12, Pydantic v2, Jinja2, pytest, ruff, `uv` workspace, Nextflow ≥ 24.10, nf-core modules.

## Global Constraints

- Python 3.12 minimum. Managed with `uv`; the repo is a `uv` workspace.
- `comeni-core`, `mendel-resolver`, `mendel-compiler` MUST NOT import any web framework, any HTTP client, or any LLM library. Enforced by a test (Task 1).
- All data models are Pydantic v2 `BaseModel`. No dataclasses, no dicts-as-models.
- AI is reachable only through `Protocol` ports. This plan implements `FlagOnlyResolver` and nothing else.
- Tier 3 is a declared rule table. A rule miss demotes to tier 4 — it never calls a model.
- Review levels are fixed: tier 1 → `none`, tier 2 → `none`, tier 3 → `advisory`, tier 4 → `required`.
- Every ambiguity emits a `DecisionRecord`, including when resolved by `FlagOnlyResolver`.
- Determinism is a test, not an aspiration: same `Goal` → byte-identical `.nf`.
- Vocabularies are closed. A contract using an undeclared state fails to load.
- Data leaves through four declared doors and no others; only the two fields named in
  `tests/test_egress.py` may carry free text. Plan 1 opens none of the doors — it declares them.
- A `Goal` describes a shape, never data. No filename, sample identifier or path may enter it,
  and `extra="forbid"` is what enforces that rather than good intentions.
- Ruff for lint and format, line length 100. `uv run ruff check` and `uv run pytest` must pass before every commit.

---

## File Structure

```
comeni-labs/
├─ pyproject.toml                          uv workspace root
├─ packages/
│  ├─ comeni-core/
│  │  ├─ pyproject.toml
│  │  ├─ src/comeni_core/
│  │  │  ├─ __init__.py                    public exports
│  │  │  ├─ vocabulary.py                  Vocabulary — closed state lists
│  │  │  ├─ contract.py                    ModuleContract, InputPort, OutputPort, Param
│  │  │  ├─ ir.py                          PipelineIR, IRNode, IREdge, ResolvedValue, Tier
│  │  │  ├─ decision.py                    DecisionRecord, Ambiguity, Resolution
│  │  │  ├─ egress.py                      the four doors and their payload types
│  │  │  └─ registry.py                    Registry — contract lookup by produced type
│  │  └─ tests/
│  ├─ mendel-resolver/
│  │  ├─ pyproject.toml
│  │  ├─ src/mendel_resolver/
│  │  │  ├─ goal.py                        Goal, GoalInput, DataProfile
│  │  │  ├─ rules.py                       Rule, RuleTable — tier 3
│  │  │  ├─ ports.py                       AmbiguityResolver Protocol, FlagOnlyResolver
│  │  │  ├─ router.py                      routing + gap insertion
│  │  │  └─ resolve.py                     the four-tier ladder
│  │  └─ tests/
│  └─ mendel-compiler/
│     ├─ pyproject.toml
│     ├─ src/mendel_compiler/
│     │  ├─ emit.py                        IR → Nextflow DSL2
│     │  ├─ templates/main.nf.j2
│     │  ├─ gates.py                       lint / preview / stub-run
│     │  └─ cli.py                         `mendel build`
│     └─ tests/
├─ examples/                               TEST FIXTURES ONLY — not a registry
│  ├─ vocabularies/                        <type>.yml — closed state lists
│  ├─ rules/rnaseq.yml                     tier-3 rules
│  ├─ contracts/nf-core/                   hand-written module contracts
│  └─ rnaseq-goal.yml                      the example goal
├─ vendor/modules/nf-core/                 vendored nf-core module code
└─ tests/golden/                           goal → expected IR → expected .nf
```

Registry data lives under `examples/` rather than at the repository root because it is a set of
test fixtures, not a registry. The real `contracts/`, `rules/` and `vocabularies/` move to the
`comeni-registry` repository at Plan 1.7 (federation spec §3.4); keeping them under `examples/`
now makes that move a change to configuration rather than a relocation of the repository's
top-level shape. `vendor/` holds the vendored nf-core tree — module code, `modules.json`, `.nf-core.yml` and
`conf/`. It is not registry data and does not move at Plan 1.7. `nf_include` is the path a module
takes *inside the generated pipeline*, which is deliberately not where this repository keeps it.

`Registry.load()` globs `*.yml` recursively under each layer directory, so `examples/contracts/`
must hold contracts and nothing else. The goal file sits one level up, in `examples/`, for
exactly that reason.

---

### Task 1: Workspace scaffold and the purity guard

**Files:**
- Create: `pyproject.toml`, `packages/comeni-core/pyproject.toml`, `packages/comeni-core/src/comeni_core/__init__.py`
- Create: `ruff.toml`, `.gitignore`, `Makefile`
- Test: `tests/test_purity.py`

**Interfaces:**
- Consumes: nothing
- Produces: a working `uv` workspace where `uv run pytest` and `uv run ruff check` succeed

- [ ] **Step 1: Write the failing test**

`tests/test_purity.py` — this guard outlives the whole project; it is what makes "the core is pure" checkable rather than rhetorical.

```python
import ast
import pathlib

PURE_PACKAGES = ["comeni-core", "mendel-resolver", "mendel-compiler"]
BANNED_PREFIXES = (
    "fastapi", "starlette", "django", "flask",
    "httpx", "requests", "aiohttp",
    "litellm", "openai", "anthropic",
    "sqlalchemy", "arq",
)


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_pure_packages_import_nothing_impure():
    root = pathlib.Path(__file__).parent.parent
    violations = []
    for pkg in PURE_PACKAGES:
        for py in (root / "packages" / pkg / "src").rglob("*.py"):
            for imported in _imports(py):
                if imported.split(".")[0] in BANNED_PREFIXES:
                    violations.append(f"{py.relative_to(root)} imports {imported}")
    assert violations == [], "Pure packages must not import I/O or model libraries:\n" + "\n".join(
        violations
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_purity.py -v`
Expected: FAIL — `uv` errors because no workspace exists yet.

- [ ] **Step 3: Create the workspace**

Root `pyproject.toml`:

```toml
[project]
name = "comeni-labs"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["comeni-core"]

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
comeni-core = { workspace = true }

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.6", "pytest-cov>=5.0"]

[tool.pytest.ini_options]
testpaths = ["tests", "packages"]
```

**The `dependencies` line is load-bearing and was missing when this plan was first executed.**
`[tool.uv.sources]` says *where* `comeni-core` comes from if something needs it; it does not make
anything need it. Without the dependency, `uv sync` installs the dev tools and stops, and Task 2
fails on `ModuleNotFoundError: No module named 'comeni_core'` — not the error it expects. Each
later package repeats this: Task 6 adds `mendel-resolver` and Task 11 adds `mendel-compiler` to
both lists.

`packages/comeni-core/pyproject.toml`:

```toml
[project]
name = "comeni-core"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.9", "pyyaml>=6.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/comeni_core"]
```

`ruff.toml`:

```toml
line-length = 100
target-version = "py312"

[lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

`packages/comeni-core/src/comeni_core/__init__.py`:

```python
"""Shared data model for Comeni Labs: contracts, vocabularies, IR, decisions."""

__version__ = "0.1.0"
```

`Makefile`:

```make
.PHONY: test lint fmt
test:
	uv run pytest -v
lint:
	uv run ruff check .
fmt:
	uv run ruff format .
```

`.gitignore`: add `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `work/`, `.nextflow*`, `results/`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv sync && uv run pytest tests/test_purity.py -v && uv run ruff check .`
Expected: PASS (the guard finds no files to violate it yet, which is correct).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml ruff.toml Makefile .gitignore packages/ tests/
git commit -m "chore: uv workspace scaffold with core-purity guard"
```

---

### Task 2: Type vocabularies

**Files:**
- Create: `packages/comeni-core/src/comeni_core/vocabulary.py`
- Create: `examples/vocabularies/alignment.bam.yml`, `examples/vocabularies/fastq.reads.yml`, `examples/vocabularies/counts.matrix.yml`, `examples/vocabularies/genome.index.star.yml`, `examples/vocabularies/annotation.gtf.yml`, `examples/vocabularies/qc.report.yml`
- Test: `packages/comeni-core/tests/test_vocabulary.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Vocabulary.load(dir: Path) -> Vocabulary`; `Vocabulary.states_for(type_id: str) -> frozenset[str]`; `Vocabulary.validate(type_id: str, states: Iterable[str]) -> None` raising `UnknownStateError` / `UnknownTypeError`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.vocabulary import UnknownStateError, UnknownTypeError, Vocabulary


def test_loads_states_for_a_type(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text(
        "states: [coordinate_sorted, name_sorted, deduplicated]\n"
    )
    vocab = Vocabulary.load(tmp_path)
    assert vocab.states_for("alignment.bam") == frozenset(
        {"coordinate_sorted", "name_sorted", "deduplicated"}
    )


def test_validate_accepts_declared_states(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    Vocabulary.load(tmp_path).validate("alignment.bam", ["coordinate_sorted"])


def test_validate_rejects_undeclared_state(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    vocab = Vocabulary.load(tmp_path)
    with pytest.raises(UnknownStateError, match="sorted_by_coord"):
        vocab.validate("alignment.bam", ["sorted_by_coord"])


def test_validate_rejects_unknown_type(tmp_path):
    vocab = Vocabulary.load(tmp_path)
    with pytest.raises(UnknownTypeError, match="alignment.cram"):
        vocab.validate("alignment.cram", [])


def test_empty_state_list_is_always_valid(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    Vocabulary.load(tmp_path).validate("alignment.bam", [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_vocabulary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'comeni_core.vocabulary'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Closed state vocabularies. A type declares exactly the states it may carry."""

from collections.abc import Iterable
from pathlib import Path

import yaml
from pydantic import BaseModel


class UnknownTypeError(KeyError):
    """Raised when a type id has no vocabulary file."""


class UnknownStateError(ValueError):
    """Raised when a state is not declared for its type."""


class Vocabulary(BaseModel):
    types: dict[str, frozenset[str]]

    @classmethod
    def load(cls, directory: Path) -> "Vocabulary":
        types: dict[str, frozenset[str]] = {}
        for path in sorted(directory.glob("*.yml")):
            type_id = path.name.removesuffix(".yml")
            data = yaml.safe_load(path.read_text()) or {}
            types[type_id] = frozenset(data.get("states", []))
        return cls(types=types)

    def states_for(self, type_id: str) -> frozenset[str]:
        if type_id not in self.types:
            raise UnknownTypeError(type_id)
        return self.types[type_id]

    def validate(self, type_id: str, states: Iterable[str]) -> None:
        allowed = self.states_for(type_id)
        for state in states:
            if state not in allowed:
                raise UnknownStateError(
                    f"{state!r} is not a declared state for {type_id!r}; allowed: {sorted(allowed)}"
                )
```

- [ ] **Step 4: Create the spine vocabularies**

```yaml
# examples/vocabularies/fastq.reads.yml
states: [trimmed, deduplicated, subsampled]
```
```yaml
# examples/vocabularies/alignment.bam.yml
states: [coordinate_sorted, name_sorted, deduplicated, filtered, indexed]
```
```yaml
# examples/vocabularies/counts.matrix.yml
states: [gene_level, transcript_level, normalised]
```
```yaml
# examples/vocabularies/genome.index.star.yml
states: []
```
```yaml
# examples/vocabularies/annotation.gtf.yml
states: []
```
```yaml
# examples/vocabularies/qc.report.yml
states: [aggregated]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/comeni-core/tests/test_vocabulary.py -v && uv run ruff check .`
Expected: PASS, 5 tests.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/src/comeni_core/vocabulary.py packages/comeni-core/tests/test_vocabulary.py examples/vocabularies/
git commit -m "feat(core): closed type vocabularies with state validation"
```

---

### Task 3: Module contracts

**Files:**
- Create: `packages/comeni-core/src/comeni_core/contract.py`
- Test: `packages/comeni-core/tests/test_contract.py`

**Interfaces:**
- Consumes: `Vocabulary` from Task 2
- Produces: `ModuleContract`, `InputPort`, `OutputPort`, `Param`, `Provenance`; `ModuleContract.load(path: Path, vocab: Vocabulary) -> ModuleContract`; `ModuleContract.id: str`, `.nf_process: str`, `.nf_include: str`, `.consumes: list[InputPort]`, `.produces: list[OutputPort]`, `.params: list[Param]`, `.priority: int`, `.container: str | None`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.contract import ModuleContract
from comeni_core.vocabulary import UnknownStateError, Vocabulary

CONTRACT_YAML = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes:
  - name: bam
    type_id: alignment.bam
    state_required: []
produces:
  - name: bam
    type_id: alignment.bam
    state: [coordinate_sorted]
params: []
priority: 0
container: quay.io/biocontainers/samtools:1.21--h50ea8bc_0
provenance:
  source: nf-core-meta-yml
  drafted_by: hand
  approved_by: rafael
  approved_at: "2026-08-02"
"""


@pytest.fixture
def vocab(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted, name_sorted]\n")
    return Vocabulary.load(tmp_path)


def test_loads_a_contract(tmp_path, vocab):
    path = tmp_path / "sort.yml"
    path.write_text(CONTRACT_YAML)
    contract = ModuleContract.load(path, vocab)
    assert contract.id == "nf-core/samtools/sort@1.21.0"
    assert contract.nf_process == "SAMTOOLS_SORT"
    assert contract.produces[0].state == frozenset({"coordinate_sorted"})
    assert contract.consumes[0].state_required == frozenset()


def test_rejects_contract_using_undeclared_state(tmp_path, vocab):
    path = tmp_path / "bad.yml"
    path.write_text(CONTRACT_YAML.replace("coordinate_sorted", "sorted_by_coord"))
    with pytest.raises(UnknownStateError, match="sorted_by_coord"):
        ModuleContract.load(path, vocab)


def test_input_port_defaults_preferred_to_empty(tmp_path, vocab):
    path = tmp_path / "sort.yml"
    path.write_text(CONTRACT_YAML)
    contract = ModuleContract.load(path, vocab)
    assert contract.consumes[0].state_preferred == frozenset()


def test_carries_the_container_reference(tmp_path, vocab):
    """The lockfile pins container digests; the contract is where the reference starts."""
    path = tmp_path / "sort.yml"
    path.write_text(CONTRACT_YAML)
    contract = ModuleContract.load(path, vocab)
    assert contract.container == "quay.io/biocontainers/samtools:1.21--h50ea8bc_0"


def test_container_is_optional(tmp_path, vocab):
    path = tmp_path / "no-container.yml"
    path.write_text(
        "\n".join(
            line
            for line in CONTRACT_YAML.splitlines()
            if not line.startswith("container:")
        )
    )
    assert ModuleContract.load(path, vocab).container is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_contract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'comeni_core.contract'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Module contracts: what a module consumes and produces, in typed terms."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from comeni_core.vocabulary import Vocabulary


class InputPort(BaseModel):
    name: str
    type_id: str
    state_required: frozenset[str] = frozenset()
    state_preferred: frozenset[str] = frozenset()
    cardinality: str = "1"


class OutputPort(BaseModel):
    name: str
    type_id: str
    state: frozenset[str] = frozenset()


class Param(BaseModel):
    name: str
    tier_hint: int | None = None
    default: Any = None


class Provenance(BaseModel):
    source: str
    drafted_by: str
    approved_by: str
    approved_at: str


class ModuleContract(BaseModel):
    id: str
    nf_process: str
    nf_include: str
    consumes: list[InputPort] = Field(default_factory=list)
    produces: list[OutputPort] = Field(default_factory=list)
    params: list[Param] = Field(default_factory=list)
    priority: int = 0
    container: str | None = None
    """The container URI as the module declares it, tag and all.

    Optional here because `nf-core` declares containers in `main.nf` rather than
    `meta.yml`, so a hand-written contract may not have one yet. The clinical spec
    (§6.1) resolves this reference to a digest at lock time, and the `sealed`
    profile refuses to build against a reference that will not resolve — but both
    of those live in later plans. What Plan 1 owes them is somewhere to start.
    """
    provenance: Provenance

    @classmethod
    def load(cls, path: Path, vocab: Vocabulary) -> "ModuleContract":
        contract = cls.model_validate(yaml.safe_load(path.read_text()))
        contract.check_against(vocab)
        return contract

    def check_against(self, vocab: Vocabulary) -> None:
        for port in self.consumes:
            vocab.validate(port.type_id, port.state_required)
            vocab.validate(port.type_id, port.state_preferred)
        for port in self.produces:
            vocab.validate(port.type_id, port.state)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/comeni-core/tests/test_contract.py -v && uv run ruff check .`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/comeni-core/src/comeni_core/contract.py packages/comeni-core/tests/test_contract.py
git commit -m "feat(core): module contract model validated against vocabularies"
```

---

### Task 4: The pipeline IR and decision records

**Files:**
- Create: `packages/comeni-core/src/comeni_core/ir.py`, `packages/comeni-core/src/comeni_core/decision.py`
- Test: `packages/comeni-core/tests/test_ir.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Tier` (IntEnum: `STRUCTURAL=1, CONVENTION=2, DATA_PROFILED=3, AMBIGUOUS=4`), `ReviewLevel` (StrEnum: `NONE, ADVISORY, REQUIRED`), `review_level_for(tier) -> ReviewLevel`, `ResolvedValue`, `IRNode`, `IREdge`, `PipelineIR`, `PipelineIR.needs_review() -> list[str]`; `Ambiguity`, `Resolution`, `DecisionRecord`

- [ ] **Step 1: Write the failing test**

```python
from comeni_core.ir import (
    IREdge,
    IRNode,
    PipelineIR,
    ResolvedValue,
    ReviewLevel,
    Tier,
    review_level_for,
)


def test_review_level_mapping_is_fixed():
    assert review_level_for(Tier.STRUCTURAL) is ReviewLevel.NONE
    assert review_level_for(Tier.CONVENTION) is ReviewLevel.NONE
    assert review_level_for(Tier.DATA_PROFILED) is ReviewLevel.ADVISORY
    assert review_level_for(Tier.AMBIGUOUS) is ReviewLevel.REQUIRED


def test_resolved_value_derives_its_review_level():
    value = ResolvedValue(value=2, tier=Tier.DATA_PROFILED, reason="rule strandedness-reverse")
    assert value.review_level is ReviewLevel.ADVISORY


def test_needs_review_lists_only_required_items():
    ir = PipelineIR(
        nodes=[
            IRNode(
                id="featurecounts",
                contract_id="nf-core/subread/featurecounts@2.0.6",
                params={
                    "strandedness": ResolvedValue(value=2, tier=Tier.DATA_PROFILED, reason="rule"),
                    "seq_platform": ResolvedValue(value="illumina", tier=Tier.AMBIGUOUS, reason="no rule"),
                },
            )
        ],
        edges=[],
    )
    assert ir.needs_review() == ["featurecounts.seq_platform"]


def test_ir_is_deterministically_serialisable():
    ir = PipelineIR(nodes=[], edges=[IREdge(
        from_node="star", from_port="bam", to_node="sort", to_port="bam",
        type_id="alignment.bam", states=frozenset({"b", "a"}),
    )])
    once = ir.model_dump_json()
    assert once == PipelineIR.model_validate_json(once).model_dump_json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_ir.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'comeni_core.ir'`

- [ ] **Step 3: Write `ir.py`**

Note the `field_serializer` on `states` — frozensets have no stable order, and byte-identical output is a hard requirement.

```python
"""The pipeline IR: resolver output, compiler input, and what tests assert on."""

from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_serializer


class Tier(IntEnum):
    STRUCTURAL = 1
    CONVENTION = 2
    DATA_PROFILED = 3
    AMBIGUOUS = 4


class ReviewLevel(StrEnum):
    NONE = "none"
    ADVISORY = "advisory"
    REQUIRED = "required"


_REVIEW_BY_TIER = {
    Tier.STRUCTURAL: ReviewLevel.NONE,
    Tier.CONVENTION: ReviewLevel.NONE,
    Tier.DATA_PROFILED: ReviewLevel.ADVISORY,
    Tier.AMBIGUOUS: ReviewLevel.REQUIRED,
}


def review_level_for(tier: Tier) -> ReviewLevel:
    return _REVIEW_BY_TIER[tier]


class ResolvedValue(BaseModel):
    value: Any
    tier: Tier
    reason: str

    @computed_field
    @property
    def review_level(self) -> ReviewLevel:
        return review_level_for(self.tier)


class IRNode(BaseModel):
    id: str
    contract_id: str
    params: dict[str, ResolvedValue] = Field(default_factory=dict)


class IREdge(BaseModel):
    from_node: str
    from_port: str
    to_node: str
    to_port: str
    type_id: str
    states: frozenset[str] = frozenset()

    @field_serializer("states")
    def _sorted_states(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class PipelineIR(BaseModel):
    nodes: list[IRNode] = Field(default_factory=list)
    edges: list[IREdge] = Field(default_factory=list)
    decisions: list[Any] = Field(default_factory=list)

    def needs_review(self) -> list[str]:
        return [
            f"{node.id}.{name}"
            for node in self.nodes
            for name, value in node.params.items()
            if value.review_level is ReviewLevel.REQUIRED
        ]
```

- [ ] **Step 4: Write `decision.py`**

```python
"""Decision records: what was ambiguous, what was chosen, and why."""

from typing import Any

from pydantic import BaseModel, Field

from comeni_core.ir import Tier


class Ambiguity(BaseModel):
    """A question the deterministic ladder could not answer."""

    node_id: str
    subject: str
    candidates: list[Any] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    def key(self) -> str:
        return f"{self.node_id}.{self.subject}"


class Resolution(BaseModel):
    chosen: Any
    reason: str
    confidence: float = 0.0
    resolved_by: str = "flag-only"


class DecisionRecord(BaseModel):
    key: str
    subject: str
    candidates: list[Any] = Field(default_factory=list)
    chosen: Any
    reason: str
    confidence: float = 0.0
    resolved_by: str
    tier: Tier = Tier.AMBIGUOUS
    human_override: Any = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/comeni-core/tests/ -v && uv run ruff check .`
Expected: PASS, 4 new tests, 12 total.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/src/comeni_core/ir.py packages/comeni-core/src/comeni_core/decision.py packages/comeni-core/tests/test_ir.py
git commit -m "feat(core): pipeline IR, tiers, review levels and decision records"
```

---

### Task 5: The layered registry

Implements invariant 11 and §3 of the federation spec. The registry is an ordered stack —
public curated base, then private overlays — where a higher layer **shadows** every contract
sharing a module key with a lower one. `load()` accepts a single `Path` as the one-layer case,
so every other task in this plan calls it unchanged.

Collision is keyed on the **module key** (`id` minus `@version`), not the full ID. That is
what lets a lab pin `nf-core/samtools/sort@1.22.0` over the base's `@1.21.0` without the two
tying and demoting every downstream build to tier 4. Within one layer nothing changes: two
versions of the same module remain separate candidates under `(-priority, id)`.

**Files:**
- Create: `packages/comeni-core/src/comeni_core/registry.py`
- Modify: `packages/comeni-core/src/comeni_core/__init__.py`
- Test: `packages/comeni-core/tests/test_registry.py`

**Interfaces:**
- Consumes: `ModuleContract` (Task 3), `Vocabulary` (Task 2)
- Produces: `Registry.load(layers: Path | Sequence[Path], vocab: Vocabulary) -> Registry`; `Registry.get(contract_id: str) -> ModuleContract`; `Registry.producers_of(type_id: str, states: frozenset[str]) -> list[ModuleContract]` sorted by `(-priority, id)`; `Registry.all() -> list[ModuleContract]`; `Registry.shadowed: list[ShadowRecord]`; `module_key(contract_id: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.registry import Registry, module_key
from comeni_core.vocabulary import Vocabulary

SORT = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""

PREFERRED_SORT = SORT.replace(
    "nf-core/samtools/sort@1.21.0", "nf-core/samtools/fastsort@1.21.0"
).replace("priority: 0", "priority: 10")

# same module key, newer version — the lab pinning a different build
NEWER_SORT = SORT.replace("@1.21.0", "@1.22.0").replace("SAMTOOLS_SORT", "SAMTOOLS_SORT_NEW")


def _layer(root, name, files):
    d = root / name
    d.mkdir()
    for filename, body in files.items():
        (d / filename).write_text(body)
    return d


@pytest.fixture
def vocab(tmp_path):
    vocab_dir = tmp_path / "vocab"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    return Vocabulary.load(vocab_dir)


@pytest.fixture
def base(tmp_path):
    return _layer(tmp_path, "base", {"sort.yml": SORT, "fastsort.yml": PREFERRED_SORT})


@pytest.fixture
def registry(base, vocab):
    return Registry.load(base, vocab)


def test_module_key_strips_the_version():
    assert module_key("nf-core/samtools/sort@1.21.0") == "nf-core/samtools/sort"


def test_get_returns_contract_by_id(registry):
    assert registry.get("nf-core/samtools/sort@1.21.0").nf_process == "SAMTOOLS_SORT"


def test_producers_of_matches_required_states(registry):
    found = registry.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    assert len(found) == 2


def test_producers_of_returns_nothing_for_unproduced_state(registry):
    assert registry.producers_of("alignment.bam", frozenset({"name_sorted"})) == []


def test_producers_are_sorted_by_priority_then_id(registry):
    found = registry.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    assert [c.id for c in found] == [
        "nf-core/samtools/fastsort@1.21.0",
        "nf-core/samtools/sort@1.21.0",
    ]


def test_get_raises_on_unknown_id(registry):
    with pytest.raises(KeyError):
        registry.get("nf-core/nope@1.0.0")


def test_a_single_path_is_the_one_layer_case(base, vocab):
    assert Registry.load(base, vocab).contracts == Registry.load([base], vocab).contracts


def test_overlay_shadows_the_same_module_key_at_any_version(tmp_path, base, vocab):
    overlay = _layer(tmp_path, "lab", {"sort.yml": NEWER_SORT})
    reg = Registry.load([base, overlay], vocab)

    # the base's @1.21.0 is gone, displaced by the overlay's @1.22.0
    assert reg.get("nf-core/samtools/sort@1.22.0").nf_process == "SAMTOOLS_SORT_NEW"
    with pytest.raises(KeyError):
        reg.get("nf-core/samtools/sort@1.21.0")

    # and it did not tie: exactly one sort candidate survives, plus fastsort
    found = reg.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    assert [c.id for c in found] == [
        "nf-core/samtools/fastsort@1.21.0",
        "nf-core/samtools/sort@1.22.0",
    ]


def test_shadowing_is_recorded(tmp_path, base, vocab):
    overlay = _layer(tmp_path, "lab", {"sort.yml": NEWER_SORT})
    reg = Registry.load([base, overlay], vocab)

    assert len(reg.shadowed) == 1
    record = reg.shadowed[0]
    assert record.module_key == "nf-core/samtools/sort"
    assert record.winning_id == "nf-core/samtools/sort@1.22.0"
    assert record.displaced_ids == ["nf-core/samtools/sort@1.21.0"]


def test_shadow_record_names_the_contract_routing_prefers(tmp_path, base, vocab):
    """A layer may hold two versions of one module. The record must not name a loser."""
    overlay = _layer(
        tmp_path,
        "lab",
        {
            "sort.yml": NEWER_SORT,
            "sort-old.yml": SORT.replace("priority: 0", "priority: 5"),
        },
    )
    reg = Registry.load([base, overlay], vocab)

    # @1.21.0 at priority 5 outranks @1.22.0 at priority 0 under (-priority, id) — so it is
    # the winner named, even though it sorts later lexically.
    assert reg.shadowed[0].winning_id == "nf-core/samtools/sort@1.21.0"
    produced = reg.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    sorts = [c.id for c in produced if module_key(c.id) == "nf-core/samtools/sort"]
    assert sorts[0] == "nf-core/samtools/sort@1.21.0"


def test_a_different_module_key_does_not_shadow(tmp_path, base, vocab):
    overlay = _layer(tmp_path, "lab", {"mine.yml": SORT.replace("nf-core/samtools/sort", "lab/mysort")})
    reg = Registry.load([base, overlay], vocab)

    assert reg.shadowed == []
    # it competes normally — and ties with the base at equal priority, which invariant 8
    # leaves for the router to demote to tier 4
    found = reg.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    assert len(found) == 3


def test_unshadowed_stack_is_the_union(tmp_path, base, vocab):
    overlay = _layer(tmp_path, "lab", {"mine.yml": SORT.replace("nf-core/samtools/sort", "lab/mysort")})
    assert len(Registry.load([base, overlay], vocab).contracts) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'comeni_core.registry'`

- [ ] **Step 3: Write minimal implementation**

```python
"""The contract registry: what exists, what produces what, and which layer won."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from comeni_core.contract import ModuleContract
from comeni_core.vocabulary import Vocabulary


def module_key(contract_id: str) -> str:
    """A contract ID minus its version. Shadowing is decided on this, not the full ID."""
    return contract_id.rsplit("@", 1)[0]


class ShadowRecord(BaseModel):
    """A higher layer displaced every lower-layer contract for one module key."""

    module_key: str
    winning_id: str
    winning_layer: str
    displaced_ids: list[str]


class Registry(BaseModel):
    contracts: dict[str, ModuleContract]
    shadowed: list[ShadowRecord] = []

    @classmethod
    def load(cls, layers: Path | Sequence[Path], vocab: Vocabulary) -> "Registry":
        if isinstance(layers, Path):
            layers = [layers]

        contracts: dict[str, ModuleContract] = {}
        shadowed: list[ShadowRecord] = []

        for layer in layers:
            incoming = {}
            for path in sorted(layer.rglob("*.yml")):
                contract = ModuleContract.load(path, vocab)
                incoming[contract.id] = contract

            keys = {module_key(cid) for cid in incoming}
            for key in sorted(keys):
                displaced = sorted(c for c in contracts if module_key(c) == key)
                if not displaced:
                    continue
                # A layer may legitimately hold two versions of one module. Name the one
                # routing would actually prefer, so the record does not contradict the build:
                # the same (-priority, id) order producers_of returns.
                winner = min(
                    (c for cid, c in incoming.items() if module_key(cid) == key),
                    key=lambda c: (-c.priority, c.id),
                ).id
                shadowed.append(
                    ShadowRecord(
                        module_key=key,
                        winning_id=winner,
                        winning_layer=str(layer),
                        displaced_ids=displaced,
                    )
                )
                for cid in displaced:
                    del contracts[cid]

            contracts.update(incoming)

        return cls(contracts=contracts, shadowed=shadowed)

    def get(self, contract_id: str) -> ModuleContract:
        if contract_id not in self.contracts:
            raise KeyError(contract_id)
        return self.contracts[contract_id]

    def all(self) -> list[ModuleContract]:
        return sorted(self.contracts.values(), key=lambda c: c.id)

    def producers_of(self, type_id: str, states: frozenset[str]) -> list[ModuleContract]:
        matches = [
            contract
            for contract in self.contracts.values()
            for port in contract.produces
            if port.type_id == type_id and states <= port.state
        ]
        return sorted(matches, key=lambda c: (-c.priority, c.id))
```

Every collection that reaches `shadowed` is sorted before it is stored. `ShadowRecord` ends up
in `PipelineIR`, so it is subject to the byte-identical rule like everything else.

- [ ] **Step 4: Export the public API**

`packages/comeni-core/src/comeni_core/__init__.py`:

```python
"""Shared data model for Comeni Labs: contracts, vocabularies, IR, decisions."""

from comeni_core.contract import InputPort, ModuleContract, OutputPort, Param, Provenance
from comeni_core.decision import Ambiguity, DecisionRecord, Resolution
from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, ReviewLevel, Tier
from comeni_core.registry import Registry, ShadowRecord, module_key
from comeni_core.vocabulary import UnknownStateError, UnknownTypeError, Vocabulary

__version__ = "0.1.0"

__all__ = [
    "Ambiguity", "DecisionRecord", "IREdge", "IRNode", "InputPort", "ModuleContract",
    "OutputPort", "Param", "PipelineIR", "Provenance", "Registry", "ResolvedValue",
    "Resolution", "ReviewLevel", "ShadowRecord", "Tier", "UnknownStateError",
    "UnknownTypeError", "Vocabulary", "module_key",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/comeni-core/tests/ -v && uv run ruff check .`
Expected: PASS, 12 new tests, 24 total.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/
git commit -m "feat(core): layered registry with module-key shadowing"
```

---

### Task 6: Goal, data profile and tier-3 rule tables

**Files:**
- Create: `packages/mendel-resolver/pyproject.toml`, `packages/mendel-resolver/src/mendel_resolver/__init__.py`, `goal.py`, `rules.py`
- Create: `examples/rules/rnaseq.yml`
- Test: `packages/mendel-resolver/tests/test_rules.py`

**Interfaces:**
- Consumes: `comeni-core`
- Produces: `Goal(have: list[GoalInput], want: list[str], constraints: dict, profile: DataProfile | None)`; `GoalInput(type_id: str, states: frozenset[str])`; `DataProfile(read_length, strandedness, n_samples, paired)`; `Rule(id, when, then, citation)`; `RuleTable.load(path) -> RuleTable`; `RuleTable.match(subject: str, profile: DataProfile) -> Rule | None`

- [ ] **Step 1: Write the failing test**

```python
from mendel_resolver.goal import DataProfile
from mendel_resolver.rules import RuleTable

RULES = """
rules:
  - id: aligner-long-reads
    subject: aligner
    when: {read_length: {">=": 70}}
    then: {module: nf-core/star/align@1.11.0}
    citation: "STAR handles reads >=70bp well (Dobin 2013)"
  - id: aligner-short-reads
    subject: aligner
    when: {read_length: {"<": 70}}
    then: {module: nf-core/hisat2/align@2.2.1}
    citation: "HISAT2 preferred for short reads"
  - id: strand-reverse
    subject: strandedness
    when: {strandedness: {"==": reverse}}
    then: {value: 2}
    citation: "featureCounts -s 2 for reverse-stranded libraries"
"""


def test_matches_rule_on_numeric_comparison(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    table = RuleTable.load(path)
    rule = table.match("aligner", DataProfile(read_length=150))
    assert rule is not None
    assert rule.id == "aligner-long-reads"
    assert rule.then == {"module": "nf-core/star/align@1.11.0"}


def test_matches_the_other_branch(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    rule = RuleTable.load(path).match("aligner", DataProfile(read_length=50))
    assert rule.id == "aligner-short-reads"


def test_matches_string_equality(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    rule = RuleTable.load(path).match("strandedness", DataProfile(strandedness="reverse"))
    assert rule.then == {"value": 2}


def test_returns_none_when_no_rule_matches(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    assert RuleTable.load(path).match("aligner", DataProfile()) is None


def test_returns_none_for_unknown_subject(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    assert RuleTable.load(path).match("umi_handling", DataProfile(read_length=150)) is None


def test_first_matching_rule_wins(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    table = RuleTable.load(path)
    assert table.match("aligner", DataProfile(read_length=70)).id == "aligner-long-reads"
```

Then, in the same file, the two tests that make invariant 15 enforceable rather than
aspirational. A goal describes a shape; there must be nowhere to put a sample identifier.

```python
import pytest
from pydantic import ValidationError

from mendel_resolver.goal import DataProfile, Goal


def test_goal_has_nowhere_to_put_a_sample_identifier():
    """Invariant 15. Not a rule the user must follow — an absence they cannot fill."""
    with pytest.raises(ValidationError):
        Goal(want=["counts.matrix"], samples=["patient_4471023_R1.fastq.gz"])


def test_profile_rejects_unknown_measurements():
    with pytest.raises(ValidationError):
        DataProfile(read_length=150, sample_name="SILVA_biopsy_01")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-resolver/tests/test_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_resolver'`

- [ ] **Step 3: Create the package**

`packages/mendel-resolver/pyproject.toml`:

```toml
[project]
name = "mendel-resolver"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["comeni-core", "pydantic>=2.9", "pyyaml>=6.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mendel_resolver"]
```

`src/mendel_resolver/__init__.py`:

```python
"""Mendel's four-tier resolver: typed goal in, pipeline IR out."""

__version__ = "0.1.0"
```

Then add the package to the root `pyproject.toml`, in both places — `dependencies` so it is
installed at all, `[tool.uv.sources]` so it resolves to the workspace copy rather than PyPI:

```toml
dependencies = ["comeni-core", "mendel-resolver"]

[tool.uv.sources]
comeni-core = { workspace = true }
mendel-resolver = { workspace = true }
```

`src/mendel_resolver/goal.py`:

```python
"""What the user has, what they want, and what the data actually looks like.

Invariant 15: Mendel does not receive patient data. A `Goal` describes a *shape* —
type ids, states, and four measurements. "Paired, 150bp, reverse-stranded, twelve
samples" is true of thousands of studies and identifies nobody. There is no
filename field, no sample identifier field and no path, and `extra="forbid"` on
both models is what stops one being added by accident: an unrecognised key is a
loud error rather than a quietly carried payload.

Sample identity enters at run time, in the laboratory's own environment, through
the `params.input` placeholder the emitted pipeline declares. It never reaches
Mendel's process. See the clinical data-protection spec, §3.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DataProfile(BaseModel):
    """Measured properties of the input data. Pure computation, no inference."""

    model_config = ConfigDict(extra="forbid")

    read_length: int | None = None
    strandedness: str | None = None
    n_samples: int | None = None
    paired: bool | None = None


class GoalInput(BaseModel):
    type_id: str
    states: frozenset[str] = frozenset()


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    have: list[GoalInput] = Field(default_factory=list)
    want: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    profile: DataProfile = Field(default_factory=DataProfile)
```

- [ ] **Step 4: Write `rules.py`**

```python
"""Tier 3: measured data properties matched against a declared rule table.

A miss is not an escalation to a model. It is a demotion to tier 4.
"""

import operator
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from mendel_resolver.goal import DataProfile

_OPS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


class Rule(BaseModel):
    id: str
    subject: str
    when: dict[str, dict[str, Any]]
    then: dict[str, Any]
    citation: str | None = None

    def matches(self, profile: DataProfile) -> bool:
        for field, comparison in self.when.items():
            actual = getattr(profile, field, None)
            if actual is None:
                return False
            for symbol, expected in comparison.items():
                if not _OPS[symbol](actual, expected):
                    return False
        return True


class RuleTable(BaseModel):
    rules: list[Rule] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "RuleTable":
        return cls.model_validate(yaml.safe_load(path.read_text()) or {"rules": []})

    def match(self, subject: str, profile: DataProfile) -> Rule | None:
        for rule in self.rules:
            if rule.subject == subject and rule.matches(profile):
                return rule
        return None
```

- [ ] **Step 5: Create `examples/rules/rnaseq.yml`**

```yaml
rules:
  - id: aligner-long-reads
    subject: aligner
    when: {read_length: {">=": 70}}
    then: {module: nf-core/star/align@1.11.0}
    citation: "STAR is the nf-core/rnaseq default for reads >=70bp (Dobin et al. 2013)"
  - id: aligner-short-reads
    subject: aligner
    when: {read_length: {"<": 70}}
    then: {module: nf-core/hisat2/align@2.2.1}
    citation: "HISAT2 handles short reads with lower memory (Kim et al. 2019)"
  - id: strandedness-reverse
    subject: strandedness
    when: {strandedness: {"==": reverse}}
    then: {value: 2}
    citation: "featureCounts -s 2 for reverse-stranded (dUTP) libraries"
  - id: strandedness-forward
    subject: strandedness
    when: {strandedness: {"==": forward}}
    then: {value: 1}
    citation: "featureCounts -s 1 for forward-stranded libraries"
  - id: strandedness-unstranded
    subject: strandedness
    when: {strandedness: {"==": unstranded}}
    then: {value: 0}
    citation: "featureCounts -s 0 for unstranded libraries"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv sync && uv run pytest packages/mendel-resolver/tests/ -v && uv run ruff check .`
Expected: PASS, 8 tests.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-resolver/ examples/rules/
git commit -m "feat(resolver): goal model, data profile and tier-3 rule tables"
```

---

### Task 7: The ambiguity port

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/ports.py`
- Test: `packages/mendel-resolver/tests/test_ports.py`

**Interfaces:**
- Consumes: `Ambiguity`, `Resolution`, `DecisionRecord` from `comeni-core`
- Produces: `AmbiguityResolver` Protocol with `resolve(self, ambiguity: Ambiguity) -> Resolution`; `FlagOnlyResolver` implementing it; `NoCandidatesError`

This is the seam AI plugs into in Plan 2. Plan 1 ships only the honest non-AI implementation: pick the first candidate deterministically, mark it tier 4, flag it for review.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.decision import Ambiguity
from mendel_resolver.ports import FlagOnlyResolver, NoCandidatesError


def test_picks_first_candidate_deterministically():
    ambiguity = Ambiguity(node_id="star", subject="seq_platform", candidates=["illumina", "nanopore"])
    resolution = FlagOnlyResolver().resolve(ambiguity)
    assert resolution.chosen == "illumina"
    assert resolution.resolved_by == "flag-only"
    assert resolution.confidence == 0.0


def test_reason_names_the_subject_so_the_user_knows_what_to_check():
    ambiguity = Ambiguity(node_id="star", subject="seq_platform", candidates=["illumina"])
    assert "seq_platform" in FlagOnlyResolver().resolve(ambiguity).reason


def test_raises_when_there_is_nothing_to_choose_from():
    with pytest.raises(NoCandidatesError, match="star.seq_platform"):
        FlagOnlyResolver().resolve(Ambiguity(node_id="star", subject="seq_platform", candidates=[]))


def test_is_deterministic_across_calls():
    ambiguity = Ambiguity(node_id="n", subject="s", candidates=["b", "a", "c"])
    resolver = FlagOnlyResolver()
    assert resolver.resolve(ambiguity).chosen == resolver.resolve(ambiguity).chosen == "b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-resolver/tests/test_ports.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_resolver.ports'`

- [ ] **Step 3: Write minimal implementation**

```python
"""The seam where AI plugs in. Plan 1 ships only the non-AI implementation."""

from typing import Protocol

from comeni_core.decision import Ambiguity, Resolution


class NoCandidatesError(ValueError):
    """Raised when an ambiguity has no options to choose between."""


class AmbiguityResolver(Protocol):
    """Resolves what the deterministic ladder could not.

    Implementations MUST be side-effect free with respect to the IR; they return
    a Resolution and the resolver records it.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution: ...


class FlagOnlyResolver:
    """Picks the first candidate and flags it. Never guesses cleverly.

    This keeps the whole pipeline runnable with no model available, and makes
    the flagged count an honest measure of how much the rules do not yet cover.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        if not ambiguity.candidates:
            raise NoCandidatesError(f"no candidates for {ambiguity.key()}")
        return Resolution(
            chosen=ambiguity.candidates[0],
            reason=(
                f"no rule covered {ambiguity.subject!r}; selected the first of "
                f"{len(ambiguity.candidates)} candidates without judgement — please review"
            ),
            confidence=0.0,
            resolved_by="flag-only",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-resolver/tests/test_ports.py -v && uv run ruff check .`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-resolver/src/mendel_resolver/ports.py packages/mendel-resolver/tests/test_ports.py
git commit -m "feat(resolver): ambiguity port with flag-only implementation"
```

---

### Task 7B: Egress payload types and the boundary guard

Implements invariant 14 and §4 of the clinical data-protection spec. Numbered `7B` rather than
renumbering everything after it, because Task 11's known defect and Task 12's gate are referred
to by number in `CLAUDE.md` and in this plan's self-review.

This lands in Plan 1, before any of the code it constrains exists, for the same reason Task 1's
purity guard does: a guard written after the thing it guards is a guard written around the thing
it guards. Nothing in Plan 1 can violate it. Plan 2 is where that stops being true, and by then
the test is already in CI.

**Files:**
- Create: `packages/comeni-core/src/comeni_core/egress.py`
- Test: `tests/test_egress.py`

**Interfaces:**
- Consumes: `PipelineIR`, `DecisionRecord` (Task 4)
- Produces: `FreeText` marker; `Text`, `ContractId`, `TypeId`, `NodeId`, `Subject` annotated
  aliases; `EgressPayload`; `ErrorCategory` StrEnum; `GateFailure`, `PromptRequest`,
  `AmbiguityRequest`, `RepairRequest`, `PublishBundle`; `DOORS: dict[str, type[EgressPayload]]`

- [ ] **Step 1: Write the failing test**

`tests/test_egress.py` — sibling of `test_purity.py`, and the same kind of object: a claim about
the shape of the system that a machine checks.

```python
"""Invariant 14: data leaves through four declared doors and no others.

The doors are listed here, literally, on purpose. Adding one means editing a file
whose contents say "these are all the ways data leaves this building" — which is
the moment a person should be thinking, and this test is what makes them.
"""

import typing

from pydantic import BaseModel

from comeni_core import egress

DOORS = {"goal_extraction", "tier4_resolution", "compiler_repair", "publication"}

# Free text is the taint source. Exactly two fields may carry it, and both are
# named here. A third requires editing this line.
FREE_TEXT_FIELDS = {
    ("PromptRequest", "prompt"),
    ("GateFailure", "tool_message"),
}


def _payload_types() -> set[type[BaseModel]]:
    return {
        obj
        for obj in vars(egress).values()
        if isinstance(obj, type)
        and issubclass(obj, egress.EgressPayload)
        and obj is not egress.EgressPayload
    }


def _mentions(annotation: object, marker: object) -> bool:
    """Walk an annotation tree. `Text | None` hides its metadata one level down."""
    metadata = getattr(annotation, "__metadata__", ())
    if any(meta is marker for meta in metadata):
        return True
    return any(_mentions(arg, marker) for arg in typing.get_args(annotation))


def _fields(model: type[BaseModel], marker: object) -> set[tuple[str, str]]:
    hints = typing.get_type_hints(model, include_extras=True)
    return {
        (model.__name__, name)
        for name, annotation in hints.items()
        if name in model.model_fields and _mentions(annotation, marker)
    }


def test_the_doors_are_exactly_four():
    assert set(egress.DOORS) == DOORS


def test_every_door_declares_an_egress_payload():
    for name, payload in egress.DOORS.items():
        assert issubclass(payload, egress.EgressPayload), name


def test_free_text_lives_only_where_declared():
    found: set[tuple[str, str]] = set()
    for payload in _payload_types():
        found |= _fields(payload, egress.FreeText)
    assert found == FREE_TEXT_FIELDS


def test_payloads_forbid_unknown_fields():
    for payload in _payload_types():
        assert payload.model_config.get("extra") == "forbid", payload.__name__


def test_no_payload_carries_an_untyped_container():
    """A dict[str, Any] would defeat the whole thing, so no payload may declare one."""
    offenders = []
    for payload in _payload_types():
        for name, annotation in typing.get_type_hints(payload, include_extras=True).items():
            if name in payload.model_fields and _mentions(annotation, typing.Any):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_egress.py -v`
Expected: FAIL with `ImportError: cannot import name 'egress' from 'comeni_core'`

- [ ] **Step 3: Write minimal implementation**

`packages/comeni-core/src/comeni_core/egress.py`:

```python
"""The doors data may leave through, and the types that may pass them.

Invariant 14. There are four: goal extraction, tier-4 resolution, compiler repair,
and publication. Each carries one declared payload type.

This module declares those types and can never send one. Invariant 1 keeps every
transport in the impure packages, so pure code decides what may leave and impure
code does the leaving; neither can do the other's job.

Publication is the door with no undo. A leaked prompt in a model call is an
incident; a leaked prompt in a signed public registry is in every clone's history
permanently, and git is built to make that hard to reverse.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict

from comeni_core.decision import DecisionRecord
from comeni_core.ir import PipelineIR


class FreeText:
    """Marker: this field may hold text a human typed or a tool printed.

    Two fields carry it and `tests/test_egress.py` names both. A third means
    editing that test, which is the point — the admission is forced rather than
    made quietly.
    """


Text = Annotated[str, FreeText]
ContractId = Annotated[str, "contract-id"]
TypeId = Annotated[str, "type-id"]
NodeId = Annotated[str, "node-id"]
Subject = Annotated[str, "subject"]


class EgressPayload(BaseModel):
    """Base for anything that may cross a door.

    `extra="forbid"` so a field cannot be smuggled in at runtime; `frozen=True` so
    what was reviewed is what is sent.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class ErrorCategory(StrEnum):
    """Why a gate failed, as closed vocabulary.

    Nextflow's stderr carries work directories and input filenames, and the repair
    loop would forward it to a model. Machine-generated text is the likeliest leak
    precisely because nobody wrote it and nobody reads it. So the category is
    parsed from the output and the output itself stays on the machine that made it.
    """

    MISSING_INPUT = "missing_input"
    CHANNEL_CARDINALITY = "channel_cardinality"
    SYNTAX = "syntax"
    CONTAINER_PULL = "container_pull"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"


class GateFailure(EgressPayload):
    """A gate failure reduced to facts."""

    process: NodeId
    exit_code: int
    category: ErrorCategory
    tool_message: Text | None = None
    """Populated only in the `open` profile. Free text, and declared as such."""


class PromptRequest(EgressPayload):
    """Door 1 — goal extraction. The single taint source."""

    prompt: Text


class AmbiguityRequest(EgressPayload):
    """Door 2 — tier-4 resolution. Registry vocabulary and nothing else.

    Deliberately not a free-form context dict. `dict[str, Any]` would carry
    anything, which is why the guard forbids it — the fields a tier-4 call
    actually needs are these.
    """

    node_id: NodeId
    subject: Subject
    candidates: list[ContractId] = []
    states: list[TypeId] = []
    tier_hint: int | None = None


class RepairRequest(EgressPayload):
    """Door 3 — compiler repair. The IR, plus typed failure facts."""

    ir: PipelineIR
    failure: GateFailure


class PublishBundle(EgressPayload):
    """Door 4 — publication.

    Carries the IR and its decision records. The `Goal` is absent because it lives
    in `mendel-resolver` and `comeni-core` must not depend on it, and the lockfile
    is absent because it does not exist until Plan 1.7. Both are additions to this
    type, made where those questions are settled, not predicted here.
    """

    ir: PipelineIR
    decisions: list[DecisionRecord] = []


DOORS: dict[str, type[EgressPayload]] = {
    "goal_extraction": PromptRequest,
    "tier4_resolution": AmbiguityRequest,
    "compiler_repair": RepairRequest,
    "publication": PublishBundle,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_egress.py -v && uv run ruff check .`
Expected: PASS, 6 tests.

- [ ] **Step 5: Prove the guard actually catches something**

A guard nobody has watched fail is a guard nobody knows works. Temporarily add
`user_note: Text | None = None` to `AmbiguityRequest` and confirm
`test_free_text_lives_only_where_declared` fails naming `('AmbiguityRequest', 'user_note')`.
Then change it to `user_note: str | None = None` and confirm
`test_no_payload_carries_an_undeclared_string` fails naming `AmbiguityRequest.user_note`.
Remove it before committing.

**Run this step. It found a real hole when the plan was executed on 2026-08-03.** The first
five tests all passed with a bare `user_note: str` in place: no `FreeText` marker to catch, no
`Any` to forbid, and a prompt fits in it perfectly. The spec claimed every string field was
either a declared ID alias or marked free text, and nothing enforced the claim. Hence
`test_no_payload_carries_an_undeclared_string` and `_has_bare_str`, which treats `Annotated[...]`
as the declaration — so `NodeId`, `Text` and a `StrEnum` all pass, and a plain `str`, the one
with nothing said about it, does not.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/src/comeni_core/egress.py tests/test_egress.py
git commit -m "feat(core): four declared egress doors with a free-text boundary guard"
```

---

### Task 8: Routing and gap insertion

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/router.py`
- Test: `packages/mendel-resolver/tests/test_router.py`

**Interfaces:**
- Consumes: `Registry` (Task 5), `Goal`/`GoalInput` (Task 6)
- Produces: `route(goal: Goal, registry: Registry, max_depth: int = 10) -> RoutePlan`; `RoutePlan(steps: list[RouteStep], ambiguities: list[Ambiguity])`; `RouteStep(contract_id: str, node_id: str, satisfies: str)`; `UnroutableError`

This is the heart of the system. Backward chaining from wanted types to available ones, inserting producers to fill gaps. A tie between candidate routes is ambiguity, not a coin flip.

**Two rules below were added during implementation on 2026-08-03**, because the version first
written here recursed until it hit the depth bound and then reported a perfectly routable goal as
unroutable. Both are consequences of `producers_of` matching on **superset**, which is correct —
asking for `coordinate_sorted` should accept a producer that also indexes — but which means an
empty requirement matches every producer of the type.

1. **A contract may not satisfy its own input.** `SAMTOOLS_SORT` consumes `alignment.bam` and
   produces `alignment.bam`, so it is a candidate for its own dependency and selects itself
   forever. The recursion carries the set of contracts currently being expanded and excludes
   them.
2. **Prefer the producer with the smallest surplus** — the fewest states beyond those asked for.
   With nothing required, the aligner (`alignment.bam[]`) and the sorter
   (`alignment.bam[coordinate_sorted]`) both match, and lexical order picks the sorter. Ranking
   by `(surplus, -priority, id)` keeps "get me a BAM" from quietly meaning "get me a sorted
   BAM". Invariant 8 still holds: a tie is now a tie on `(surplus, priority)`, and still demotes.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.router import UnroutableError, route

ALIGN = """
id: nf-core/star/align@1.11.0
nf_process: STAR_ALIGN
nf_include: modules/nf-core/star/align/main
consumes: [{name: reads, type_id: fastq.reads, state_required: [trimmed]}]
produces: [{name: bam, type_id: alignment.bam, state: []}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""
TRIM = """
id: nf-core/trimgalore@0.6.10
nf_process: TRIMGALORE
nf_include: modules/nf-core/trimgalore/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces: [{name: reads, type_id: fastq.reads, state: [trimmed]}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""
SORT = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""


@pytest.fixture
def registry(tmp_path):
    vocab_dir = tmp_path / "vocab"
    vocab_dir.mkdir()
    (vocab_dir / "fastq.reads.yml").write_text("states: [trimmed]\n")
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    for name, body in [("align", ALIGN), ("trim", TRIM), ("sort", SORT)]:
        (contracts / f"{name}.yml").write_text(body)
    return Registry.load(contracts, Vocabulary.load(vocab_dir))


def test_inserts_the_gap_filling_step(registry):
    """Raw reads -> sorted BAM must insert both trimming and sorting."""
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["alignment.bam"],
        constraints={"required_states": {"alignment.bam": ["coordinate_sorted"]}},
    )
    plan = route(goal, registry)
    assert [step.contract_id for step in plan.steps] == [
        "nf-core/trimgalore@0.6.10",
        "nf-core/star/align@1.11.0",
        "nf-core/samtools/sort@1.21.0",
    ]


def test_no_insertion_when_input_already_satisfies(registry):
    goal = Goal(have=[GoalInput(type_id="fastq.reads", states=frozenset({"trimmed"}))],
                want=["alignment.bam"])
    plan = route(goal, registry)
    assert [s.contract_id for s in plan.steps] == ["nf-core/star/align@1.11.0"]


def test_unroutable_goal_raises(registry):
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["counts.matrix"])
    with pytest.raises(UnroutableError, match="counts.matrix"):
        route(goal, registry)


def test_routing_is_deterministic(registry):
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["alignment.bam"])
    assert [s.contract_id for s in route(goal, registry).steps] == [
        s.contract_id for s in route(goal, registry).steps
    ]


def test_tie_between_producers_becomes_an_ambiguity(tmp_path):
    vocab_dir = tmp_path / "vocab"
    vocab_dir.mkdir()
    (vocab_dir / "fastq.reads.yml").write_text("states: []\n")
    (vocab_dir / "alignment.bam.yml").write_text("states: []\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "a.yml").write_text(ALIGN.replace("state_required: [trimmed]", "state_required: []"))
    (contracts / "b.yml").write_text(
        ALIGN.replace("state_required: [trimmed]", "state_required: []")
        .replace("nf-core/star/align@1.11.0", "nf-core/hisat2/align@2.2.1")
        .replace("STAR_ALIGN", "HISAT2_ALIGN")
    )
    registry = Registry.load(contracts, Vocabulary.load(vocab_dir))
    plan = route(Goal(have=[GoalInput(type_id="fastq.reads")], want=["alignment.bam"]), registry)
    assert len(plan.ambiguities) == 1
    assert plan.ambiguities[0].subject == "producer:alignment.bam"
    assert sorted(plan.ambiguities[0].candidates) == [
        "nf-core/hisat2/align@2.2.1",
        "nf-core/star/align@1.11.0",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-resolver/tests/test_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_resolver.router'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Backward chaining from wanted types to available ones, inserting producers.

Ties are ambiguity, never a coin flip. Depth is bounded.
"""

from pydantic import BaseModel, Field

from comeni_core.contract import ModuleContract
from comeni_core.decision import Ambiguity
from comeni_core.registry import Registry
from mendel_resolver.goal import Goal


class UnroutableError(ValueError):
    """Raised when no chain of contracts can reach a wanted type."""


class RouteStep(BaseModel):
    contract_id: str
    node_id: str
    satisfies: str


class RoutePlan(BaseModel):
    steps: list[RouteStep] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)


def _node_id(contract: ModuleContract) -> str:
    return contract.nf_process.lower()


def _have_satisfies(goal: Goal, type_id: str, states: frozenset[str]) -> bool:
    return any(
        held.type_id == type_id and states <= held.states for held in goal.have
    )


def route(goal: Goal, registry: Registry, max_depth: int = 10) -> RoutePlan:
    plan = RoutePlan()
    emitted: set[str] = set()
    required_states: dict[str, list[str]] = goal.constraints.get("required_states", {})

    def satisfy(type_id: str, states: frozenset[str], depth: int) -> None:
        if depth > max_depth:
            raise UnroutableError(f"exceeded depth {max_depth} satisfying {type_id}")
        if _have_satisfies(goal, type_id, states):
            return
        candidates = registry.producers_of(type_id, states)
        if not candidates:
            raise UnroutableError(f"nothing produces {type_id} with states {sorted(states)}")
        if len(candidates) > 1 and candidates[0].priority == candidates[1].priority:
            plan.ambiguities.append(
                Ambiguity(
                    node_id=_node_id(candidates[0]),
                    subject=f"producer:{type_id}",
                    candidates=sorted(c.id for c in candidates),
                    context={"states": sorted(states)},
                )
            )
        chosen = candidates[0]
        for port in chosen.consumes:
            satisfy(port.type_id, port.state_required, depth + 1)
        if chosen.id not in emitted:
            emitted.add(chosen.id)
            plan.steps.append(
                RouteStep(contract_id=chosen.id, node_id=_node_id(chosen), satisfies=type_id)
            )

    for wanted in goal.want:
        satisfy(wanted, frozenset(required_states.get(wanted, [])), 0)
    return plan
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-resolver/tests/test_router.py -v && uv run ruff check .`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-resolver/src/mendel_resolver/router.py packages/mendel-resolver/tests/test_router.py
git commit -m "feat(resolver): backward-chaining router with gap insertion"
```

---

### Task 9: The four-tier ladder

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Test: `packages/mendel-resolver/tests/test_resolve.py`

**Interfaces:**
- Consumes: `route`/`RoutePlan` (Task 8), `RuleTable`/`Goal` (Task 6), `AmbiguityResolver`/`FlagOnlyResolver` (Task 7), `PipelineIR`/`ResolvedValue`/`Tier`/`DecisionRecord` (Task 4)
- Produces: `resolve(goal, registry, rules, resolver=FlagOnlyResolver()) -> PipelineIR`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.ir import ReviewLevel, Tier
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import DataProfile, Goal, GoalInput
from mendel_resolver.resolve import resolve
from mendel_resolver.rules import RuleTable

COUNTS = """
id: nf-core/subread/featurecounts@2.0.6
nf_process: FEATURECOUNTS
nf_include: modules/nf-core/subread/featurecounts/main
consumes: [{name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}]
produces: [{name: counts, type_id: counts.matrix, state: [gene_level]}]
params:
  - {name: strandedness, tier_hint: 3}
  - {name: seq_platform, tier_hint: 4, default: illumina}
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""
SORT = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""
RULES = """
rules:
  - id: strandedness-reverse
    subject: strandedness
    when: {strandedness: {"==": reverse}}
    then: {value: 2}
    citation: "featureCounts -s 2 for reverse-stranded libraries"
"""


@pytest.fixture
def setup(tmp_path):
    vocab_dir = tmp_path / "vocab"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    (vocab_dir / "counts.matrix.yml").write_text("states: [gene_level]\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "fc.yml").write_text(COUNTS)
    (contracts / "sort.yml").write_text(SORT)
    rules = tmp_path / "rules.yml"
    rules.write_text(RULES)
    return Registry.load(contracts, Vocabulary.load(vocab_dir)), RuleTable.load(rules)


def test_tier_3_rule_sets_value_and_marks_advisory(setup):
    registry, rules = setup
    goal = Goal(
        have=[GoalInput(type_id="alignment.bam")],
        want=["counts.matrix"],
        profile=DataProfile(strandedness="reverse"),
    )
    ir = resolve(goal, registry, rules)
    node = next(n for n in ir.nodes if n.id == "featurecounts")
    assert node.params["strandedness"].value == 2
    assert node.params["strandedness"].tier is Tier.DATA_PROFILED
    assert node.params["strandedness"].review_level is ReviewLevel.ADVISORY
    assert "featureCounts -s 2" in node.params["strandedness"].reason


def test_rule_miss_demotes_to_tier_4_and_flags(setup):
    registry, rules = setup
    goal = Goal(have=[GoalInput(type_id="alignment.bam")], want=["counts.matrix"],
                profile=DataProfile())
    ir = resolve(goal, registry, rules)
    node = next(n for n in ir.nodes if n.id == "featurecounts")
    assert node.params["strandedness"].tier is Tier.AMBIGUOUS
    assert node.params["strandedness"].review_level is ReviewLevel.REQUIRED
    assert "featurecounts.strandedness" in ir.needs_review()


def test_param_with_default_and_no_rule_is_tier_2_convention(setup):
    registry, rules = setup
    goal = Goal(have=[GoalInput(type_id="alignment.bam")], want=["counts.matrix"],
                profile=DataProfile(strandedness="reverse"))
    ir = resolve(goal, registry, rules)
    node = next(n for n in ir.nodes if n.id == "featurecounts")
    assert node.params["seq_platform"].value == "illumina"
    assert node.params["seq_platform"].tier is Tier.CONVENTION


def test_every_tier_4_resolution_emits_a_decision_record(setup):
    registry, rules = setup
    goal = Goal(have=[GoalInput(type_id="alignment.bam")], want=["counts.matrix"],
                profile=DataProfile())
    ir = resolve(goal, registry, rules)
    keys = [d.key for d in ir.decisions]
    assert "featurecounts.strandedness" in keys
    assert ir.decisions[0].resolved_by == "flag-only"


def test_gap_insertion_appears_as_nodes_and_edges(setup):
    registry, rules = setup
    goal = Goal(have=[GoalInput(type_id="alignment.bam")], want=["counts.matrix"],
                profile=DataProfile(strandedness="reverse"))
    ir = resolve(goal, registry, rules)
    assert [n.id for n in ir.nodes] == ["samtools_sort", "featurecounts"]
    assert len(ir.edges) == 1
    assert ir.edges[0].from_node == "samtools_sort"
    assert ir.edges[0].to_node == "featurecounts"
    assert ir.edges[0].states == frozenset({"coordinate_sorted"})


def test_resolution_is_deterministic(setup):
    registry, rules = setup
    goal = Goal(have=[GoalInput(type_id="alignment.bam")], want=["counts.matrix"],
                profile=DataProfile(strandedness="reverse"))
    assert resolve(goal, registry, rules).model_dump_json() == resolve(
        goal, registry, rules
    ).model_dump_json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-resolver/tests/test_resolve.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_resolver.resolve'`

- [ ] **Step 3: Write minimal implementation**

```python
"""The four-tier ladder. Every value exits at exactly one tier and carries it."""

from comeni_core.decision import Ambiguity, DecisionRecord
from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.registry import Registry
from mendel_resolver.goal import Goal
from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver
from mendel_resolver.router import route
from mendel_resolver.rules import RuleTable


def resolve(
    goal: Goal,
    registry: Registry,
    rules: RuleTable,
    resolver: AmbiguityResolver | None = None,
) -> PipelineIR:
    resolver = resolver or FlagOnlyResolver()
    plan = route(goal, registry)
    ir = PipelineIR()
    produced: dict[str, tuple[str, str, frozenset[str]]] = {}

    for step in plan.steps:
        contract = registry.get(step.contract_id)
        node = IRNode(id=step.node_id, contract_id=contract.id)

        for param in contract.params:
            node.params[param.name] = _resolve_param(
                node_id=node.id,
                param_name=param.name,
                tier_hint=param.tier_hint,
                default=param.default,
                goal=goal,
                rules=rules,
                resolver=resolver,
                decisions=ir.decisions,
            )

        for port in contract.consumes:
            source = produced.get(port.type_id)
            if source is not None:
                ir.edges.append(
                    IREdge(
                        from_node=source[0],
                        from_port=source[1],
                        to_node=node.id,
                        to_port=port.name,
                        type_id=port.type_id,
                        states=source[2],
                    )
                )

        for port in contract.produces:
            produced[port.type_id] = (node.id, port.name, port.state)

        ir.nodes.append(node)

    for ambiguity in plan.ambiguities:
        resolution = resolver.resolve(ambiguity)
        ir.decisions.append(
            DecisionRecord(
                key=ambiguity.key(),
                subject=ambiguity.subject,
                candidates=ambiguity.candidates,
                chosen=resolution.chosen,
                reason=resolution.reason,
                confidence=resolution.confidence,
                resolved_by=resolution.resolved_by,
            )
        )

    return ir


def _resolve_param(
    *,
    node_id: str,
    param_name: str,
    tier_hint: int | None,
    default: object,
    goal: Goal,
    rules: RuleTable,
    resolver: AmbiguityResolver,
    decisions: list[DecisionRecord],
) -> ResolvedValue:
    # Tier 1 — the goal states it outright. No choice exists.
    if param_name in goal.constraints:
        return ResolvedValue(
            value=goal.constraints[param_name],
            tier=Tier.STRUCTURAL,
            reason=f"specified in the goal as {param_name}",
        )

    # Tier 3 — a declared rule matches the measured profile.
    rule = rules.match(param_name, goal.profile)
    if rule is not None and "value" in rule.then:
        return ResolvedValue(
            value=rule.then["value"],
            tier=Tier.DATA_PROFILED,
            reason=f"rule {rule.id}: {rule.citation}",
        )

    # Tier 2 — a documented default exists for this context.
    if default is not None:
        return ResolvedValue(
            value=default,
            tier=Tier.CONVENTION,
            reason=f"contract default for {param_name}",
        )

    # Tier 4 — nothing decided it. Ask the port, record it, flag it.
    ambiguity = Ambiguity(
        node_id=node_id,
        subject=param_name,
        candidates=[default] if default is not None else [None],
        context={"tier_hint": tier_hint},
    )
    resolution = resolver.resolve(ambiguity)
    decisions.append(
        DecisionRecord(
            key=ambiguity.key(),
            subject=param_name,
            candidates=ambiguity.candidates,
            chosen=resolution.chosen,
            reason=resolution.reason,
            confidence=resolution.confidence,
            resolved_by=resolution.resolved_by,
        )
    )
    return ResolvedValue(value=resolution.chosen, tier=Tier.AMBIGUOUS, reason=resolution.reason)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-resolver/tests/ -v && uv run ruff check .`
Expected: PASS, 6 new tests, 16 in the resolver package.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-resolver/src/mendel_resolver/resolve.py packages/mendel-resolver/tests/test_resolve.py
git commit -m "feat(resolver): four-tier ladder producing pipeline IR"
```

---

### Task 10: The RNA-seq spine contracts

**Files:**
- Create: `examples/contracts/nf-core/*.yml` — 8 contracts covering the spine
- Create: `modules/nf-core/` — vendored module code, fetched with `nf-core`
- Test: `tests/test_spine_contracts.py`

**Interfaces:**
- Consumes: `Registry`, `Vocabulary`
- Produces: a loadable registry where `route()` can reach `counts.matrix` and `qc.report` from `fastq.reads`

- [ ] **Step 1: Write the failing test**

```python
import pathlib

import pytest
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.router import route

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def registry():
    return Registry.load(
        ROOT / "examples" / "contracts", Vocabulary.load(ROOT / "examples" / "vocabularies")
    )


def test_all_spine_contracts_load(registry):
    assert len(registry.all()) >= 6


def test_every_contract_points_at_vendored_module_code(registry):
    missing = [
        c.id for c in registry.all()
        if not (ROOT / f"{c.nf_include}.nf").exists()
    ]
    assert missing == [], f"contracts without vendored module code: {missing}"


def test_counts_matrix_is_reachable_from_raw_reads(registry):
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["counts.matrix"])
    steps = [s.contract_id for s in route(goal, registry).steps]
    assert "nf-core/trimgalore@0.6.10" in steps
    assert "nf-core/star/align@1.11.0" in steps
    assert "nf-core/samtools/sort@1.21.0" in steps
    assert "nf-core/subread/featurecounts@2.0.6" in steps


def test_qc_report_is_reachable_from_raw_reads(registry):
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"])
    assert route(goal, registry).steps != []


def test_every_spine_contract_declares_its_container(registry):
    """The lockfile resolves these to digests later. It cannot resolve what is absent."""
    missing = [c.id for c in registry.all() if not c.container]
    assert missing == [], f"contracts without a container reference: {missing}"


def test_no_contract_uses_a_floating_container_tag(registry):
    """`latest` and friends are not reproducible, and nf-core forbids them upstream too."""
    floating = [
        c.id
        for c in registry.all()
        if c.container and c.container.rsplit(":", 1)[-1] in {"latest", "dev", "master"}
    ]
    assert floating == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_spine_contracts.py -v`
Expected: FAIL — `examples/contracts/` is empty so `test_all_spine_contracts_load` fails on the count.

- [ ] **Step 3: Vendor the nf-core modules**

`nf-core modules install` refuses to run outside something it recognises as a pipeline, so three
things must exist first. It also crashes on the *first* install writing
`conf/containers_docker_amd64.config` if `conf/` is absent — after the module files have already
landed, which makes it look like a partial failure when it is not.

```bash
mkdir -p vendor/modules vendor/conf
cat > vendor/.nf-core.yml <<'YAML'
repository_type: pipeline
nf_core_version: "4.1.0"
YAML
```

`WARNING Could not find a 'main.nf' or 'nextflow.config' file` on every install is expected and
harmless — this repository is not a pipeline, it vendors modules for one it generates.

```bash
uvx nf-core modules install --dir vendor fastqc
uvx nf-core modules install --dir vendor trimgalore
uvx nf-core modules install --dir vendor star/align
uvx nf-core modules install --dir vendor star/genomegenerate
uvx nf-core modules install --dir vendor samtools/sort
uvx nf-core modules install --dir vendor samtools/index
uvx nf-core modules install --dir vendor subread/featurecounts
uvx nf-core modules install --dir vendor multiqc
```

Verify each landed: `ls vendor/modules/nf-core/*/main.nf vendor/modules/nf-core/*/*/main.nf`

- [ ] **Step 4: Write the eight contracts**

`examples/contracts/nf-core/fastqc.yml`:

```yaml
id: nf-core/fastqc@0.12.1
nf_process: FASTQC
nf_include: modules/nf-core/fastqc/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces: [{name: zip, type_id: qc.report, state: []}]
params: []
priority: 0
container: quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-02"}
```

**Every one of the eight carries a `container:` line, and you read it out of the vendored module
rather than out of this plan.** If the module disagrees with anything written here, **the module
is right and this plan is stale** — a container reference invented by a planner is exactly the
plausible wrong value the whole project exists to stop producing.

The `container` directive is a ternary: a Singularity URL when the engine is
singularity/apptainer, an OCI reference otherwise. Take the **last** quoted string — the OCI
one — and do not grep for `quay.io`, because as of nf-core 4.1.0 most modules have moved to
Seqera Containers and only two of the eight are still biocontainers:

```bash
uv run python - <<'PY'
import re, pathlib
for f in sorted(pathlib.Path("vendor/modules/nf-core").rglob("main.nf")):
    src = f.read_text()
    proc = re.search(r"process\s+([A-Z0-9_]+)", src).group(1)
    directive = re.search(r'container\s+"(.*?)"', src, re.S)
    print(f"{proc:24} {re.findall(r\"'([^']+)'\", directive.group(1))[-1]}")
PY
```

On 2026-08-03 that printed `quay.io/biocontainers/...` for `FASTQC` and
`SUBREAD_FEATURECOUNTS`, and `community.wave.seqera.io/library/...` for the other six. Worth
noticing for §6.1 of the clinical spec: the Seqera Singularity URLs are already
`blobs/sha256/<digest>/data`, and the Docker tags carry a content hash
(`1.24--d697cfb9dce007cd`), so upstream has largely solved digest pinning ahead of us.

**Use the process name the module declares, not the one you expect.** `subread/featurecounts`
declares `SUBREAD_FEATURECOUNTS`, so its node id is `subread_featurecounts` — Task 12's
end-to-end test depends on this and the plan originally had it wrong.

`test_contract_containers_match_the_vendored_modules` in Step 1 keeps the contract and the module
honest with each other, so an upstream bump shows up as a failing test rather than as a build
claiming a reproducibility it does not have.

`examples/contracts/nf-core/trimgalore.yml`:

```yaml
id: nf-core/trimgalore@0.6.10
nf_process: TRIMGALORE
nf_include: modules/nf-core/trimgalore/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces: [{name: reads, type_id: fastq.reads, state: [trimmed]}]
params: []
priority: 0
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-02"}
```

`examples/contracts/nf-core/star-genomegenerate.yml`:

```yaml
id: nf-core/star/genomegenerate@1.11.0
nf_process: STAR_GENOMEGENERATE
nf_include: modules/nf-core/star/genomegenerate/main
consumes: [{name: gtf, type_id: annotation.gtf, state_required: []}]
produces: [{name: index, type_id: genome.index.star, state: []}]
params: []
priority: 0
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-02"}
```

`examples/contracts/nf-core/star-align.yml`:

```yaml
id: nf-core/star/align@1.11.0
nf_process: STAR_ALIGN
nf_include: modules/nf-core/star/align/main
consumes:
  - {name: reads, type_id: fastq.reads, state_required: [trimmed]}
  - {name: index, type_id: genome.index.star, state_required: []}
produces:
  - {name: bam, type_id: alignment.bam, state: []}
params:
  - {name: seq_platform, tier_hint: 4, default: illumina}
priority: 10
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-02"}
```

`examples/contracts/nf-core/samtools-sort.yml`:

```yaml
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]
params: []
priority: 0
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-02"}
```

`examples/contracts/nf-core/samtools-index.yml`:

```yaml
id: nf-core/samtools/index@1.21.0
nf_process: SAMTOOLS_INDEX
nf_include: modules/nf-core/samtools/index/main
consumes: [{name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}]
produces: [{name: bai, type_id: alignment.bam, state: [coordinate_sorted, indexed]}]
params: []
priority: 0
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-02"}
```

`examples/contracts/nf-core/subread-featurecounts.yml`:

```yaml
id: nf-core/subread/featurecounts@2.0.6
nf_process: FEATURECOUNTS
nf_include: modules/nf-core/subread/featurecounts/main
consumes:
  - {name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}
  - {name: gtf, type_id: annotation.gtf, state_required: []}
produces:
  - {name: counts, type_id: counts.matrix, state: [gene_level]}
params:
  - {name: strandedness, tier_hint: 3}
priority: 0
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-02"}
```

`examples/contracts/nf-core/multiqc.yml`:

```yaml
id: nf-core/multiqc@1.25.0
nf_process: MULTIQC
nf_include: modules/nf-core/multiqc/main
consumes: [{name: files, type_id: qc.report, state_required: [], cardinality: "1..*"}]
produces: [{name: report, type_id: qc.report, state: [aggregated]}]
params: []
priority: 0
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-02"}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_spine_contracts.py -v && uv run ruff check .`
Expected: PASS, 6 tests.

- [ ] **Step 6: Commit**

```bash
git add examples/contracts/ vendor/ tests/test_spine_contracts.py
git commit -m "feat(contracts): RNA-seq spine contracts with vendored nf-core modules"
```

---

### Task 11: Nextflow emission

**Files:**
- Create: `packages/mendel-compiler/pyproject.toml`, `src/mendel_compiler/__init__.py`, `emit.py`, `templates/main.nf.j2`
- Test: `packages/mendel-compiler/tests/test_emit.py`, `tests/golden/spine/main.nf`

**Interfaces:**
- Consumes: `PipelineIR`, `Registry`
- Produces: `emit(ir: PipelineIR, registry: Registry) -> str` returning Nextflow DSL2 source

- [ ] **Step 1: Write the failing test**

```python
import pathlib

from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_compiler.emit import emit

ROOT = pathlib.Path(__file__).parent.parent.parent.parent


def _registry():
    return Registry.load(
        ROOT / "examples" / "contracts", Vocabulary.load(ROOT / "examples" / "vocabularies")
    )


def _ir():
    return PipelineIR(
        nodes=[
            IRNode(id="trimgalore", contract_id="nf-core/trimgalore@0.6.10"),
            IRNode(
                id="star_align",
                contract_id="nf-core/star/align@1.11.0",
                params={
                    "seq_platform": ResolvedValue(
                        value="illumina", tier=Tier.CONVENTION, reason="contract default"
                    )
                },
            ),
        ],
        edges=[
            IREdge(from_node="trimgalore", from_port="reads", to_node="star_align",
                   to_port="reads", type_id="fastq.reads", states=frozenset({"trimmed"}))
        ],
    )


def test_emits_include_statements_for_every_node():
    source = emit(_ir(), _registry())
    assert "include { TRIMGALORE } from './modules/nf-core/trimgalore/main'" in source
    assert "include { STAR_ALIGN } from './modules/nf-core/star/align/main'" in source


def test_emits_workflow_block_wiring_edges():
    source = emit(_ir(), _registry())
    assert "workflow {" in source
    assert "TRIMGALORE(ch_reads)" in source
    assert "STAR_ALIGN(TRIMGALORE.out.reads" in source


def test_annotates_each_param_with_its_tier():
    source = emit(_ir(), _registry())
    assert "// tier 2 (none): contract default" in source
    assert "params.star_align_seq_platform = 'illumina'" in source


def test_emission_is_byte_identical_across_runs():
    assert emit(_ir(), _registry()) == emit(_ir(), _registry())


def test_carries_its_intended_purpose_statement():
    """The .nf travels alone. It has to say what it is without the rest of the repo."""
    source = emit(_ir(), _registry())
    assert "It is not a diagnostic" in source
    assert "must be validated by" in source


def test_matches_the_golden_file():
    golden = ROOT / "tests" / "golden" / "spine" / "main.nf"
    assert emit(_ir(), _registry()) == golden.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-compiler/tests/test_emit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_compiler'`

- [ ] **Step 3: Create the package**

`packages/mendel-compiler/pyproject.toml`:

```toml
[project]
name = "mendel-compiler"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["comeni-core", "mendel-resolver", "pydantic>=2.9", "jinja2>=3.1", "pyyaml>=6.0"]

[project.scripts]
mendel = "mendel_compiler.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mendel_compiler"]
```

`src/mendel_compiler/__init__.py`:

```python
"""Mendel's compiler: pipeline IR to Nextflow DSL2."""

__version__ = "0.1.0"
```

And the root `pyproject.toml`, both places again — this is the third and last package, so the
root ends up as:

```toml
dependencies = ["comeni-core", "mendel-resolver", "mendel-compiler"]

[tool.uv.sources]
comeni-core = { workspace = true }
mendel-resolver = { workspace = true }
mendel-compiler = { workspace = true }
```

This is also what puts `mendel` on the path, so `uv run mendel build` works in Task 12.

- [ ] **Step 4: Write the template**

`src/mendel_compiler/templates/main.nf.j2`:

The header is not decoration. The `.nf` is the artifact that travels — it gets emailed,
committed to somebody else's repository and pasted into methods sections with every other file
left behind — so it has to carry its own label. Wording is fixed by the clinical
data-protection spec §2.2 and must match it verbatim; it is what keeps the manufacturer
boundary where §2.1 needs it.

**Use `{% endfor %}`, not `{%- endfor %}`.** The `-` strips whitespace *before* the tag, and
`trim_blocks=True` already removes the newline *after* it, so every loop iteration loses its line
ending. The first draft of this template emitted both include statements on one line and every
process call on one line with the closing brace attached — not valid Nextflow, and caught only
because Step 6 says to read the golden file rather than trust it.

```jinja
#!/usr/bin/env nextflow
// Generated by Mendel. Do not edit by hand — edit the goal and recompile.
//
// Mendel constructs and documents analysis pipelines. It is not a diagnostic
// device and produces no diagnostic result. This pipeline must be validated by
// the laboratory before clinical use.
nextflow.enable.dsl = 2

{% for node in nodes %}
include { {{ node.process }} } from './{{ node.include }}'
{% endfor %}

{% for node in nodes %}
{% for name, value in node.params %}
// tier {{ value.tier.value }} ({{ value.review_level.value }}): {{ value.reason }}
params.{{ node.id }}_{{ name }} = {{ value.rendered }}
{% endfor %}
{% endfor %}

workflow {
    ch_reads = Channel.fromFilePairs(params.input, checkIfExists: true)

{% for call in calls %}
    {{ call }}
{% endfor %}
}
```

- [ ] **Step 5: Write `emit.py`**

```python
"""IR to Nextflow DSL2. Deterministic: same IR, byte-identical output."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from comeni_core.ir import PipelineIR
from comeni_core.registry import Registry

_TEMPLATES = Path(__file__).parent / "templates"


def _render_literal(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return f"'{value}'"


def _calls(ir: PipelineIR, registry: Registry) -> list[str]:
    incoming: dict[str, list[str]] = {node.id: [] for node in ir.nodes}
    for edge in ir.edges:
        incoming[edge.to_node].append(f"{_process(ir, registry, edge.from_node)}.out.{edge.from_port}")

    calls = []
    for node in ir.nodes:
        args = incoming[node.id] or ["ch_reads"]
        calls.append(f"{_process(ir, registry, node.id)}({', '.join(args)})")
    return calls


def _process(ir: PipelineIR, registry: Registry, node_id: str) -> str:
    node = next(n for n in ir.nodes if n.id == node_id)
    return registry.get(node.contract_id).nf_process


def emit(ir: PipelineIR, registry: Registry) -> str:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    nodes = [
        {
            "id": node.id,
            "process": registry.get(node.contract_id).nf_process,
            "include": registry.get(node.contract_id).nf_include,
            "params": [
                (name, type("V", (), {
                    "tier": value.tier,
                    "review_level": value.review_level,
                    "reason": value.reason,
                    "rendered": _render_literal(value.value),
                })())
                for name, value in sorted(node.params.items())
            ],
        }
        for node in ir.nodes
    ]
    return env.get_template("main.nf.j2").render(nodes=nodes, calls=_calls(ir, registry))
```

- [ ] **Step 6: Generate the golden file and verify**

Run the emitter once and write its output to `tests/golden/spine/main.nf`, then read that file and confirm by eye that the `include` paths, the `workflow` block wiring and the tier comments are all correct before committing it. A golden file committed without being read is worthless.

```bash
mkdir -p tests/golden/spine
uv run python -c "
from pathlib import Path
import sys; sys.path.insert(0, 'packages/mendel-compiler/tests')
from test_emit import _ir, _registry
from mendel_compiler.emit import emit
Path('tests/golden/spine/main.nf').write_text(emit(_ir(), _registry()))
"
cat tests/golden/spine/main.nf
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-compiler/tests/ -v && uv run ruff check .`
Expected: PASS, 6 tests.

- [ ] **Step 8: Commit**

```bash
git add packages/mendel-compiler/ tests/golden/
git commit -m "feat(compiler): deterministic Nextflow emission with golden-file test"
```

---

### Task 12: Validation gates and the CLI

**Files:**
- Create: `packages/mendel-compiler/src/mendel_compiler/gates.py`, `cli.py`
- Create: `examples/rnaseq-goal.yml`
- Test: `packages/mendel-compiler/tests/test_gates.py`, `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: everything above
- Produces: `run_gate(gate: Gate, workdir: Path) -> GateResult`; `Gate` StrEnum (`LINT, PREVIEW, STUB, TEST`); `GateResult(gate, passed, stdout, stderr)`; CLI `mendel build --goal <path> --out <dir> [--gate stub]`

- [ ] **Step 1: Write the failing test**

```python
import shutil

import pytest
from mendel_compiler.gates import Gate, GateResult, run_gate


def test_gate_result_reports_failure_with_output(tmp_path):
    (tmp_path / "main.nf").write_text("this is not valid nextflow {{{\n")
    result = run_gate(Gate.LINT, tmp_path)
    assert isinstance(result, GateResult)
    assert result.passed is False
    assert result.stderr != ""


@pytest.mark.skipif(shutil.which("nextflow") is None, reason="nextflow not installed")
def test_lint_passes_on_a_trivial_valid_pipeline(tmp_path):
    (tmp_path / "main.nf").write_text(
        "nextflow.enable.dsl = 2\nworkflow { Channel.of(1).view() }\n"
    )
    assert run_gate(Gate.LINT, tmp_path).passed is True


def test_gates_are_ordered_cheapest_first():
    assert list(Gate) == [Gate.LINT, Gate.PREVIEW, Gate.STUB, Gate.TEST]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-compiler/tests/test_gates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_compiler.gates'`

- [ ] **Step 3: Write `gates.py`**

```python
"""Validation gates, cheapest first. Each is a subprocess call to nextflow."""

import subprocess
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel


class Gate(StrEnum):
    LINT = "lint"
    PREVIEW = "preview"
    STUB = "stub"
    TEST = "test"


_ARGS: dict[Gate, list[str]] = {
    Gate.LINT: ["nextflow", "lint", "main.nf"],
    Gate.PREVIEW: ["nextflow", "run", "main.nf", "-preview", "-profile", "test"],
    Gate.STUB: ["nextflow", "run", "main.nf", "-stub-run", "-profile", "test"],
    Gate.TEST: ["nextflow", "run", "main.nf", "-profile", "test"],
}

_TIMEOUTS: dict[Gate, int] = {
    Gate.LINT: 60,
    Gate.PREVIEW: 180,
    Gate.STUB: 300,
    Gate.TEST: 3600,
}


class GateResult(BaseModel):
    gate: Gate
    passed: bool
    stdout: str = ""
    stderr: str = ""


def run_gate(gate: Gate, workdir: Path) -> GateResult:
    try:
        completed = subprocess.run(
            _ARGS[gate],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=_TIMEOUTS[gate],
            check=False,
        )
    except FileNotFoundError:
        return GateResult(gate=gate, passed=False, stderr="nextflow not found on PATH")
    except subprocess.TimeoutExpired:
        return GateResult(gate=gate, passed=False, stderr=f"{gate} timed out")
    return GateResult(
        gate=gate,
        passed=completed.returncode == 0,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
```

- [ ] **Step 4: Write `cli.py`**

```python
"""`mendel build` — goal in, pipeline directory out."""

import argparse
import shutil
import sys
from pathlib import Path

import yaml

from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_compiler.emit import emit
from mendel_compiler.gates import Gate, run_gate
from mendel_resolver.goal import Goal
from mendel_resolver.resolve import resolve
from mendel_resolver.rules import RuleTable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mendel")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--goal", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--gate", type=Gate, default=None)
    parser.add_argument(
        "--registry",
        type=Path,
        action="append",
        default=None,
        help="a registry layer; repeat to stack overlays, later layers win",
    )
    args = parser.parse_args(argv)

    data = args.root / "examples"
    layers = args.registry or [data / "contracts"]

    vocab = Vocabulary.load(data / "vocabularies")
    registry = Registry.load(layers, vocab)
    rules = RuleTable.load(data / "rules" / "rnaseq.yml")
    goal = Goal.model_validate(yaml.safe_load(args.goal.read_text()))

    ir = resolve(goal, registry, rules)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "main.nf").write_text(emit(ir, registry))
    (args.out / "pipeline.ir.json").write_text(ir.model_dump_json(indent=2))
    if (args.root / "modules").exists():
        shutil.copytree(args.root / "modules", args.out / "modules", dirs_exist_ok=True)

    for record in registry.shadowed:
        print(
            f"  SHADOW  {record.module_key}: {record.winning_id} from {record.winning_layer} "
            f"displaced {', '.join(record.displaced_ids)}",
            file=sys.stderr,
        )

    flagged = ir.needs_review()
    print(f"{len(ir.nodes)} modules, {len(flagged)} requiring review", file=sys.stderr)
    for item in flagged:
        print(f"  REVIEW  {item}", file=sys.stderr)

    if args.gate is not None:
        result = run_gate(args.gate, args.out)
        print(f"gate {result.gate}: {'PASS' if result.passed else 'FAIL'}", file=sys.stderr)
        if not result.passed:
            print(result.stderr, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Write the example goal**

`examples/rnaseq-goal.yml`:

```yaml
have:
  - type_id: fastq.reads
  - type_id: annotation.gtf
want:
  - counts.matrix
constraints:
  required_states:
    counts.matrix: [gene_level]
profile:
  read_length: 150
  strandedness: reverse
  n_samples: 12
  paired: true
```

- [ ] **Step 6: Write the end-to-end test**

`tests/test_end_to_end.py`:

```python
import json
import pathlib

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent


def test_builds_a_pipeline_from_the_example_goal(tmp_path):
    exit_code = main([
        "build",
        "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "pipeline"),
        "--root", str(ROOT),
    ])
    assert exit_code == 0
    source = (tmp_path / "pipeline" / "main.nf").read_text()
    assert "STAR_ALIGN" in source
    assert "FEATURECOUNTS" in source
    assert (tmp_path / "pipeline" / "pipeline.ir.json").exists()


def test_strandedness_resolves_at_tier_3_from_the_profile(tmp_path):
    main([
        "build",
        "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "pipeline"),
        "--root", str(ROOT),
    ])
    ir = json.loads((tmp_path / "pipeline" / "pipeline.ir.json").read_text())
    node = next(n for n in ir["nodes"] if n["id"] == "featurecounts")
    assert node["params"]["strandedness"]["value"] == 2
    assert node["params"]["strandedness"]["tier"] == 3
    assert node["params"]["strandedness"]["review_level"] == "advisory"


def test_an_overlay_shadows_and_says_so(tmp_path, capsys):
    """--registry stacks layers, and a build on a modified registry announces it."""
    overlay = tmp_path / "lab"
    overlay.mkdir()
    base = ROOT / "examples" / "contracts" / "nf-core" / "samtools-sort.yml"
    (overlay / "sort.yml").write_text(base.read_text().replace("@1.21.0", "@1.99.0"))

    exit_code = main([
        "build",
        "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "pipeline"),
        "--root", str(ROOT),
        "--registry", str(ROOT / "examples" / "contracts"),
        "--registry", str(overlay),
    ])
    assert exit_code == 0
    assert "SHADOW  nf-core/samtools/sort" in capsys.readouterr().err
    ir = json.loads((tmp_path / "pipeline" / "pipeline.ir.json").read_text())
    assert "nf-core/samtools/sort@1.99.0" in [n["contract_id"] for n in ir["nodes"]]


def test_two_builds_produce_identical_output(tmp_path):
    for name in ["a", "b"]:
        main([
            "build",
            "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
            "--out", str(tmp_path / name),
            "--root", str(ROOT),
        ])
    assert (tmp_path / "a" / "main.nf").read_text() == (tmp_path / "b" / "main.nf").read_text()
```

- [ ] **Step 7: Run the full suite**

Run: `uv sync && uv run pytest -v && uv run ruff check .`
Expected: PASS, all tests.

- [ ] **Step 7B: The mapping the plan was missing — added 2026-08-03**

The stub gate failed with *"Process `STAR_GENOMEGENERATE` declares 2 inputs but was called with
1 argument"*, and investigating it found an assumption running through Tasks 9 and 11:

> **A contract port is semantic; a process input is plumbing. They do not correspond.**

Measured against the vendored modules, only one of five spine processes matches its contract's
port count:

| process | inputs declared | contract ports |
|---|---|---|
| `TRIMGALORE` | 1 | 1 |
| `STAR_GENOMEGENERATE` | 2 (fasta, gtf) | 1 |
| `STAR_ALIGN` | 4 (reads, index, gtf, a `val`) | 2 |
| `SAMTOOLS_SORT` | 3 (bam, fasta+fai, a `val`) | 1 |
| `SUBREAD_FEATURECOUNTS` | **1** tuple carrying bam *and* annotation | 2 |

`ModuleContract` therefore gains `nf_inputs: list[NfInput]`, one entry per process input, each
naming contract ports (several may share one channel), an `empty` tuple width, or a `literal`.
Absent, it defaults to one channel per port, which keeps simple modules simple.

**Declared rather than parsed out of `main.nf`, deliberately.** A parser would work for nf-core
and nothing else; the compiler has to emit calls for a pegi3s image or an in-house process too.
The contract is the module-agnostic layer, so the signature belongs in it — and `meta.yml`'s
`input:` is a list-of-lists carrying exactly this, so the Plan 2 forge can draft it rather than
it being hand-work forever.

Four smaller things fell out of the same investigation:

- **Entry channels are declared in the vocabulary**, as `entry_channel`, for the same
  module-agnostic reason. A type says how it arrives; the compiler does not hardcode it.
- **`empty` carries a tuple width.** Nextflow matches arity, so `[[:], []]` handed to
  `tuple val(meta), path(fasta), path(fai)` fails with "Path value cannot be null".
  `samtools/sort` needs 3.
- **`_render_literal(None)` emitted the string `'None'`.** It emits `null`.
- **The pipeline had no `nextflow.config`.** `emit_config` writes one where every input parameter
  defaults to `null` — invariant 15 reaching the configuration as well as the workflow — plus
  `docker`/`singularity` profiles and a `stub_data` profile pointing at synthetic files the gate
  materialises. Fixtures belong to the validation harness, never to the emitted pipeline.

Also: nf-core 4.x captures tool versions with `eval()`, which runs **even under `-stub-run`**, so
the stub gate needs a container engine — hence `-profile stub_data,docker` and a 900s timeout for
the first run's image pulls. And the docker profile sets
`docker.runOptions = '-u $(id -u):$(id -g)'`, without which every work directory is root-owned and
the person who created it cannot delete it.

- [ ] **Step 8: Run the real gate manually**

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
```

Expected: the review summary prints to stderr, and `gate stub: PASS`. If it fails, the stderr from Nextflow is the actual signal — read it before changing anything.

- [ ] **Step 9: Commit**

```bash
git add packages/mendel-compiler/ examples/ tests/test_end_to_end.py
git commit -m "feat(compiler): validation gates and mendel build CLI"
```

---

## Self-Review

**Spec coverage.** Walking §1–13 of the spec against the tasks:

| Spec section | Covered by |
|---|---|
| §4.3 ports and adapters | Task 1 (purity guard), Task 7 (the port), Task 7B (the egress guard) |
| §4.4 packages | Tasks 1, 6, 11 — `mendel-ai`, `mendel-forge`, `mendel-api` are Plans 2 and 3 |
| §5.1 module contracts | Task 3, Task 10 |
| §5.2 vocabularies | Task 2 |
| §5.3 pipeline IR | Task 4 |
| §5.4 decision records | Task 4, Task 9 |
| §6.1 four tiers + review levels | Task 4, Task 9 |
| §6.2 tier-3 rule table, miss demotes | Task 6, Task 9 |
| §6.3 routing and gap insertion | Task 8 |
| §7.1 repair edits IR | **Plan 2** — no repair without AI |
| §7.3 validation gates | Task 12 |
| §8 the forge | **Plan 2** |
| §9 stack | Task 1, Task 11 (FastAPI/ARQ are Plan 3) |
| §11 testing | golden files in Task 11, determinism tests in Tasks 8, 9, 11, 12 |

Gaps are deliberate and named: everything AI-shaped is Plan 2, everything web-shaped is Plan 3.

**Clinical data-protection spec coverage.** That spec's §9 assigns Plan 1 three additions, and a
fourth moved here during planning:

| Spec section | Covered by |
|---|---|
| §2.2 intended purpose on the artifact | Task 11 — template header, asserted by test |
| §3 Mendel receives a shape, not data (invariant 15) | Task 6 — `extra="forbid"` on `Goal` and `DataProfile` |
| §4 the four doors (invariant 14) | **Task 7B** |
| §6.1 container reference | Task 3 (`ModuleContract.container`), Task 10 (the eight contracts) |
| §5 profiles, §5.5 `EgressRecord`, §5.6 prompt store | **Plan 2** — nothing to protect until a door opens |
| §6.1 lockfile, §6.2 curation evidence | **Plan 1.7** |

Task 7B was moved from Plan 2 to Plan 1 deliberately. It is pure `comeni-core` work needing no
model, and a guard belongs in place before the code it constrains — the same reasoning that puts
the purity guard in Task 1. Nothing in Plan 1 can violate it; Plan 2 is where that changes, and
by then it is already in CI.

**Placeholder scan.** No TBDs. Every code step contains runnable code. Task 11 Step 6 asks the engineer to read the golden file before committing it rather than generating it blind.

**Type consistency.** `ResolvedValue.review_level` is a computed field throughout. `Ambiguity.key()` is used identically in Tasks 7 and 9. `Registry.producers_of` returns `list[ModuleContract]` sorted `(-priority, id)` and both callers rely on that order. `nf_include` is consistently a path without the `.nf` suffix — Task 10's test appends it, Task 11's template prefixes `./`.

**Two known rough edges to watch during execution.**

1. Task 11's `emit` builds an anonymous class for template values. It works but is ugly. If it causes trouble, replace it with a small Pydantic model — the tests will tell you immediately either way.
2. Task 11's `_calls` gives every node with no incoming edge the same `ch_reads` channel. That is correct for `FASTQC` and `TRIMGALORE` but wrong for `STAR_GENOMEGENERATE`, which needs the GTF channel. The `-stub-run` gate in Task 12 is what will surface it. When it does, the fix is to key entry channels by the port's `type_id` (`fastq.reads` → `ch_reads`, `annotation.gtf` → `ch_gtf`) rather than defaulting them all.

   **Executed 2026-08-03: the gate surfaced it, and that fix is not sufficient.** Keying entry channels on `type_id` yields `STAR_GENOMEGENERATE(ch_gtf)` — one argument to a two-input process, which fails identically. The root cause is deeper and is recorded in Task 12, Step 7B.

---

## Verification

End to end, from a clean clone:

```bash
uv sync
uv run pytest -v                              # all unit + golden + e2e tests
uv run ruff check .                           # lint
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
```

The plan is complete when that last command prints `gate stub: PASS` and reports its flagged-parameter count. That is the v1 thesis proven with zero AI: a typed goal became a running pipeline, every parameter carries a tier, and the things Mendel was unsure about are listed rather than hidden.

The `-profile test` gate (real execution, minutes not seconds) is the remaining milestone and should be run nightly in CI once this plan lands.
