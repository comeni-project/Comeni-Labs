# The builder is a builder — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` and drive it
> yourself, sequentially, task by task. **Do NOT use `subagent-driven-development`** — that is the
> operator's standing instruction in `CLAUDE.md`, not a preference. Subagents are for review and
> design only. **Tick each `- [ ]` as it completes**, and where a step was carried out differently
> than written, tick it anyway and record the deviation in the execution record at the foot of
> this file.

**Goal:** turn `/build` from a visualiser into a Galaxy-style builder that checks a hand-drawn
pipeline, shows what the resolver would have built instead, and can be driven by a person's
clicks or by an agent's API calls through the same verbs.

**Architecture:** one new pure verb, `validate(graph, layers) -> Verdict`, in `mendel-resolver`.
The API exposes it, plus `compare` (validate yours, resolve the goal, align the two) and a
server-computed compatibility index the browser uses for zero-latency drag feedback without
re-implementing the rule. Drafts live in Postgres under an opaque id; keeping one writes the
`pipeline.yml`. Every choice a model made is recorded distinguishably from one a person made.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, SQLAlchemy 2 + Alembic, React 19 + TS + Vite +
Tailwind 4, TanStack Query, Vitest.

**Spec:** [`notes/specs/2026-08-19-the-builder-is-a-builder.md`](../specs/2026-08-19-the-builder-is-a-builder.md)
— verified against the code on 2026-08-23. Read it before Task 1; the plan argues from it.

## Global Constraints

- **`mendel-resolver` is PURE.** No network, no `ctypes`, no `subprocess`, no dynamic import.
  `tests/test_purity.py` and `tests/test_purity_runtime.py` enforce it. `validate()` lives there
  precisely because it must be golden-testable.
- **Never write a diagnostic code as a string literal.** Declare it in
  `packages/comeni-core/src/comeni_core/diagnostics.yml`, emit it through
  `comeni_core.diagnostics.coded(code, message)`. Both directions are tested.
- **`MD0400`–`MD0499` is allocated to gates and emission.** Validation uses `MD0500`–`MD0599`.
  A published code is never renumbered.
- **Anything reaching `pipeline.yml` is egress payload.** `tests/test_egress.py` runs an
  **allowlist**: every leaf field must be a declared ID alias from `comeni_core/spell/marks.py`
  or marked `Mark.FREE_TEXT`. A bare `str`, an `Any`, a `Path` or an `object` fails. `DecisionRecord`
  reaches door 4, so Task 6's new fields are egress fields.
- **`frozenset` has no stable order.** Anything new that serialises a set needs a
  `field_serializer` that sorts, like `IREdge._sorted_states`. Byte-identical emission is a hard
  requirement.
- **Run `make verify`, not `make check`.** This touches `mendel_compiler/emit.py`'s neighbours and
  `comeni_core/artifact/pipeline.py`, both on `CLAUDE.md`'s named list. `make check` deselects
  `tests/test_counts.py`, the only test exercising the v1 criterion.
- **No test may pass `--gate` to `mendel build`** unless it is *about* gates and `skipif`-guarded
  on `shutil.which("nextflow")`. CI has no Nextflow; a machine with one hides the failure.
- **Import modules, not symbols, where tests monkeypatch.** `from x import f` binds past a later
  patch of `x.f`.
- **`ruff check .` must pass; line length 100.** `ruff format` is not a gate — do not run a
  formatting sweep.
- **Commit after every task.** Message style: `feat:`, `fix:`, `docs:` with a lowercase subject.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/comeni-core/src/comeni_core/plan/draft.py` | **new** — `DraftGraph`, `DraftNode`, `DraftEdge`: a hand-drawn graph before anything has been decided about it |
| `packages/comeni-core/src/comeni_core/review/verdict.py` | **new** — `Verdict`, `Finding`, `Level`: what a check reports |
| `packages/comeni-core/src/comeni_core/diagnostics.yml` | **modify** — the `MD0500` band header comment and nine codes |
| `packages/comeni-core/src/comeni_core/plan/decision.py` | **modify** — `model_override` on all three kinds, `model_override_by` on `_Decided` |
| `packages/comeni-core/src/comeni_core/artifact/pipeline.py:63` | **modify** — `SCHEMA_VERSION = 5` |
| `packages/mendel-resolver/src/mendel_resolver/validate.py` | **new** — `validate(graph, layers) -> Verdict`, the whole verb |
| `packages/mendel-resolver/src/mendel_resolver/compatibility.py` | **new** — `index(layers) -> Compatibility`, derived from the same rules |
| `packages/mendel-api/src/mendel_api/services/validate.py` | **new** — thin: load the cached stack, call the verb |
| `packages/mendel-api/src/mendel_api/services/compare.py` | **new** — validate + resolve + align |
| `packages/mendel-api/src/mendel_api/services/drafts.py` | **new** — draft CRUD and `keep` |
| `packages/mendel-api/src/mendel_api/routes/build.py` | **modify** — five new endpoints |
| `packages/mendel-api/src/mendel_api/models.py` | **modify** — the `pipeline_draft` table |
| `packages/mendel-api/migrations/versions/<rev>_pipeline_draft.py` | **new** — one migration |
| `frontend/src/build/useGraph.ts` | **new** — the client-side working graph; every edit is local |
| `frontend/src/build/useCompatibility.ts` | **new** — index lookup during a drag |
| `frontend/src/build/Compare.tsx` | **new** — the alignment rail |
| `frontend/src/build/Builder.tsx` | **modify** — wire the above in |

---

## Task 1: The vocabulary — draft graphs, verdicts, and the MD0500 band

Nothing here decides anything. It exists so Tasks 2–4 have types to return and codes to cite.

**Files:**
- Create: `packages/comeni-core/src/comeni_core/plan/draft.py`
- Create: `packages/comeni-core/src/comeni_core/review/verdict.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`
- Modify: `packages/comeni-core/src/comeni_core/__init__.py`
- Test: `packages/comeni-core/tests/test_draft.py`

**Interfaces:**
- Consumes: `NodeId`, `ContractId`, `PortName` from `comeni_core.spell.marks`; `ParamBinding`
  from `comeni_core.plan.ir`; `DataProfile` from `comeni_core.goal.profile`.
- Produces: `DraftGraph(nodes, edges, profile)`, `DraftNode(id, contract_id, params)`,
  `DraftEdge(from_node, from_port, to_node, to_port)`, `Verdict(findings)`,
  `Finding(code, level, message, node, edge, port)`, `Level.ILLEGAL|UNMET|ADVISORY`.

- [ ] **Step 1: Write the failing test**

```python
# packages/comeni-core/tests/test_draft.py
"""A hand-drawn graph states four names per edge and derives nothing.

`IREdge` carries `type_id` and `states` because the resolver *computed* them from the source
port. A person drawing a wire has not computed anything, and a draft that carried those fields
could disagree with the contract it points at — a lie the validator would then have to catch.
Four names is the whole of what a drawn wire knows.
"""

import pytest
from pydantic import ValidationError

from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from comeni_core.review.verdict import Finding, Level, Verdict


def test_review_does_not_import_plan():
    """A146. `plan/` imports `review/`; the reverse edge is a cycle, and `plan/tiers.py` says so.
    A guard here rather than a convention, because the tempting field is `Finding.edge`."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "comeni_core" / "review"
    for module in root.rglob("*.py"):
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "comeni_core.plan"
            ):
                raise AssertionError(f"{module.name} imports {node.module}")


def test_a_drawn_edge_is_four_names():
    edge = DraftEdge(from_node="align", from_port="bam", to_node="sort", to_port="bam")
    assert edge.from_port == "bam"
    with pytest.raises(ValidationError):
        DraftEdge(  # type: ignore[call-arg]
            from_node="align", from_port="bam", to_node="sort", to_port="bam",
            type_id="alignment.bam",
        )


def test_a_draft_node_needs_only_an_id_and_a_contract():
    node = DraftNode(id="align", contract_id="nf-core/star/align@1.11.0")
    assert node.params == []


def test_a_verdict_is_illegal_when_any_finding_is():
    ok = Verdict(findings=[Finding(code="MD0507", level=Level.ADVISORY, message="unconventional")])
    assert ok.illegal == []
    assert ok.emittable is True

    bad = Verdict(findings=[Finding(code="MD0503", level=Level.ILLEGAL, message="state missing")])
    assert [f.code for f in bad.illegal] == ["MD0503"]
    assert bad.emittable is False


def test_a_finding_must_cite_a_declared_code():
    with pytest.raises(ValueError, match="not a declared diagnostic"):
        Finding(code="MD9999", level=Level.ILLEGAL, message="nope")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/comeni-core/tests/test_draft.py -v
```

Expected: `ModuleNotFoundError: No module named 'comeni_core.plan.draft'`.

- [ ] **Step 3: Add the `MD0500` band to the header comment**

In `packages/comeni-core/src/comeni_core/diagnostics.yml`, after the `MD0400` line (line 16):

```yaml
#   MD0500-MD0599  validating a hand-built graph
```

- [ ] **Step 4: Declare the nine codes**

Append to `diagnostics.yml`. Every field is required; copy the shape from `MD0011`.

```yaml
MD0501:
  emitted_by: core
  concern: validation
  says: "an edge names a port that does not exist on that contract"
  fires_on: [validate]
  refuses: false
  fix: |
    The message names the contract and the port. Check the contract's `consumes` and
    `produces` — the port name is the emit label, not the semantic type, so `bam` and
    `alignment.bam` are different things.
  explanation: |
    A drawn wire names four things and any of them can be wrong. This is the first check
    because every later one reads the port it could not find.

MD0502:
  emitted_by: core
  concern: validation
  says: "an edge runs the wrong way — an input feeding an output, or an output into an output"
  fires_on: [validate]
  refuses: false
  fix: |
    Wires run from a `produces` port to a `consumes` port. Reverse it.
  explanation: |
    The resolver cannot produce this error because it only ever draws edges from a producer
    it searched for. A hand-drawn graph has no such protection, which is the whole difference
    between searching and checking.

MD0503:
  emitted_by: core
  concern: validation
  says: "the source type does not satisfy what the target port requires"
  fires_on: [validate]
  refuses: false
  fix: |
    Either wire a different producer, or check the target's `accepts` list — an alternative
    declares its own `type_id` and `states` and is a legitimate second answer.
  explanation: |
    Type identity is the cheap half. The states are the half that matters: `alignment.bam`
    with no state and `alignment.bam[coordinate_sorted]` are the same type and only one of
    them can feed featureCounts.

MD0504:
  emitted_by: core
  concern: validation
  says: "the source does not carry every state the target requires"
  fires_on: [validate]
  refuses: false
  fix: |
    Insert the step that adds the state. A BAM straight out of an aligner is unsorted;
    `samtools/sort` is what produces `coordinate_sorted`.
  explanation: |
    This is the single most common thing a hand-drawn RNA-seq graph gets wrong, and it is
    invisible in `meta.yml`: nf-core declares both ports as `type: file, *.bam` and the word
    "sorted" exists only in the English description. The semantic state overlay is what makes
    this checkable at all.

MD0505:
  emitted_by: core
  concern: validation
  says: "too many wires reach a port that accepts one"
  fires_on: [validate]
  refuses: false
  fix: |
    The message names the port's declared `cardinality`. Remove the extra wires, or wire
    through a step that collects them.
  explanation: |
    Nextflow matches arity, and a channel carrying two things where one is expected does not
    fail at lint — it fails at run, late, with a message about a null path.

MD0506:
  emitted_by: core
  concern: validation
  says: "a required input has no wire and no entry channel"
  fires_on: [validate]
  refuses: false
  fix: |
    Wire something into it, or check whether the type declares an `entry_channel` — a genome
    or an annotation arrives from `params`, not from an upstream step.
  explanation: |
    The half of this check that is not about edges. 3C drew a hollow *unmet* dot on
    `star_align.gtf`, which arrives from `params.gtf` and is perfectly satisfied. A check that
    reads only edges is wrong about every entry channel in the pipeline.

MD0507:
  emitted_by: core
  concern: validation
  says: "the edge is legal but not what convention would choose"
  fires_on: [validate]
  refuses: false
  fix: |
    Nothing is broken. The message names the state the target prefers and what it got. Keep
    it deliberately, or wire the preferred producer.
  explanation: |
    `InputPort` declares three kinds of requirement — `state_required`,
    `state_required_conventional`, and `state_preferred` / `prefer`. Only the first is a
    refusal. Returning a boolean would collapse the other two into silence, and the difference
    between "illegal" and "not what we would have done" is the difference between a compiler
    and a colleague.

MD0509:
  emitted_by: core
  concern: validation
  says: "a node names a contract that is not in the registry stack"
  fires_on: [validate]
  refuses: false
  fix: |
    Check the spelling and the version — a contract id carries `@version` and a draft saved
    against a different registry stack may name one that is no longer there. `forge check`
    reports what the registry actually holds.
  explanation: |
    Distinct from MD0501, which is about a *port* on a contract that was found. This one is
    reported once per node rather than once per edge touching it: a draft naming a contract
    that has been renamed would otherwise print the same failure four times and bury it.

    It is `illegal` rather than `unmet` because nothing about the node can be checked — every
    later check reads a contract this one could not load.

MD0508:
  emitted_by: core
  concern: validation
  says: "the graph contains a cycle"
  fires_on: [validate]
  refuses: false
  fix: |
    The message names the nodes on the cycle in order. Break it.
  explanation: |
    Routing forbids cycles by construction — `producers_of` excludes the node itself, which
    is what stops `SAMTOOLS_SORT` recursing into its own BAM input forever. A hand-drawn graph
    has no such protection.
```

- [ ] **Step 5: Write `draft.py`**

```python
# packages/comeni-core/src/comeni_core/plan/draft.py
"""A graph somebody drew, before anything has been decided about it.

