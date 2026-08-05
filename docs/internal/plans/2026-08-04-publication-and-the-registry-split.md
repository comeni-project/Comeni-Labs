# Publication and the Registry Split Implementation Plan

> **Plan 1.7.** Execute after Plan 1.6 (complete) and **before** Plan 2 — see the execution
> order in [`docs/internal/README.md`](../README.md), which is also where the reason for that
> order is written down.
>
> **This plan was called "Plan 2.5" until 2026-08-05.** The number recorded when it was
> *written* — after Plan 2 existed — and was read by everyone, reasonably, as when it should
> *run*. It is pure-package work in the same family as Plans 1.5 and 1.6: no AI, no network,
> no new dependency. Journal entries dated on or before 2026-08-05 still say "Plan 2.5"; they
> are append-only and correct about the day they were written.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax for
> tracking. Do **not** farm the tasks out with subagent-driven-development — subagents are for
> review and design only. This matches the execution decision recorded in `CLAUDE.md`.

**Goal:** Make a pipeline a shareable artifact — `Goal` + `PipelineIR` + `DecisionRecord[]` +
a lockfile — that reproduces byte-identically, replays every untouched decision when edited,
and reports honestly what moved when the registry underneath it changes.

**Architecture:** Everything here is pure-package work plus two CLI verbs. The lockfile is
content-addressed over data already on disk, so it needs no new dependency. Replay is not a new
subsystem: it is one more implementation of the `AmbiguityResolver` protocol Plan 1 already
declared, which is why "edit a curated pipeline and only what you touched moves" costs one class.

**Tech Stack:** Python 3.12, Pydantic v2, `hashlib` and `pathlib` (both already on the
`comeni-core` purity allowlist), pytest, ruff, `uv` workspace. No AI, no network, no new
dependency.

## Global Constraints

- `comeni-core` and `mendel-resolver` are under a **closed allowlist** in `tests/test_purity.py`.
  `hashlib` and `pathlib` are already on it. Adding anything else means editing that file
  deliberately, in the same commit.
- **`PublishBundle` is an egress payload.** Everything reachable from it must satisfy
  `tests/test_egress.py`: no `Any`, no mapping, no bare `str`, `extra="forbid"`. Every string is
  a declared alias in `marks.py` or marked `FreeText` and added to `FREE_TEXT_FIELDS`.
- **No filesystem paths in the lockfile, ever.** A path is meaningless on another machine and is
  exactly what invariant 15 keeps out. Layers are identified by *name and digest*, never by where
  they happened to sit. This is a hard rule and Task 3 tests it.
- **No timestamps in the lockfile.** Determinism is a test: the same inputs must produce the same
  bytes. A `generated_at` field would break `test_output_is_identical_across_hash_seeds` the day
  it is added.
- Determinism generally: anything serialising a `frozenset` needs a `field_serializer` that sorts.
- Ruff line length 100. `make check` passes before every commit.
- **Curation is human and stays human.** Nothing in this plan may set a curated stamp
  mechanically. `published` has a mechanical gate; `curated` requires a named person.

---

## File Structure

```
packages/comeni-core/src/comeni_core/
├─ goal.py                 NEW — Goal, GoalInput, Constraints, ParamOverride move here
├─ lockfile.py             NEW — Digest, LockedContract, LockedLayer, Lockfile
├─ digest.py               NEW — content addressing for contracts and layer directories
├─ marks.py                MODIFY — Digest, LayerName aliases
├─ ir.py                   MODIFY — PipelineIR.registry_layers, PipelineIR.shadowed
├─ egress.py               MODIFY — PublishBundle gains goal and lockfile
packages/mendel-resolver/src/mendel_resolver/
├─ goal.py                 MODIFY — becomes a re-export shim
├─ replay.py               NEW — ReplayResolver
├─ diff.py                 NEW — IRDiff, diff_ir
├─ layers.py               MODIFY — Layers.paths, so a build knows its own layers
packages/mendel-compiler/src/mendel_compiler/
├─ cli.py                  MODIFY — `mendel publish`, `mendel upgrade`
registry/                  NEW — the layer, moved out of examples/, ready to extract
├─ registry.yml            NEW — the layer manifest: name, version, licence
tests/
├─ test_lockfile.py        NEW
├─ test_publish.py         NEW
├─ test_upgrade.py         NEW
```

**Ordering rationale.** `Goal` moves first because `PublishBundle` cannot carry one until it
does, and every later task references the bundle. Digests come before the lockfile that contains
them. Replay comes before `upgrade`, which is replay plus a diff. The registry split is last of
the code tasks because it moves the files every earlier test reads.

**Out of scope, and why.** The **pipeline catalogue and the pipeline review screens**
(federation §5) are named in §8 as Plan 1.7's work, but they need `mendel-api` and the frontend,
which are Plan 3. Building a catalogue before there is a service to serve it would be predicting
types again — the exact mistake this plan exists downstream of. They move to Plan 3, and this
plan produces the artifact they will display. **Resolving container tags to digests** (clinical
spec §6.1, required by `sealed`) needs a registry client and therefore network access, which
`comeni-core` cannot have; it belongs with `mendel-api`.

---

### Task 1: `Goal` moves to `comeni-core`

`PublishBundle` currently says, in its own docstring, that the `Goal` is absent "because it lives
in `mendel-resolver` and `comeni-core` must not depend on it". The federation spec (§4.1) says a
shareable pipeline is `Goal` + `PipelineIR` + `DecisionRecord[]` + lockfile. One of those has to
give, and it is the location, not the contents.

This is the same move `DataProfile` made on 2026-08-03, for the same reason and with the same
shim. `Goal` is data, not resolution logic, and it already contains a `comeni_core.profile.DataProfile`.

**Files:**
- Create: `packages/comeni-core/src/comeni_core/goal.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/goal.py` (becomes a re-export shim)
- Modify: `packages/comeni-core/src/comeni_core/__init__.py`
- Modify: `packages/comeni-core/src/comeni_core/egress.py`
- Test: `packages/comeni-core/tests/test_goal_location.py`

**Interfaces:**
- Consumes: `comeni_core.profile.DataProfile`, `comeni_core.marks`
- Produces: `comeni_core.goal.Goal`, `GoalInput`, `Constraints`, `ParamOverride`;
  `PublishBundle.goal: Goal`

- [ ] **Step 1: Write the failing test**

```python
"""`Goal` lives in comeni-core, and the resolver re-exports it.

The move exists so `PublishBundle` can carry one. `mendel_resolver.goal` stays as a shim
because a goal is what most resolver code actually meets, and breaking every import to
relocate a type is churn nobody reviews carefully.
"""

import pytest
from pydantic import ValidationError


def test_goal_is_importable_from_core():
    from comeni_core.goal import Constraints, Goal, GoalInput, ParamOverride

    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"])
    assert goal.want == ["qc.report"]
    assert isinstance(goal.constraints, Constraints)
    assert ParamOverride(name="x", value=1).value == 1


def test_the_resolver_re_export_is_the_same_class():
    """Not a copy. `isinstance` across the two import paths must hold."""
    from comeni_core.goal import Goal as CoreGoal
    from mendel_resolver.goal import Goal as ResolverGoal

    assert CoreGoal is ResolverGoal


def test_a_publish_bundle_carries_the_goal():
    from comeni_core.egress import PublishBundle
    from comeni_core.goal import Goal
    from comeni_core.ir import PipelineIR

    bundle = PublishBundle(goal=Goal(want=["counts.matrix"]), ir=PipelineIR())
    assert bundle.goal.want == ["counts.matrix"]


def test_the_goal_still_has_nowhere_to_put_a_sample_identifier():
    """Invariant 15 survives the move. This is the test that makes the move safe."""
    from comeni_core.goal import Goal

    with pytest.raises(ValidationError):
        Goal(want=["counts.matrix"], samples=["patient_4471023_R1.fastq.gz"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_goal_location.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'comeni_core.goal'`

- [ ] **Step 3: Move the file**

```bash
git mv packages/mendel-resolver/src/mendel_resolver/goal.py \
       packages/comeni-core/src/comeni_core/goal.py
```

Then in `packages/comeni-core/src/comeni_core/goal.py`, change the import line

```python
from comeni_core.profile import DataProfile, Measured
```

to

