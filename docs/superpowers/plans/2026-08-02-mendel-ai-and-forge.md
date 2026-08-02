# Mendel — AI Adapters and Forge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the three declared runtime AI points and the offline contract forge, turning a typed-goal compiler into a prompt-driven one without weakening determinism.

**Architecture:** `mendel-ai` implements the `Protocol` ports that Plan 1 declared, backed by LiteLLM so any provider works. A `DecisionStore` persists every resolution and replays it on rerun, which is how reproducibility survives having a model in the loop. `mendel-forge` is an offline batch tool: it ingests nf-core `meta.yml`, drafts contracts, and queues them for human approval — never writing to the registry directly.

**Tech Stack:** Python 3.12, Pydantic v2, LiteLLM, pytest, `respx`-style recorded fixtures (no live model calls in tests).

## Global Constraints

- **Plan 1 must be complete and green before starting this plan.** Every task here consumes types it defined.
- `comeni-core`, `mendel-resolver`, `mendel-compiler` remain pure. The Task 1 purity guard from Plan 1 must still pass — if a change to those packages requires an LLM import, the design is wrong.
- **No test in this plan may call a live model.** All model interaction is tested against recorded fixtures committed to the repo.
- LiteLLM is the only model interface. No direct `anthropic` or `openai` SDK imports.
- Every model call sets `temperature=0` and pins a model id from config. Both go into the `DecisionRecord`.
- Model outputs are parsed into Pydantic models. A parse failure is a retry, then a hard failure — never a silent fallback.
- The forge writes to `proposals/`, never to `contracts/`. Only human approval moves a file across that boundary.
- Repair proposes IR patches. Any change to generated `.nf` text is a last resort that sets `PipelineIR.diverged = True`.
- Repair is bounded to 3 attempts.
- Ruff line length 100. `uv run ruff check` and `uv run pytest` pass before every commit.

---

## File Structure

```
packages/
├─ mendel-ai/
│  ├─ pyproject.toml
│  ├─ src/mendel_ai/
│  │  ├─ __init__.py
│  │  ├─ client.py               LiteLLM wrapper: pinned model, temp 0, structured parse
│  │  ├─ extract.py              prompt -> Goal (runtime AI point 1)
│  │  ├─ ambiguity.py            LLMAmbiguityResolver (runtime AI point 2)
│  │  ├─ repair.py               RepairProposer (runtime AI point 3)
│  │  └─ store.py                DecisionStore — persist and replay
│  └─ tests/fixtures/            recorded model responses
└─ mendel-forge/
   ├─ pyproject.toml
   ├─ src/mendel_forge/
   │  ├─ __init__.py
   │  ├─ sources.py              MetaYmlSource — nf-core ingestion
   │  ├─ draft.py                AI drafting of contracts
   │  ├─ proposal.py             Proposal model + approval queue
   │  └─ cli.py                  `forge ingest` / `forge approve`
   └─ tests/
proposals/                       drafted, awaiting human approval
```

Also modified: `packages/mendel-resolver/src/mendel_resolver/ports.py` (add two Protocols), `packages/mendel-compiler/src/mendel_compiler/cli.py` (wire the repair loop), `packages/comeni-core/src/comeni_core/ir.py` (add `diverged`).

---

### Task 1: The LiteLLM client

**Files:**
- Create: `packages/mendel-ai/pyproject.toml`, `src/mendel_ai/__init__.py`, `src/mendel_ai/client.py`
- Test: `packages/mendel-ai/tests/test_client.py`

**Interfaces:**
- Consumes: nothing from earlier packages
- Produces: `ModelConfig(model: str, temperature: float = 0.0, max_retries: int = 2)`; `ModelClient(config, completion_fn=None)`; `ModelClient.structured(prompt: str, schema: type[T], system: str = "") -> T`; `ModelParseError`

`completion_fn` is injected so every test runs against a recorded fixture instead of the network.

- [ ] **Step 1: Write the failing test**

```python
import json

import pytest
from mendel_ai.client import ModelClient, ModelConfig, ModelParseError
from pydantic import BaseModel


class Answer(BaseModel):
    value: int
    why: str


def _fake_completion(response: str):
    calls = []

    def completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": response}}]}

    completion.calls = calls
    return completion


def test_parses_a_structured_response():
    fn = _fake_completion(json.dumps({"value": 2, "why": "reverse stranded"}))
    client = ModelClient(ModelConfig(model="claude-opus-5"), completion_fn=fn)
    answer = client.structured("what strandedness flag?", Answer)
    assert answer.value == 2
    assert answer.why == "reverse stranded"


def test_pins_model_and_forces_temperature_zero():
    fn = _fake_completion(json.dumps({"value": 1, "why": "x"}))
    ModelClient(ModelConfig(model="claude-opus-5"), completion_fn=fn).structured("q", Answer)
    assert fn.calls[0]["model"] == "claude-opus-5"
    assert fn.calls[0]["temperature"] == 0.0


def test_strips_markdown_fences_before_parsing():
    fn = _fake_completion('```json\n{"value": 3, "why": "fenced"}\n```')
    client = ModelClient(ModelConfig(model="m"), completion_fn=fn)
    assert client.structured("q", Answer).value == 3


def test_retries_then_raises_on_unparseable_output():
    fn = _fake_completion("not json at all")
    client = ModelClient(ModelConfig(model="m", max_retries=2), completion_fn=fn)
    with pytest.raises(ModelParseError):
        client.structured("q", Answer)
    assert len(fn.calls) == 3  # initial + 2 retries


def test_retry_prompt_includes_the_parse_error():
    fn = _fake_completion("nope")
    client = ModelClient(ModelConfig(model="m", max_retries=1), completion_fn=fn)
    with pytest.raises(ModelParseError):
        client.structured("q", Answer)
    assert "previous response could not be parsed" in fn.calls[1]["messages"][-1]["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-ai/tests/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_ai'`

- [ ] **Step 3: Create the package**

`packages/mendel-ai/pyproject.toml`:

```toml
[project]
name = "mendel-ai"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["comeni-core", "mendel-resolver", "pydantic>=2.9", "litellm>=1.50"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mendel_ai"]
```

`src/mendel_ai/__init__.py`:

```python
"""Mendel's AI adapters: the only package in Mendel that talks to models."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Write `client.py`**

```python
"""LiteLLM wrapper. Pinned model, temperature 0, structured output or failure."""

import json
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class ModelParseError(RuntimeError):
    """Raised when the model's output cannot be parsed into the requested schema."""


class ModelConfig(BaseModel):
    model: str
    temperature: float = 0.0
    max_retries: int = 2


def _default_completion(**kwargs: Any) -> Any:
    from litellm import completion

    return completion(**kwargs)


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        return "\n".join(lines)
    return stripped