**Not `PipelineIR`.** An `IREdge` carries `type_id` and `states` because the resolver computed
them from the source port while searching; an `IRNode` carries a `selection` and a `presence`
saying at which tier it was chosen. A person dragging a wire has computed nothing and chosen
nothing at any tier, and a draft carrying those fields could *disagree* with the contract it
points at — which would make the validator's first job checking the input against itself.

Four names per edge, two per node. Everything else is derived by `validate`.
"""

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.goal.profile import DataProfile
from comeni_core.plan.ir import ParamBinding
from comeni_core.spell.marks import ContractId, NodeId, PortName

__all__ = ["DraftEdge", "DraftGraph", "DraftNode"]


class DraftEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_node: NodeId
    from_port: PortName
    to_node: NodeId
    to_port: PortName


class DraftNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    contract_id: ContractId
    params: list[ParamBinding] = Field(default_factory=list)


class DraftGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[DraftNode] = Field(default_factory=list)
    edges: list[DraftEdge] = Field(default_factory=list)
    profile: DataProfile = Field(default_factory=DataProfile)
    """Carried because an advisory check may want to say *the rule that would have fired here
    read a measurement you have not supplied*. `validate` never resolves; it only reports."""
```

- [ ] **Step 6: Write `verdict.py`**

```python
# packages/comeni-core/src/comeni_core/review/verdict.py
"""What a check reports. **It reports; it does not refuse.**

The precedent is the forge's `verify` ladder. Three problems visible in one pass through the
screen beats three refusals, and the person drawing the graph is mid-gesture rather than at a
gate. Refusal stays where it already lives: `keep` and the emission gates.

`review/` is the right home rather than `plan/` — this is the stage where something is *open*,
and a `Verdict` is the forge's and the resolver's shared answer to "what is still wrong".

**Which is exactly why nothing here may import `plan/`.** `plan/decision.py` imports `Question`
from this package and `plan/tiers.py` imports `ValueSource`; an edge back would be a cycle, and
`tiers.py`'s own comment says so. A finding names a wire with an `EdgeRef` — a `spell/` alias,
below both — and never with a `DraftEdge`.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from comeni_core.diagnostics import REGISTRY
from comeni_core.spell.marks import EdgeRef, NodeId, PortName

__all__ = ["Finding", "Level", "Verdict"]


class Level(StrEnum):
    ILLEGAL = "illegal"
    """The graph cannot be emitted."""

    UNMET = "unmet"
    """Something required has nothing behind it. Not illegal — incomplete."""

    ADVISORY = "advisory"
    """Legal, and not what convention or a rule would have chosen."""


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    level: Level
    message: str
    node: NodeId | None = None
    port: PortName | None = None

    source: EdgeRef | None = None
    """The upstream output this finding is about, as `<node>.<port>`."""

    target: EdgeRef | None = None
    """The consuming input. **Two `EdgeRef`s, not one `DraftEdge` and not one wire string** —
    audits A146 and A157.

    A146: `plan/decision.py` and `plan/tiers.py` both import from `review/`, and `plan/tiers.py`
    says in as many words that `ValueSource` lives in `review/answer.py` *"so that `review/` need
    not import `plan/` — the reverse edge would be a cycle"*. A `Finding` carrying a `DraftEdge`
    closes that loop and fails at import.

    A157: the first fix for A146 made this one `EdgeRef` spelled `a:bam->b:bam`, which
    `_edge_ref` refuses — an `EdgeRef` names **one endpoint**, `<node>.<port>`, and its docstring
    says so. A wire is two of them. Two fields, both validated by an alias that already exists,
    and no new spelling invented for something the system already knows how to write down.
    """

    @field_validator("code")
    @classmethod
    def _declared(cls, code: str) -> str:
        """Same guarantee `coded()` gives, at the other end.

        `coded()` checks the code when a *message* is built. A `Finding` is data that may be
        constructed without one, so the check has to exist here too or an undeclared code
        reaches a client through the field rather than the sentence.
        """
        if code not in REGISTRY:
            raise ValueError(
                f"{code} is not a declared diagnostic. Declare it in comeni_core/"
                f"diagnostics.yml, or fix the code."
            )
        return code


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[Finding] = []

    @property
    def illegal(self) -> list[Finding]:
        return [f for f in self.findings if f.level is Level.ILLEGAL]

    @property
    def emittable(self) -> bool:
        """**Not "is it finished".** An `UNMET` port is legal to hold in a draft and illegal to
        emit; that is `keep`'s judgement, made against `illegal` plus `unmet`. This property
        answers only whether anything is outright wrong."""
        return not self.illegal
```

- [ ] **Step 7: Export both from the package surface**

`comeni_core/__init__.py` is what holds the public surface stable (issue #41). Add
`DraftEdge`, `DraftGraph`, `DraftNode`, `Finding`, `Level`, `Verdict` to its imports and
`__all__`, in the existing alphabetical position.

- [ ] **Step 8: Regenerate the diagnostics page and run the tests**

```bash
uv run python tools/generate_diagnostics_doc.py
uv run pytest packages/comeni-core/tests/test_draft.py tests/test_diagnostics_ownership.py -v
```

Expected: the draft tests PASS. **`test_diagnostics_ownership.py` will FAIL** with
"declared but never emitted" for all nine new codes.

**This commit is knowingly red, and audit A151 says to say so rather than let it look like an
accident.** Two options were weighed: split the declarations across Tasks 1–3 so each commit is
green, or declare them together and carry one red commit. The second was taken because the nine
codes are one vocabulary and reading them in one diff is worth more than a green intermediate —
but that is a judgement, and if you would rather have green commits, split Step 4 by task and
record the deviation. **Do not skip the ownership test to make it pass.**

If it does *not* fail, the ownership guard is not watching — a finding in its own right; append
it to `notes/audits/guard-ledger.md`.

- [ ] **Step 9: Commit, and say in the message that it is red**

```bash
git add packages/comeni-core/src/comeni_core/plan/draft.py \
        packages/comeni-core/src/comeni_core/review/verdict.py \
        packages/comeni-core/src/comeni_core/diagnostics.yml \
        packages/comeni-core/src/comeni_core/__init__.py \
        packages/comeni-core/tests/test_draft.py \
        docs/reference/diagnostics.md
git commit -m "feat(core): a drawn graph, a verdict, and the MD0500 band

The nine codes are declared and not yet emitted, so test_diagnostics_ownership
fails until the next commit. Declared together on purpose: they are one
vocabulary and read better in one diff than split across three."
```

---

## Task 2: `validate()` — the edge checks

Six of the nine codes. This task makes `test_diagnostics_ownership.py` green again for
`MD0501`–`MD0504`, `MD0507` and `MD0509`.

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/validate.py`
- Test: `packages/mendel-resolver/tests/test_validate_edges.py`

**Interfaces:**
- Consumes: `DraftGraph`, `DraftEdge`, `Verdict`, `Finding`, `Level` from Task 1; `Layers` from
  `mendel_resolver.layers`; `InputPort.alternatives()` and `OutputPort` from
  `comeni_core.declared.contract`; `Registry.get`.
- Produces: `validate(graph: DraftGraph, layers: Layers) -> Verdict`.

**Read before starting:** `packages/mendel-resolver/src/mendel_resolver/router.py:294` —
`_satisfy_port`. It walks `port.alternatives()` first-match-wins and that is exactly the
comparison this task inverts. Do not re-derive it.

- [ ] **Step 0: Add a `stack` fixture to the resolver conftest**

`packages/mendel-resolver/tests/conftest.py` already has `EXAMPLES = ROOT / "registry"` and a
`spine` fixture built from it. Add beside them — one loaded stack for every validate test, rather
than three test files each inventing a path:

```python
@pytest.fixture(scope="session")
def stack():
    """The shipped registry, loaded once. `session` rather than `module` because `layers.load`
    is the 244ms function the performance audit found and three test files share this."""
    return layers.load(EXAMPLES)
```

- [ ] **Step 1: Write the failing tests**

The example is real and comes from the shipped registry: `nf-core/star/align` produces
`alignment.bam` with `state: []`; `nf-core/subread/featurecounts` consumes `alignment.bam` with
`state_required: [coordinate_sorted]`; `nf-core/samtools/sort` consumes `alignment.bam` with no
state required and produces it `[coordinate_sorted]`.

```python
# packages/mendel-resolver/tests/test_validate_edges.py
"""Wiring an aligner straight into featureCounts is the canonical hand-drawn mistake.

It is invisible in `meta.yml` — nf-core declares both ports as `type: file, *.bam` and the word
"sorted" lives only in the English description — so it is exactly the error a semantic state
overlay exists to make checkable.
"""

import pytest

from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from comeni_core.review.verdict import Level
from mendel_resolver import layers as layers_module
from mendel_resolver.validate import validate

STAR = "nf-core/star/align"
SORT = "nf-core/samtools/sort"
COUNTS = "nf-core/subread/featurecounts"


# `stack` comes from the conftest — see Step 0.


def _graph(*nodes_and_edges):
    nodes, edges = nodes_and_edges
    return DraftGraph(
        nodes=[DraftNode(id=i, contract_id=c) for i, c in nodes],
        edges=[DraftEdge(from_node=a, from_port=b, to_node=c, to_port=d) for a, b, c, d in edges],
    )


def test_an_unsorted_bam_into_featurecounts_is_illegal(stack):
    graph = _graph(
        [("align", STAR), ("counts", COUNTS)],
        [("align", "bam", "counts", "bam")],
    )
    verdict = validate(graph, stack)
    codes = {f.code for f in verdict.illegal}
    assert "MD0504" in codes, verdict.findings
    assert "coordinate_sorted" in next(f for f in verdict.illegal if f.code == "MD0504").message


def test_the_same_bam_through_a_sorter_is_legal(stack):
    graph = _graph(
        [("align", STAR), ("sort", SORT), ("counts", COUNTS)],
        [("align", "bam", "sort", "bam"), ("sort", "bam", "counts", "bam")],
    )
    verdict = validate(graph, stack)
    assert [f for f in verdict.illegal if f.code in {"MD0503", "MD0504"}] == []


def test_a_port_that_does_not_exist(stack):
    graph = _graph(
        [("align", STAR), ("sort", SORT)],
        [("align", "bamm", "sort", "bam")],
    )
    verdict = validate(graph, stack)
    assert [f.code for f in verdict.illegal if f.code == "MD0501"] == ["MD0501"]


def test_a_wire_running_backwards(stack):
    """`sort.bam` is BOTH an input and an output port name on samtools/sort, which is why this
    check reads the direction rather than the name."""
    graph = _graph(
        [("align", STAR), ("sort", SORT)],
        [("sort", "bam", "align", "bam")],
    )
    verdict = validate(graph, stack)
    assert "MD0502" in {f.code for f in verdict.illegal}


def test_a_wrong_type_is_MD0503_not_MD0504(stack):
    """Type identity and state are different failures and must not collapse into one code —
    "wire a sorter in" is the fix for one of them and useless for the other."""
    graph = _graph(
        [("counts", COUNTS), ("sort", SORT)],
        [("counts", "counts", "sort", "bam")],
    )
    verdict = validate(graph, stack)
    assert "MD0503" in {f.code for f in verdict.illegal}
    assert "MD0504" not in {f.code for f in verdict.illegal}


def test_every_finding_carries_the_edge_it_is_about(stack):
    """A verdict a canvas can draw. A finding with no anchor is a sentence in a log."""
    graph = _graph(
        [("align", STAR), ("counts", COUNTS)],
        [("align", "bam", "counts", "bam")],
    )
    for finding in validate(graph, stack).findings:
        assert finding.target is not None or finding.node is not None


def test_a_node_naming_an_unknown_contract_is_reported_once(stack):
    """Once per node, not once per edge. A renamed contract with four wires on it would
    otherwise print the same failure four times and bury it."""
    graph = _graph(
        [("gone", "nf-core/nothing/here@1.0.0"), ("sort", SORT)],
        [("gone", "bam", "sort", "bam")],
    )
    codes = [f.code for f in validate(graph, stack).findings]
    assert codes.count("MD0509") == 1


def test_it_reports_every_problem_rather_than_the_first(stack):
    """The forge's `verify` ladder is the precedent. Three problems in one pass."""
    graph = _graph(
        [("align", STAR), ("counts", COUNTS), ("sort", SORT)],
        [("align", "bam", "counts", "bam"), ("align", "nope", "sort", "bam")],
    )
    codes = {f.code for f in validate(graph, stack).findings}
    assert {"MD0501", "MD0504"} <= codes
```