```python
from comeni_core.profile import DataProfile, Measured  # noqa: F401  (re-exported)
```

and leave everything else exactly as it is. The module already imports only from `comeni_core`,
which is why this move is a rename rather than a rewrite.

- [ ] **Step 4: Write the resolver shim**

Create `packages/mendel-resolver/src/mendel_resolver/goal.py`:

```python
"""Re-export of the goal types, which live in `comeni_core.goal`.

They moved there so `PublishBundle` could carry a `Goal` — a shareable pipeline is
`Goal` + `PipelineIR` + `DecisionRecord[]` + lockfile, and `comeni-core` must not depend
on `mendel-resolver`. Same move `DataProfile` made, for the same reason.

This shim stays because a goal is what most resolver code actually meets, and rewriting
every import to relocate a type is churn nobody reviews carefully.
"""

from comeni_core.goal import Constraints, Goal, GoalInput, ParamOverride
from comeni_core.profile import DataProfile, Measured

__all__ = ["Constraints", "DataProfile", "Goal", "GoalInput", "Measured", "ParamOverride"]
```

- [ ] **Step 5: Add `goal` to the bundle**

In `packages/comeni-core/src/comeni_core/egress.py`, add the import

```python
from comeni_core.goal import Goal
```

and replace the `PublishBundle` class body:

```python
class PublishBundle(EgressPayload):
    """Door 4 — publication. The door with no undo.

    A shareable pipeline is what a human asked for, what it resolved to, why each choice
    was made, and against exactly which registry — federation spec §4.1. All four, or the
    recipient cannot reproduce it and cannot audit it.
    """

    goal: Goal
    ir: PipelineIR
    decisions: list[DecisionRecord] = []
```

The `lockfile` field arrives in Task 3, once the type exists.

- [ ] **Step 6: Export from `comeni_core`**

In `packages/comeni-core/src/comeni_core/__init__.py`, add to the imports and to `__all__`:

```python
from comeni_core.goal import Constraints, Goal, GoalInput, ParamOverride
```

`__all__` entries: `"Constraints"`, `"Goal"`, `"GoalInput"`, `"ParamOverride"`. Keep it
alphabetically sorted — the existing list is.

- [ ] **Step 7: Run the suite and watch the egress guard fail**

Run: `make check`
Expected: **FAIL**, with:

```
these fields are mappings; use a list of declared records instead: Constraints.required_states
```

This is correct and was verified against the real guard before this plan was written.
`Constraints.required_states` is `dict[TypeId, list[StateName]]`, and `Goal` has never been
reachable from an egress payload before, so nothing had ever walked it. A typed key does not
prove a *declared* key — the same reasoning that made `ParamBinding` and `Measured` lists.

**Do not exempt it.** The guard is right.

- [ ] **Step 8: Convert `required_states` to a list of records**

In `packages/comeni-core/src/comeni_core/goal.py`, replace `Constraints`:

```python
class RequiredStates(BaseModel):
    """States a wanted output must carry.

    A record rather than a mapping key, because `tests/test_egress.py` forbids mappings in
    anything reachable from a payload and `Goal` became reachable when `PublishBundle`
    started carrying one. `dict[TypeId, list[StateName]]` type-checks perfectly while
    saying nothing about whether the key was ever declared.
    """

    model_config = ConfigDict(extra="forbid")

    type_id: TypeId
    states: list[StateName] = Field(default_factory=list)


class Constraints(BaseModel):
    """Everything a goal may pin. `extra="forbid"` is the whole point of the type."""

    model_config = ConfigDict(extra="forbid")

    required_states: list[RequiredStates] = Field(default_factory=list)
    params: list[ParamOverride] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_mapping(cls, data: object) -> object:
        """`required_states: {counts.matrix: [gene_level]}` still works.

        A mapping is the natural way to *write* one in a goal file, and every existing
        goal and test does. The list is what the guard requires; this keeps the ergonomic
        form and the safe representation from being the same decision. Same pattern as
        `IRNode.params` and `DataProfile.measurements`.
        """
        if isinstance(data, dict) and isinstance(data.get("required_states"), dict):
            data = dict(data)
            data["required_states"] = [
                {"type_id": k, "states": v} for k, v in sorted(data["required_states"].items())
            ]
        return data

    def states_for(self, type_id: str) -> frozenset[StateName]:
        return frozenset(
            state
            for required in self.required_states
            if required.type_id == type_id
            for state in required.states
        )
```

Add `model_validator` to the pydantic import.

- [ ] **Step 9: Fix the one consumer**

`router.py` reads `goal.constraints.required_states` as a mapping. In
`packages/mendel-resolver/src/mendel_resolver/router.py`, delete the line

```python
    required_states = goal.constraints.required_states
```

and change the final loop to use the accessor:

```python
    for wanted in goal.want:
        satisfy(wanted, goal.constraints.states_for(wanted), 0, frozenset())
```

- [ ] **Step 10: Run the suite and lint**

Run: `make check`
Expected: PASS, 169 tests. `examples/rnaseq-goal.yml` is unchanged and must still build —
the mapping shorthand is what keeps it working.

Then prove the shorthand is not the only thing tested, by adding to
`packages/comeni-core/tests/test_goal_location.py`:

```python
def test_required_states_accepts_both_forms():
    from comeni_core.goal import Constraints

    mapping = Constraints(required_states={"counts.matrix": ["gene_level"]})
    listed = Constraints(
        required_states=[{"type_id": "counts.matrix", "states": ["gene_level"]}]
    )
    assert mapping.states_for("counts.matrix") == frozenset({"gene_level"})
    assert mapping.model_dump() == listed.model_dump()
    assert mapping.states_for("absent.type") == frozenset()
```

- [ ] **Step 11: Commit**

```bash
git add packages/comeni-core packages/mendel-resolver
git commit -m "refactor(core): Goal moves to comeni-core so a bundle can carry one

Constraints.required_states becomes a list of declared records. Goal had never
been reachable from an egress payload, so nothing had walked it; the moment
PublishBundle carries one, the mapping is exactly what test_egress.py forbids.
The mapping shorthand survives as a before-validator, so no goal file changes."
```

---

### Task 2: Content addressing

A lockfile pins "contract IDs with content digests" (federation §4.1). This task is the digest.

**Files:**
- Create: `packages/comeni-core/src/comeni_core/digest.py`
- Modify: `packages/comeni-core/src/comeni_core/marks.py`
- Test: `packages/comeni-core/tests/test_digest.py`

**Interfaces:**
- Consumes: `ModuleContract`
- Produces: `digest_of(model: BaseModel) -> Digest`; `digest_of_directory(path: Path) -> Digest`;
  `Digest` and `LayerName` aliases in `marks.py`

- [ ] **Step 1: Write the failing test**