class ModelClient:
    def __init__(
        self,
        config: ModelConfig,
        completion_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config
        self._completion = completion_fn or _default_completion

    def structured(self, prompt: str, schema: type[T], system: str = "") -> T:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error = ""
        for attempt in range(self.config.max_retries + 1):
            if attempt > 0:
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your previous response could not be parsed: {last_error}. "
                        f"Reply with JSON matching this schema and nothing else: "
                        f"{json.dumps(schema.model_json_schema())}"
                    ),
                })
            response = self._completion(
                model=self.config.model,
                temperature=self.config.temperature,
                messages=list(messages),
            )
            content = response["choices"][0]["message"]["content"]
            try:
                return schema.model_validate_json(_strip_fences(content))
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)[:300]

        raise ModelParseError(
            f"could not parse {schema.__name__} after {self.config.max_retries + 1} attempts: {last_error}"
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv sync && uv run pytest packages/mendel-ai/tests/test_client.py -v && uv run ruff check .`
Expected: PASS, 5 tests.

- [ ] **Step 6: Confirm the purity guard still passes**

Run: `uv run pytest tests/test_purity.py -v`
Expected: PASS — `mendel-ai` is not in `PURE_PACKAGES`, and nothing pure imports it.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-ai/
git commit -m "feat(ai): LiteLLM client with pinned model and structured parsing"
```

---

### Task 2: Declare the remaining ports

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/ports.py`
- Modify: `packages/comeni-core/src/comeni_core/ir.py`
- Test: `packages/mendel-resolver/tests/test_ports.py`

**Interfaces:**
- Consumes: `Goal` (Plan 1 Task 6), `PipelineIR` (Plan 1 Task 4)
- Produces: `GoalExtractor` Protocol with `extract(self, prompt: str) -> Goal`; `RepairProposer` Protocol with `propose(self, ir: PipelineIR, failure: str) -> IRPatch`; `IRPatch(kind, node_id, contract_id, param_name, value, reason)`; `PipelineIR.diverged: bool`

Declaring ports in the pure package keeps the dependency arrow pointing the right way: `mendel-ai` depends on `mendel-resolver`, never the reverse.

- [ ] **Step 1: Write the failing test**

```python
from comeni_core.ir import PipelineIR
from mendel_resolver.ports import IRPatch, PatchKind


def test_patch_kinds_cover_the_three_repair_moves():
    assert set(PatchKind) == {PatchKind.INSERT_NODE, PatchKind.SET_PARAM, PatchKind.SWAP_NODE}


def test_insert_patch_carries_the_contract_to_insert():
    patch = IRPatch(
        kind=PatchKind.INSERT_NODE,
        node_id="featurecounts",
        contract_id="nf-core/samtools/sort@1.21.0",
        reason="featureCounts requires coordinate-sorted input",
    )
    assert patch.contract_id == "nf-core/samtools/sort@1.21.0"


def test_set_param_patch_carries_name_and_value():
    patch = IRPatch(
        kind=PatchKind.SET_PARAM,
        node_id="star_align",
        param_name="seq_platform",
        value="illumina",
        reason="platform tag missing from read group",
    )
    assert patch.param_name == "seq_platform"
    assert patch.value == "illumina"


def test_ir_defaults_to_not_diverged():
    assert PipelineIR().diverged is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-resolver/tests/test_ports.py -v`
Expected: FAIL with `ImportError: cannot import name 'IRPatch'`

- [ ] **Step 3: Add `diverged` to the IR**

In `packages/comeni-core/src/comeni_core/ir.py`, add to `PipelineIR`:

```python
    diverged: bool = False
    """True when generated Nextflow was text-patched and no longer matches this IR."""
```

- [ ] **Step 4: Add the ports**

Append to `packages/mendel-resolver/src/mendel_resolver/ports.py`:

```python
from enum import StrEnum
from typing import Any

from comeni_core.ir import PipelineIR
from mendel_resolver.goal import Goal


class GoalExtractor(Protocol):
    """Turns free text into a typed Goal. Runtime AI point 1.

    The Goal it returns is shown to the user for correction before anything runs.
    """

    def extract(self, prompt: str) -> Goal: ...


class PatchKind(StrEnum):
    INSERT_NODE = "insert_node"
    SET_PARAM = "set_param"
    SWAP_NODE = "swap_node"


class IRPatch(BaseModel):
    kind: PatchKind
    node_id: str
    contract_id: str | None = None
    param_name: str | None = None
    value: Any = None
    reason: str


class RepairProposer(Protocol):
    """Proposes an IR-level fix for a failed compilation. Runtime AI point 3.

    MUST return an IRPatch. Implementations never edit generated Nextflow text.
    """

    def propose(self, ir: PipelineIR, failure: str) -> IRPatch: ...
```

Add `from pydantic import BaseModel` to the imports at the top of the file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-resolver/tests/ packages/comeni-core/tests/ tests/test_purity.py -v && uv run ruff check .`
Expected: PASS — 4 new tests, and the purity guard still green because Protocols carry no implementation.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-resolver/src/mendel_resolver/ports.py packages/comeni-core/src/comeni_core/ir.py packages/mendel-resolver/tests/test_ports.py
git commit -m "feat(resolver): declare GoalExtractor and RepairProposer ports"
```

---

### Task 3: Prompt to Goal extraction

**Files:**
- Create: `packages/mendel-ai/src/mendel_ai/extract.py`
- Create: `packages/mendel-ai/tests/fixtures/extract_rnaseq.json`
- Test: `packages/mendel-ai/tests/test_extract.py`

**Interfaces:**
- Consumes: `ModelClient` (Task 1), `Goal`/`GoalInput`/`DataProfile` (Plan 1 Task 6), `Vocabulary` (Plan 1 Task 2)
- Produces: `LLMGoalExtractor(client: ModelClient, vocab: Vocabulary)` implementing `GoalExtractor`; `UnknownTypeInGoalError`

The vocabulary is passed in so the model is told which type ids exist. An extractor that invents `rna.fastq` is worse than one that fails.

- [ ] **Step 1: Write the failing test**

```python
import json

import pytest
from comeni_core.vocabulary import Vocabulary
from mendel_ai.client import ModelClient, ModelConfig
from mendel_ai.extract import LLMGoalExtractor, UnknownTypeInGoalError

FIXTURE = {
    "have": [{"type_id": "fastq.reads", "states": []}, {"type_id": "annotation.gtf", "states": []}],
    "want": ["counts.matrix"],
    "constraints": {},
    "profile": {"read_length": 150, "strandedness": "reverse", "n_samples": 12, "paired": True},
}


def _client(payload):
    def completion(**kwargs):
        completion.last = kwargs
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    return ModelClient(ModelConfig(model="m"), completion_fn=completion), completion


@pytest.fixture
def vocab(tmp_path):
    for name in ["fastq.reads", "annotation.gtf", "counts.matrix"]:
        (tmp_path / f"{name}.yml").write_text("states: []\n")
    return Vocabulary.load(tmp_path)


def test_extracts_a_goal_from_prose(vocab):
    client, _ = _client(FIXTURE)
    goal = LLMGoalExtractor(client, vocab).extract(
        "human paired-end RNA-seq, 12 samples, I want a counts matrix"
    )
    assert [held.type_id for held in goal.have] == ["fastq.reads", "annotation.gtf"]
    assert goal.want == ["counts.matrix"]
    assert goal.profile.read_length == 150


def test_prompt_lists_the_available_type_ids(vocab):
    client, completion = _client(FIXTURE)
    LLMGoalExtractor(client, vocab).extract("anything")
    sent = completion.last["messages"][-1]["content"]
    for type_id in ["fastq.reads", "annotation.gtf", "counts.matrix"]:
        assert type_id in sent


def test_rejects_a_goal_referencing_an_unknown_type(vocab):
    bad = {**FIXTURE, "want": ["proteomics.spectra"]}
    client, _ = _client(bad)
    with pytest.raises(UnknownTypeInGoalError, match="proteomics.spectra"):
        LLMGoalExtractor(client, vocab).extract("anything")


def test_rejects_an_unknown_type_in_have(vocab):
    bad = {**FIXTURE, "have": [{"type_id": "nonsense.type", "states": []}]}
    client, _ = _client(bad)
    with pytest.raises(UnknownTypeInGoalError, match="nonsense.type"):
        LLMGoalExtractor(client, vocab).extract("anything")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-ai/tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_ai.extract'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Runtime AI point 1: free text to a typed Goal the user can correct."""

from comeni_core.vocabulary import UnknownTypeError, Vocabulary
from mendel_ai.client import ModelClient
from mendel_resolver.goal import Goal

SYSTEM = (
    "You translate a researcher's plain-language request into a typed goal for a "
    "bioinformatics pipeline builder. You never invent type ids. You only use type "
    "ids from the list you are given. If the request does not mention something, "
    "leave it null rather than guessing."
)


class UnknownTypeInGoalError(ValueError):
    """Raised when the extracted goal references a type id with no vocabulary entry."""


class LLMGoalExtractor:
    def __init__(self, client: ModelClient, vocab: Vocabulary) -> None:
        self._client = client
        self._vocab = vocab

    def extract(self, prompt: str) -> Goal:
        known = "\n".join(f"  - {type_id}" for type_id in sorted(self._vocab.types))
        goal = self._client.structured(
            (
                f"Available type ids:\n{known}\n\n"
                f"Researcher's request:\n{prompt}\n\n"
                "Return the goal as JSON."
            ),
            Goal,
            system=SYSTEM,
        )
        self._check(goal)
        return goal

    def _check(self, goal: Goal) -> None:
        referenced = [held.type_id for held in goal.have] + list(goal.want)
        for type_id in referenced:
            try:
                self._vocab.states_for(type_id)
            except UnknownTypeError as exc:
                raise UnknownTypeInGoalError(
                    f"extracted goal references unknown type {type_id!r}"
                ) from exc
```

- [ ] **Step 4: Record the fixture**

Write the `FIXTURE` dict above to `packages/mendel-ai/tests/fixtures/extract_rnaseq.json` so later tasks and Plan 3 can reuse the same recorded response.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-ai/tests/ -v && uv run ruff check .`
Expected: PASS, 4 new tests.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-ai/src/mendel_ai/extract.py packages/mendel-ai/tests/
git commit -m "feat(ai): prompt-to-goal extraction constrained by the vocabulary"
```

---

### Task 4: The decision store

**Files:**
- Create: `packages/mendel-ai/src/mendel_ai/store.py`
- Test: `packages/mendel-ai/tests/test_store.py`

**Interfaces:**
- Consumes: `Ambiguity`, `Resolution`, `DecisionRecord` (Plan 1 Task 4)
- Produces: `DecisionStore(path: Path)`; `.lookup(ambiguity) -> Resolution | None`; `.record(ambiguity, resolution) -> None`; `.override(key, value, by) -> None`; `ReplayingResolver(inner, store)` implementing `AmbiguityResolver`

This is what makes determinism survive having a model in the loop: the first run pays for the call, every later run replays it. A human override always wins over both.

- [ ] **Step 1: Write the failing test**

```python
from comeni_core.decision import Ambiguity, Resolution
from mendel_ai.store import DecisionStore, ReplayingResolver


class CountingResolver:
    def __init__(self):
        self.calls = 0

    def resolve(self, ambiguity):
        self.calls += 1
        return Resolution(chosen="star", reason="model picked star", confidence=0.8, resolved_by="model")


def test_records_and_replays_a_resolution(tmp_path):
    store = DecisionStore(tmp_path / "decisions.jsonl")
    ambiguity = Ambiguity(node_id="align", subject="aligner", candidates=["star", "hisat2"])
    inner = CountingResolver()
    resolver = ReplayingResolver(inner, store)

    first = resolver.resolve(ambiguity)
    second = resolver.resolve(ambiguity)

    assert first.chosen == second.chosen == "star"
    assert inner.calls == 1, "second resolution must come from the store, not the model"


def test_replay_survives_a_new_store_instance(tmp_path):
    path = tmp_path / "decisions.jsonl"
    ambiguity = Ambiguity(node_id="align", subject="aligner", candidates=["star"])
    inner = CountingResolver()
    ReplayingResolver(inner, DecisionStore(path)).resolve(ambiguity)
    ReplayingResolver(inner, DecisionStore(path)).resolve(ambiguity)
    assert inner.calls == 1


def test_replayed_resolution_is_marked_as_replayed(tmp_path):
    store = DecisionStore(tmp_path / "d.jsonl")
    ambiguity = Ambiguity(node_id="align", subject="aligner", candidates=["star"])
    resolver = ReplayingResolver(CountingResolver(), store)
    resolver.resolve(ambiguity)
    assert resolver.resolve(ambiguity).resolved_by == "replay"


def test_human_override_beats_the_stored_model_answer(tmp_path):
    store = DecisionStore(tmp_path / "d.jsonl")
    ambiguity = Ambiguity(node_id="align", subject="aligner", candidates=["star", "hisat2"])
    resolver = ReplayingResolver(CountingResolver(), store)
    resolver.resolve(ambiguity)
    store.override(ambiguity.key(), "hisat2", by="rafael")
    result = resolver.resolve(ambiguity)
    assert result.chosen == "hisat2"
    assert result.resolved_by == "human"


def test_different_candidates_are_a_different_decision(tmp_path):
    store = DecisionStore(tmp_path / "d.jsonl")
    inner = CountingResolver()
    resolver = ReplayingResolver(inner, store)
    resolver.resolve(Ambiguity(node_id="a", subject="s", candidates=["x"]))
    resolver.resolve(Ambiguity(node_id="a", subject="s", candidates=["x", "y"]))
    assert inner.calls == 2, "changing the option set invalidates the stored answer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-ai/tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_ai.store'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Persist resolved ambiguities and replay them, so reruns do not re-ask the model."""

import hashlib
import json
from pathlib import Path

from comeni_core.decision import Ambiguity, Resolution
from mendel_resolver.ports import AmbiguityResolver


def _fingerprint(ambiguity: Ambiguity) -> str:
    payload = json.dumps(
        {"key": ambiguity.key(), "candidates": sorted(map(str, ambiguity.candidates))},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class DecisionStore:
    """Append-only JSONL. Last entry for a fingerprint wins; overrides win outright."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def _append(self, entry: dict) -> None:
        with self.path.open("a") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def lookup(self, ambiguity: Ambiguity) -> Resolution | None:
        fingerprint = _fingerprint(ambiguity)
        key = ambiguity.key()

        for entry in reversed(self._entries()):
            if entry.get("kind") == "override" and entry["key"] == key:
                return Resolution(
                    chosen=entry["chosen"],
                    reason=f"human override by {entry['by']}",
                    confidence=1.0,
                    resolved_by="human",
                )
        for entry in reversed(self._entries()):
            if entry.get("kind") == "resolution" and entry["fingerprint"] == fingerprint:
                return Resolution(
                    chosen=entry["chosen"],
                    reason=entry["reason"],
                    confidence=entry["confidence"],
                    resolved_by="replay",
                )
        return None

    def record(self, ambiguity: Ambiguity, resolution: Resolution) -> None:
        self._append({
            "kind": "resolution",
            "fingerprint": _fingerprint(ambiguity),
            "key": ambiguity.key(),
            "candidates": [str(c) for c in ambiguity.candidates],
            "chosen": resolution.chosen,
            "reason": resolution.reason,
            "confidence": resolution.confidence,
            "resolved_by": resolution.resolved_by,
        })

    def override(self, key: str, value: object, by: str) -> None:
        self._append({"kind": "override", "key": key, "chosen": value, "by": by})


class ReplayingResolver:
    """Wraps any AmbiguityResolver with store-backed replay."""

    def __init__(self, inner: AmbiguityResolver, store: DecisionStore) -> None:
        self._inner = inner
        self._store = store

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        cached = self._store.lookup(ambiguity)
        if cached is not None:
            return cached
        resolution = self._inner.resolve(ambiguity)
        self._store.record(ambiguity, resolution)
        return resolution
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-ai/tests/test_store.py -v && uv run ruff check .`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-ai/src/mendel_ai/store.py packages/mendel-ai/tests/test_store.py
git commit -m "feat(ai): decision store with replay and human override"
```

---

### Task 5: The LLM ambiguity resolver

**Files:**
- Create: `packages/mendel-ai/src/mendel_ai/ambiguity.py`
- Test: `packages/mendel-ai/tests/test_ambiguity.py`

**Interfaces:**
- Consumes: `ModelClient` (Task 1), `Ambiguity`/`Resolution` (Plan 1 Task 4), `AmbiguityResolver` (Plan 1 Task 7)
- Produces: `LLMAmbiguityResolver(client, model_id)` implementing `AmbiguityResolver`; `ModelChoice(chosen, reasoning, confidence)`

- [ ] **Step 1: Write the failing test**

```python
import json

import pytest
from comeni_core.decision import Ambiguity
from mendel_ai.ambiguity import LLMAmbiguityResolver, OffMenuChoiceError
from mendel_ai.client import ModelClient, ModelConfig


def _resolver(payload):
    def completion(**kwargs):
        completion.last = kwargs
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    client = ModelClient(ModelConfig(model="claude-opus-5"), completion_fn=completion)
    return LLMAmbiguityResolver(client), completion


def test_chooses_from_the_candidates():
    resolver, _ = _resolver({"chosen": "star", "reasoning": "150bp reads suit STAR", "confidence": 0.9})
    result = resolver.resolve(Ambiguity(node_id="a", subject="aligner", candidates=["star", "hisat2"]))
    assert result.chosen == "star"
    assert result.confidence == 0.9
    assert "STAR" in result.reason


def test_records_which_model_answered():
    resolver, _ = _resolver({"chosen": "star", "reasoning": "r", "confidence": 0.5})
    result = resolver.resolve(Ambiguity(node_id="a", subject="aligner", candidates=["star"]))
    assert result.resolved_by == "claude-opus-5"


def test_prompt_includes_every_candidate_and_the_context():
    resolver, completion = _resolver({"chosen": "star", "reasoning": "r", "confidence": 0.5})
    resolver.resolve(Ambiguity(
        node_id="a", subject="aligner", candidates=["star", "hisat2"],
        context={"read_length": 150},
    ))
    sent = completion.last["messages"][-1]["content"]
    assert "star" in sent and "hisat2" in sent and "read_length" in sent


def test_rejects_a_choice_outside_the_candidate_list():
    resolver, _ = _resolver({"chosen": "bowtie2", "reasoning": "r", "confidence": 0.9})
    with pytest.raises(OffMenuChoiceError, match="bowtie2"):
        resolver.resolve(Ambiguity(node_id="a", subject="aligner", candidates=["star", "hisat2"]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-ai/tests/test_ambiguity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_ai.ambiguity'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Runtime AI point 2: tier-4 resolution. Always flagged, always recorded."""

from pydantic import BaseModel

from comeni_core.decision import Ambiguity, Resolution
from mendel_ai.client import ModelClient

SYSTEM = (
    "You choose between bioinformatics tool and parameter options. You MUST pick "
    "exactly one option from the candidate list given — never suggest anything else. "
    "State your reasoning in one or two sentences a biologist would understand. "
    "Give an honest confidence: low confidence is useful information, not a failure."
)


class OffMenuChoiceError(ValueError):
    """Raised when the model picks something that was not offered."""


class ModelChoice(BaseModel):
    chosen: str
    reasoning: str
    confidence: float


class LLMAmbiguityResolver:
    def __init__(self, client: ModelClient) -> None:
        self._client = client

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        candidates = [str(c) for c in ambiguity.candidates]
        options = "\n".join(f"  - {c}" for c in candidates)
        context = "\n".join(f"  {k}: {v}" for k, v in sorted(ambiguity.context.items()))
        choice = self._client.structured(
            (
                f"Decision needed: {ambiguity.subject}\n"
                f"Pipeline step: {ambiguity.node_id}\n\n"
                f"Candidates:\n{options}\n\n"
                f"Known context:\n{context or '  (none)'}\n"
            ),
            ModelChoice,
            system=SYSTEM,
        )
        if choice.chosen not in candidates:
            raise OffMenuChoiceError(
                f"model chose {choice.chosen!r}, which is not among {candidates}"
            )
        return Resolution(
            chosen=choice.chosen,
            reason=choice.reasoning,
            confidence=choice.confidence,
            resolved_by=self._client.config.model,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-ai/tests/test_ambiguity.py -v && uv run ruff check .`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-ai/src/mendel_ai/ambiguity.py packages/mendel-ai/tests/test_ambiguity.py
git commit -m "feat(ai): tier-4 ambiguity resolver constrained to offered candidates"
```

---

### Task 6: Repair proposals and the bounded loop

**Files:**
- Create: `packages/mendel-ai/src/mendel_ai/repair.py`
- Create: `packages/mendel-compiler/src/mendel_compiler/loop.py`
- Test: `packages/mendel-ai/tests/test_repair.py`, `packages/mendel-compiler/tests/test_loop.py`

**Interfaces:**
- Consumes: `IRPatch`/`PatchKind`/`RepairProposer` (Task 2), `Gate`/`GateResult`/`run_gate` (Plan 1 Task 12), `emit` (Plan 1 Task 11)
- Produces: `LLMRepairProposer(client, registry)` implementing `RepairProposer`; `apply_patch(ir, patch, registry) -> PipelineIR`; `compile_with_repair(ir, registry, workdir, proposer, gate=Gate.STUB, max_attempts=3) -> RepairOutcome`; `RepairOutcome(ir, source, passed, attempts, patches)`

- [ ] **Step 1: Write the failing test for patch application**

`packages/mendel-compiler/tests/test_loop.py`:

```python
import pathlib

from comeni_core.ir import IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_compiler.gates import Gate, GateResult
from mendel_compiler.loop import apply_patch, compile_with_repair
from mendel_resolver.ports import IRPatch, PatchKind

ROOT = pathlib.Path(__file__).parent.parent.parent.parent


def _registry():
    return Registry.load(ROOT / "contracts", Vocabulary.load(ROOT / "vocabularies"))


def _ir():
    return PipelineIR(nodes=[IRNode(id="featurecounts", contract_id="nf-core/subread/featurecounts@2.0.6")])


def test_insert_node_patch_adds_a_node_before_the_target():
    patched = apply_patch(
        _ir(),
        IRPatch(kind=PatchKind.INSERT_NODE, node_id="featurecounts",
                contract_id="nf-core/samtools/sort@1.21.0", reason="needs sorted input"),
        _registry(),
    )
    assert [n.id for n in patched.nodes] == ["samtools_sort", "featurecounts"]


def test_set_param_patch_marks_the_value_as_ambiguous_tier():
    patched = apply_patch(
        _ir(),
        IRPatch(kind=PatchKind.SET_PARAM, node_id="featurecounts", param_name="strandedness",
                value=0, reason="library appears unstranded"),
        _registry(),
    )
    value = patched.nodes[0].params["strandedness"]
    assert value.value == 0
    assert value.tier is Tier.AMBIGUOUS
    assert "repair" in value.reason


def test_patch_returns_a_new_ir_and_does_not_mutate_the_original():
    original = _ir()
    apply_patch(original, IRPatch(kind=PatchKind.SET_PARAM, node_id="featurecounts",
                                  param_name="x", value=1, reason="r"), _registry())
    assert original.nodes[0].params == {}


def test_loop_stops_at_the_first_green_gate():
    calls = []

    def gate_runner(gate, workdir):
        calls.append(gate)
        return GateResult(gate=gate, passed=True)

    outcome = compile_with_repair(_ir(), _registry(), pathlib.Path("/tmp/x"),
                                  proposer=None, gate_runner=gate_runner)
    assert outcome.passed is True
    assert outcome.attempts == 1
    assert outcome.patches == []


def test_loop_gives_up_after_three_attempts():
    class AlwaysPatch:
        def propose(self, ir, failure):
            return IRPatch(kind=PatchKind.SET_PARAM, node_id="featurecounts",
                           param_name="x", value=1, reason="try again")

    def gate_runner(gate, workdir):
        return GateResult(gate=gate, passed=False, stderr="boom")

    outcome = compile_with_repair(_ir(), _registry(), pathlib.Path("/tmp/x"),
                                  proposer=AlwaysPatch(), gate_runner=gate_runner)
    assert outcome.passed is False
    assert outcome.attempts == 3
    assert len(outcome.patches) == 3


def test_loop_records_every_patch_it_applied():
    class OnePatch:
        def __init__(self):
            self.n = 0

        def propose(self, ir, failure):
            self.n += 1
            return IRPatch(kind=PatchKind.SET_PARAM, node_id="featurecounts",
                           param_name="strandedness", value=self.n, reason=f"attempt {self.n}")

    results = iter([False, True])

    def gate_runner(gate, workdir):
        return GateResult(gate=gate, passed=next(results), stderr="boom")

    outcome = compile_with_repair(_ir(), _registry(), pathlib.Path("/tmp/x"),
                                  proposer=OnePatch(), gate_runner=gate_runner)
    assert outcome.passed is True
    assert [p.reason for p in outcome.patches] == ["attempt 1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-compiler/tests/test_loop.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_compiler.loop'`

- [ ] **Step 3: Write `loop.py`**

```python
"""The bounded repair cycle. Patches the IR and re-emits; never edits .nf text."""

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

from comeni_core.ir import IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.registry import Registry
from mendel_compiler.emit import emit
from mendel_compiler.gates import Gate, GateResult, run_gate
from mendel_resolver.ports import IRPatch, PatchKind, RepairProposer


class RepairOutcome(BaseModel):
    ir: PipelineIR
    source: str
    passed: bool
    attempts: int
    patches: list[IRPatch] = Field(default_factory=list)


def apply_patch(ir: PipelineIR, patch: IRPatch, registry: Registry) -> PipelineIR:
    """Return a new IR with the patch applied. Never mutates the input."""
    patched = ir.model_copy(deep=True)

    if patch.kind is PatchKind.SET_PARAM:
        for node in patched.nodes:
            if node.id == patch.node_id:
                node.params[patch.param_name] = ResolvedValue(
                    value=patch.value,
                    tier=Tier.AMBIGUOUS,
                    reason=f"repair: {patch.reason}",
                )
        return patched

    if patch.kind is PatchKind.INSERT_NODE:
        contract = registry.get(patch.contract_id)
        new_node = IRNode(id=contract.nf_process.lower(), contract_id=contract.id)
        index = next(i for i, n in enumerate(patched.nodes) if n.id == patch.node_id)
        patched.nodes.insert(index, new_node)
        return patched

    if patch.kind is PatchKind.SWAP_NODE:
        contract = registry.get(patch.contract_id)
        for i, node in enumerate(patched.nodes):
            if node.id == patch.node_id:
                patched.nodes[i] = IRNode(id=contract.nf_process.lower(), contract_id=contract.id)
        return patched

    raise ValueError(f"unhandled patch kind {patch.kind}")


def compile_with_repair(
    ir: PipelineIR,
    registry: Registry,
    workdir: Path,
    proposer: RepairProposer | None,
    gate: Gate = Gate.STUB,
    max_attempts: int = 3,
    gate_runner: Callable[[Gate, Path], GateResult] = run_gate,
) -> RepairOutcome:
    patches: list[IRPatch] = []
    current = ir

    for attempt in range(1, max_attempts + 1):
        source = emit(current, registry)
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "main.nf").write_text(source)

        result = gate_runner(gate, workdir)
        if result.passed:
            return RepairOutcome(
                ir=current, source=source, passed=True, attempts=attempt, patches=patches
            )
        if proposer is None or attempt == max_attempts:
            return RepairOutcome(
                ir=current, source=source, passed=False, attempts=attempt, patches=patches
            )

        patch = proposer.propose(current, result.stderr)
        patches.append(patch)
        current = apply_patch(current, patch, registry)

    raise AssertionError("unreachable")
```

- [ ] **Step 4: Write the failing test for the proposer**

`packages/mendel-ai/tests/test_repair.py`:

```python
import json
import pathlib

import pytest
from comeni_core.ir import IRNode, PipelineIR
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_ai.client import ModelClient, ModelConfig
from mendel_ai.repair import LLMRepairProposer, UnknownPatchTargetError

ROOT = pathlib.Path(__file__).parent.parent.parent.parent


def _proposer(payload):
    def completion(**kwargs):
        completion.last = kwargs
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    registry = Registry.load(ROOT / "contracts", Vocabulary.load(ROOT / "vocabularies"))
    return LLMRepairProposer(ModelClient(ModelConfig(model="m"), completion_fn=completion), registry), completion


def _ir():
    return PipelineIR(nodes=[IRNode(id="featurecounts", contract_id="nf-core/subread/featurecounts@2.0.6")])


def test_proposes_an_insert_patch():
    proposer, _ = _proposer({
        "kind": "insert_node", "node_id": "featurecounts",
        "contract_id": "nf-core/samtools/sort@1.21.0",
        "reason": "featureCounts needs coordinate-sorted BAM",
    })
    patch = proposer.propose(_ir(), "ERROR: input BAM is not sorted")
    assert patch.contract_id == "nf-core/samtools/sort@1.21.0"


def test_prompt_includes_the_failure_text_and_available_contracts():
    proposer, completion = _proposer({
        "kind": "set_param", "node_id": "featurecounts", "param_name": "s", "value": 0, "reason": "r"
    })
    proposer.propose(_ir(), "ERROR: unsorted input")
    sent = completion.last["messages"][-1]["content"]
    assert "unsorted input" in sent
    assert "nf-core/samtools/sort@1.21.0" in sent


def test_rejects_a_patch_targeting_a_node_not_in_the_ir():
    proposer, _ = _proposer({
        "kind": "set_param", "node_id": "nonexistent", "param_name": "s", "value": 0, "reason": "r"
    })
    with pytest.raises(UnknownPatchTargetError, match="nonexistent"):
        proposer.propose(_ir(), "boom")


def test_rejects_an_insert_of_an_unregistered_contract():
    proposer, _ = _proposer({
        "kind": "insert_node", "node_id": "featurecounts",
        "contract_id": "nf-core/invented@9.9.9", "reason": "r",
    })
    with pytest.raises(UnknownPatchTargetError, match="nf-core/invented"):
        proposer.propose(_ir(), "boom")
```

- [ ] **Step 5: Write `repair.py`**

```python
"""Runtime AI point 3: propose an IR-level fix for a failed compilation."""

from comeni_core.ir import PipelineIR
from comeni_core.registry import Registry
from mendel_ai.client import ModelClient
from mendel_resolver.ports import IRPatch, PatchKind

SYSTEM = (
    "You fix broken bioinformatics pipelines by proposing ONE change to the pipeline's "
    "intermediate representation — never by editing generated code. You may insert a "
    "module, set a parameter, or swap a module. Only use module ids from the list given."
)


class UnknownPatchTargetError(ValueError):
    """Raised when a proposed patch names a node or contract that does not exist."""


class LLMRepairProposer:
    def __init__(self, client: ModelClient, registry: Registry) -> None:
        self._client = client
        self._registry = registry

    def propose(self, ir: PipelineIR, failure: str) -> IRPatch:
        nodes = "\n".join(f"  - {n.id} ({n.contract_id})" for n in ir.nodes)
        available = "\n".join(f"  - {c.id}" for c in self._registry.all())
        patch = self._client.structured(
            (
                f"The pipeline failed to validate.\n\n"
                f"Error output:\n{failure[:2000]}\n\n"
                f"Current pipeline nodes:\n{nodes}\n\n"
                f"Modules you may insert or swap in:\n{available}\n\n"
                "Propose exactly one IR patch."
            ),
            IRPatch,
            system=SYSTEM,
        )
        self._check(patch, ir)
        return patch

    def _check(self, patch: IRPatch, ir: PipelineIR) -> None:
        if patch.node_id not in {node.id for node in ir.nodes}:
            raise UnknownPatchTargetError(f"patch targets unknown node {patch.node_id!r}")
        if patch.kind in (PatchKind.INSERT_NODE, PatchKind.SWAP_NODE):
            if patch.contract_id is None:
                raise UnknownPatchTargetError(f"{patch.kind} requires a contract_id")
            try:
                self._registry.get(patch.contract_id)
            except KeyError as exc:
                raise UnknownPatchTargetError(
                    f"patch references unregistered contract {patch.contract_id!r}"
                ) from exc
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-ai/tests/test_repair.py packages/mendel-compiler/tests/test_loop.py -v && uv run ruff check .`
Expected: PASS, 10 tests.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-ai/src/mendel_ai/repair.py packages/mendel-compiler/src/mendel_compiler/loop.py packages/mendel-ai/tests/test_repair.py packages/mendel-compiler/tests/test_loop.py
git commit -m "feat(ai,compiler): IR-patch repair proposals and bounded repair loop"
```

---

### Task 7: Wire AI into the CLI

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Create: `packages/mendel-compiler/src/mendel_compiler/config.py`
- Test: `tests/test_end_to_end_ai.py`

**Interfaces:**
- Consumes: everything above
- Produces: `MendelConfig(model, decisions_path, use_ai)`; CLI gains `--prompt`, `--model`, `--no-ai`

`--no-ai` must keep working forever: it is how the deterministic guarantee stays testable.

- [ ] **Step 1: Write the failing test**

```python
import json
import pathlib

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent


def test_no_ai_flag_still_builds_from_a_typed_goal(tmp_path):
    code = main([
        "build", "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "p"), "--root", str(ROOT), "--no-ai",
    ])
    assert code == 0
    ir = json.loads((tmp_path / "p" / "pipeline.ir.json").read_text())
    for decision in ir["decisions"]:
        assert decision["resolved_by"] == "flag-only"


def test_replay_makes_a_second_build_identical_without_calling_the_model(tmp_path, monkeypatch):
    """Once decisions are stored, a rebuild must reproduce them with no model available.

    This is the reproducibility claim under test. The second build runs with a
    completion function that raises, so any model call fails the test outright.
    """
    out = tmp_path / "p"
    main([
        "build", "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(out), "--root", str(ROOT), "--no-ai",
    ])
    first = (out / "main.nf").read_text()

    def explode(**kwargs):
        raise AssertionError("a rebuild must replay decisions, not call the model")

    monkeypatch.setattr("mendel_ai.client._default_completion", explode)
    main([
        "build", "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(out), "--root", str(ROOT), "--no-ai",
    ])
    assert (out / "main.nf").read_text() == first


def test_decisions_file_is_written_under_the_output_directory(tmp_path):
    main([
        "build", "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"),
        "--out", str(tmp_path / "p"), "--root", str(ROOT), "--no-ai",
    ])
    assert (tmp_path / "p" / "decisions.jsonl").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_end_to_end_ai.py -v`
Expected: FAIL — `--no-ai` is not a recognised argument.

- [ ] **Step 3: Write `config.py`**

```python
"""Runtime configuration for the AI adapters."""

import os
from pathlib import Path

from pydantic import BaseModel


class MendelConfig(BaseModel):
    model: str = "claude-opus-5"
    use_ai: bool = True
    decisions_path: Path = Path("decisions.jsonl")

    @classmethod
    def from_env(cls) -> "MendelConfig":
        return cls(
            model=os.environ.get("MENDEL_MODEL", "claude-opus-5"),
            use_ai=os.environ.get("MENDEL_USE_AI", "1") != "0",
        )
```

- [ ] **Step 4: Wire the CLI**

In `cli.py`, add the arguments and build the resolver chain. Replace the fixed `resolve(goal, registry, rules)` call with:

```python
    parser.add_argument("--prompt", type=str, default=None)
    parser.add_argument("--model", type=str, default="claude-opus-5")
    parser.add_argument("--no-ai", action="store_true")
```

and after loading `registry`/`rules`:

```python
    from mendel_ai.store import DecisionStore, ReplayingResolver
    from mendel_resolver.ports import FlagOnlyResolver

    decisions_path = args.out / "decisions.jsonl"
    store = DecisionStore(decisions_path)

    if args.no_ai:
        inner = FlagOnlyResolver()
    else:
        from mendel_ai.ambiguity import LLMAmbiguityResolver
        from mendel_ai.client import ModelClient, ModelConfig

        inner = LLMAmbiguityResolver(ModelClient(ModelConfig(model=args.model)))

    resolver = ReplayingResolver(inner, store)

    if args.prompt is not None:
        if args.no_ai:
            parser.error("--prompt requires AI; drop --no-ai or pass --goal instead")
        from mendel_ai.client import ModelClient, ModelConfig
        from mendel_ai.extract import LLMGoalExtractor

        goal = LLMGoalExtractor(ModelClient(ModelConfig(model=args.model)), vocab).extract(args.prompt)
    else:
        goal = Goal.model_validate(yaml.safe_load(args.goal.read_text()))

    ir = resolve(goal, registry, rules, resolver=resolver)
```

Make `--goal` optional (`required=False`) and error if neither `--goal` nor `--prompt` is given. Move `args.out.mkdir(...)` above the `DecisionStore` construction.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS — including every Plan 1 test unchanged.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-compiler/ tests/test_end_to_end_ai.py
git commit -m "feat(compiler): wire AI extraction and resolution into the CLI behind --no-ai"
```

---

### Task 8: nf-core meta.yml ingestion

**Files:**
- Create: `packages/mendel-forge/pyproject.toml`, `src/mendel_forge/__init__.py`, `sources.py`
- Test: `packages/mendel-forge/tests/test_sources.py`

**Interfaces:**
- Consumes: nothing from `mendel-ai`
- Produces: `MetaYmlSource(modules_dir: Path)`; `.scan() -> list[RawModule]`; `RawModule(name, nf_process, nf_include, inputs, outputs, tool_names, description)`

This is pure parsing with no model involved — it is the 60% of the contract that `meta.yml` genuinely gives you.

- [ ] **Step 1: Write the failing test**

```python
from mendel_forge.sources import MetaYmlSource

META = """
name: "samtools_sort"
description: Sort SAM/BAM/CRAM file
tools:
  - samtools:
      description: SAM tools
input:
  - - meta:
        type: map
        description: Groovy Map containing sample information
    - bam:
        type: file
        description: BAM/CRAM/SAM file
        pattern: "*.{bam,cram,sam}"
output:
  - bam:
      - meta:
          type: map
      - "*.bam":
          type: file
          description: Sorted BAM file
          pattern: "*.{bam}"
"""

MAIN_NF = """
process SAMTOOLS_SORT {
    tag "$meta.id"
    input:
    tuple val(meta), path(bam)
    output:
    tuple val(meta), path("*.bam"), emit: bam
}
"""


def _module(tmp_path, name="samtools/sort"):
    directory = tmp_path / "modules" / "nf-core" / name
    directory.mkdir(parents=True)
    (directory / "meta.yml").write_text(META)
    (directory / "main.nf").write_text(MAIN_NF)
    return tmp_path / "modules"


def test_scan_finds_every_module_with_a_meta_yml(tmp_path):
    modules = _module(tmp_path)
    assert len(MetaYmlSource(modules).scan()) == 1


def test_extracts_the_process_name_from_main_nf(tmp_path):
    raw = MetaYmlSource(_module(tmp_path)).scan()[0]
    assert raw.nf_process == "SAMTOOLS_SORT"


def test_builds_the_include_path_without_the_nf_suffix(tmp_path):
    raw = MetaYmlSource(_module(tmp_path)).scan()[0]
    assert raw.nf_include == "modules/nf-core/samtools/sort/main"


def test_collects_input_and_output_names_with_patterns(tmp_path):
    raw = MetaYmlSource(_module(tmp_path)).scan()[0]
    assert "bam" in raw.inputs
    assert "bam" in raw.outputs
    assert raw.description.startswith("Sort SAM/BAM/CRAM")


def test_skips_directories_without_meta_yml(tmp_path):
    modules = _module(tmp_path)
    (modules / "nf-core" / "orphan").mkdir(parents=True)
    assert len(MetaYmlSource(modules).scan()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-forge/tests/test_sources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_forge'`

- [ ] **Step 3: Create the package and write `sources.py`**

`packages/mendel-forge/pyproject.toml`:

```toml
[project]
name = "mendel-forge"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["comeni-core", "mendel-ai", "pydantic>=2.9", "pyyaml>=6.0"]

[project.scripts]
forge = "mendel_forge.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mendel_forge"]
```

`src/mendel_forge/__init__.py`:

```python
"""The forge: ingest module sources, draft contracts, queue them for approval."""

__version__ = "0.1.0"
```

`src/mendel_forge/sources.py`:

```python
"""Ingest nf-core modules. Pure parsing — the 60% of a contract meta.yml gives you."""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_PROCESS = re.compile(r"^process\s+([A-Z0-9_]+)\s*\{", re.MULTILINE)


class RawModule(BaseModel):
    name: str
    nf_process: str
    nf_include: str
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    tool_names: list[str] = Field(default_factory=list)
    description: str = ""


def _flatten(entries: object, into: dict[str, str]) -> None:
    """meta.yml nests inputs/outputs in lists of dicts to arbitrary depth."""
    if isinstance(entries, dict):
        for key, value in entries.items():
            if key == "meta":
                continue
            pattern = value.get("pattern", "") if isinstance(value, dict) else ""
            if isinstance(value, dict) and "type" in value:
                into[key] = pattern
            else:
                _flatten(value, into)
    elif isinstance(entries, list):
        for entry in entries:
            _flatten(entry, into)


class MetaYmlSource:
    def __init__(self, modules_dir: Path) -> None:
        self._modules_dir = modules_dir

    def scan(self) -> list[RawModule]:
        found = []
        for meta_path in sorted(self._modules_dir.rglob("meta.yml")):
            directory = meta_path.parent
            main_nf = directory / "main.nf"
            if not main_nf.exists():
                continue
            match = _PROCESS.search(main_nf.read_text())
            if match is None:
                continue
            meta = yaml.safe_load(meta_path.read_text()) or {}

            inputs: dict[str, str] = {}
            outputs: dict[str, str] = {}
            _flatten(meta.get("input", []), inputs)
            _flatten(meta.get("output", []), outputs)

            relative = directory.relative_to(self._modules_dir.parent)
            found.append(
                RawModule(
                    name=meta.get("name", directory.name),
                    nf_process=match.group(1),
                    nf_include=f"{relative}/main",
                    inputs=inputs,
                    outputs=outputs,
                    tool_names=[
                        key for tool in meta.get("tools", []) for key in tool
                    ],
                    description=meta.get("description", ""),
                )
            )
        return found
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv sync && uv run pytest packages/mendel-forge/tests/test_sources.py -v && uv run ruff check .`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-forge/
git commit -m "feat(forge): nf-core meta.yml ingestion"
```

---

### Task 9: Contract drafting and the approval queue

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/draft.py`, `proposal.py`, `cli.py`
- Test: `packages/mendel-forge/tests/test_draft.py`, `test_proposal.py`

**Interfaces:**
- Consumes: `RawModule` (Task 8), `ModelClient` (Task 1), `Vocabulary` (Plan 1 Task 2), `ModuleContract` (Plan 1 Task 3)
- Produces: `ContractDrafter(client, vocab)`; `.draft(raw: RawModule) -> Proposal`; `Proposal(kind, target_path, body, source_module, drafted_by, rationale)`; `ProposalQueue(directory)` with `.add`, `.pending()`, `.approve(name, by, contracts_dir)`, `.reject(name, why)`; CLI `forge ingest --modules <dir>` and `forge approve <name> --by <who>`

The drafter proposes; it never writes to `contracts/`. That boundary is the entire point of the queue.

- [ ] **Step 1: Write the failing test for drafting**

```python
import json

import pytest
from comeni_core.vocabulary import Vocabulary
from mendel_ai.client import ModelClient, ModelConfig
from mendel_forge.draft import ContractDrafter, InvalidDraftError
from mendel_forge.sources import RawModule

RAW = RawModule(
    name="samtools_sort",
    nf_process="SAMTOOLS_SORT",
    nf_include="modules/nf-core/samtools/sort/main",
    inputs={"bam": "*.{bam,cram,sam}"},
    outputs={"bam": "*.{bam}"},
    tool_names=["samtools"],
    description="Sort SAM/BAM/CRAM file",
)

DRAFT = {
    "consumes": [{"name": "bam", "type_id": "alignment.bam", "state_required": []}],
    "produces": [{"name": "bam", "type_id": "alignment.bam", "state": ["coordinate_sorted"]}],
    "params": [],
    "rationale": "samtools sort always emits coordinate-sorted output by default",
}


@pytest.fixture
def vocab(tmp_path):
    (tmp_path / "alignment.bam.yml").write_text("states: [coordinate_sorted, name_sorted]\n")
    return Vocabulary.load(tmp_path)


def _drafter(payload, vocab):
    def completion(**kwargs):
        completion.last = kwargs
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    return ContractDrafter(ModelClient(ModelConfig(model="m"), completion_fn=completion), vocab), completion


def test_drafts_a_proposal_with_a_valid_contract_body(vocab):
    drafter, _ = _drafter(DRAFT, vocab)
    proposal = drafter.draft(RAW)
    assert proposal.kind == "contract"
    assert "coordinate_sorted" in proposal.body
    assert proposal.source_module == "samtools_sort"


def test_prompt_lists_the_allowed_types_and_their_states(vocab):
    drafter, completion = _drafter(DRAFT, vocab)
    drafter.draft(RAW)
    sent = completion.last["messages"][-1]["content"]
    assert "alignment.bam" in sent
    assert "coordinate_sorted" in sent
    assert "Sort SAM/BAM/CRAM" in sent


def test_rejects_a_draft_using_an_undeclared_state(vocab):
    bad = {**DRAFT, "produces": [{"name": "bam", "type_id": "alignment.bam", "state": ["sorted_by_coord"]}]}
    drafter, _ = _drafter(bad, vocab)
    with pytest.raises(InvalidDraftError, match="sorted_by_coord"):
        drafter.draft(RAW)


def test_rejects_a_draft_using_an_unknown_type(vocab):
    bad = {**DRAFT, "produces": [{"name": "x", "type_id": "alignment.cram", "state": []}]}
    drafter, _ = _drafter(bad, vocab)
    with pytest.raises(InvalidDraftError, match="alignment.cram"):
        drafter.draft(RAW)
```

- [ ] **Step 2: Write the failing test for the queue**

```python
from comeni_core.vocabulary import Vocabulary
from mendel_forge.proposal import Proposal, ProposalQueue

BODY = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]
params: []
priority: 0
provenance: {source: nf-core-meta-yml, drafted_by: model, approved_by: PENDING, approved_at: PENDING}
"""


def _queue(tmp_path):
    return ProposalQueue(tmp_path / "proposals")


def _proposal():
    return Proposal(kind="contract", target_path="nf-core/samtools-sort.yml", body=BODY,
                    source_module="samtools_sort", drafted_by="m", rationale="r")


def test_added_proposal_appears_as_pending(tmp_path):
    queue = _queue(tmp_path)
    queue.add(_proposal())
    assert [p.source_module for p in queue.pending()] == ["samtools_sort"]


def test_approval_moves_the_file_into_contracts(tmp_path):
    queue = _queue(tmp_path)
    queue.add(_proposal())
    contracts = tmp_path / "contracts"
    queue.approve("nf-core/samtools-sort.yml", by="rafael", contracts_dir=contracts)
    assert (contracts / "nf-core/samtools-sort.yml").exists()
    assert queue.pending() == []


def test_approval_stamps_the_approver_into_provenance(tmp_path):
    queue = _queue(tmp_path)
    queue.add(_proposal())
    contracts = tmp_path / "contracts"
    queue.approve("nf-core/samtools-sort.yml", by="rafael", contracts_dir=contracts)
    written = (contracts / "nf-core/samtools-sort.yml").read_text()
    assert "approved_by: rafael" in written
    assert "PENDING" not in written


def test_rejection_removes_it_without_touching_contracts(tmp_path):
    queue = _queue(tmp_path)
    queue.add(_proposal())
    queue.reject("nf-core/samtools-sort.yml", why="wrong state")
    assert queue.pending() == []
    assert not (tmp_path / "contracts").exists()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest packages/mendel-forge/tests/ -v`
Expected: FAIL with `ModuleNotFoundError` for `mendel_forge.draft` and `mendel_forge.proposal`.

- [ ] **Step 4: Write `proposal.py`**

```python
"""The approval queue. Nothing reaches contracts/ without passing through here."""

import datetime as dt
import json
from pathlib import Path

from pydantic import BaseModel


class Proposal(BaseModel):
    # free string, not an enum: "contract" and "state" here, "rule" and "pipeline" later
    # without a schema migration. See the federation spec §5.
    kind: str
    target_path: str
    body: str
    source_module: str
    drafted_by: str
    rationale: str


class ProposalQueue:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _slug(self, target_path: str) -> str:
        return target_path.replace("/", "__")

    def add(self, proposal: Proposal) -> None:
        path = self.directory / f"{self._slug(proposal.target_path)}.json"
        path.write_text(proposal.model_dump_json(indent=2))

    def pending(self) -> list[Proposal]:
        return [
            Proposal.model_validate(json.loads(path.read_text()))
            for path in sorted(self.directory.glob("*.json"))
        ]

    def approve(self, target_path: str, by: str, contracts_dir: Path) -> Path:
        path = self.directory / f"{self._slug(target_path)}.json"
        proposal = Proposal.model_validate(json.loads(path.read_text()))

        today = dt.date.today().isoformat()
        body = proposal.body.replace("approved_by: PENDING", f"approved_by: {by}")
        body = body.replace("approved_at: PENDING", f'approved_at: "{today}"')

        destination = contracts_dir / proposal.target_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body)
        path.unlink()
        return destination

    def reject(self, target_path: str, why: str) -> None:
        path = self.directory / f"{self._slug(target_path)}.json"
        rejected = self.directory / "rejected"
        rejected.mkdir(exist_ok=True)
        proposal = json.loads(path.read_text())
        proposal["rejected_because"] = why
        (rejected / path.name).write_text(json.dumps(proposal, indent=2))
        path.unlink()
```

- [ ] **Step 5: Write `draft.py`**

```python
"""AI drafts the semantic overlay meta.yml cannot give you. Humans approve it."""

import yaml
from pydantic import BaseModel, Field

from comeni_core.contract import InputPort, OutputPort, Param
from comeni_core.vocabulary import UnknownStateError, UnknownTypeError, Vocabulary
from mendel_ai.client import ModelClient
from mendel_forge.proposal import Proposal
from mendel_forge.sources import RawModule

SYSTEM = (
    "You assign semantic types to bioinformatics module inputs and outputs. "
    "nf-core meta.yml only says 'type: file', which is not enough to route a pipeline "
    "safely — your job is to say what KIND of file it is and what STATE it is in "
    "(sorted, trimmed, deduplicated). Use only the type ids and states you are given. "
    "If you are unsure whether an output carries a state, leave the state list empty."
)


class InvalidDraftError(ValueError):
    """Raised when a drafted contract does not validate against the vocabulary."""


class DraftedOverlay(BaseModel):
    consumes: list[InputPort] = Field(default_factory=list)
    produces: list[OutputPort] = Field(default_factory=list)
    params: list[Param] = Field(default_factory=list)
    rationale: str = ""


class ContractDrafter:
    def __init__(self, client: ModelClient, vocab: Vocabulary) -> None:
        self._client = client
        self._vocab = vocab

    def draft(self, raw: RawModule) -> Proposal:
        catalogue = "\n".join(
            f"  - {type_id}: states {sorted(states) or '(none)'}"
            for type_id, states in sorted(self._vocab.types.items())
        )
        overlay = self._client.structured(
            (
                f"Module: {raw.name}\n"
                f"Process: {raw.nf_process}\n"
                f"Description: {raw.description}\n"
                f"Tools: {', '.join(raw.tool_names)}\n"
                f"Declared inputs (name: filename pattern): {raw.inputs}\n"
                f"Declared outputs (name: filename pattern): {raw.outputs}\n\n"
                f"Available type ids and their allowed states:\n{catalogue}\n\n"
                "Assign a semantic type and state to each input and output."
            ),
            DraftedOverlay,
            system=SYSTEM,
        )
        self._check(overlay)

        body = yaml.safe_dump(
            {
                "id": f"nf-core/{raw.name.replace('_', '/')}@0.0.0",
                "nf_process": raw.nf_process,
                "nf_include": raw.nf_include,
                "consumes": [port.model_dump(mode="json") for port in overlay.consumes],
                "produces": [port.model_dump(mode="json") for port in overlay.produces],
                "params": [param.model_dump(mode="json") for param in overlay.params],
                "priority": 0,
                "provenance": {
                    "source": "nf-core-meta-yml",
                    "drafted_by": self._client.config.model,
                    "approved_by": "PENDING",
                    "approved_at": "PENDING",
                },
            },
            sort_keys=False,
        )
        return Proposal(
            kind="contract",
            target_path=f"nf-core/{raw.name.replace('_', '-')}.yml",
            body=body,
            source_module=raw.name,
            drafted_by=self._client.config.model,
            rationale=overlay.rationale,
        )

    def _check(self, overlay: DraftedOverlay) -> None:
        try:
            for port in overlay.consumes:
                self._vocab.validate(port.type_id, port.state_required)
                self._vocab.validate(port.type_id, port.state_preferred)
            for port in overlay.produces:
                self._vocab.validate(port.type_id, port.state)
        except (UnknownStateError, UnknownTypeError) as exc:
            raise InvalidDraftError(str(exc)) from exc
```

- [ ] **Step 6: Write `cli.py`**

```python
"""`forge ingest` drafts proposals; `forge approve` moves them into contracts/."""

import argparse
from pathlib import Path

from comeni_core.vocabulary import Vocabulary
from mendel_ai.client import ModelClient, ModelConfig
from mendel_forge.draft import ContractDrafter, InvalidDraftError
from mendel_forge.proposal import ProposalQueue
from mendel_forge.sources import MetaYmlSource


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forge")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--modules", type=Path, required=True)
    ingest.add_argument("--root", type=Path, default=Path.cwd())
    ingest.add_argument("--model", type=str, default="claude-opus-5")

    approve = sub.add_parser("approve")
    approve.add_argument("target")
    approve.add_argument("--by", required=True)
    approve.add_argument("--root", type=Path, default=Path.cwd())

    pending = sub.add_parser("pending")
    pending.add_argument("--root", type=Path, default=Path.cwd())

    args = parser.parse_args(argv)
    queue = ProposalQueue(args.root / "proposals")

    if args.command == "ingest":
        vocab = Vocabulary.load(args.root / "vocabularies")
        drafter = ContractDrafter(ModelClient(ModelConfig(model=args.model)), vocab)
        for raw in MetaYmlSource(args.modules).scan():
            try:
                queue.add(drafter.draft(raw))
                print(f"drafted {raw.name}")
            except InvalidDraftError as exc:
                print(f"SKIPPED {raw.name}: {exc}")
        return 0

    if args.command == "pending":
        for proposal in queue.pending():
            print(f"{proposal.target_path}  ({proposal.source_module})  {proposal.rationale}")
        return 0

    destination = queue.approve(args.target, by=args.by, contracts_dir=args.root / "contracts")
    print(f"approved -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-forge/tests/ -v && uv run ruff check .`
Expected: PASS, 8 tests.

- [ ] **Step 8: Commit**

```bash
git add packages/mendel-forge/
git commit -m "feat(forge): AI contract drafting behind a human approval queue"
```

---

### Task 10: Vocabulary state proposals

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/draft.py`, `proposal.py`, `cli.py`
- Test: `packages/mendel-forge/tests/test_vocabulary_proposal.py`

**Interfaces:**
- Consumes: `ProposalQueue` (Task 9)
- Produces: `ProposalQueue.approve_state(type_id, state, by, vocabularies_dir)`; `ContractDrafter.propose_state(type_id, state, rationale) -> Proposal`

This closes the loop the spec promised: closed vocabulary for validation, one-click extension for genuinely new states.

- [ ] **Step 1: Write the failing test**

```python
from mendel_forge.proposal import Proposal, ProposalQueue


def test_state_proposal_appends_to_the_vocabulary_file(tmp_path):
    vocabularies = tmp_path / "vocabularies"
    vocabularies.mkdir()
    (vocabularies / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")

    queue = ProposalQueue(tmp_path / "proposals")
    queue.add(Proposal(kind="state", target_path="alignment.bam#name_sorted", body="",
                       source_module="samtools_sort", drafted_by="m",
                       rationale="samtools sort -n produces name-sorted output"))
    queue.approve_state("alignment.bam#name_sorted", by="rafael", vocabularies_dir=vocabularies)

    import yaml
    states = yaml.safe_load((vocabularies / "alignment.bam.yml").read_text())["states"]
    assert sorted(states) == ["coordinate_sorted", "name_sorted"]
    assert queue.pending() == []


def test_approving_an_existing_state_is_a_no_op(tmp_path):
    vocabularies = tmp_path / "vocabularies"
    vocabularies.mkdir()
    (vocabularies / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    queue = ProposalQueue(tmp_path / "proposals")
    queue.add(Proposal(kind="state", target_path="alignment.bam#coordinate_sorted", body="",
                       source_module="x", drafted_by="m", rationale="r"))
    queue.approve_state("alignment.bam#coordinate_sorted", by="r", vocabularies_dir=vocabularies)

    import yaml
    assert yaml.safe_load((vocabularies / "alignment.bam.yml").read_text())["states"] == ["coordinate_sorted"]


def test_state_proposal_for_a_new_type_creates_the_file(tmp_path):
    vocabularies = tmp_path / "vocabularies"
    vocabularies.mkdir()
    queue = ProposalQueue(tmp_path / "proposals")
    queue.add(Proposal(kind="state", target_path="variant.vcf#filtered", body="",
                       source_module="x", drafted_by="m", rationale="r"))
    queue.approve_state("variant.vcf#filtered", by="r", vocabularies_dir=vocabularies)
    assert (vocabularies / "variant.vcf.yml").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-forge/tests/test_vocabulary_proposal.py -v`
Expected: FAIL with `AttributeError: 'ProposalQueue' object has no attribute 'approve_state'`

- [ ] **Step 3: Add `approve_state` to `ProposalQueue`**

```python
    def approve_state(self, target_path: str, by: str, vocabularies_dir: Path) -> Path:
        """target_path is '<type_id>#<state>'. Adds the state if it is not already there."""
        path = self.directory / f"{self._slug(target_path)}.json"
        type_id, state = target_path.split("#", 1)

        vocabularies_dir.mkdir(parents=True, exist_ok=True)
        vocab_file = vocabularies_dir / f"{type_id}.yml"
        existing = []
        if vocab_file.exists():
            existing = yaml.safe_load(vocab_file.read_text()).get("states", []) or []

        if state not in existing:
            existing = sorted([*existing, state])
        vocab_file.write_text(yaml.safe_dump({"states": existing}, sort_keys=False))

        if path.exists():
            path.unlink()
        return vocab_file
```

Add `import yaml` to `proposal.py`.

- [ ] **Step 4: Add `propose_state` to `ContractDrafter`**

```python
    def propose_state(self, type_id: str, state: str, rationale: str) -> Proposal:
        return Proposal(
            kind="state",
            target_path=f"{type_id}#{state}",
            body="",
            source_module=type_id,
            drafted_by=self._client.config.model,
            rationale=rationale,
        )
```

- [ ] **Step 5: Add the CLI subcommand**

In `cli.py`, add to the parser:

```python
    approve_state = sub.add_parser("approve-state")
    approve_state.add_argument("target", help="<type_id>#<state>")
    approve_state.add_argument("--by", required=True)
    approve_state.add_argument("--root", type=Path, default=Path.cwd())
```

and before the final `approve` branch:

```python
    if args.command == "approve-state":
        destination = queue.approve_state(
            args.target, by=args.by, vocabularies_dir=args.root / "vocabularies"
        )
        print(f"approved state -> {destination}")
        return 0
```

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -v && uv run ruff check .`
Expected: PASS, everything including all Plan 1 tests.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-forge/
git commit -m "feat(forge): vocabulary state proposals through the same approval queue"
```

---

## Self-Review

**Spec coverage.** The sections Plan 1 deferred:

| Spec section | Covered by |
|---|---|
| §4.2 three runtime AI points | Task 3 (extract), Task 5 (tier 4), Task 6 (repair) |
| §4.2 AI authors offline, humans approve | Tasks 9, 10 |
| §4.4 `mendel-ai` package | Tasks 1, 3, 4, 5, 6 |
| §4.4 `mendel-forge` package | Tasks 8, 9, 10 |
| §5.4 decision records replayed on rerun | Task 4 |
| §7.1 repair edits the IR, `diverged` flag | Task 2, Task 6 |
| §7.2 bounded to 3 attempts | Task 6 |
| §8 one queue, three proposal kinds | Tasks 9, 10 — contract and state. **Tier-3 rule proposals are not implemented**; the queue's `kind` field accepts them and `approve_state` is the template to copy, but no drafter emits them yet. |
| §9 LiteLLM | Task 1 |

**Known gap, stated rather than hidden:** the spec's §8 promises three proposal kinds and this plan ships two. Rule drafting needs a corpus of tier-4 flags to learn from, which does not exist until Mendel has been run on real data — so it belongs after Plan 3, not here.

**Placeholder scan.** No TBDs. Every step has runnable code.

**Type consistency.** `AmbiguityResolver.resolve` has the same signature in `FlagOnlyResolver` (Plan 1), `LLMAmbiguityResolver` (Task 5) and `ReplayingResolver` (Task 4). `IRPatch` is defined once in `ports.py` and consumed by both `repair.py` and `loop.py`. `ModelClient.config.model` is read by Tasks 5, 9 for provenance — `config` is a public attribute on `ModelClient`, set in Task 1. `Proposal.target_path` doubles as the queue key in Tasks 9 and 10 via `_slug`.

---

## Verification

```bash
uv sync
uv run pytest -v                      # no test calls a live model
uv run ruff check .
uv run pytest tests/test_purity.py    # the pure three are still pure

# deterministic path still works with no model available
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --no-ai --gate stub

# full path, needs a provider key in the environment
export ANTHROPIC_API_KEY=...
uv run mendel build --prompt "human paired-end RNA-seq, 12 samples, I want a counts matrix" \
    --out build-ai/ --gate stub

# rerun replays decisions instead of re-asking the model — should be visibly faster
uv run mendel build --prompt "human paired-end RNA-seq, 12 samples, I want a counts matrix" \
    --out build-ai/ --gate stub

# the forge
uv run forge ingest --modules modules/
uv run forge pending
uv run forge approve nf-core/samtools-sort.yml --by "$USER"
```

This plan is complete when the second AI build is measurably faster than the first (proving replay), `--no-ai` still produces byte-identical output to Plan 1's, and a drafted contract can be approved into `contracts/` and immediately used by a build.