- [ ] **Step 2: Run them and watch them fail**

```bash
uv run pytest packages/mendel-resolver/tests/test_validate_edges.py -v
```

Expected: `ModuleNotFoundError: No module named 'mendel_resolver.validate'`.

There is no `tests.helpers` module — audit A147. The resolver's own
`packages/mendel-resolver/tests/conftest.py` already defines `ROOT = pathlib.Path(__file__).parents[3]`
and `EXAMPLES = ROOT / "registry"`. Step 0 below adds the fixture there.

- [ ] **Step 3: Write the edge half of `validate.py`**

```python
# packages/mendel-resolver/src/mendel_resolver/validate.py
"""`validate(graph, layers) -> Verdict` — the inverse of `resolve`.

**`resolve()` searches; this checks.** Both read the same declared facts in opposite directions:
the resolver is handed a goal and asked to find edges, and this is handed edges and asked whether
they hold. Nothing new is declared — see the spec's §2 table.

**It reports; it never raises.** The router raises `UnroutableError` because it has failed to
build something; there is nothing to hand back. Here there is: a graph with three problems in it,
and a person mid-gesture who would rather see all three.

**Pure, and that is load-bearing.** A check living in the browser would be a check the agent
driving the API cannot run, and then there are two answers to *is this legal*. The compatibility
index in `compatibility.py` is an optimisation *of this verb's answer*, never a second opinion.
"""

from comeni_core.declared.contract import InputPort, ModuleContract, OutputPort
from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftEdge, DraftGraph
from comeni_core.review.verdict import Finding, Level, Verdict

from mendel_resolver.layers import Layers

__all__ = ["validate"]


def validate(graph: DraftGraph, layers: Layers) -> Verdict:
    findings: list[Finding] = []
    contracts = _contracts(graph, layers, findings)
    for edge in graph.edges:
        findings.extend(_check_edge(edge, contracts))
    return Verdict(findings=findings)


def _contracts(
    graph: DraftGraph, layers: Layers, findings: list[Finding]
) -> dict[str, ModuleContract]:
    """Node id to contract, skipping nodes whose contract is not in the stack.

    A node naming an unknown contract is reported once as `MD0509`, rather than once per edge
    that touches it — a renamed contract would otherwise print the same failure four times.
    `MD0501` is the *port* failure and stays distinct, because the fixes differ.
    """
    resolved: dict[str, ModuleContract] = {}
    for node in graph.nodes:
        try:
            resolved[node.id] = layers.registry.get(node.contract_id)
        except (KeyError, ValueError):
            findings.append(
                Finding(
                    code="MD0509",
                    level=Level.ILLEGAL,
                    message=coded(
                        "MD0509",
                        # `Registry.get` raises a bare `KeyError(contract_id)`, so `{exc}` is
                        # just the id in quotes and adds nothing (audit A154). The sentence
                        # carries the explanation instead.
                        f"node {node.id!r} names {node.contract_id!r}, which is not in this "
                        f"registry stack",
                    ),
                    node=node.id,
                )
            )
    return resolved


def _output(contract: ModuleContract, name: str) -> OutputPort | None:
    return next((p for p in contract.produces if p.name == name), None)


def _input(contract: ModuleContract, name: str) -> InputPort | None:
    return next((p for p in contract.consumes if p.name == name), None)


def _check_edge(edge: DraftEdge, contracts: dict[str, ModuleContract]) -> list[Finding]:
    source = contracts.get(edge.from_node)
    target = contracts.get(edge.to_node)
    if source is None or target is None:
        return []  # already reported by `_contracts`

    out = _output(source, edge.from_port)
    inp = _input(target, edge.to_port)

    # Direction before existence-of-the-right-kind: `samtools/sort` has a `bam` on BOTH sides,
    # so a backwards wire names two ports that both exist and is not a typo.
    if out is None and _input(source, edge.from_port) is not None:
        return [
            _f("MD0502", Level.ILLEGAL, edge,
               f"{edge.from_node}.{edge.from_port} is an input; a wire starts at an output")
        ]
    if inp is None and _output(target, edge.to_port) is not None:
        return [
            _f("MD0502", Level.ILLEGAL, edge,
               f"{edge.to_node}.{edge.to_port} is an output; a wire ends at an input")
        ]
    if out is None:
        return [
            _f("MD0501", Level.ILLEGAL, edge,
               f"{source.id} has no output port {edge.from_port!r}; it produces "
               f"{sorted(p.name for p in source.produces)}")
        ]
    if inp is None:
        return [
            _f("MD0501", Level.ILLEGAL, edge,
               f"{target.id} has no input port {edge.to_port!r}; it consumes "
               f"{sorted(p.name for p in target.consumes)}")
        ]

    return _check_types(edge, out, inp)


def _check_types(edge: DraftEdge, out: OutputPort, inp: InputPort) -> list[Finding]:
    """`alternatives()` is the author's own preference order and is not re-derived here.

    Index 0 is the conventional form — `state_required | state_required_conventional`; the
    fallback, where one exists, is `state_required` alone. Matching only the fallback is legal
    and unconventional, which is the `advisory` level.
    """
    alternatives = inp.alternatives()
    for position, alternative in enumerate(alternatives):
        if alternative.type_id != out.type_id:
            continue
        if not alternative.states <= out.state:
            continue
        if position == 0:
            return _preference(edge, out, inp)
        return [
            _f("MD0507", Level.ADVISORY, edge,
               f"{edge.to_node}.{edge.to_port} conventionally wants "
               f"{sorted(alternatives[0].states)}; this source carries {sorted(out.state)}")
        ] + _preference(edge, out, inp)

    # Nothing matched. Which half failed decides the code, because the fixes differ.
    if any(a.type_id == out.type_id for a in alternatives):
        wanted = next(a for a in alternatives if a.type_id == out.type_id)
        return [
            _f("MD0504", Level.ILLEGAL, edge,
               f"{edge.to_node}.{edge.to_port} requires {sorted(wanted.states)}; "
               f"{edge.from_node}.{edge.from_port} carries {sorted(out.state)}")
        ]
    return [
        _f("MD0503", Level.ILLEGAL, edge,
           f"{edge.to_node}.{edge.to_port} takes {' or '.join(sorted(a.type_id for a in alternatives))}; "
           f"{edge.from_node}.{edge.from_port} emits {out.type_id}")
    ]


def _preference(edge: DraftEdge, out: OutputPort, inp: InputPort) -> list[Finding]:
    """`prefer` is a preference between SOURCES, not between kinds of input.

    That is why it sits outside `alternatives()`: an alternative says *what shape of thing*,
    and this says *which of two legal things we would rather have*.
    """
    missing = inp.prefer - out.state
    if not missing:
        return []
    return [
        _f("MD0507", Level.ADVISORY, edge,
           f"{edge.to_node}.{edge.to_port} prefers {sorted(missing)}, which this source "
           f"does not carry")
    ]


def _f(code: str, level: Level, edge: DraftEdge, message: str) -> Finding:
    """`<node>.<port>` on each end — the spelling `SourceDecision.chosen` already uses, so a
    finding and a decision name an endpoint the same way (audit A157)."""
    return Finding(
        code=code,
        level=level,
        message=coded(code, message),
        source=f"{edge.from_node}.{edge.from_port}",
        target=f"{edge.to_node}.{edge.to_port}",
    )
```

- [ ] **Step 4: Run the tests and the ownership guard**

```bash
uv run pytest packages/mendel-resolver/tests/test_validate_edges.py -v
uv run pytest tests/test_diagnostics_ownership.py -v
```

Expected: edge tests PASS. Ownership still fails for `MD0505`, `MD0506`, `MD0508` — Task 3.

- [ ] **Step 5: Confirm the verb did not break purity**

```bash
uv run pytest tests/test_purity.py tests/test_purity_runtime.py -v
```

Expected: PASS. `validate.py` imports only `comeni_core` and `collections`.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-resolver/src/mendel_resolver/validate.py \
        packages/mendel-resolver/tests/test_validate_edges.py
git commit -m "feat(resolver): validate the edges of a hand-drawn graph"
```

---

## Task 3: `validate()` — unmet inputs, arity, and cycles

The other three codes. **`MD0506` is the one 3C got wrong**, so its test comes from the defect.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/validate.py`
- Test: `packages/mendel-resolver/tests/test_validate_graph.py`

**Interfaces:**
- Consumes: everything from Task 2, plus `Vocabulary.entry_channels: dict[str, str]` from
  `layers.vocabulary`.
- Produces: no signature change. `validate` returns more findings.

- [ ] **Step 1: Read every landed contract's declared cardinality before trusting the field**

Spec §C4: `InputPort.cardinality` has no reader anywhere in `packages/`, so no contract's value
has ever been checked against reality.

```bash
uv run python - <<'EOF'
from pathlib import Path
from mendel_resolver import layers
stack = layers.load(Path("registry"))
for c in stack.registry.all():
    for p in c.consumes:
        if p.cardinality != "1":
            print(f"{c.id:45} {p.name:16} cardinality={p.cardinality!r}")
EOF
```

Record the output in the execution table. If every port is `"1"`, `MD0505` ships with one legal
value exercised and that is worth saying out loud rather than implying broader coverage.

- [ ] **Step 2: Write the failing tests**

```python
# packages/mendel-resolver/tests/test_validate_graph.py
"""The checks that are about the graph rather than about one wire."""

import pytest

from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from comeni_core.review.verdict import Level
from mendel_resolver import layers as layers_module
from mendel_resolver.validate import validate

STAR = "nf-core/star/align"
SORT = "nf-core/samtools/sort"
COUNTS = "nf-core/subread/featurecounts"


def test_an_input_fed_by_an_entry_channel_is_not_unmet(stack):
    """**The defect 3C shipped and caught.**

    `star/align` consumes a GTF that arrives from `params.gtf` and has no incoming edge. A
    check reading only edges drew a hollow *unmet* dot on a satisfied input. `annotation.gtf`
    declares an `entry_channel` in the vocabulary, and that is what makes it met.
    """
    graph = DraftGraph(nodes=[DraftNode(id="align", contract_id=STAR)])
    unmet = [f for f in validate(graph, stack).findings if f.code == "MD0506"]
    assert "gtf" not in {f.port for f in unmet}, [f.message for f in unmet]


def test_an_input_with_neither_a_wire_nor_an_entry_channel_is_unmet(stack):
    graph = DraftGraph(nodes=[DraftNode(id="counts", contract_id=COUNTS)])
    unmet = [f for f in validate(graph, stack).findings if f.code == "MD0506"]
    assert "bam" in {f.port for f in unmet}
    assert all(f.level is Level.UNMET for f in unmet)


def test_unmet_is_not_illegal(stack):
    """A half-drawn graph is a legal thing to be holding. `keep` refuses it; `validate` does not."""
    graph = DraftGraph(nodes=[DraftNode(id="counts", contract_id=COUNTS)])
    verdict = validate(graph, stack)
    assert verdict.illegal == []
    assert verdict.emittable is True


def test_a_cycle_is_reported_with_its_nodes_in_order(stack):
    """`SAMTOOLS_SORT` consumes and produces `alignment.bam`, so it is a candidate for its own
    dependency. Routing excludes the node itself and cannot draw this; a person can."""
    graph = DraftGraph(
        nodes=[DraftNode(id="a", contract_id=SORT), DraftNode(id="b", contract_id=SORT)],
        edges=[
            DraftEdge(from_node="a", from_port="bam", to_node="b", to_port="bam"),
            DraftEdge(from_node="b", from_port="bam", to_node="a", to_port="bam"),
        ],
    )
    cycles = [f for f in validate(graph, stack).findings if f.code == "MD0508"]
    assert cycles and cycles[0].level is Level.ILLEGAL
    assert "a" in cycles[0].message and "b" in cycles[0].message


def test_a_self_loop_is_a_cycle(stack):
    graph = DraftGraph(
        nodes=[DraftNode(id="a", contract_id=SORT)],
        edges=[DraftEdge(from_node="a", from_port="bam", to_node="a", to_port="bam")],
    )
    assert "MD0508" in {f.code for f in validate(graph, stack).findings}


def test_two_wires_into_a_port_that_takes_one(stack):
    graph = DraftGraph(
        nodes=[
            DraftNode(id="x", contract_id=STAR),
            DraftNode(id="y", contract_id=STAR),
            DraftNode(id="sort", contract_id=SORT),
        ],
        edges=[
            DraftEdge(from_node="x", from_port="bam", to_node="sort", to_port="bam"),
            DraftEdge(from_node="y", from_port="bam", to_node="sort", to_port="bam"),
        ],
    )
    arity = [f for f in validate(graph, stack).findings if f.code == "MD0505"]
    assert arity and arity[0].level is Level.ILLEGAL
```

- [ ] **Step 3: Run and watch them fail**