```python
import pathlib
import subprocess
import sys

import pytest
from comeni_core.contract import ModuleContract
from comeni_core.digest import digest_of, digest_of_directory
from comeni_core.vocabulary import Vocabulary

CONTRACT = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted, indexed]}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-04"}
"""


@pytest.fixture
def contract(tmp_path):
    vocab_dir = tmp_path / "v"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted, indexed]\n")
    path = tmp_path / "c.yml"
    path.write_text(CONTRACT)
    return ModuleContract.load(path, Vocabulary.load(vocab_dir))


def test_a_digest_is_prefixed_and_hex(contract):
    d = digest_of(contract)
    algorithm, _, hexdigest = d.partition(":")
    assert algorithm == "sha256"
    assert len(hexdigest) == 64
    assert int(hexdigest, 16) >= 0


def test_the_same_contract_digests_the_same(contract):
    assert digest_of(contract) == digest_of(contract.model_copy(deep=True))


def test_a_changed_field_changes_the_digest(contract):
    assert digest_of(contract) != digest_of(contract.model_copy(update={"priority": 1}))


def test_a_digest_is_stable_across_hash_seeds(contract):
    """The contract carries a two-element frozenset, so this bites.

    `frozenset` iterates in hash order and hash order varies with PYTHONHASHSEED. A digest
    that varied per process would make every lockfile spuriously dirty.
    """
    import os

    script = (
        "from comeni_core.contract import ModuleContract;"
        "from comeni_core.digest import digest_of;"
        "from comeni_core.vocabulary import Vocabulary;"
        f"print(digest_of(ModuleContract.load(__import__('pathlib').Path({str(contract_path := None)!r})"
        ", Vocabulary(types={'alignment.bam': frozenset({'coordinate_sorted', 'indexed'})}))))"
    )
    # Simpler and equivalent: digest the same model in three subprocesses.
    outputs = set()
    for seed in ("1", "7", "99999"):
        result = subprocess.run(
            [sys.executable, "-c",
             "from comeni_core.contract import OutputPort;"
             "from comeni_core.digest import digest_of;"
             "print(digest_of(OutputPort(name='bam', type_id='alignment.bam',"
             " state=frozenset({'coordinate_sorted','indexed','filtered','deduplicated'}))))"],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True, text=True, check=True,
        )
        outputs.add(result.stdout)
    assert len(outputs) == 1, f"digest varies with PYTHONHASHSEED: {outputs}"


def test_a_directory_digest_covers_its_files(tmp_path):
    layer = tmp_path / "layer"
    (layer / "contracts").mkdir(parents=True)
    (layer / "contracts" / "a.yml").write_text("id: a\n")
    before = digest_of_directory(layer)
    (layer / "contracts" / "a.yml").write_text("id: b\n")
    assert digest_of_directory(layer) != before


def test_a_directory_digest_covers_file_names_too(tmp_path):
    """Renaming a file changes the layer, even if every byte is the same."""
    layer = tmp_path / "layer"
    layer.mkdir()
    (layer / "a.yml").write_text("x: 1\n")
    before = digest_of_directory(layer)
    (layer / "a.yml").rename(layer / "b.yml")
    assert digest_of_directory(layer) != before


def test_a_directory_digest_ignores_traversal_order(tmp_path):
    """Two directories with the same contents digest the same, whatever order they were built."""
    one, two = tmp_path / "one", tmp_path / "two"
    for d in (one, two):
        (d / "sub").mkdir(parents=True)
    for name in ("a.yml", "b.yml", "c.yml"):
        (one / name).write_text(name)
    for name in ("c.yml", "a.yml", "b.yml"):
        (two / name).write_text(name)
    (one / "sub" / "d.yml").write_text("d")
    (two / "sub" / "d.yml").write_text("d")
    assert digest_of_directory(one) == digest_of_directory(two)


def test_a_missing_directory_digests_to_the_empty_digest(tmp_path):
    """A layer may legitimately have no `rules/`. That is not an error."""
    assert digest_of_directory(tmp_path / "nope").startswith("sha256:")
```

> **Note on the first subprocess test.** Delete the unused `script` variable and the walrus
> when you write this — it is left in the plan only to show what was tried and rejected
> (reconstructing a `ModuleContract` inside a subprocess needs a vocabulary, which makes the
> test about vocabulary loading rather than about digests). Digesting an `OutputPort` with a
> four-element frozenset is the same property, tested directly.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_digest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'comeni_core.digest'`

- [ ] **Step 3: Add the aliases**

Append to `packages/comeni-core/src/comeni_core/marks.py`:

```python
Digest = Annotated[str, "digest"]
LayerName = Annotated[str, "layer-name"]
```

- [ ] **Step 4: Write `digest.py`**

```python
"""Content addressing for contracts and registry layers.

A lockfile has to be able to say "this pipeline was built against exactly this contract",
and a version string cannot say that — a contract can be edited without its `@version`
moving, and in a private overlay it routinely is.

`hashlib` and `pathlib` are on `comeni-core`'s purity allowlist deliberately; this is what
they were put there for. Nothing here reads the network.
"""

import hashlib
from pathlib import Path

from pydantic import BaseModel

from comeni_core.marks import Digest

_ALGORITHM = "sha256"
_CHUNK = 65536


def _hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_of(model: BaseModel) -> Digest:
    """Content digest of a Pydantic model, stable across processes.

    `model_dump_json` emits fields in declaration order, and every `frozenset` in this
    codebase carries a `field_serializer` that sorts — which is what makes this stable
    rather than hash-seed dependent. Anything new that serialises a set needs the same
    treatment or it silently breaks this function and every lockfile made with it.
    """
    return f"{_ALGORITHM}:{_hex(model.model_dump_json().encode())}"


def digest_of_directory(path: Path) -> Digest:
    """Content digest of every file under `path`, name and bytes alike.

    Names are included because renaming a contract file changes which layer it belongs to
    and can change load order, even when no byte of content moved.

    Sorted by relative path so two copies of the same layer digest identically regardless
    of the order the filesystem happened to hand them over. A missing directory digests to
    the digest of nothing, because a layer with no `rules/` is ordinary rather than broken.
    """
    parts: list[str] = []
    if path.exists():
        for file in sorted(p for p in path.rglob("*") if p.is_file()):
            hasher = hashlib.sha256()
            with file.open("rb") as handle:
                while chunk := handle.read(_CHUNK):
                    hasher.update(chunk)
            parts.append(f"{file.relative_to(path).as_posix()}:{hasher.hexdigest()}")
    return f"{_ALGORITHM}:{_hex('\n'.join(parts).encode())}"
```

- [ ] **Step 5: Run tests and lint**

Run: `uv run pytest packages/comeni-core/tests/test_digest.py -v && uv run ruff check .`
Expected: PASS, 7 tests.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core
git commit -m "feat(core): content addressing for contracts and layers"
```

---

### Task 3: The lockfile

Federation §4.1: *"The lockfile pins contract IDs with content digests, module versions,
registry layer sources and the vocabulary version. Loading a locked pipeline reproduces
byte-identical Nextflow."*

**Files:**
- Create: `packages/comeni-core/src/comeni_core/lockfile.py`
- Modify: `packages/comeni-core/src/comeni_core/egress.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py`
- Test: `tests/test_lockfile.py`

**Interfaces:**
- Consumes: `digest_of`, `digest_of_directory` (Task 2), `Registry`, `PipelineIR`
- Produces: `LockedContract(id, digest, container)`; `LockedLayer(name, digest)`;
  `Lockfile(version, contracts, layers)`; `Lockfile.of(ir, registry, layers) -> Lockfile`;
  `Lockfile.drift_against(ir, registry, layers) -> list[str]`;
  `Layers.paths: list[LayerName]`; `PublishBundle.lockfile`

- [ ] **Step 1: Write the failing test**

```python
import pathlib

import pytest
from comeni_core.lockfile import Lockfile
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def built():
    loaded = layers.load(ROOT / "examples")
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads"), GoalInput(type_id="annotation.gtf")],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )
    return resolve(goal, loaded.registry, loaded.rules), loaded


def test_a_lockfile_pins_every_contract_the_pipeline_uses(built):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert {c.id for c in lock.contracts} == {n.contract_id for n in ir.nodes}


def test_a_lockfile_pins_nothing_the_pipeline_does_not_use(built):
    """The registry has twelve contracts and the spine uses five. Pin what was used."""
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert len(lock.contracts) == len(ir.nodes) < len(loaded.registry.all())


def test_contracts_are_pinned_in_a_stable_order(built):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert [c.id for c in lock.contracts] == sorted(c.id for c in lock.contracts)


def test_a_lockfile_records_the_container(built):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    star = next(c for c in lock.contracts if c.id.startswith("nf-core/star/align"))
    assert star.container.startswith("community.wave.seqera.io/")


def test_a_lockfile_holds_no_filesystem_path(built):
    """A path is meaningless on another machine, and invariant 15 keeps them out.

    Layers are identified by name and digest. `Lockfile.of` is handed absolute paths and
    must reduce them to basenames before anything is stored.
    """
    ir, loaded = built
    text = Lockfile.of(ir, loaded.registry, loaded.paths).model_dump_json()
    assert "/home" not in text and str(ROOT) not in text
    assert "examples" in text


def test_a_lockfile_has_no_timestamp(built):
    """Determinism is a test. A generated_at field would break it the day it is added."""
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert not any("time" in f or "date" in f or "at" == f for f in type(lock).model_fields)


def test_the_same_build_locks_identically(built):
    ir, loaded = built
    first = Lockfile.of(ir, loaded.registry, loaded.paths)
    second = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert first.model_dump_json() == second.model_dump_json()


def test_drift_is_empty_against_the_registry_that_built_it(built):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert lock.drift_against(ir, loaded.registry, loaded.paths) == []


def test_an_edited_contract_is_reported_as_drift(built, tmp_path):
    """The property a lockfile exists for: a contract changed underneath you, silently."""
    import shutil

    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)

    layer = tmp_path / "examples"
    shutil.copytree(ROOT / "examples", layer)
    sort = next(layer.rglob("samtools-sort.yml"))
    sort.write_text(sort.read_text().replace("priority: 0", "priority: 7"))
    changed = layers.load(layer)

    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("samtools/sort" in line for line in drift)


def test_a_missing_contract_is_reported_as_drift(built, tmp_path):
    import shutil

    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)

    layer = tmp_path / "examples"
    shutil.copytree(ROOT / "examples", layer)
    next(layer.rglob("samtools-sort.yml")).unlink()
    changed = layers.load(layer)

    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("no longer in the registry" in line for line in drift)


def test_a_changed_layer_is_reported_as_drift(built, tmp_path):
    """Contracts can be unchanged while a rule that chose them moved."""
    import shutil

    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)

    layer = tmp_path / "examples"
    shutil.copytree(ROOT / "examples", layer)
    rules = layer / "rules" / "rnaseq.yml"
    rules.write_text(rules.read_text().replace('">= 70"', '">= 60"'))
    changed = layers.load(layer)

    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("layer" in line and "examples" in line for line in drift)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lockfile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'comeni_core.lockfile'`

