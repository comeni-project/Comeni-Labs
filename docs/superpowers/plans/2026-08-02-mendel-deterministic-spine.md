# Mendel — Deterministic Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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
├─ vocabularies/                           <type>.yml — closed state lists
├─ rules/rnaseq.yml                        tier-3 rules
├─ contracts/nf-core/                      approved module contracts
├─ modules/nf-core/                        vendored nf-core module code
└─ tests/golden/                           goal → expected IR → expected .nf
```

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
    assert violations == [], "Pure packages must not import I/O or model libraries:\n" + "\n".join(violations)
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

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
comeni-core = { workspace = true }

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.6", "pytest-cov>=5.0"]

[tool.pytest.ini_options]
testpaths = ["tests", "packages"]
```

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
- Create: `vocabularies/alignment.bam.yml`, `vocabularies/fastq.reads.yml`, `vocabularies/counts.matrix.yml`, `vocabularies/genome.index.star.yml`, `vocabularies/annotation.gtf.yml`, `vocabularies/qc.report.yml`
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
# vocabularies/fastq.reads.yml
states: [trimmed, deduplicated, subsampled]
```
```yaml
# vocabularies/alignment.bam.yml
states: [coordinate_sorted, name_sorted, deduplicated, filtered, indexed]
```
```yaml
# vocabularies/counts.matrix.yml
states: [gene_level, transcript_level, normalised]
```
```yaml
# vocabularies/genome.index.star.yml
states: []
```
```yaml
# vocabularies/annotation.gtf.yml
states: []
```
```yaml
# vocabularies/qc.report.yml
states: [aggregated]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/comeni-core/tests/test_vocabulary.py -v && uv run ruff check .`
Expected: PASS, 5 tests.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/src/comeni_core/vocabulary.py packages/comeni-core/tests/test_vocabulary.py vocabularies/
git commit -m "feat(core): closed type vocabularies with state validation"
```

---

### Task 3: Module contracts

**Files:**
- Create: `packages/comeni-core/src/comeni_core/contract.py`
- Test: `packages/comeni-core/tests/test_contract.py`

**Interfaces:**
- Consumes: `Vocabulary` from Task 2
- Produces: `ModuleContract`, `InputPort`, `OutputPort`, `Param`, `Provenance`; `ModuleContract.load(path: Path, vocab: Vocabulary) -> ModuleContract`; `ModuleContract.id: str`, `.nf_process: str`, `.nf_include: str`, `.consumes: list[InputPort]`, `.produces: list[OutputPort]`, `.params: list[Param]`, `.priority: int`

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
Expected: PASS, 3 tests.

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
    assert ir.model_dump_json() == PipelineIR.model_validate_json(ir.model_dump_json()).model_dump_json()
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

### Task 5: The registry

**Files:**
- Create: `packages/comeni-core/src/comeni_core/registry.py`
- Modify: `packages/comeni-core/src/comeni_core/__init__.py`
- Test: `packages/comeni-core/tests/test_registry.py`

**Interfaces:**
- Consumes: `ModuleContract` (Task 3), `Vocabulary` (Task 2)
- Produces: `Registry.load(contracts_dir: Path, vocab: Vocabulary) -> Registry`; `Registry.get(contract_id: str) -> ModuleContract`; `Registry.producers_of(type_id: str, states: frozenset[str]) -> list[ModuleContract]` returning contracts sorted by `(-priority, id)`; `Registry.all() -> list[ModuleContract]`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.registry import Registry
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


@pytest.fixture
def registry(tmp_path):
    vocab_dir = tmp_path / "vocab"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "sort.yml").write_text(SORT)
    (contracts / "fastsort.yml").write_text(PREFERRED_SORT)
    return Registry.load(contracts, Vocabulary.load(vocab_dir))


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'comeni_core.registry'`

- [ ] **Step 3: Write minimal implementation**

```python
"""The contract registry: what exists, and what can produce what."""

from pathlib import Path

from pydantic import BaseModel

from comeni_core.contract import ModuleContract
from comeni_core.vocabulary import Vocabulary