```bash
uv run pytest packages/mendel-resolver/tests/test_validate_graph.py -v
```

Expected: FAIL — no `MD0505`/`MD0506`/`MD0508` is emitted by anything yet.

- [ ] **Step 4: Add the three checks to `validate.py`**

Add `from collections import defaultdict` at the top — it is **not** imported in Task 2, because
an import with no user fails `ruff` F401 and `make check` runs ruff (audit A152). Then extend
`validate()` and add the functions:

```python
def validate(graph: DraftGraph, layers: Layers) -> Verdict:
    findings: list[Finding] = []
    contracts = _contracts(graph, layers, findings)
    for edge in graph.edges:
        findings.extend(_check_edge(edge, contracts))
    findings.extend(_check_ports(graph, contracts, layers))
    findings.extend(_check_cycles(graph))
    return Verdict(findings=findings)


def _check_ports(
    graph: DraftGraph, contracts: dict[str, ModuleContract], layers: Layers
) -> list[Finding]:
    """Every input either has a wire, or arrives from an entry channel.

    **The second half is not optional.** A type declares its own `entry_channel` — the compiler
    has no built-in idea what a FASTQ or a GTF is — and `Vocabulary.entry_channels` is that map.
    An input whose type has one is fed from `params`, not from an upstream step.
    """
    incoming: dict[tuple[str, str], int] = defaultdict(int)
    for edge in graph.edges:
        incoming[(edge.to_node, edge.to_port)] += 1

    findings: list[Finding] = []
    for node in graph.nodes:
        contract = contracts.get(node.id)
        if contract is None:
            continue
        for port in contract.consumes:
            count = incoming[(node.id, port.name)]
            if count == 0:
                if not _has_entry_channel(port, layers):
                    findings.append(
                        Finding(
                            code="MD0506",
                            level=Level.UNMET,
                            message=coded(
                                "MD0506",
                                f"{node.id}.{port.name} has no wire and its type declares no "
                                f"entry channel",
                            ),
                            node=node.id,
                            port=port.name,
                        )
                    )
            elif port.cardinality == "1" and count > 1:
                findings.append(
                    Finding(
                        code="MD0505",
                        level=Level.ILLEGAL,
                        message=coded(
                            "MD0505",
                            f"{node.id}.{port.name} takes one input and {count} wires reach it",
                        ),
                        node=node.id,
                        port=port.name,
                    )
                )
    return findings


def _has_entry_channel(port: InputPort, layers: Layers) -> bool:
    """Any alternative arriving from `params` satisfies the port."""
    return any(a.type_id in layers.vocabulary.entry_channels for a in port.alternatives())


def _check_cycles(graph: DraftGraph) -> list[Finding]:
    """Iterative depth-first search, colour-marked. Recursion would blow the stack on a graph a
    person can draw by holding a key down."""
    edges: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        edges[edge.from_node].append(edge.to_node)

    WHITE, GREY, BLACK = 0, 1, 2
    colour: dict[str, int] = {n.id: WHITE for n in graph.nodes}
    findings: list[Finding] = []

    for start in sorted(colour):  # sorted: a verdict must be deterministic
        if colour[start] != WHITE:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        path: list[str] = []
        colour[start] = GREY
        path.append(start)
        while stack:
            node, index = stack[-1]
            if index < len(edges[node]):
                stack[-1] = (node, index + 1)
                nxt = edges[node][index]
                if colour.get(nxt, WHITE) == GREY:
                    loop = path[path.index(nxt):] + [nxt]
                    findings.append(
                        Finding(
                            code="MD0508",
                            level=Level.ILLEGAL,
                            message=coded("MD0508", "cycle: " + " → ".join(loop)),
                            node=nxt,
                        )
                    )
                elif colour.get(nxt, WHITE) == WHITE:
                    colour[nxt] = GREY
                    path.append(nxt)
                    stack.append((nxt, 0))
            else:
                colour[node] = BLACK
                stack.pop()
                path.pop()
    return findings
```

- [ ] **Step 5: Run every validate test and the ownership guard**

```bash
uv run pytest packages/mendel-resolver/tests/test_validate_edges.py \
              packages/mendel-resolver/tests/test_validate_graph.py -v
uv run pytest tests/test_diagnostics_ownership.py -v
```

Expected: all PASS. All nine codes are now both declared and emitted.

- [ ] **Step 6: Watch a guard fail on purpose, and record it**

A14 is the open critical finding: a guard never watched failing may be inert. Delete the
`_has_entry_channel` call so every entry-channel input reports `MD0506`, run
`test_an_input_fed_by_an_entry_channel_is_not_unmet`, and confirm it fails with a readable
message. Restore the call, then append a row to `notes/audits/guard-ledger.md` with the message
it printed.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-resolver/src/mendel_resolver/validate.py \
        packages/mendel-resolver/tests/test_validate_graph.py \
        notes/audits/guard-ledger.md
git commit -m "feat(resolver): unmet inputs, arity and cycles"
```

---

## Task 4: The compatibility index — one rule, two readers

A wire must turn green while the mouse is still moving, and a round trip per drag frame is what
makes that impossible. **The server computes the answer; the client looks it up.** A check written
in TypeScript would be a second implementation of the rule, which is the drift this repository has
already paid for twice — the tier vocabulary hardcoded in a React file, the `Standing` union
declared in two places — and per the spec's §4 it would also be a check the agent cannot run.

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/compatibility.py`
- Test: `packages/mendel-resolver/tests/test_compatibility.py`

**Interfaces:**
- Consumes: `Layers`, `InputPort.alternatives()`, `OutputPort`.
- Produces: `index(layers: Layers) -> Compatibility`; `Compatibility(satisfies, emits, requires)`;
  `signature(type_id: str, states: frozenset[str]) -> str`.

**The encoding.** A *signature* is `"alignment.bam"` or `"alignment.bam[coordinate_sorted,indexed]"`
— states sorted, so it is stable, and readable in a network tab.

| field | shape | what the client does with it |
|---|---|---|
| `emits` | `port key -> signature` | "I grabbed this output port; what does it emit?" |
| `requires` | `port key -> [signature]`, **conventional first** | "what does this input accept?" |
| `satisfies` | `signature -> [signature]` | "does what I have satisfy what that wants?" |

The client performs a set-membership test. It never compares a type to a type or a state to a
state — the server already did, with the same `alternatives()` call `validate` uses.

**Why keyed on signature and not on port pairs.** Port-pair keying is roughly 24 million entries
at the ~2,000 contracts issue #77 forecasts. Signature keying is bounded by the vocabulary, which
invariant 7 keeps closed.

- [ ] **Step 1: Write the failing test**

```python
# packages/mendel-resolver/tests/test_compatibility.py
"""The index is an optimisation of `validate`'s answer, never a second opinion.

The last test is the one that matters: it runs both over the whole registry and asserts they
never disagree. If someone changes the verb and forgets the index, that fails here rather than
lighting up a wire in the browser that the server will later refuse.
"""

import pytest

from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftNode
from mendel_resolver import layers as layers_module
from mendel_resolver.compatibility import index, signature
from mendel_resolver.validate import validate


def test_a_signature_sorts_its_states():
    assert signature("alignment.bam", frozenset()) == "alignment.bam"
    assert (
        signature("alignment.bam", frozenset({"indexed", "coordinate_sorted"}))
        == "alignment.bam[coordinate_sorted,indexed]"
    )


def test_an_unsorted_bam_does_not_satisfy_featurecounts(stack):
    idx = index(stack)
    star = idx.emits["nf-core/star/align#bam"]
    counts = idx.requires["nf-core/subread/featurecounts#bam"]
    assert not set(counts) & set(idx.satisfies[star])


def test_a_sorted_bam_does(stack):
    idx = index(stack)
    sorted_bam = idx.emits["nf-core/samtools/sort#bam"]
    counts = idx.requires["nf-core/subread/featurecounts#bam"]
    assert set(counts) & set(idx.satisfies[sorted_bam])


def test_the_conventional_alternative_is_first(stack):
    """The client renders green for index 0 and amber for a later match; the order carries that
    and nothing else does."""
    idx = index(stack)
    for key, requirements in idx.requires.items():
        assert requirements, key
        assert len(requirements) == len(set(requirements)), key


def test_the_index_agrees_with_the_verb_on_every_pair(stack):
    """**The guarantee. One rule, one answer.**

    Every output port against every input port in the registry: the index's verdict and
    `validate`'s must match. ~30 ports over 12 contracts today; the loop is quadratic on
    purpose because the point is exhaustiveness, not speed.
    """
    idx = index(stack)
    contracts = stack.registry.all()
    disagreements = []
    for source in contracts:
        for out in source.produces:
            emitted = idx.emits[f"{source.id}#{out.name}"]
            for target in contracts:
                for inp in target.consumes:
                    accepted = idx.requires[f"{target.id}#{inp.name}"]
                    index_says = bool(set(accepted) & set(idx.satisfies.get(emitted, [])))

                    graph = DraftGraph(
                        nodes=[
                            DraftNode(id="a", contract_id=source.id),
                            DraftNode(id="b", contract_id=target.id),
                        ],
                        edges=[
                            DraftEdge(from_node="a", from_port=out.name,
                                      to_node="b", to_port=inp.name)
                        ],
                    )
                    verb_says = not [
                        f for f in validate(graph, stack).illegal
                        if f.code in {"MD0503", "MD0504"} and f.edge is not None
                    ]
                    if index_says != verb_says:
                        disagreements.append(
                            f"{source.id}#{out.name} -> {target.id}#{inp.name}: "
                            f"index={index_says} verb={verb_says}"
                        )
    assert not disagreements, "\n".join(disagreements)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/mendel-resolver/tests/test_compatibility.py -v
```

Expected: `ModuleNotFoundError: No module named 'mendel_resolver.compatibility'`.

- [ ] **Step 3: Write `compatibility.py`**

```python
# packages/mendel-resolver/src/mendel_resolver/compatibility.py
"""What can feed what, precomputed from the registry.

**This is not a second implementation of the rule.** It walks the same `InputPort.alternatives()`
`validate` walks, and `test_the_index_agrees_with_the_verb_on_every_pair` holds the two together
over the whole registry. What it buys is that a browser can colour a wire during a drag without a
round trip, and can do so by *looking an answer up* rather than by deciding anything.

Keyed on a signature rather than on a port pair: pairs are quadratic in the registry and this is
bounded by the vocabulary, which invariant 7 keeps closed.
"""

from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.layers import Layers

__all__ = ["Compatibility", "index", "signature"]


def signature(type_id: str, states: frozenset[str]) -> str:
    """`alignment.bam[coordinate_sorted,indexed]`. Sorted, because a `frozenset` has no order and
    byte-identical output is a hard requirement everywhere else in this system."""
    if not states:
        return type_id
    return f"{type_id}[{','.join(sorted(states))}]"


class Compatibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emits: dict[str, str] = Field(default_factory=dict)
    """`"<contract id>#<port>"` to the signature that port emits."""

    requires: dict[str, list[str]] = Field(default_factory=dict)
    """`"<contract id>#<port>"` to the signatures it accepts, **conventional first**.

    The order is the whole of how a client tells a green wire from an amber one, and it comes
    from `InputPort.alternatives()` rather than from anything decided here.
    """

    satisfies: dict[str, list[str]] = Field(default_factory=dict)
    """An emitted signature to every required signature it satisfies."""


def index(layers: Layers) -> Compatibility:
    emits: dict[str, str] = {}
    requires: dict[str, list[str]] = {}
    emitted: set[tuple[str, frozenset[str]]] = set()
    required: set[tuple[str, frozenset[str]]] = set()

    for contract in layers.registry.all():
        for out in contract.produces:
            emits[f"{contract.id}#{out.name}"] = signature(out.type_id, out.state)
            emitted.add((out.type_id, out.state))
        for inp in contract.consumes:
            alternatives = inp.alternatives()
            requires[f"{contract.id}#{inp.name}"] = [
                signature(a.type_id, a.states) for a in alternatives
            ]
            for alternative in alternatives:
                required.add((alternative.type_id, alternative.states))

    satisfies: dict[str, list[str]] = {}
    for out_type, out_states in sorted(emitted):
        key = signature(out_type, out_states)
        satisfies[key] = sorted(
            signature(in_type, in_states)
            for in_type, in_states in required
            if in_type == out_type and in_states <= out_states
        )
    return Compatibility(emits=emits, requires=requires, satisfies=satisfies)
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest packages/mendel-resolver/tests/test_compatibility.py -v
```

Expected: all PASS, including the agreement test.

**If the agreement test fails**, the index is wrong and `validate` is right — `validate` is the
authority and this file is the optimisation. Do not adjust the verb to match the index.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-resolver/src/mendel_resolver/compatibility.py \
        packages/mendel-resolver/tests/test_compatibility.py