- [ ] **Step 3: Give `Layers` its own paths**

A build cannot lock what it does not know it loaded. In
`packages/mendel-resolver/src/mendel_resolver/layers.py`, add a field to `Layers`:

```python
    paths: list[Path] = Field(default_factory=list)
    """The layer directories this was loaded from, in order.

    Carried so a build can lock itself. `Lockfile.of` reduces these to basenames — a
    lockfile never stores a filesystem path.
    """
```

Add `Field` to the pydantic import, `Path` is already imported, and set it in `load`:

```python
    return Layers(
        measurements=measurements,
        vocabulary=vocabulary,
        registry=registry,
        rules=rules,
        paths=list(layers),
    )
```

- [ ] **Step 4: Write `lockfile.py`**

```python
"""What a pipeline was built against, pinned by content.

Federation §4.1. A version string cannot pin a contract — a contract can be edited without
its `@version` moving, and in a private overlay it routinely is. Digests can.

Two deliberate absences:

**No filesystem paths.** A layer is identified by name and digest. Where it sat on the
machine that built it is meaningless to the machine that reads it, and invariant 15 keeps
paths out of anything that can be published.

**No timestamps.** Determinism is a test: the same inputs produce the same bytes. A
`generated_at` field would make every lockfile differ from every other one, and the
determinism tests would go from meaningful to noise.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.digest import digest_of, digest_of_directory
from comeni_core.ir import PipelineIR
from comeni_core.marks import ContractId, Digest, LayerName
from comeni_core.registry import Registry


class LockedContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ContractId
    digest: Digest
    container: str | None = None
    """The container as the contract declared it, tag and all.

    Resolving a tag to an immutable digest needs a registry client, which means the
    network, which `comeni-core` may not have. That belongs with `mendel-api`, and the
    `sealed` profile's digests-required rule depends on it.
    """


class LockedLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: LayerName
    digest: Digest


class Lockfile(BaseModel):
    """Enough to reproduce a build, and enough to detect that you cannot."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    contracts: list[LockedContract] = Field(default_factory=list)
    layers: list[LockedLayer] = Field(default_factory=list)

    @classmethod
    def of(
        cls, ir: PipelineIR, registry: Registry, layers: Sequence[Path]
    ) -> "Lockfile":
        """Pin the contracts this pipeline actually used, and the layers it came from.

        Used, not available: the example registry holds twelve contracts and the RNA-seq
        spine uses five. Pinning all twelve would report drift for a module the pipeline
        never touched, and a lockfile that cries wolf gets ignored.
        """
        used = sorted({node.contract_id for node in ir.nodes})
        return cls(
            contracts=[
                LockedContract(
                    id=contract_id,
                    digest=digest_of(registry.get(contract_id)),
                    container=registry.get(contract_id).container,
                )
                for contract_id in used
            ],
            layers=[
                LockedLayer(name=path.name, digest=digest_of_directory(path))
                for path in layers
            ],
        )

    def drift_against(
        self, ir: PipelineIR, registry: Registry, layers: Sequence[Path]
    ) -> list[str]:
        """Every way the world has moved since this lockfile was written.

        Returned as prose lines for a human, not as a structured diff, because the caller
        is `mendel upgrade` printing to a terminal and every line here is something a
        person has to decide about. Empty means reproducible.
        """
        found: list[str] = []
        current = Lockfile.of(ir, registry, layers)

        locked = {c.id: c for c in self.contracts}
        now = {c.id: c for c in current.contracts}

        for contract_id, pinned in sorted(locked.items()):
            if contract_id not in registry.contracts:
                found.append(f"{contract_id} is no longer in the registry")
            elif now[contract_id].digest != pinned.digest:
                found.append(f"{contract_id} has been edited since it was locked")

        for added in sorted(set(now) - set(locked)):
            found.append(f"{added} is used now but was not locked")

        locked_layers = {layer.name: layer.digest for layer in self.layers}
        for layer in current.layers:
            if layer.name not in locked_layers:
                found.append(f"layer {layer.name} was not present when this was locked")
            elif locked_layers[layer.name] != layer.digest:
                found.append(f"layer {layer.name} has changed since it was locked")
        for gone in sorted(set(locked_layers) - {layer.name for layer in current.layers}):
            found.append(f"layer {gone} was locked but is not loaded now")

        return found
```

- [ ] **Step 5: Add it to the bundle**

In `egress.py`, import `Lockfile` and add the field:

```python
from comeni_core.lockfile import Lockfile
```

```python
class PublishBundle(EgressPayload):
    goal: Goal
    ir: PipelineIR
    decisions: list[DecisionRecord] = []
    lockfile: Lockfile = Lockfile()
```

- [ ] **Step 6: Run the full suite and lint**

Run: `make check`
Expected: PASS. `tests/test_egress.py` now walks `Lockfile` — `LockedContract.container` is a
bare `str | None` and **will fail** `test_no_payload_carries_an_undeclared_string`. Fix it by
adding a `ContainerRef = Annotated[str, "container-ref"]` alias to `marks.py` and using it. Do
not add it to `FREE_TEXT_FIELDS`: a container reference is registry data, not prose.

- [ ] **Step 7: Commit**

```bash
git add packages/comeni-core packages/mendel-resolver tests/test_lockfile.py
git commit -m "feat(core): lockfiles pin contracts and layers by content"
```

---

### Task 4: The IR records which registry built it

Federation §8 says the dashboard "renders `registry_layers` and shadow markers, but that is
display of data the IR already carries". It does not carry it. This task makes that sentence
true.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/ir.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Test: `packages/comeni-core/tests/test_ir_provenance.py`

**Interfaces:**
- Consumes: `ShadowRecord`, `LockedLayer` (Task 3)
- Produces: `PipelineIR.registry_layers: list[LayerName]`; `PipelineIR.shadowed: list[ShadowRecord]`;
  `resolve(goal, registry, rules, resolver=None, layer_names=())`

- [ ] **Step 1: Write the failing test**

```python
import pathlib

from comeni_core.ir import PipelineIR
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve

ROOT = pathlib.Path(__file__).parents[3]


def test_an_ir_defaults_to_no_layers():
    assert PipelineIR().registry_layers == []
    assert PipelineIR().shadowed == []


def test_a_resolved_ir_records_the_layers_it_was_built_from():
    loaded = layers.load(ROOT / "examples")
    ir = resolve(
        Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"]),
        loaded.registry,
        loaded.rules,
        layer_names=[p.name for p in loaded.paths],
    )
    assert ir.registry_layers == ["examples"]


def test_a_resolved_ir_carries_the_shadow_records(tmp_path):
    """An overlay that displaced a contract must be visible in the artifact, not only
    on stderr at build time. A published pipeline that hid it would be unauditable."""
    import shutil

    base = ROOT / "examples"
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    sort = next(base.rglob("samtools-sort.yml"))
    (overlay / "contracts" / "sort.yml").write_text(
        sort.read_text().replace("@1.21.0", "@1.99.0")
    )
    loaded = layers.load([base, overlay])
    ir = resolve(
        Goal(
            have=[GoalInput(type_id="fastq.reads"), GoalInput(type_id="annotation.gtf")],
            want=["counts.matrix"],
            constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        ),
        loaded.registry,
        loaded.rules,
        layer_names=[p.name for p in loaded.paths],
    )
    assert ir.registry_layers == ["examples", "lab"]
    assert [s.module_key for s in ir.shadowed] == ["nf-core/samtools/sort"]
    assert shutil  # keeps the import honest if the body is edited later


def test_layers_are_recorded_in_stacking_order(tmp_path):
    """Order is meaning: later layers win. A set would lose that."""
    for name in ("a", "b"):
        (tmp_path / name / "contracts").mkdir(parents=True)
    ir = PipelineIR(registry_layers=["a", "b"])
    assert ir.registry_layers == ["a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_ir_provenance.py -v`