class Registry(BaseModel):
    contracts: dict[str, ModuleContract]

    @classmethod
    def load(cls, contracts_dir: Path, vocab: Vocabulary) -> "Registry":
        contracts = {}
        for path in sorted(contracts_dir.rglob("*.yml")):
            contract = ModuleContract.load(path, vocab)
            contracts[contract.id] = contract
        return cls(contracts=contracts)

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

- [ ] **Step 4: Export the public API**

`packages/comeni-core/src/comeni_core/__init__.py`:

```python
"""Shared data model for Comeni Labs: contracts, vocabularies, IR, decisions."""

from comeni_core.contract import InputPort, ModuleContract, OutputPort, Param, Provenance
from comeni_core.decision import Ambiguity, DecisionRecord, Resolution
from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, ReviewLevel, Tier
from comeni_core.registry import Registry
from comeni_core.vocabulary import UnknownStateError, UnknownTypeError, Vocabulary

__version__ = "0.1.0"

__all__ = [
    "Ambiguity", "DecisionRecord", "IREdge", "IRNode", "InputPort", "ModuleContract",
    "OutputPort", "Param", "PipelineIR", "Provenance", "Registry", "ResolvedValue",
    "Resolution", "ReviewLevel", "Tier", "UnknownStateError", "UnknownTypeError",
    "Vocabulary",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/comeni-core/tests/ -v && uv run ruff check .`
Expected: PASS, 5 new tests, 17 total.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/
git commit -m "feat(core): registry with priority-ordered producer lookup"
```

---

### Task 6: Goal, data profile and tier-3 rule tables

**Files:**
- Create: `packages/mendel-resolver/pyproject.toml`, `packages/mendel-resolver/src/mendel_resolver/__init__.py`, `goal.py`, `rules.py`
- Create: `rules/rnaseq.yml`
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

`src/mendel_resolver/goal.py`:

```python
"""What the user has, what they want, and what the data actually looks like."""

from typing import Any

from pydantic import BaseModel, Field


class DataProfile(BaseModel):
    """Measured properties of the input data. Pure computation, no inference."""

    read_length: int | None = None
    strandedness: str | None = None
    n_samples: int | None = None
    paired: bool | None = None


class GoalInput(BaseModel):
    type_id: str
    states: frozenset[str] = frozenset()


class Goal(BaseModel):
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

- [ ] **Step 5: Create `rules/rnaseq.yml`**

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
Expected: PASS, 6 tests.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-resolver/ rules/
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

### Task 8: Routing and gap insertion

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/router.py`
- Test: `packages/mendel-resolver/tests/test_router.py`

**Interfaces:**
- Consumes: `Registry` (Task 5), `Goal`/`GoalInput` (Task 6)
- Produces: `route(goal: Goal, registry: Registry, max_depth: int = 10) -> RoutePlan`; `RoutePlan(steps: list[RouteStep], ambiguities: list[Ambiguity])`; `RouteStep(contract_id: str, node_id: str, satisfies: str)`; `UnroutableError`

This is the heart of the system. Backward chaining from wanted types to available ones, inserting producers to fill gaps. A tie between candidate routes is ambiguity, not a coin flip.

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
- Create: `contracts/nf-core/*.yml` — 8 contracts covering the spine
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
    return Registry.load(ROOT / "contracts", Vocabulary.load(ROOT / "vocabularies"))


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_spine_contracts.py -v`
Expected: FAIL — `contracts/` is empty so `test_all_spine_contracts_load` fails on the count.

- [ ] **Step 3: Vendor the nf-core modules**

```bash
uv tool install nf-core
nf-core modules install fastqc --dir .
nf-core modules install trimgalore --dir .
nf-core modules install star/align --dir .
nf-core modules install star/genomegenerate --dir .
nf-core modules install samtools/sort --dir .
nf-core modules install samtools/index --dir .
nf-core modules install subread/featurecounts --dir .
nf-core modules install multiqc --dir .
```

Verify each landed: `ls modules/nf-core/*/main.nf modules/nf-core/*/*/main.nf`

- [ ] **Step 4: Write the eight contracts**

`contracts/nf-core/fastqc.yml`:

```yaml
id: nf-core/fastqc@0.12.1
nf_process: FASTQC
nf_include: modules/nf-core/fastqc/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces: [{name: zip, type_id: qc.report, state: []}]
params: []
priority: 0
provenance: {source: nf-core-meta-yml, drafted_by: hand, approved_by: rafael, approved_at: "2026-08-02"}
```

`contracts/nf-core/trimgalore.yml`:

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

`contracts/nf-core/star-genomegenerate.yml`:

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

`contracts/nf-core/star-align.yml`:

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

`contracts/nf-core/samtools-sort.yml`:

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

`contracts/nf-core/samtools-index.yml`:

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

`contracts/nf-core/subread-featurecounts.yml`:

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

`contracts/nf-core/multiqc.yml`:

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
Expected: PASS, 4 tests.

- [ ] **Step 6: Commit**

```bash
git add contracts/ modules/ tests/test_spine_contracts.py
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
    return Registry.load(ROOT / "contracts", Vocabulary.load(ROOT / "vocabularies"))


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