git commit -m "feat(resolver): the compatibility index, held to the verb by a test"
```

---

## Task 5: Who overrode — a human, or a model

**A schema break, taken deliberately and at the start.** `decision.py:152` calls `human_override`
*"the one field in the system that is by design a person's answer"*. The moment an agent driving
the API writes there, that sentence is false and a pipeline the AI assembled is indistinguishable
from one a person drew by hand — which is A130 arriving from the other direction, and it lands on
the exact distinction this product sells.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/plan/decision.py`
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py:63`
- Modify: `packages/comeni-core/pyproject.toml` — minor→major version bump
- Test: `packages/comeni-core/tests/test_model_override.py`

**Interfaces:**
- Consumes: `ResolverId` from `comeni_core.spell.marks` — its own docstring already says it names
  *"`flag-only`, `replay`, `human`, or **a model adapter's own name**"*, so no new alias is
  needed and the egress allowlist is already satisfied.
- Produces: `_Decided.model_override_by: ResolverId`; `ParamDecision.model_override`,
  `ProducerDecision.model_override`, `SourceDecision.model_override`.

**Constraint that decides the field types.** `DecisionRecord` reaches `pipeline.yml`, which is
door 4's payload, so `tests/test_egress.py`'s allowlist applies: every leaf must be a declared ID
alias or `Mark.FREE_TEXT`. Mirror each kind's existing `human_override` type exactly —
`HumanParamValue`, `ContractId | None`, `EdgeRef | None`.

- [ ] **Step 1: Write the failing test**

```python
# packages/comeni-core/tests/test_model_override.py
"""A model's choice and a person's choice are different facts and must stay different fields.

The alternative — a model writing `human_override` — reproduces A130: an adapter writing
`resolver` on every value is indistinguishable from the ladder, and there is no way to check the
claim afterwards. `ValueSource.MODEL` exists precisely so a model has somewhere truthful to write.
"""

import pytest
from pydantic import ValidationError

from comeni_core.plan.decision import ProducerDecision, SourceDecision


def _producer(**kw):
    base = dict(
        key="producer:alignment.bam", subject="alignment.bam", reason="r",
        resolved_by="flag-only", chosen="nf-core/star/align",
    )
    return ProducerDecision(**{**base, **kw})


def test_a_model_choice_is_not_a_human_choice():
    d = _producer(model_override="nf-core/hisat2/align", model_override_by="claude-opus-5")
    assert d.human_override is None
    assert d.model_override == "nf-core/hisat2/align"
    assert d.model_override_by == "claude-opus-5"


def test_a_model_override_must_name_who():
    """An override with no author is the indistinguishability this field exists to prevent."""
    with pytest.raises(ValidationError, match="model_override_by"):
        _producer(model_override="nf-core/hisat2/align")


def test_both_at_once_is_refused():
    """A person and a model cannot both have made one choice. If a person changed a model's
    answer, that is a human override and the model's is history, not a co-signature."""
    with pytest.raises(ValidationError, match="both"):
        _producer(
            human_override="nf-core/star/align",
            model_override="nf-core/hisat2/align",
            model_override_by="claude-opus-5",
        )


def test_a_param_overridden_to_null_still_needs_an_author():
    """A156. `HumanParamValue` includes `None`, so a default and a deliberate null look the
    same to `is not None`. `model_fields_set` is what tells them apart."""
    from comeni_core.plan.decision import ParamDecision

    with pytest.raises(ValidationError, match="model_override_by"):
        ParamDecision(
            key="param:star.seq_platform", subject="star.seq_platform", reason="r",
            resolved_by="flag-only", chosen="ILLUMINA", model_override=None,
        )


def test_the_edge_kind_carries_it_too():
    d = SourceDecision(
        key="source:counts.bam", subject="counts.bam", reason="r", resolved_by="flag-only",
        chosen="align:bam->counts:bam",
        model_override="sort:bam->counts:bam", model_override_by="claude-opus-5",
    )
    assert d.model_override_by == "claude-opus-5"


def test_the_schema_version_moved():
    """A new field on a record that lands in `pipeline.yml` is a break for `comeni-core`."""
    from comeni_core.artifact.pipeline import SCHEMA_VERSION

    assert SCHEMA_VERSION == 5
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest packages/comeni-core/tests/test_model_override.py -v
```

Expected: FAIL — `ProducerDecision` has no `model_override`; `extra="forbid"` rejects it.

- [ ] **Step 3: Add `model_override_by` and the guard to `_Decided`**

```python
class _Decided(BaseModel):
    ...
    model_override_by: ResolverId = ""
    """Which model made the override, when one did. Empty when none did.

    On `_Decided` rather than on each kind because it answers the same question whatever was
    overridden, and because `resolved_by` — the field it sits beside — is already here for the
    same reason. `ResolverId` is reused rather than a new alias invented: its docstring already
    names "a model adapter's own name" as one of the things it holds.
    """

    @model_validator(mode="after")
    def _one_author(self) -> "_Decided":
        """A person and a model cannot both have made one choice.

        `_Decided` declares neither override field — each kind does — so read them off `self`
        defensively; a `_Decided` subclass without one is legal and must not raise here.

        Written on the base so no kind can forget it. A person changing a model's answer is a
        human override and the model's answer is history — a decision has one author, and two
        would mean neither is checkable.
        """
        # `ParamDecision.model_override` is `HumanParamValue`, which *includes* `None`, so
        # `is not None` cannot tell "not overridden" from "overridden to null" (audit A156).
        # That hole is inherited — `human_override` has had it since A3 — and it is narrowed
        # rather than closed here: presence is read off the field being set at all, which
        # `model_fields_set` answers and a default never does.
        model = self.model_override if "model_override" in self.model_fields_set else None
        if model is not None and not self.model_override_by:
            raise ValueError(
                "model_override without model_override_by: an override with no author is "
                "indistinguishable from the resolver's own answer"
            )
        human = self.human_override if "human_override" in self.model_fields_set else None
        if model is not None and human is not None:
            raise ValueError("both human_override and model_override are set; a choice has one author")
        return self
```

`_Decided` is `frozen=True`; a `mode="after"` validator that only raises is compatible with that.
Import `model_validator` from `pydantic` if it is not already imported in this module.

- [ ] **Step 4: Add `model_override` to each of the three kinds**

```python
class ParamDecision(_Decided):
    ...
    model_override: HumanParamValue = None
    """Same guarded type as `human_override`. The name of that alias is about the path-shaped
    blocklist (audit A3), not about the author — a model can emit a path exactly as a person can,
    and it is if anything likelier to."""


class ProducerDecision(_Decided):
    ...
    model_override: ContractId | None = None


class SourceDecision(_Decided):
    ...
    model_override: EdgeRef | None = None
```

- [ ] **Step 5: Bump the schema version and the package version**

`packages/comeni-core/src/comeni_core/artifact/pipeline.py:63` → `SCHEMA_VERSION = 5`.

Then `packages/comeni-core/pyproject.toml`: a `SCHEMA_VERSION` bump is always a **break** for
`comeni-core`, so the major digit moves. Read `docs/guides/releasing.md` before choosing the
number — the bump is judged, not derived.

- [ ] **Step 6: Run the test, the egress guard, and the whole core suite**

```bash
uv run pytest packages/comeni-core/tests/test_model_override.py -v
uv run pytest tests/test_egress.py tests/test_construction.py -v
uv run pytest packages/comeni-core -q
```

Expected: PASS. **If `test_every_payload_field_is_a_declared_shape` fails**, a field was typed as
a bare `str` — go back to Step 3 and use `ResolverId`.

- [ ] **Step 7: Check what a v4 `pipeline.yml` does now**

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/v5-check
uv run mendel emit /tmp/v5-check/pipeline.yml --out /tmp/v5-emit
```

Both must succeed. `pipeline.py:648` already tolerates older `version` values on read; confirm a
`pipeline.yml` written before this task still emits, and record the answer in the execution
table. If it does not, that is a migration step this plan is missing — stop and say so.

- [ ] **Step 8: Commit**

```bash
git add packages/comeni-core/src/comeni_core/plan/decision.py \
        packages/comeni-core/src/comeni_core/artifact/pipeline.py \
        packages/comeni-core/pyproject.toml \
        packages/comeni-core/tests/test_model_override.py
git commit -m "feat(core)!: a model's override is not a person's"
```

---

## Task 6: `POST /validate` and `GET /compatibility`, with an ETag

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/validate.py`
- Modify: `packages/mendel-api/src/mendel_api/services/registry.py` — expose the digest
- Modify: `packages/mendel-api/src/mendel_api/routes/build.py`
- Test: `packages/mendel-api/tests/test_validate_route.py`

**Interfaces:**
- Consumes: `validate`, `index`, `Compatibility` from Tasks 2–4; `registry.stack()`, which is
  already `lru_cache`d on the registry digest.
- Produces: `POST /api/pipeline/validate` taking `DraftGraph` returning `Verdict`;
  `GET /api/pipeline/compatibility` returning `Compatibility`; `registry.digest() -> str`.

**Performance context, so nothing is optimised on a guess.** After Plan 3A phase 7 a
registry-touching request is **~10ms warm** because `layers.load` is cached on the digest; the
audit's conclusion was that *the resolver is not where the time goes, at any size*. The operator's
budget is **500ms**. Reuse `registry.stack()` and do nothing else — a private `lru_cache` here
would pay the 244ms cold cost a second time, which is the mistake `checked.py`'s docstring
records.

- [ ] **Step 1: Write the failing test**

```python
# packages/mendel-api/tests/test_validate_route.py
"""The agent and the browser call the same verb. That is the whole point of it being here.

**There is no shared `client` fixture** (audit A148) — `conftest.py` has `clean_db` and
`broken_registry_copy` and nothing else. Every route test file builds its own, and this follows
that rather than adding a shared one nobody asked for.
"""

import pytest
from fastapi.testclient import TestClient
from mendel_api.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def test_an_illegal_graph_comes_back_with_its_findings(client):
    body = {
        "nodes": [
            {"id": "align", "contract_id": "nf-core/star/align"},
            {"id": "counts", "contract_id": "nf-core/subread/featurecounts"},
        ],
        "edges": [
            {"from_node": "align", "from_port": "bam",
             "to_node": "counts", "to_port": "bam"}
        ],
    }
    response = client.post("/api/pipeline/validate", json=body)
    assert response.status_code == 200
    codes = {f["code"] for f in response.json()["findings"]}
    assert "MD0504" in codes


def test_validate_is_200_even_when_the_graph_is_wrong(client):
    """**It reports; it does not refuse.** A 422 here would make three problems into one."""
    body = {"nodes": [{"id": "x", "contract_id": "nf-core/star/align"}], "edges": []}
    assert client.post("/api/pipeline/validate", json=body).status_code == 200


def test_an_unknown_contract_is_a_finding_not_a_500(client):
    body = {"nodes": [{"id": "x", "contract_id": "nf-core/nothing/here"}], "edges": []}
    response = client.post("/api/pipeline/validate", json=body)
    assert response.status_code == 200
    assert "MD0509" in {f["code"] for f in response.json()["findings"]}


def test_the_index_carries_an_etag(client):
    first = client.get("/api/pipeline/compatibility")
    assert first.status_code == 200
    etag = first.headers["etag"]
    again = client.get("/api/pipeline/compatibility", headers={"If-None-Match": etag})
    assert again.status_code == 304


def test_the_index_and_the_verb_agree_through_the_api(client):
    """The agreement test again, at the boundary — a serialiser can lose a state set."""
    index = client.get("/api/pipeline/compatibility").json()
    star = index["emits"]["nf-core/star/align#bam"]
    counts = index["requires"]["nf-core/subread/featurecounts#bam"]
    assert not set(counts) & set(index["satisfies"][star])
```

- [ ] **Step 2: Run and watch it fail**

```bash
uv run pytest packages/mendel-api/tests/test_validate_route.py -v
```

Expected: 404 on every route.

- [ ] **Step 3: Expose the digest from the registry service**

In `services/registry.py`, add beside `stack()`:

```python
def digest() -> str:
    """The cache key, borrowed as an ETag.

    The same string that decides whether `_load` reloads decides whether a client's copy is
    stale — one definition of "the registry changed", not two.
    """
    return str(digest_of_directory(settings.registry_root))
```

Then rewrite `stack()` as `return _load(digest())` so there is one caller of
`digest_of_directory`.

- [ ] **Step 4: Write the service**

```python
# packages/mendel-api/src/mendel_api/services/validate.py
"""Thin by design: load the cached stack, call the pure verb.

Nothing is decided here. If a rule about what may feed what appears in this file, it is in the
wrong package — `mendel-resolver` is where a check is golden-testable and where the CLI can reach
it too.
"""

from comeni_core.plan.draft import DraftGraph
from comeni_core.review.verdict import Verdict
from mendel_resolver import compatibility, validate as verb

from mendel_api.services import registry


def of(graph: DraftGraph) -> Verdict:
    return verb.validate(graph, registry.stack())


def index() -> compatibility.Compatibility:
    return compatibility.index(registry.stack())