Expected: FAIL — `PipelineIR` has no `registry_layers`, and `resolve` takes no `layer_names`.

- [ ] **Step 3: Add the fields**

In `packages/comeni-core/src/comeni_core/ir.py`, import `ShadowRecord` and `LayerName`:

```python
from comeni_core.marks import ..., LayerName
from comeni_core.registry import ShadowRecord
```

and add to `PipelineIR`:

```python
    registry_layers: list[LayerName] = Field(default_factory=list)
    """Which layers built this, in stacking order. A list because order is meaning:
    later layers win, and a set would lose that."""

    shadowed: list[ShadowRecord] = Field(default_factory=list)
    """Contracts an overlay displaced.

    Carried on the artifact rather than only printed at build time. A published pipeline
    whose registry quietly rerouted it would be unauditable by the person who downloaded
    it, which is the failure invariant 11 exists to prevent."""
```

> **Watch for an import cycle.** `registry.py` imports `contract.py`, which imports
> `vocabulary.py`. `ir.py` currently imports neither. Adding `from comeni_core.registry import
> ShadowRecord` is safe today — nothing in that chain imports `ir` — but if it ever raises
> `ImportError`, move `ShadowRecord` into `marks.py`'s neighbourhood rather than adding a
> `TYPE_CHECKING` guard: a field type that only exists for type checkers is not a field the
> egress guard can walk.

- [ ] **Step 4: Populate them in `resolve`**

In `packages/mendel-resolver/src/mendel_resolver/resolve.py`, extend the signature:

```python
def resolve(
    goal: Goal,
    registry: Registry,
    rules: RuleTable,
    resolver: AmbiguityResolver | None = None,
    layer_names: Sequence[str] = (),
) -> PipelineIR:
    resolver = resolver or FlagOnlyResolver()
    plan = route(goal, registry, rules)
    ir = PipelineIR(
        registry_layers=list(layer_names),
        shadowed=list(registry.shadowed),
    )
```

Add `from collections.abc import Sequence` at the top.

- [ ] **Step 5: Pass them from the CLI**

In `packages/mendel-compiler/src/mendel_compiler/cli.py`, change the resolve call:

```python
    ir = resolve(goal, registry, rules, layer_names=[p.name for p in loaded.paths])
```

- [ ] **Step 6: Run the full suite and lint**

Run: `make check`
Expected: PASS. `pipeline.ir.json` gains two keys, so if any golden file asserts the whole
document it needs regenerating — read the diff before accepting it.

- [ ] **Step 7: Commit**

```bash
git add packages/
git commit -m "feat(core): the IR records which registry layers built it, and what they shadowed"
```

---

### Task 5: Decision replay

Federation §4.3, the property that makes curation worth anything:

> *Load a curated Goal, change one thing, and every untouched decision replays from its
> record. Only what you touched can move.*

Invariant 9 already says records are replayed rather than re-asked. This task is the class that
does it — and it is one more `AmbiguityResolver`, not a new subsystem.

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/replay.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/__init__.py`
- Test: `packages/mendel-resolver/tests/test_replay.py`

**Interfaces:**
- Consumes: `AmbiguityResolver`, `FlagOnlyResolver`, `DecisionRecord`, `Ambiguity`, `Resolution`
- Produces: `ReplayResolver(records, fallback=None)`; `ReplayResolver.replayed: list[DecisionKey]`;
  `ReplayResolver.fresh: list[DecisionKey]`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from comeni_core.decision import Ambiguity, DecisionRecord
from mendel_resolver.replay import ReplayResolver


def _ambiguity(subject="aligner", node="star_align"):
    return Ambiguity(node_id=node, subject=subject, candidates=["a", "b"], context={})


def _record(ambiguity, chosen="b", **kwargs):
    return DecisionRecord(
        key=ambiguity.key(),
        subject=ambiguity.subject,
        candidates=ambiguity.candidates,
        chosen=chosen,
        reason="recorded earlier",
        confidence=0.0,
        resolved_by="flag-only",
        **kwargs,
    )


def test_a_recorded_decision_replays_rather_than_being_re_asked():
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity)])
    resolution = resolver.resolve(ambiguity)
    assert resolution.chosen == "b"
    assert resolver.replayed == [ambiguity.key()]


def test_a_human_override_wins_over_the_original_choice():
    """The whole point of `human_override`: a person disagreed, and that must stick."""
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, chosen="b", human_override="a")])
    assert resolver.resolve(ambiguity).chosen == "a"


def test_a_replayed_resolution_says_it_was_replayed():
    ambiguity = _ambiguity()
    resolution = ReplayResolver([_record(ambiguity)]).resolve(ambiguity)
    assert resolution.resolved_by == "replay"
    assert "replay" in resolution.reason.lower()


def test_an_unrecorded_decision_falls_through_to_the_fallback():
    resolver = ReplayResolver([])
    resolution = resolver.resolve(_ambiguity())
    assert resolution.resolved_by == "flag-only"
    assert resolver.fresh == [_ambiguity().key()]


def test_a_record_whose_candidates_changed_is_not_replayed():
    """The registry moved underneath the record. Replaying would assert a choice between
    options that no longer exist, which is worse than asking again."""
    ambiguity = _ambiguity()
    stale = _record(ambiguity)
    resolver = ReplayResolver([stale])
    widened = Ambiguity(
        node_id="star_align", subject="aligner", candidates=["a", "b", "c"], context={}
    )
    assert resolver.resolve(widened).resolved_by == "flag-only"
    assert widened.key() in resolver.fresh


def test_a_record_whose_choice_is_no_longer_a_candidate_is_not_replayed():
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, chosen="gone")])
    assert resolver.resolve(ambiguity).resolved_by == "flag-only"


def test_replay_is_deterministic_over_duplicate_keys():
    """Two records for one key is a corrupt bundle. First wins, and it is documented."""
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, chosen="a"), _record(ambiguity, chosen="b")])
    assert resolver.resolve(ambiguity).chosen == "a"


def test_no_candidates_still_raises():
    from mendel_resolver.ports import NoCandidatesError

    empty = Ambiguity(node_id="n", subject="s", candidates=[], context={})
    with pytest.raises(NoCandidatesError):
        ReplayResolver([]).resolve(empty)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-resolver/tests/test_replay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_resolver.replay'`

- [ ] **Step 3: Write `replay.py`**