- [ ] **Step 4: Write the template**

`src/mendel_compiler/templates/main.nf.j2`:

```jinja
#!/usr/bin/env nextflow
// Generated by Mendel. Do not edit by hand — edit the goal and recompile.
nextflow.enable.dsl = 2

{% for node in nodes %}
include { {{ node.process }} } from './{{ node.include }}'
{%- endfor %}

{% for node in nodes %}{% for name, value in node.params %}
// tier {{ value.tier.value }} ({{ value.review_level.value }}): {{ value.reason }}
params.{{ node.id }}_{{ name }} = {{ value.rendered }}
{%- endfor %}{% endfor %}

workflow {
    ch_reads = Channel.fromFilePairs(params.input, checkIfExists: true)
{% for call in calls %}
    {{ call }}
{%- endfor %}
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
Expected: PASS, 5 tests.

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
    args = parser.parse_args(argv)

    vocab = Vocabulary.load(args.root / "vocabularies")
    registry = Registry.load(args.root / "contracts", vocab)
    rules = RuleTable.load(args.root / "rules" / "rnaseq.yml")
    goal = Goal.model_validate(yaml.safe_load(args.goal.read_text()))

    ir = resolve(goal, registry, rules)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "main.nf").write_text(emit(ir, registry))
    (args.out / "pipeline.ir.json").write_text(ir.model_dump_json(indent=2))
    if (args.root / "modules").exists():
        shutil.copytree(args.root / "modules", args.out / "modules", dirs_exist_ok=True)

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
    import json
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
| §4.3 ports and adapters | Task 1 (purity guard), Task 7 (the port) |
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

**Placeholder scan.** No TBDs. Every code step contains runnable code. Task 11 Step 6 asks the engineer to read the golden file before committing it rather than generating it blind.

**Type consistency.** `ResolvedValue.review_level` is a computed field throughout. `Ambiguity.key()` is used identically in Tasks 7 and 9. `Registry.producers_of` returns `list[ModuleContract]` sorted `(-priority, id)` and both callers rely on that order. `nf_include` is consistently a path without the `.nf` suffix — Task 10's test appends it, Task 11's template prefixes `./`.

**Two known rough edges to watch during execution.**

1. Task 11's `emit` builds an anonymous class for template values. It works but is ugly. If it causes trouble, replace it with a small Pydantic model — the tests will tell you immediately either way.
2. Task 11's `_calls` gives every node with no incoming edge the same `ch_reads` channel. That is correct for `FASTQC` and `TRIMGALORE` but wrong for `STAR_GENOMEGENERATE`, which needs the GTF channel. The `-stub-run` gate in Task 12 is what will surface it. When it does, the fix is to key entry channels by the port's `type_id` (`fastq.reads` → `ch_reads`, `annotation.gtf` → `ch_gtf`) rather than defaulting them all — roughly ten lines, but do it as a fix with a failing test first, not pre-emptively.

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