```

**Import the module, not the function** — `from mendel_resolver import validate as verb` — so a
test monkeypatching `mendel_resolver.validate.validate` is not bound past.

- [ ] **Step 5: Add the routes**

In `routes/build.py`:

```python
@router.post(
    "/validate",
    operation_id="validatePipeline",
    summary="Is this graph legal, and what is unmet or unconventional about it",
)
def validate_graph(graph: DraftGraph) -> Verdict:
    """**200 whatever it finds.** A verdict is the answer, not an error: a person mid-gesture
    would rather see three problems than the first one, and the forge's `verify` ladder is the
    precedent. Refusal lives at `keep` and at the emission gates."""
    return service.of(graph)


@router.get(
    "/compatibility",
    operation_id="compatibilityIndex",
    summary="What can feed what, so a browser can colour a wire without a round trip",
)
def compatibility_index(request: Request, response: Response) -> Compatibility:
    """The client looks up; it never decides. See the resolver module's docstring.

    `ETag` is the registry digest — the same string that invalidates the server's own cache, so
    "the registry changed" has one definition rather than two.
    """
    etag = f'"{registry.digest()}"'
    if request.headers.get("if-none-match") == etag:
        raise NotModified()
    response.headers["ETag"] = etag
    return service.index()
```

Implement `NotModified` as a tiny `HTTPException(status_code=304)` subclass, or return a
`Response(status_code=304)` directly and widen the return annotation — whichever the app's
existing error handling makes cleaner. Record which in the execution table.

- [ ] **Step 6: Regenerate the typed client**

```bash
make client
```

**Never hand-edit `frontend/src/api/`.** The generated client is what stops the IR types drifting
between the two halves.

- [ ] **Step 7: Run the tests**

```bash
uv run pytest packages/mendel-api/tests/test_validate_route.py -v
uv run pytest packages/mendel-api -q
```

- [ ] **Step 8: Commit**

```bash
git add packages/mendel-api/src/mendel_api/services/validate.py \
        packages/mendel-api/src/mendel_api/services/registry.py \
        packages/mendel-api/src/mendel_api/routes/build.py \
        packages/mendel-api/tests/test_validate_route.py \
        frontend/src/api/
git commit -m "feat(api): validate a graph, and serve the compatibility index"
```

---

## Task 7: Drafts — a third table, deliberately

**The API may not accept a path.** `routes/build.py:8` states it: *"Invariant 15 is why the body
is a `Goal` and not a path: no input here accepts a sample identifier, a filename or a path."* An
opaque server-generated id is not a filename, which is why a draft is a row.

**And this is a third table where `models.py` says a second one was already a deliberate act.**
`test_the_registry_is_not_in_the_database` asserts the exact set. Changing it is part of this
task, and the argument goes in the model's docstring: issue #43 decided *declared* data is files
because contracts, rules and vocabularies need diff, blame, review, signature and merge. A
half-drawn draft needs none of those **until it is landed**, and landing is what `keep` does.

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/models.py`
- Modify: `packages/mendel-api/tests/test_models.py`
- Create: `packages/mendel-api/migrations/versions/<rev>_pipeline_draft.py`
- Create: `packages/mendel-api/src/mendel_api/services/drafts.py`
- Modify: `packages/mendel-api/src/mendel_api/routes/build.py`
- Test: `packages/mendel-api/tests/test_drafts.py`

**Interfaces:**
- Consumes: `Base`, `session_scope` from `mendel_api.db`; `identity.default_author()`;
  `DraftGraph`; `validate` service from Task 6.
- Produces: `POST /api/pipeline/drafts -> {id}`, `GET /api/pipeline/drafts/{id}`,
  `PUT /api/pipeline/drafts/{id}`, `POST /api/pipeline/drafts/{id}/keep`.

- [ ] **Step 1: Write the failing tests**

```python
# packages/mendel-api/tests/test_drafts.py
"""A draft is server state. A pipeline is an artifact. `keep` is where one becomes the other.

**These need Postgres and CI does not have it** — audit A149. `test_visits.py` set the precedent
and says so in its own docstring: skip when the database is unreachable, the way `test_gates.py`
skips without Nextflow. The *decision* these support — that `keep` refuses an illegal graph — is
also tested without a database in `test_drafts_service.py`, where the session is monkeypatched,
because a rule that only runs on a developer machine is a rule CI cannot defend.
"""

import pytest
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from sqlalchemy import text


def _database_is_reachable() -> bool:
    from mendel_api.db import session_scope

    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="these are about storage, and CI has no Postgres"
)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


GRAPH = {
    "nodes": [{"id": "align", "contract_id": "nf-core/star/align"}],
    "edges": [],
}


def test_a_draft_round_trips(client):
    created = client.post("/api/pipeline/drafts", json={"graph": GRAPH, "name": "mine"})
    assert created.status_code == 201
    draft_id = created.json()["id"]
    read = client.get(f"/api/pipeline/drafts/{draft_id}")
    assert read.json()["graph"]["nodes"][0]["id"] == "align"


def test_the_id_is_opaque_and_not_a_path(client):
    """Invariant 15 is why. An id that looked like a filename would be the thing the API
    already refuses, wearing a different name."""
    draft_id = client.post("/api/pipeline/drafts", json={"graph": GRAPH}).json()["id"]
    assert "/" not in draft_id and "." not in draft_id and ".." not in draft_id
    assert len(draft_id) >= 16


def test_an_unknown_draft_is_404_not_500(client):
    assert client.get("/api/pipeline/drafts/deadbeefdeadbeef").status_code == 404


def test_keep_refuses_a_graph_with_an_illegal_finding(client):
    """`validate` reports; `keep` refuses. The boundary is here and nowhere else."""
    bad = {
        "nodes": [
            {"id": "align", "contract_id": "nf-core/star/align"},
            {"id": "counts", "contract_id": "nf-core/subread/featurecounts"},
        ],
        "edges": [{"from_node": "align", "from_port": "bam",
                   "to_node": "counts", "to_port": "bam"}],
    }
    draft_id = client.post("/api/pipeline/drafts", json={"graph": bad}).json()["id"]
    refused = client.post(f"/api/pipeline/drafts/{draft_id}/keep")
    assert refused.status_code == 422
    assert "MD0504" in refused.text


```

- [ ] **Step 2: Update the existing table guard, with the argument**

`packages/mendel-api/tests/test_models.py:24` currently asserts
`tables == {"source_check", "queue_visit"}`. Change it to include `"pipeline_draft"` and extend
the docstring:

```python
def test_the_registry_is_not_in_the_database():
    """Issue #43 decided declared data is files. A table holding contracts, types or
    roles would be that decision quietly reversed.

    `pipeline_draft` is the third table and is not that reversal: a draft is not declared data.
    The five properties #43 argued for — diff, blame, review, signature, merge — are what a
    *cited registry* sells, and a half-drawn graph needs none of them until it is landed.
    `POST /drafts/{id}/keep` is landing, and it writes a file.
    """
```

- [ ] **Step 3: Run and watch them fail**

```bash
uv run pytest packages/mendel-api/tests/test_drafts.py -v
```

Expected: 404 on every route; the table-set assertion fails.

- [ ] **Step 4: Add the model**

```python
class PipelineDraft(Base):
    """A graph somebody is still drawing.

    **The third table, and the first one's docstring said that would be a deliberate act.**
    Issue #43 decided *declared* data is files — contracts, rules, vocabularies — because those
    need diff, blame, review, signature and merge. A draft needs none of those until it is
    landed, and `keep` is landing: it validates, refuses anything illegal, and writes the
    `pipeline.yml` that is the actual artifact.

    `id` is a `secrets.token_hex(16)` string and not a serial, because invariant 15 forbids the
    API accepting a path and a guessable id is the next-worst thing.

    `graph` is a JSON column holding a `DraftGraph`. It is stored whole rather than shredded into
    node and edge tables: the client owns the working graph and sends it whole, and a schema that
    could hold half a graph would be a second definition of what a graph is.

    `who` is ATTRIBUTION, not authentication, exactly as on `QueueVisit`.
    """

    __tablename__ = "pipeline_draft"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    who: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    graph: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
```

Import `JSON` from `sqlalchemy`.

- [ ] **Step 5: Generate and read the migration**

```bash
cd packages/mendel-api && uv run alembic revision --autogenerate -m pipeline_draft
```

**`make migrate` takes no `ARGS`** (audit A150) — the target is `alembic upgrade head` and
nothing else, so passing a revision command to it silently applies migrations instead of
generating one.

**Read the generated file before applying it.** Alembic's autogenerate says "please adjust" in a
comment for a reason, and the two existing migrations in `migrations/versions/` are the shape to
compare against. Then:

```bash
make migrate
```

- [ ] **Step 6: Write the service and the routes**

`services/drafts.py` — `create(graph, name, who) -> str`, `read(id) -> PipelineDraft`,
`update(id, graph)`, `keep(id) -> Path`. `keep` calls the Task 6 validate service, raises the
app's coded 422 if `verdict.illegal` is non-empty, and otherwise writes `pipeline.yml` through
the existing artifact writer rather than a new one.

Routes go in `routes/build.py` beside the others. `POST /drafts` returns **201**.

- [ ] **Step 7: The round trip — invariant 10 applied to the hand-built path**

Spec §11 asks for this and nothing else in the plan covers it. **A draft that is kept must emit
the same Nextflow a resolved pipeline of the same shape emits**, or `pipeline.yml` is not really
the save file for a hand-built graph and every claim in §6 is weaker than it reads.

```python
# packages/mendel-api/tests/test_drafts.py — append

def test_kept_draft_emits_byte_identical_nextflow(client, tmp_path):
    """Determinism is a test, not an aspiration (invariant 10). The hand-built path has to
    hold it too, or `mendel emit` is only true of pipelines the resolver wrote."""
    import subprocess, yaml
    from pathlib import Path

    goal = yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text())
    built = client.post("/api/pipeline", json=goal).json()
    graph = {
        "nodes": [{"id": s["id"], "contract_id": s["contract_id"]} for s in built["steps"]],
        "edges": [
            {"from_node": w["from_node"], "from_port": w["from_port"],
             "to_node": w["to_node"], "to_port": w["to_port"]}
            for w in built["layout"]["wires"]
        ],
    }
    draft_id = client.post("/api/pipeline/drafts", json={"graph": graph}).json()["id"]
    kept = client.post(f"/api/pipeline/drafts/{draft_id}/keep")
    assert kept.status_code == 200, kept.text

    # No `--gate`: CI has no Nextflow, and this test is not about gates.
    reference = tmp_path / "reference"
    subprocess.run(
        ["uv", "run", "mendel", "build", "--goal", "examples/rnaseq-goal.yml",
         "--out", str(reference)],
        check=True,
    )
    from_draft = tmp_path / "from-draft"
    subprocess.run(
        ["uv", "run", "mendel", "emit", kept.json()["path"], "--out", str(from_draft)],
        check=True,
    )
    a = (reference / "main.nf").read_bytes()
    b = (from_draft / "main.nf").read_bytes()
    assert a == b, "a kept draft and a resolved build disagree on the emitted Nextflow"
```

**If this fails, do not adjust the test.** It is asking whether §6's claim — *a builder edits a
pipeline, and `pipeline.yml` is already the save file* — is true. A failure means the draft is
losing something the resolver carried (most likely `params` or the tier on a selection), and that
is a finding worth stopping and reporting rather than patching around.

- [ ] **Step 8: Test the refusal without a database**

Audit A149: everything above skips in CI, and `keep` refusing an illegal graph is the rule most
worth defending there. Follow `test_queue_service.py`, which tests the decision with the storage
monkeypatched.

```python
# packages/mendel-api/tests/test_drafts_service.py
"""The rule, without the storage. Runs in CI, where the route tests cannot."""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.services import drafts


def test_keep_refuses_an_illegal_graph(monkeypatch):
    graph = DraftGraph.model_validate({
        "nodes": [
            {"id": "align", "contract_id": "nf-core/star/align"},
            {"id": "counts", "contract_id": "nf-core/subread/featurecounts"},
        ],
        "edges": [{"from_node": "align", "from_port": "bam",
                   "to_node": "counts", "to_port": "bam"}],
    })
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    with pytest.raises(ValueError, match="MD0504"):
        drafts.keep("whatever")


def test_keep_allows_a_graph_with_only_unmet_ports(monkeypatch, tmp_path):
    """`unmet` is not `illegal`. A half-drawn graph is a legal thing to hold; §11 of the spec
    leaves what `keep` does with one as an open question, and this pins the answer taken here."""
    graph = DraftGraph.model_validate(
        {"nodes": [{"id": "counts", "contract_id": "nf-core/subread/featurecounts"}], "edges": []}
    )
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)
    assert drafts.keep("whatever").exists()
```

`drafts.keep` must therefore take its graph through a `_load` seam and its destination through an
`_output_root` seam, or it is untestable without Postgres. Design them that way in Step 6 rather
than retrofitting.

- [ ] **Step 9: Run the tests**

```bash
uv run pytest packages/mendel-api/tests/test_drafts.py \
              packages/mendel-api/tests/test_drafts_service.py \
              packages/mendel-api/tests/test_models.py -v
make client
```

- [ ] **Step 10: Commit**

```bash
git add packages/mendel-api/ frontend/src/api/
git commit -m "feat(api): drafts live in a row; keeping one writes the file"
```

---