```python
"""Replaying recorded decisions instead of re-asking.

Invariant 9: records are replayed on rerun rather than re-asking the model. That is how
determinism survives having a model available at all — and applied to a *downloaded*
pipeline it is the property that makes curation worth doing (federation §4.3):

    Load a curated Goal, change one thing, and every untouched decision replays from its
    record. Only what you touched can move.

This is one more `AmbiguityResolver`, not a new subsystem. That is the payoff for having
declared the port in Plan 1: the thing that makes editing a curated pipeline safe costs
one class and no changes to the resolver.
"""

from collections.abc import Sequence

from comeni_core.decision import Ambiguity, DecisionRecord, Resolution
from comeni_core.marks import DecisionKey

from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver


class ReplayResolver:
    """Answers from a prior run's records; asks the fallback for anything new."""

    def __init__(
        self,
        records: Sequence[DecisionRecord],
        fallback: AmbiguityResolver | None = None,
    ) -> None:
        # First wins. Two records for one key is a corrupt bundle rather than a choice,
        # and picking arbitrarily between them would be the coin flip invariant 8 forbids.
        self._records: dict[str, DecisionRecord] = {}
        for record in records:
            self._records.setdefault(record.key, record)
        self._fallback = fallback or FlagOnlyResolver()
        self.replayed: list[DecisionKey] = []
        self.fresh: list[DecisionKey] = []

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        record = self._records.get(ambiguity.key())
        if record is not None and self._still_applies(record, ambiguity):
            self.replayed.append(ambiguity.key())
            chosen = record.human_override if record.human_override is not None else record.chosen
            return Resolution(
                chosen=chosen,
                reason=f"replayed from a recorded decision: {record.reason}",
                confidence=record.confidence,
                resolved_by="replay",
            )
        self.fresh.append(ambiguity.key())
        return self._fallback.resolve(ambiguity)

    @staticmethod
    def _still_applies(record: DecisionRecord, ambiguity: Ambiguity) -> bool:
        """Whether the world is close enough to when this was decided.

        Two ways it is not. The candidate set moved, so the record answers a question
        nobody is asking any more; or the choice itself is gone from the registry. Either
        way, replaying would assert a decision between options that no longer exist —
        worse than asking again, because it would look decided.
        """
        if list(record.candidates) != list(ambiguity.candidates):
            return False
        chosen = record.human_override if record.human_override is not None else record.chosen
        return chosen in ambiguity.candidates
```

- [ ] **Step 4: Export it**

In `packages/mendel-resolver/src/mendel_resolver/__init__.py`, add the import and the
`__all__` entry:

```python
from mendel_resolver.replay import ReplayResolver
```

- [ ] **Step 5: Run tests and lint**

Run: `uv run pytest packages/mendel-resolver/tests/test_replay.py -v && uv run ruff check .`
Expected: PASS, 8 tests.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-resolver
git commit -m "feat(resolver): replay recorded decisions, so only what you touched moves"
```

---

### Task 6: `mendel publish`

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: `Lockfile` (Task 3), `PublishBundle`, `PipelineIR.registry_layers` (Task 4)
- Produces: CLI `mendel publish --goal <path> --out <dir>`, writing `pipeline.bundle.json` and
  `mendel.lock.yml`

- [ ] **Step 1: Write the failing test**

```python
import json
import pathlib

import yaml
from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent
GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _publish(tmp_path, name="p"):
    out = tmp_path / name
    code = main(["publish", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)])
    assert code == 0
    return out


def test_publish_writes_a_bundle_and_a_lockfile(tmp_path):
    out = _publish(tmp_path)
    assert (out / "pipeline.bundle.json").exists()
    assert (out / "mendel.lock.yml").exists()


def test_the_bundle_carries_all_four_parts(tmp_path):
    """Federation 4.1: goal, IR, decisions, lockfile. Fewer than four is not reproducible."""
    bundle = json.loads((_publish(tmp_path) / "pipeline.bundle.json").read_text())
    assert set(bundle) == {"goal", "ir", "decisions", "lockfile"}
    assert bundle["goal"]["want"] == ["counts.matrix"]
    assert len(bundle["ir"]["nodes"]) == 5


def test_the_lockfile_pins_every_module_used(tmp_path):
    out = _publish(tmp_path)
    lock = yaml.safe_load((out / "mendel.lock.yml").read_text())
    ir = json.loads((out / "pipeline.bundle.json").read_text())["ir"]
    assert {c["id"] for c in lock["contracts"]} == {n["contract_id"] for n in ir["nodes"]}


def test_the_bundle_records_which_layers_built_it(tmp_path):
    bundle = json.loads((_publish(tmp_path) / "pipeline.bundle.json").read_text())
    assert bundle["ir"]["registry_layers"] == ["examples"]


def test_publishing_twice_produces_identical_bytes(tmp_path):
    """Determinism, applied to the artifact people share. No timestamps anywhere."""
    a, b = _publish(tmp_path, "a"), _publish(tmp_path, "b")
    assert (a / "pipeline.bundle.json").read_text() == (b / "pipeline.bundle.json").read_text()
    assert (a / "mendel.lock.yml").read_text() == (b / "mendel.lock.yml").read_text()


def test_publish_holds_no_filesystem_path(tmp_path):
    out = _publish(tmp_path)
    for name in ("pipeline.bundle.json", "mendel.lock.yml"):
        assert str(ROOT) not in (out / name).read_text()


def test_publish_reports_what_still_needs_review(tmp_path, capsys):
    """Federation 5.3: a published pipeline still carries its tier-4 flags."""
    _publish(tmp_path)
    err = capsys.readouterr().err
    assert "requiring review" in err
    assert "star_align.seq_platform" in err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_publish.py -v`
Expected: FAIL — argparse rejects `publish`.

- [ ] **Step 3: Add the verb**

In `cli.py`, add `"publish"` to the command choices:

```python
    parser.add_argument("command", choices=["build", "profile", "publish"])
```

`publish` needs `--goal`, exactly like `build`. In `_build`, change the goal-required check:

```python
    if args.command == "profile":
        goal = _profiling_goal(args, loaded)
    else:
        if args.goal is None:
            parser.error(f"{args.command} needs --goal")
```

- [ ] **Step 4: Write the bundle**

In `cli.py`, after the IR is emitted and before the gate block, add:

```python
    if args.command == "publish":
        # Federation §4.1: a shareable pipeline is what was asked for, what it resolved
        # to, why each choice was made, and against exactly which registry. All four, or
        # the recipient can neither reproduce it nor audit it.
        lockfile = Lockfile.of(ir, registry, loaded.paths)
        bundle = PublishBundle(
            goal=goal, ir=ir, decisions=ir.decisions, lockfile=lockfile
        )
        (args.out / "pipeline.bundle.json").write_text(bundle.model_dump_json(indent=2))
        (args.out / "mendel.lock.yml").write_text(
            yaml.safe_dump(lockfile.model_dump(mode="json"), sort_keys=True)
        )
```

with the imports:

```python
from comeni_core.egress import PublishBundle
from comeni_core.lockfile import Lockfile
```

> **Publication is the door with no undo, and this command does not send anything.** It
> writes files. Transmitting them is a later, separate act — which is the right shape,
> because it means a human can read what they are about to publish.

- [ ] **Step 5: Run the full suite and lint**

Run: `make check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-compiler tests/test_publish.py
git commit -m "feat(compiler): mendel publish writes a bundle and a lockfile"
```

---

### Task 7: `mendel upgrade`

Federation §4.3: *"`mendel upgrade` re-resolves a locked pipeline against the current registry
and reports what moved, at which tier, and why. Nothing upgrades implicitly."*

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/diff.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Test: `tests/test_upgrade.py`

**Interfaces:**
- Consumes: `ReplayResolver` (Task 5), `Lockfile.drift_against` (Task 3)
- Produces: `Change(what, before, after, tier, reason)`; `diff_ir(before, after) -> list[Change]`;
  CLI `mendel upgrade --bundle <path> --out <dir>`

- [ ] **Step 1: Write the failing test**

```python
import json
import pathlib
import shutil

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent
GOAL = ROOT / "examples" / "rnaseq-goal.yml"


def _published(tmp_path):
    out = tmp_path / "published"
    assert main(["publish", "--goal", str(GOAL), "--out", str(out), "--root", str(ROOT)]) == 0
    return out / "pipeline.bundle.json"


def _registry_with(tmp_path, edit):
    layer = tmp_path / "examples"
    shutil.copytree(ROOT / "examples", layer)
    edit(layer)
    return layer


def test_upgrading_against_an_unchanged_registry_reports_nothing(tmp_path, capsys):
    bundle = _published(tmp_path)
    code = main([
        "upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT),
    ])
    assert code == 0
    assert "no changes" in capsys.readouterr().err


def test_upgrading_reproduces_byte_identical_nextflow(tmp_path):
    """Federation 4.1: loading a locked pipeline reproduces byte-identical Nextflow."""
    bundle = _published(tmp_path)
    main(["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    assert (tmp_path / "up" / "main.nf").read_text() == (
        tmp_path / "published" / "main.nf"
    ).read_text()


def test_a_changed_rule_is_reported_with_its_tier_and_reason(tmp_path, capsys):
    def flip(layer):
        rules = layer / "rules" / "rnaseq.yml"
        rules.write_text(
            rules.read_text().replace(
                "{when: {strandedness: reverse},    then: 2}",
                "{when: {strandedness: reverse},    then: 1}",
            )
        )

    layer = _registry_with(tmp_path, flip)
    bundle = _published(tmp_path)
    main([
        "upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"),
        "--root", str(ROOT), "--registry", str(layer),
    ])
    err = capsys.readouterr().err
    assert "subread_featurecounts.strandedness" in err
    assert "2" in err and "1" in err
    assert "tier 3" in err