## Task 8: `POST /compare` — yours beside Mendel's

**The alignment is a judgement, and that is why it is one call rather than two.** Deciding what
counts as *the same step* when you drew HISAT2 and the resolver picked STAR — both produce
`alignment.bam` with `state: []`, so they are interchangeable at the port level and not the same
choice — is not a join the browser can do. Put it in TypeScript and the agent cannot reach it,
and there are two answers to *how does my pipeline differ from Mendel's*.

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/compare.py`
- Modify: `packages/mendel-api/src/mendel_api/routes/build.py`
- Test: `packages/mendel-api/tests/test_compare.py`

**Interfaces:**
- Consumes: `validate` service (Task 6); `services.build.of(goal) -> BuiltPipeline`; `Goal`.
- Produces: `POST /api/pipeline/compare` taking `{graph, goal}` returning
  `Comparison(yours: Verdict, mendel: BuiltPipeline, alignment: list[AlignedStep])`;
  `AlignedStep(state, yours_node, yours_contract, mendel_node, mendel_contract, why)`.

**Alignment rule, stated so it is one rule and not a heuristic that grew.** Two steps are the
same step when they carry the **same contract id**. Where contracts differ, they are the same
*slot* when their `produces` signatures match — the same `(type_id, states)` from Task 4's
`signature()`, reusing that function rather than comparing by hand. Everything else is
`yours-only` or `mendel-only`.

| `state` | means |
|---|---|
| `same` | identical contract id |
| `differs` | different contract, same produced signature — HISAT2 where Mendel put STAR |
| `yours-only` | a step the resolver did not reach for |
| `mendel-only` | a step you do not have — the missing `samtools/sort` |

- [ ] **Step 1: Write the failing test**

```python
# packages/mendel-api/tests/test_compare.py
"""What Galaxy does not do. Legality is the floor; this is the screen's argument."""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from mendel_api.main import create_app

GOAL = yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text())


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def test_a_graph_missing_the_sorter_reports_it_as_mendel_only(client):
    graph = {
        "nodes": [
            {"id": "align", "contract_id": "nf-core/star/align"},
            {"id": "counts", "contract_id": "nf-core/subread/featurecounts"},
        ],
        "edges": [{"from_node": "align", "from_port": "bam",
                   "to_node": "counts", "to_port": "bam"}],
    }
    body = client.post("/api/pipeline/compare", json={"graph": graph, "goal": GOAL}).json()
    states = [row["state"] for row in body["alignment"]]
    assert "mendel-only" in states
    missing = [r for r in body["alignment"] if r["state"] == "mendel-only"]
    assert any("samtools/sort" in (r["mendel_contract"] or "") for r in missing)


def test_it_carries_your_verdict_too(client):
    """One call, both answers. Two calls stitched in the browser is where the alignment goes
    somewhere the agent cannot read it."""
    graph = {"nodes": [{"id": "align", "contract_id": "nf-core/star/align"}], "edges": []}
    body = client.post("/api/pipeline/compare", json={"graph": graph, "goal": GOAL}).json()
    assert "findings" in body["yours"]
    assert "steps" in body["mendel"]


def test_an_identical_graph_is_all_same(client):
    """Build the goal, turn the result back into a draft, compare it with itself. Nothing may
    read `differs` — if it does, the alignment rule is asymmetric and the diff will always show
    noise."""
    built = client.post("/api/pipeline", json=GOAL).json()
    graph = {
        "nodes": [{"id": s["id"], "contract_id": s["contract_id"]} for s in built["steps"]],
        "edges": [
            {"from_node": w["from_node"], "from_port": w["from_port"],
             "to_node": w["to_node"], "to_port": w["to_port"]}
            for w in built["layout"]["wires"]
        ],
    }
    body = client.post("/api/pipeline/compare", json={"graph": graph, "goal": GOAL}).json()
    assert {r["state"] for r in body["alignment"]} == {"same"}


def test_the_alignment_is_deterministic(client):
    """Same inputs, same order. A diff that reorders between two calls is unreadable."""
    graph = {"nodes": [{"id": "align", "contract_id": "nf-core/star/align"}], "edges": []}
    first = client.post("/api/pipeline/compare", json={"graph": graph, "goal": GOAL}).json()
    again = client.post("/api/pipeline/compare", json={"graph": graph, "goal": GOAL}).json()
    assert first["alignment"] == again["alignment"]
```

- [ ] **Step 2: Run and watch it fail**

```bash
uv run pytest packages/mendel-api/tests/test_compare.py -v
```

Expected: 404.

- [ ] **Step 3: Write `compare.py`**

```python
# packages/mendel-api/src/mendel_api/services/compare.py
"""Your graph beside the one the resolver would have built.

**The alignment is the reason this is one endpoint.** Deciding what counts as *the same step*
when you drew HISAT2 and Mendel picked STAR — both emit `alignment.bam` with no state, so they
are interchangeable at the port level and are not the same choice — is a judgement. In the
browser it is a judgement the agent cannot reach, and then there are two answers.
"""

from enum import StrEnum

from comeni_core.plan.draft import DraftGraph
from comeni_core.review.verdict import Verdict
from mendel_resolver.compatibility import signature
from mendel_resolver.goal import Goal
from pydantic import BaseModel, ConfigDict

from mendel_api.services import build, registry, validate as validation


class Alignment(StrEnum):
    SAME = "same"
    DIFFERS = "differs"
    YOURS_ONLY = "yours-only"
    MENDEL_ONLY = "mendel-only"


class AlignedStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Alignment
    yours_node: str | None = None
    yours_contract: str | None = None
    mendel_node: str | None = None
    mendel_contract: str | None = None
    why: str = ""
    """The resolver's own `reason` for its choice, carried through rather than composed here.
    A diff that explains itself in words this file invented is a fourth author of prose about a
    decision it did not make."""


class Comparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yours: Verdict
    mendel: build.BuiltPipeline
    alignment: list[AlignedStep]


def _emits(contract_id: str) -> frozenset[str]:
    """The set of signatures a contract produces. Two steps fill the same slot when these match.

    Reuses `signature()` rather than comparing `type_id` and `state` here, so "the same shape of
    output" has one definition and Task 4's index cannot drift from this.
    """
    contract = registry.stack().registry.get(contract_id)
    return frozenset(signature(p.type_id, p.state) for p in contract.produces)


def of(graph: DraftGraph, goal: Goal) -> Comparison:
    verdict = validation.of(graph)
    built = build.of(goal)

    yours = {n.id: n.contract_id for n in graph.nodes}
    theirs = {s.id: s.contract_id for s in built.steps}

    rows: list[AlignedStep] = []
    matched_theirs: set[str] = set()

    for node_id, contract_id in yours.items():
        exact = [t for t, c in theirs.items() if c == contract_id and t not in matched_theirs]
        if exact:
            matched_theirs.add(exact[0])
            rows.append(AlignedStep(
                state=Alignment.SAME, yours_node=node_id, yours_contract=contract_id,
                mendel_node=exact[0], mendel_contract=contract_id,
            ))
            continue

        shape = _emits(contract_id)
        slot = [
            t for t, c in theirs.items()
            if t not in matched_theirs and _emits(c) == shape
        ]
        if slot:
            matched_theirs.add(slot[0])
            step = next(s for s in built.steps if s.id == slot[0])
            rows.append(AlignedStep(
                state=Alignment.DIFFERS, yours_node=node_id, yours_contract=contract_id,
                mendel_node=slot[0], mendel_contract=theirs[slot[0]], why=step.reason,
            ))
            continue

        rows.append(AlignedStep(
            state=Alignment.YOURS_ONLY, yours_node=node_id, yours_contract=contract_id,
        ))

    for step in built.steps:
        if step.id not in matched_theirs:
            rows.append(AlignedStep(
                state=Alignment.MENDEL_ONLY, mendel_node=step.id,
                mendel_contract=step.contract_id, why=step.reason,
            ))

    # Deterministic, so two calls with the same inputs produce the same diff. A diff that
    # reorders between calls is unreadable, and `test_the_alignment_is_deterministic` holds it.
    rows.sort(key=lambda r: (r.state.value, r.mendel_node or "", r.yours_node or ""))
    return Comparison(yours=verdict, mendel=built, alignment=rows)
```

**Note the iteration order dependency.** `yours` is a dict built from `graph.nodes` in list order,
so which of two identical contracts matches first is stable but arbitrary. That is fine while
`state` is `same`; if the corpus ever grows a goal with two instances of one tool carrying
different settings, this needs a better key and the test that catches it is a new one. Record it
in the execution table if you hit it.

- [ ] **Step 4: Add the route, regenerate the client, run everything**

```bash
uv run pytest packages/mendel-api -q
make client
```

- [ ] **Step 5: Time it against the budget**

```bash
uv run python - <<'EOF'
import time, yaml
from pathlib import Path
from fastapi.testclient import TestClient
from mendel_api.main import create_app

goal = yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text())
graph = {"nodes": [{"id": "align", "contract_id": "nf-core/star/align"}], "edges": []}
body = {"graph": graph, "goal": goal}

with TestClient(create_app()) as c:
    c.post("/api/pipeline/compare", json=body)          # warm the registry cache
    times = []
    for _ in range(3):
        start = time.perf_counter()
        c.post("/api/pipeline/compare", json=body)
        times.append(time.perf_counter() - start)
print(f"compare warm: {min(times) * 1000:.0f}ms (best of 3)")
EOF
```

Record the number in the execution table. **The budget is 500ms.** The audit predicts 10–25ms; if
it is above 100ms, say so before continuing — that is the estimate breaking, and issue #77's
precedent (*"the worker's job, not the request's"*) is the option to put back on the table.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-api/ frontend/src/api/
git commit -m "feat(api): compare a drawn graph with what the resolver would build"
```

---

## Task 9: The client-side working graph

**Every edit is local.** Drag, connect, delete, move — none of these touch the network. Three
explicit calls exist and no more: `validate` on drop, `compare` on a button, `save` on an explicit
action or a ~5s idle debounce.

**Files:**
- Create: `frontend/src/build/useGraph.ts`
- Create: `frontend/src/build/useGraph.test.ts`
- Modify: `frontend/src/build/Builder.tsx`

**Interfaces:**
- Consumes: `components["schemas"]["DraftGraph"]` from the generated client.
- Produces: `useGraph(initial)` returning
  `{ graph, addNode, removeNode, connect, disconnect, moveNode, dirty }`.

- [ ] **Step 1: Read the three components this touches and record their props**

`Canvas.tsx`, `Wires.tsx`, `Port.tsx` and `Node.tsx` were written in 3C and **this plan's author
did not open them.** Read all four, write their prop signatures into the execution table, and if
any of the steps below contradict what is there, follow the code and record the deviation.

Two things 3C's journal warns about and this task will meet:

- **A dragged node used to leave its wires behind** — the offset was local state and the wires
  drew from the backend's points. Offsets live on the builder and the elbow is recomputed from
  the moved ends. Do not reintroduce a second source of position.
- **jsdom has no layout engine.** Height, overflow and overlap are not things these tests can be
  wrong about. Test the *state* — which wires exist, which node moved — never the pixels.

- [ ] **Step 2: Write the failing test**

```ts
// frontend/src/build/useGraph.test.ts
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useGraph } from "./useGraph";

const STAR = "nf-core/star/align";
const SORT = "nf-core/samtools/sort";

describe("the working graph", () => {
  it("adds a node without touching the network", () => {
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));
    act(() => result.current.addNode(STAR));
    expect(result.current.graph.nodes).toHaveLength(1);
    expect(result.current.dirty).toBe(true);
  });

  it("gives every node a distinct id when the same tool is added twice", () => {
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));
    act(() => { result.current.addNode(STAR); result.current.addNode(STAR); });
    const [a, b] = result.current.graph.nodes.map((n) => n.id);
    expect(a).not.toEqual(b);
  });

  it("removes a node's wires with it", () => {
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));
    act(() => { result.current.addNode(STAR); result.current.addNode(SORT); });
    const [a, b] = result.current.graph.nodes.map((n) => n.id);
    act(() => result.current.connect(a, "bam", b, "bam"));
    expect(result.current.graph.edges).toHaveLength(1);
    act(() => result.current.removeNode(a));
    expect(result.current.graph.edges).toHaveLength(0);
  });

  it("refuses to draw the same wire twice", () => {
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));
    act(() => { result.current.addNode(STAR); result.current.addNode(SORT); });
    const [a, b] = result.current.graph.nodes.map((n) => n.id);
    act(() => { result.current.connect(a, "bam", b, "bam"); result.current.connect(a, "bam", b, "bam"); });
    expect(result.current.graph.edges).toHaveLength(1);
  });

  it("keeps wires attached when a node moves", () => {
    // The 3C defect. Position is builder state; the edge list must not change at all.
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));
    act(() => { result.current.addNode(STAR); result.current.addNode(SORT); });
    const [a, b] = result.current.graph.nodes.map((n) => n.id);
    act(() => result.current.connect(a, "bam", b, "bam"));
    const before = result.current.graph.edges;
    act(() => result.current.moveNode(a, 120, 40));
    expect(result.current.graph.edges).toEqual(before);
  });
});
```