def test_drift_is_reported_even_when_nothing_resolved_differently(tmp_path, capsys):
    """A contract can be edited in ways that do not change this pipeline. Say so anyway —
    the lockfile no longer describes what is on disk, and that is worth knowing."""

    def touch(layer):
        sort = next(layer.rglob("samtools-sort.yml"))
        sort.write_text(sort.read_text().replace("priority: 0", "priority: 3"))

    layer = _registry_with(tmp_path, touch)
    bundle = _published(tmp_path)
    main([
        "upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"),
        "--root", str(ROOT), "--registry", str(layer),
    ])
    err = capsys.readouterr().err
    assert "has been edited since it was locked" in err


def test_untouched_decisions_replay(tmp_path, capsys):
    """The curation property. A tier-4 decision recorded before must not be re-asked."""
    bundle = _published(tmp_path)
    main(["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    ir = json.loads((tmp_path / "up" / "pipeline.ir.json").read_text())
    replayed = [d for d in ir["decisions"] if d["resolved_by"] == "replay"]
    assert replayed, "a recorded decision should have replayed rather than been re-asked"


def test_upgrade_never_writes_over_the_bundle_it_read(tmp_path):
    """Nothing upgrades implicitly. The old bundle is evidence."""
    bundle = _published(tmp_path)
    before = bundle.read_text()
    main(["upgrade", "--bundle", str(bundle), "--out", str(tmp_path / "up"), "--root", str(ROOT)])
    assert bundle.read_text() == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_upgrade.py -v`
Expected: FAIL — argparse rejects `upgrade`.

- [ ] **Step 3: Write `diff.py`**

```python
"""What moved between two resolutions of the same goal.

`mendel upgrade` re-resolves a locked pipeline against the current registry. The re-resolve
is the easy half; this is the half a person reads. Every line has to say *what* changed,
*from what to what*, and *at which tier* — because a tier-1 change and a tier-4 change
demand completely different amounts of attention, and a diff that flattens them is noise.
"""

from pydantic import BaseModel, ConfigDict

from comeni_core.ir import PipelineIR
from comeni_core.tiers import Tier


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")

    what: str
    """`node_id` for a module, `node_id.param` for a parameter."""
    before: str
    after: str
    tier: Tier
    reason: str

    def __str__(self) -> str:
        return f"  {self.what}: {self.before} -> {self.after}  (tier {self.tier}) {self.reason}"


def diff_ir(before: PipelineIR, after: PipelineIR) -> list[Change]:
    """Every module and parameter that resolved differently, in a stable order."""
    changes: list[Change] = []

    was = {node.id: node for node in before.nodes}
    now = {node.id: node for node in after.nodes}

    for node_id in sorted(set(was) | set(now)):
        old, new = was.get(node_id), now.get(node_id)
        if old is None:
            changes.append(Change(
                what=node_id, before="(absent)", after=new.contract_id,
                tier=new.selection.tier, reason=new.selection.reason,
            ))
            continue
        if new is None:
            changes.append(Change(
                what=node_id, before=old.contract_id, after="(removed)",
                tier=old.selection.tier, reason="no longer routed",
            ))
            continue
        if old.contract_id != new.contract_id:
            changes.append(Change(
                what=node_id, before=old.contract_id, after=new.contract_id,
                tier=new.selection.tier, reason=new.selection.reason,
            ))

        old_params = {b.name: b.value for b in old.params}
        for binding in new.params:
            previous = old_params.get(binding.name)
            if previous is None or previous.value != binding.value.value:
                changes.append(Change(
                    what=f"{node_id}.{binding.name}",
                    before="(unset)" if previous is None else str(previous.value),
                    after=str(binding.value.value),
                    tier=binding.value.tier,
                    reason=binding.value.reason,
                ))
    return changes
```

- [ ] **Step 4: Add the verb**

In `cli.py`: add `"upgrade"` to the choices, add `--bundle`, and branch before the normal
load. `upgrade` reads its goal from the bundle rather than from a file:

```python
    parser.add_argument("command", choices=["build", "profile", "publish", "upgrade"])
    parser.add_argument("--bundle", type=Path, default=None)
```

```python
    if args.command == "upgrade":
        if args.bundle is None:
            parser.error("upgrade needs --bundle")
        previous = PublishBundle.model_validate_json(args.bundle.read_text())
        goal = previous.goal
        resolver = ReplayResolver(previous.decisions)
    else:
        resolver = None
        ...  # the existing goal-loading branch
```

and resolve with it:

```python
    ir = resolve(
        goal, registry, rules,
        resolver=resolver,
        layer_names=[p.name for p in loaded.paths],
    )
```

- [ ] **Step 5: Report what moved**

After the IR is written, add:

```python
    if args.command == "upgrade":
        for line in previous.lockfile.drift_against(ir, registry, loaded.paths):
            print(f"  DRIFT   {line}", file=sys.stderr)
        changes = diff_ir(previous.ir, ir)
        if not changes:
            print("no changes: this pipeline re-resolves identically", file=sys.stderr)
        for change in changes:
            print(f"  CHANGED {change}", file=sys.stderr)
        if resolver is not None:
            print(
                f"{len(resolver.replayed)} decisions replayed, "
                f"{len(resolver.fresh)} newly asked",
                file=sys.stderr,
            )
```

with the imports:

```python
from mendel_resolver.diff import diff_ir
from mendel_resolver.replay import ReplayResolver
```

- [ ] **Step 6: Run the full suite and lint**

Run: `make check`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/ tests/test_upgrade.py
git commit -m "feat(compiler): mendel upgrade re-resolves a locked pipeline and says what moved"
```

---

### Task 8: The registry split

Federation §8: *"moving `contracts/`, `rules/` and `vocabularies/` out of `examples/` and into
the `comeni-registry` repository, with signed tags."*

`measurements/` joins them — it did not exist when that sentence was written.

**This task prepares the split; it does not perform it.** Creating a second repository and
signing tags is an operator action, not something a test can verify. What is buildable here is
making the move a configuration change rather than surgery, and proving it by loading the layer
from a location that is not `examples/`.

**Files:**
- Create: `registry/registry.yml`
- Move: `examples/{contracts,rules,vocabularies,measurements}` → `registry/`
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Modify: every test that hardcodes `examples/`
- Test: `tests/test_registry_layer.py`

**Interfaces:**
- Consumes: `layers.load`
- Produces: `registry/` as a self-describing layer; `--registry` defaulting to `<root>/registry`

- [ ] **Step 1: Write the failing test**

```python
import pathlib

import yaml
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent


def test_the_layer_describes_itself():
    """A layer that moves to its own repository has to say what it is, since the
    directory name it happened to be checked out into stops being meaningful."""
    manifest = yaml.safe_load((ROOT / "registry" / "registry.yml").read_text())
    assert manifest["name"]
    assert manifest["licence"] == "CC-BY-4.0"
    assert manifest["kinds"] == ["contracts", "measurements", "rules", "vocabularies"]


def test_the_layer_loads_from_its_new_home():
    loaded = layers.load(ROOT / "registry")
    assert len(loaded.registry.all()) >= 12
    assert loaded.measurements.ids() == ["n_samples", "paired", "read_length", "strandedness"]


def test_the_layer_loads_from_anywhere(tmp_path):
    """The move to comeni-registry is a path change and nothing else. Prove it by loading
    the layer from a directory with a different name."""
    import shutil

    elsewhere = tmp_path / "comeni-registry"
    shutil.copytree(ROOT / "registry", elsewhere)
    assert len(layers.load(elsewhere).registry.all()) >= 12


def test_the_goal_file_stayed_behind():
    """`Registry.load` globs `*.yml` recursively, so a goal file inside a layer would be
    read as a contract. It lives one level up for that reason."""
    assert (ROOT / "examples" / "rnaseq-goal.yml").exists()
    assert not list((ROOT / "registry").glob("*-goal.yml"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_registry_layer.py -v`
Expected: FAIL — `registry/` does not exist.

- [ ] **Step 3: Move the four kinds**

```bash
mkdir registry
git mv examples/contracts examples/rules examples/vocabularies examples/measurements registry/
```

`examples/` keeps `rnaseq-goal.yml` and gains nothing else. That is now honestly what it is: an
example goal.

- [ ] **Step 4: Write the manifest**

`registry/registry.yml`:

```yaml
# This layer is a registry: contracts, rules, vocabularies and measurements.
# It moves to github.com/comeni-project/comeni-registry with signed tags; nothing
# about it depends on living here, which is what this file exists to make true.
name: comeni-registry-examples
version: 0.1.0
licence: CC-BY-4.0
kinds: [contracts, measurements, rules, vocabularies]
description: >-
  Hand-written registry data sufficient to build and test the RNA-seq spine. Not a
  curated registry: every contract here is a test fixture that happens to be true.
```

> `registry.yml` sits at the layer root, beside `contracts/` rather than inside it, so
> `Registry.load`'s recursive glob never sees it.

- [ ] **Step 5: Repoint the default and the tests**

In `cli.py`:

```python
    loaded = layers.load(args.registry or [args.root / "registry"])
```

Then update every hardcoded path. Find them with:

```bash
grep -rn 'examples" */ *"contracts\|examples / "vocabularies\|examples / "measurements\|"examples"' \
  --include="*.py" tests/ packages/ tools/
```

Each becomes `registry` except `examples/rnaseq-goal.yml`, which does not move. The conftest
fixture in `packages/mendel-resolver/tests/conftest.py` and `tools/generate_types.py`'s
`MEASUREMENTS` constant both need it.

- [ ] **Step 6: Update the documentation that names the path**

```bash
grep -rln 'examples/contracts\|examples/rules\|examples/vocabularies\|examples/measurements\|--registry examples' \
  --include="*.md" . | grep -v internal/plans
```

`README.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md` and every page under
`docs/guides/` and `docs/reference/` mention it. `docs/internal/plans/` is a dated log and is
left alone.

- [ ] **Step 7: Run everything and lint**

Run: `make check && make stub`
Expected: PASS, and `gate stub: PASS`. The stub gate matters here: `--root` also finds
`vendor/modules`, and this is the task most likely to break that path.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: the registry becomes its own layer, ready to extract"
```

---

### Task 9: Document it

**Files:**
- Create: `docs/guides/publishing-a-pipeline.md`
- Create: `docs/reference/lockfile-schema.md`
- Modify: `docs/reference/cli.md`, `docs/README.md`, `CHANGELOG.md`, `CLAUDE.md`
- Create: `docs/internal/journal/<today>.md`

- [ ] **Step 1: Verify before describing**

```bash
make check
make stub
uv run mendel publish --goal examples/rnaseq-goal.yml --out published/
uv run mendel upgrade --bundle published/pipeline.bundle.json --out upgraded/
diff published/main.nf upgraded/main.nf && echo "byte-identical"
```

Describe what that produced, not what this plan predicted.

- [ ] **Step 2: Write the guide**

`docs/guides/publishing-a-pipeline.md`, covering: the four parts of a bundle and why fewer
than four is not reproducible; what the lockfile pins and what it deliberately does not
(paths, timestamps); the three visibility tiers with the note that **curated requires a named
human and can never be mechanical**; the edit-and-replay property with a worked example; and
that a published pipeline still carries its tier-4 flags, because curation asserts the
decisions were reviewed and never rewrites one into a lower tier.

- [ ] **Step 3: Write the reference**

`docs/reference/lockfile-schema.md`: every field of `Lockfile`, `LockedContract` and
`LockedLayer`, with the two absences stated as design decisions rather than omissions.

- [ ] **Step 4: Update the CLI reference and the docs index**

`publish` and `upgrade` join the table in `docs/reference/cli.md`, with their flags, their
outputs and their exit codes. Add the guide to `docs/README.md`.

- [ ] **Step 5: Update `CHANGELOG.md` and `CLAUDE.md`**

`CHANGELOG.md`: an `Unreleased` entry for lockfiles, publication, replay and the registry
split. `CLAUDE.md`: the architecture block's `examples/` line becomes `registry/`, the reading
table gains the new docs, and the "registry is a separate repository" paragraph changes from
future tense to "the layer is extracted; the repository move is the remaining operator step".

- [ ] **Step 6: Write the journal entry**

Follow `docs/internal/journal/README.md`. Record what shipped, what was corrected in this plan
during execution, and what is next — which is Plan 2, unless the real-data verification named
in the 2026-08-04 entry is still outstanding, in which case it is that.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "docs: publishing, lockfiles, and the registry split"
```

---

## Self-Review

**Spec coverage.**

| Federation spec | Task |
|---|---|
| §4.1 a pipeline is `Goal` + IR + records + lockfile | 1, 3, 6 |
| §4.1 lockfile pins contract digests | 2, 3 |
| §4.1 layer sources and vocabulary version | 3 (layer digests cover vocabularies, rules and measurements together) |
| §4.1 byte-identical reproduction | 7 (`test_upgrading_reproduces_byte_identical_nextflow`) |
| §4.2 three visibility tiers | 9 — documented. The mechanical gate for `published` is `--gate stub` then `--gate test`, both of which exist; **`curated` is a human act and this plan deliberately builds no mechanism for it.** |
| §4.3 edit a curated pipeline, only what you touched moves | 5, 7 |
| §4.3 `mendel upgrade` reports what moved, at which tier | 7 |
| §5.3 provenance survives publication | 6 (`test_publish_reports_what_still_needs_review`) |
| §8 `PipelineIR.registry_layers` and `.shadowed` | 4 |
| §8 the registry split | 8 |
| §5.1–5.2 pipeline review screens, catalogue | **Plan 3** — they need `mendel-api` and the frontend. Stated in the header. |

**Placeholder scan.** No TBDs. Every code step contains runnable code. Task 8 Steps 5 and 6 give
`grep` commands rather than listing every call site, because the list is mechanical and will have
drifted by the time anyone runs it — the command is more durable than its output.

**Type consistency.** `Lockfile.of(ir, registry, layers)` and `drift_against(ir, registry, layers)`
take the same three arguments in the same order in Tasks 3, 6 and 7. `Layers.paths` is
`list[Path]`, and every caller reduces it with `.name` or hands it to `Lockfile.of`, which reduces
it internally — the lockfile itself only ever stores `LayerName`. `ReplayResolver` satisfies the
`AmbiguityResolver` protocol, so `resolve(resolver=...)` needs no signature change beyond
`layer_names`. `Change.tier` is `Tier`, matching `ResolvedValue.tier`.

**Two guard failures, verified against the real guard before this plan was written** — not
predicted, run:

- `Constraints.required_states` is `dict[TypeId, list[StateName]]` and fails
  `test_no_payload_carries_a_mapping` the moment `PublishBundle` carries a `Goal`. Task 1
  Steps 7–10 convert it to a list of records and keep the mapping shorthand. **This is the
  single breaking type change in the plan**, and the before-validator means no goal file moves.
- `LockedContract.container` is a bare `str | None` and fails
  `test_no_payload_carries_an_undeclared_string`. Task 3 Step 6 adds a `ContainerRef` alias.

`GoalInput.type_id` was checked and is fine — it is `TypeId`, an annotated alias; the
`model_fields` dump shows a bare `str` because Pydantic strips the metadata there, which is
misleading. Use `typing.get_type_hints(model, include_extras=True)` when checking this, which is
what the guard itself does.

**Import cycle, checked:** `ir.py` does not import `registry.py` and `registry.py` does not
import `ir.py`, so Task 4's `from comeni_core.registry import ShadowRecord` is safe today. The
warning in that task stands for whoever reads it later.

---

## Verification

```bash
uv sync
make check
make stub
uv run mendel publish --goal examples/rnaseq-goal.yml --out published/
uv run mendel upgrade --bundle published/pipeline.bundle.json --out upgraded/
diff published/main.nf upgraded/main.nf
uv run python tools/generate_types.py --check
```

Complete when `publish` writes a four-part bundle and a lockfile that holds no path and no
timestamp, `upgrade` reproduces byte-identical Nextflow against an unchanged registry and names
every change with its tier against a changed one, a recorded decision replays rather than being
re-asked, and the registry loads from a directory that is not called `examples`.