- [ ] **Step 3: Run and watch it fail**

```bash
cd frontend && npx vitest run src/build/useGraph.test.ts
```

- [ ] **Step 4: Write `useGraph.ts`**

A `useReducer` over `{nodes, edges, offsets}`. Node ids are `<tool>-<n>` with `n` the smallest
integer not already in use, so they are stable and readable in a `pipeline.yml` afterwards.
`dirty` flips true on any mutation and false when the caller reports a successful save.

- [ ] **Step 5: The idle save, which is the only thing here that touches the network**

Spec §8.5: explicit save, plus a **~5s idle debounce**. Not per-edit, not per-keystroke.

```ts
// frontend/src/build/useGraph.test.ts — append
import { vi } from "vitest";

it("does not save while you are still drawing", () => {
  vi.useFakeTimers();
  const save = vi.fn();
  const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }, { save, idleMs: 5000 }));
  act(() => { result.current.addNode(STAR); vi.advanceTimersByTime(4000); });
  act(() => { result.current.addNode(SORT); vi.advanceTimersByTime(4000); });
  expect(save).not.toHaveBeenCalled();          // the second edit restarted the clock
  act(() => vi.advanceTimersByTime(1500));
  expect(save).toHaveBeenCalledTimes(1);        // one write, not two
  vi.useRealTimers();
});

it("clears dirty only when the save reports success", async () => {
  const save = vi.fn().mockRejectedValue(new Error("offline"));
  const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }, { save, idleMs: 0 }));
  await act(async () => { result.current.addNode(STAR); });
  expect(result.current.dirty).toBe(true);      // a failed save is not a save
});
```

- [ ] **Step 6: Run the test, then the whole frontend suite**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/build/useGraph.ts frontend/src/build/useGraph.test.ts frontend/src/build/Builder.tsx
git commit -m "feat(frontend): the working graph lives in the browser"
```

---

## Task 10: Drag-to-connect, coloured by the index

**Files:**
- Create: `frontend/src/build/useCompatibility.ts`
- Create: `frontend/src/build/useCompatibility.test.ts`
- Modify: `frontend/src/build/Port.tsx`, `frontend/src/build/Canvas.tsx`, `Builder.tsx`

**Interfaces:**
- Consumes: `GET /api/pipeline/compatibility` through the generated client;
  `useGraph` from Task 9.
- Produces: `useCompatibility()` returning
  `{ accepts(sourceKey, targetKey): "yes" | "conventional-no" | "no" }`.

**The rule of this task, and the reason it exists:** `useCompatibility` performs a **set
membership test on data the server computed**. If a line in this file compares a `type_id` to a
`type_id`, or subtracts one state set from another, it has become a second implementation of the
rule and Task 4's whole argument is gone. Review it for that specifically.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/build/useCompatibility.test.ts
import { describe, expect, it } from "vitest";
import { accepts } from "./useCompatibility";

const INDEX = {
  emits: {
    "nf-core/star/align#bam": "alignment.bam",
    "nf-core/samtools/sort#bam": "alignment.bam[coordinate_sorted]",
  },
  requires: {
    "nf-core/subread/featurecounts#bam": ["alignment.bam[coordinate_sorted]"],
    "nf-core/samtools/sort#bam": ["alignment.bam"],
  },
  satisfies: {
    "alignment.bam": ["alignment.bam"],
    "alignment.bam[coordinate_sorted]": ["alignment.bam", "alignment.bam[coordinate_sorted]"],
  },
};

describe("colouring a wire during a drag", () => {
  it("refuses an unsorted bam into featureCounts", () => {
    expect(accepts(INDEX, "nf-core/star/align#bam", "nf-core/subread/featurecounts#bam"))
      .toBe("no");
  });

  it("accepts a sorted one", () => {
    expect(accepts(INDEX, "nf-core/samtools/sort#bam", "nf-core/subread/featurecounts#bam"))
      .toBe("yes");
  });

  it("accepts an unsorted bam into the sorter", () => {
    expect(accepts(INDEX, "nf-core/star/align#bam", "nf-core/samtools/sort#bam")).toBe("yes");
  });

  it("says no rather than throwing on a port it has never heard of", () => {
    expect(accepts(INDEX, "nf-core/nothing#x", "nf-core/samtools/sort#bam")).toBe("no");
  });

  it("marks a match on a non-first alternative as unconventional", () => {
    const index = {
      ...INDEX,
      requires: { "t#p": ["alignment.bam[coordinate_sorted]", "alignment.bam"] },
    };
    expect(accepts(index, "nf-core/star/align#bam", "t#p")).toBe("conventional-no");
  });
});
```

- [ ] **Step 2–5: fail, implement, pass, commit**

```bash
cd frontend && npx vitest run src/build/useCompatibility.test.ts
```

`accepts` is a pure function taking the index so it is testable without a query; the hook wraps it
with `useQuery` and a long `staleTime` — the ETag makes a revalidation a 304, so the cost of being
wrong about staleness is one small request.

Then wire it into `Port.tsx`: on drag start, mark every input port `yes` / `conventional-no` /
`no`; on drop, call `validate` for the authoritative answer. Green, amber, and greyed.

```bash
git add frontend/src/build/
git commit -m "feat(frontend): wires colour themselves from the server's index"
```

---

## Task 11: The verdict on the canvas, and the compare rail

**Files:**
- Create: `frontend/src/build/Compare.tsx`, `frontend/src/build/Compare.test.tsx`
- Modify: `frontend/src/build/Rail.tsx`, `Node.tsx`, `Wires.tsx`, `Builder.tsx`

**Interfaces:**
- Consumes: `POST /api/pipeline/validate`, `POST /api/pipeline/compare`, `useGraph`.
- Produces: findings anchored to their node/edge/port; an alignment rail with **adopt** and
  **keep** per row.

- [ ] **Step 1: Write the failing tests**

Test the state, not the pixels — jsdom has no layout engine.

```tsx
// frontend/src/build/Compare.test.tsx — the assertions this task must satisfy
// 1. a `mendel-only` row renders the contract Mendel would have added
// 2. clicking "adopt" calls the graph mutator, NOT the network
// 3. clicking "keep" opens a reason field and will not submit while it is empty
// 4. an `illegal` finding marks its edge; an `unmet` finding marks its port; an
//    `advisory` finding marks neither red
// 5. with no comparison run, the rail says so — it does not render an empty diff
```

- [ ] **Step 2: Implement**

**Keep requires a reason.** `ProducerDecision.model_override`/`human_override` exist to record a
departure from what the resolver would have done, and one with no reason is the defect
`override_reason` was added to fix (A77): a person's answer replaced by *"selected the first of
1 candidates without judgement"*.

**Reuse the tier vocabulary.** `GET /api/registry/tiers` and `useTiers` are the single
declaration; do not type a tier name into a React file. That was fixed once already, in the same
session 3C shipped.

- [ ] **Step 3: Run everything and commit**

```bash
cd frontend && npx vitest run && npx tsc --noEmit
git add frontend/src/build/
git commit -m "feat(frontend): the verdict on the canvas, and the diff beside it"
```

---

## Task 12: Documentation, and the journal entry

**Files:**
- Modify: `docs/guides/driving-mendel.md` — the builder in the loop
- Modify: `docs/reference/diagnostics.md` — regenerated, not hand-edited
- Modify: `CLAUDE.md` — the Current state section, and the stale merge claims
- Create: `notes/journal/2026-08-23-the-builder-is-a-builder.md`
- Modify: `notes/README.md` — row 17o

- [ ] **Step 1: Fix what is already stale in `CLAUDE.md`**

It says Plans 3A, 3B, 3C and 3D are on unmerged branches. **All four are ancestors of `main`** as
of `a4f17a9`. A fresh session starting from a false map is the exact failure the Current state
section warns about in its own opening.

- [ ] **Step 2: Write the journal entry**

Newest-first is the handoff. It must carry: what was built, **what was corrected during
execution** (the execution record below), what a fresh reader gets wrong, and what is next.

- [ ] **Step 3: Regenerate and check**

```bash
uv run python tools/generate_diagnostics_doc.py
make links
make verify
```

**`make verify`, not `make check`** — this changed `comeni_core/artifact/pipeline.py` and the
resolver, both on the named list. It takes about two minutes and needs Docker.

- [ ] **Step 4: Commit**

```bash
git add docs/ notes/ CLAUDE.md
git commit -m "docs: the builder, and a Current state that is true again"
```

---

## Execution record

Fill this in as you go. A tick means *this step was carried out*, not *the code was pasted
verbatim* — plans here are corrected during execution by design.

| Task | Step | Written | Actually done | Why |
|---|---|---|---|---|
| | | | | |

## Measurements taken during execution

| What | Number | Budget | Notes |
|---|---|---|---|
| `POST /compare` warm | | 500ms | Task 8 Step 5 |
| ports with `cardinality != "1"` | | — | Task 3 Step 1 |
| fast suite after Task 12 | | ~41s | |

---

## Audit — 2026-08-23, before execution

Run against the code rather than against the plan's prose. **Findings continue at A146**; A132–A145
are the performance audit. Every one below is already fixed in the text above; they are recorded
because a plan that was quietly corrected reads like a plan that was right.

| # | Finding | Severity | Where it was |
|---|---|---|---|
| A146 | `review/verdict.py` imported `comeni_core.plan.draft`, and `plan/decision.py` + `plan/tiers.py` both import `review/`. **A real cycle — it fails at import.** `plan/tiers.py:12` states the rule in as many words. `Finding.edge` is now an `EdgeRef`, a `spell/` alias `SourceDecision.chosen` already uses | **critical** | Task 1 |
| A147 | Three test files used `tests.helpers.REGISTRY_ROOT`, which **does not exist**. The resolver conftest already has `EXAMPLES = ROOT / "registry"`; a session-scoped `stack` fixture goes there | blocker | Tasks 2–4 |
| A148 | Three test files assumed a shared `client` fixture. `conftest.py` has `clean_db` and `broken_registry_copy` only; every route test builds its own `TestClient(create_app(), raise_server_exceptions=False)` | blocker | Tasks 6–8 |
| A149 | The draft tests need Postgres and **CI has none**. `test_visits.py` set the precedent and skips; the rule worth defending in CI — `keep` refuses an illegal graph — now has a database-free twin, which forces `drafts.keep` to take `_load` and `_output_root` seams | blocker | Task 7 |
| A150 | `make migrate ARGS="revision --autogenerate"` — the target is `alembic upgrade head` and ignores `ARGS`, so it would have **applied** migrations instead of generating one | blocker | Task 7 |
| A151 | Task 1 committed with `test_diagnostics_ownership` knowingly red and did not say so. Kept, with the trade written into the commit message and the alternative named | process | Task 1 |
| A152 | `from collections import defaultdict` was imported in Task 2 and first used in Task 3 — `ruff` F401, and `make check` runs ruff, so the Task 2 commit fails lint | blocker | Task 2 |
| A153 | The timing script imported `mendel_api.main.app`. It is `create_app()` | blocker | Task 8 |
| A154 | `Registry.get` raises a bare `KeyError(contract_id)`, so `MD0509`'s `{exc}` would have rendered as the id in quotes and nothing else | minor | Task 2 |
| A155 | `test_a_draft_is_not_the_registry` duplicated `test_the_registry_is_not_in_the_database` in another file | minor | Task 7 |
| A157 | **The fix for A146 was itself wrong.** `Finding.edge: EdgeRef` spelled `a:bam->b:bam` — but `_edge_ref` validates `<node>.<port>`, one endpoint, and refuses that outright. A wire is two `EdgeRef`s: `source` and `target` | **critical** | Task 1, found auditing the audit |
| A156 | `ParamDecision.model_override` is `HumanParamValue`, which **includes `None`**, so `is not None` cannot tell an unset field from a deliberate null and the author check silently skipped. Narrowed with `model_fields_set`. The same hole is inherited on `human_override` and is **not** closed here | minor | Task 5 |

**What the audit did not check.** The frontend. Tasks 9–11 were written without opening
`Canvas.tsx`, `Wires.tsx`, `Port.tsx` or `Node.tsx`, and this pass did not open them either — so
the three findings most like A147 and A148, but on the React side, are still in there. Task 9
Step 1 is the step that finds them, and it is deliberately the first thing that task does.

**A157 is the most useful finding here.** It was introduced *by this audit*, fixing A146, and
found only because the fix's own claim — "`EdgeRef` is what `SourceDecision.chosen` uses for
exactly this" — was checked against `_edge_ref` rather than believed. The claim was half true:
the alias is right and the shape was invented. **An audit's own repairs need the same treatment
as the thing audited**, and one pass is not obviously enough.

**One pattern across A147, A148 and A153.** Every one is a *fixture or entry point invented
rather than read* — three separate guesses at how the existing tests bootstrap themselves, in a
plan whose spec header warns that the last two plans each got a signature wrong writing against a
file they had only skimmed. Backend types were verified; test scaffolding was not, and it turned
out to be where the errors were.
