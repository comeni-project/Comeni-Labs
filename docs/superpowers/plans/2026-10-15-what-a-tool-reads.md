# What a tool reads must come from somewhere — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An unknown fact that a chosen tool reads makes that step tier 4 instead of a silent module default; gathering stops asking what only a tool reads and no file can measure; the chat model can no longer approve steps (#336) or quote an old turn (#337).

**Architecture:** The compiler already parses which `meta` keys each module reads (`ModuleSpec.meta_reads`); it maps them to declared measurements and hands `resolve()` a plain `{contract_id: facts}` mapping. `resolve()` appends a tier-4 `FactDecision` for each unknown one, which the build plan already turns into *tell me* on the step card. The rest are deletions or one-line conditions.

**Tech Stack:** Python 3.12, Pydantic, pytest; uv workspace; Postgres test DB (`make test-db`).

**Spec:** `docs/superpowers/specs/2026-10-15-facts-a-step-needs-design.md` (the file keeps its first name; its title is the rule).

## Global Constraints

- **Simplest change that obeys the existing rules** (operator, 2026-10-15). No new field, interface or layer beyond what a task names. The one new type is `FactDecision`.
- Pure packages (`comeni-core`, `mendel-resolver`, `mendel-compiler`, `mendel-authoring`) stay pure; the resolver never imports the compiler.
- Same goal in → byte-identical `.nf` out (invariant 10). A goal that states every fact emits exactly what it emits today.
- Tier 4 is always flagged (invariant 6): every `FactDecision` appears in `PipelineIR.needs_review()`.
- Run Python tests against the test database only: `MENDEL_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel WIENER_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/wiener uv run pytest …` (written below as `T …`). Never bare `uv run pytest` with the dev database up.
- Lint separately before each commit: `uv run ruff check packages tests`, then commit. A piped check does not stop a commit.
- Every guard watched failing gets a row in `tests/fixtures/guard-ledger.md`.
- `make verify` before the branch is called done: this touches `resolve.py` and the compiler.
- **`pipeline.yml` keeps version 6** (spec §9's open choice, taken the simple way): `FactDecision` only adds a member to the record union, every existing file loads and re-emits byte-identically (Review Focus 5), and nothing is published yet. Plan B's version 7 carries it as it stands.

## Review Focus

1. **A tool whose module source cannot be read** (a lab's bare-container layer): its entry is `None`, no `FactDecision`, nothing refused. Test in Task 2.
2. **A fact a person stated as open** (*Not sure* / *I can't share it*): open is unknown, so the step still stops; the gap is not asked again. Test in Task 5.
3. **The same fact read by two steps** (featureCounts and HISAT2): answering it once at the first stop settles the second. Test in Task 4.
4. **A boolean fact on the label** (`paired` travels as `single_end` through `meta_values`): unknown pairing stops STAR, TrimGalore, HISAT2 and featureCounts with candidates `[true, false]`. Test in Task 2.
5. **An older `pipeline.yml`** with no `FactDecision` loads and re-emits byte-identically. Test in Task 1.

---

### Task 1: The `FactDecision` record

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/plan/decision.py` (`DecisionKind`, new class after `SourceDecision`, `DecisionRecord` union)
- Test: `packages/comeni-core/tests/test_fact_decision.py` (create)

**Interfaces:**
- Produces: `comeni_core.plan.decision.FactDecision(key, subject, reason, resolved_by, candidates: list[ParamValue], unknown: list[MeasurementId], chosen: ParamValue = None)`, `kind == DecisionKind.FACT == "fact"`, `tier` defaults to `Tier.AMBIGUOUS`. Member of `DecisionRecord`.

- [x] **Step 1: Write the failing tests**

```python
"""A fact a chosen tool reads and nobody supplied is a tier-4 record (#338)."""

from comeni_core.plan.decision import DecisionKind, FactDecision
from comeni_core.plan.ir import PipelineIR
from comeni_core.plan.tiers import Tier
from pydantic import TypeAdapter

from comeni_core.plan.decision import DecisionRecord


def _open() -> FactDecision:
    return FactDecision(
        key="featurecounts.fact.strandedness",
        subject="strandedness",
        reason="nf-core/subread/featurecounts reads strandedness, and it is not known",
        resolved_by="flag-only",
        candidates=["forward", "reverse", "unstranded"],
        unknown=["strandedness"],
    )


def test_it_is_tier_four_and_round_trips_as_a_decision_record():
    record = _open()
    assert record.kind is DecisionKind.FACT and record.tier is Tier.AMBIGUOUS
    adapter = TypeAdapter(DecisionRecord)
    assert adapter.validate_python(adapter.dump_python(record, mode="json")) == record


def test_it_is_listed_for_review():
    ir = PipelineIR(decisions=[_open()])
    assert "featurecounts.fact.strandedness" in ir.needs_review()
```

- [x] **Step 2: Run them, expect failure**

Run: `T packages/comeni-core/tests/test_fact_decision.py -q`
Expected: FAIL, `ImportError: cannot import name 'FactDecision'`. If `PipelineIR()` needs arguments, build it as the nearest existing test in `packages/comeni-core/tests/` does and keep the assertion.

- [x] **Step 3: Implement**

In `DecisionKind`, add `FACT = "fact"`. After `SourceDecision`:

```python
class FactDecision(_Decided):
    """A fact a chosen tool's code reads, that nobody supplied (#338).

    Not a `ParamDecision`: a setting's answer is stored as that one step's setting, so two
    steps reading strandedness would ask twice and could disagree. This one's answer is stored
    as the **fact**, once, and the re-resolved pipeline has no record left. It exists only
    while the fact is unknown, so it is never replayed.
    """

    kind: Literal[DecisionKind.FACT] = DecisionKind.FACT
    candidates: list[ParamValue] = Field(default_factory=list)
    chosen: ParamValue = None
    """Nothing is chosen here: the answer is recorded as the fact."""
    unknown: list[MeasurementId]
```

Add `FactDecision` to the `DecisionRecord` union.

- [x] **Step 4: Run them, expect pass; then the format guards**

Run: `T packages/comeni-core/tests/test_fact_decision.py tests/guards/test_egress.py tests/artifact -q`
Expected: PASS. If `test_egress.py` counts declared free-text fields and the count moved because `FactDecision` inherits `reason`, update that one number deliberately and say so in the commit. Then `uv run python tools/check_reference.py --check`; if the schema reference pages drifted, regenerate them with the same script without `--check` and include them.

- [x] **Step 5: Lint, then commit**

```bash
uv run ruff check packages/comeni-core
git add packages/comeni-core docs/reference tests/guards
git commit -m "feat(core): FactDecision, a fact a tool reads that nobody supplied (#338)"
```

---

### Task 2: What each tool's code reads, as data

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/conformance.py` (new function beside `_meta_keys`)
- Test: `packages/mendel-compiler/tests/test_facts_read.py` (create)

**Interfaces:**
- Consumes: `ModuleSpec.parse(path).meta_reads` (`MetaRead.variable`, `MetaRead.key`), `module_path(contract, modules)`, `_ALWAYS_SET`, `MeasurementRegistry.ids()/get(id).meta_key`.
- Produces: `mendel_compiler.conformance.facts_read(registry, modules, measurements) -> dict[str, frozenset[str] | None]`: per contract id, the measurement ids whose `meta_key` its module reads on `meta`; `None` when its source is missing.

- [x] **Step 1: Write the failing tests**

```python
"""Which facts each tool's code reads, from the code (#338)."""

from mendel_compiler import conformance
from mendel_resolver import layers
from support.paths import ROOT


def _read():
    loaded = layers.load(ROOT / "registry")
    return conformance.facts_read(loaded.registry, loaded.modules, loaded.measurements)


def test_the_spine_tools_read_what_their_code_reads():
    got = _read()
    assert got, "the shipped registry has contracts"
    by_tool = {cid.split("@")[0]: facts for cid, facts in got.items()}
    assert by_tool["nf-core/subread/featurecounts"] == {"paired", "strandedness"}
    assert by_tool["nf-core/hisat2/align"] == {"paired", "strandedness"}
    assert by_tool["nf-core/star/align"] == {"paired"}
    assert by_tool["nf-core/trimgalore"] == {"paired"}
    assert by_tool["nf-core/fastqc"] == frozenset()


def test_a_tool_whose_source_is_missing_is_none(tmp_path):
    import shutil

    shutil.copytree(ROOT / "registry", tmp_path / "registry")
    module = tmp_path / "registry/tools/nf-core/subread/featurecounts/module/main.nf"
    module.unlink()
    loaded = layers.load(tmp_path / "registry")
    got = conformance.facts_read(loaded.registry, loaded.modules, loaded.measurements)
    assert next(v for k, v in got.items() if "featurecounts" in k) is None
```

Read `tests/README.md` for where `support.paths` is importable from a package's tests; if `support` is not on the path there, put this file in `tests/registry/` instead.

- [x] **Step 2: Run, expect failure**

Run: `T packages/mendel-compiler/tests/test_facts_read.py -q`
Expected: FAIL, `AttributeError: module 'mendel_compiler.conformance' has no attribute 'facts_read'`.

- [x] **Step 3: Implement**

```python
def facts_read(
    registry: Registry, modules: Mapping[str, Module], measurements: MeasurementRegistry
) -> dict[str, frozenset[str] | None]:
    """Per contract, the declared facts its module reads off the sample's label (#338).

    Derived from the code, as `_meta_keys` is: a declaration of the same thing would be a third
    copy of what the measurement's `meta_key` and the module already say. `None` when the source
    cannot be read; nothing is assumed about a module nobody could look at.
    """
    by_key = {
        measurements.get(m).meta_key: m
        for m in measurements.ids()
        if measurements.get(m).meta_key
    }
    found: dict[str, frozenset[str] | None] = {}
    for contract in sorted(registry.all(), key=lambda c: c.id):
        path = module_path(contract, modules)
        if path is None or not path.exists():
            found[contract.id] = None
            continue
        found[contract.id] = frozenset(
            by_key[entry.key]
            for entry in ModuleSpec.parse(path).meta_reads
            if entry.variable == "meta" and entry.key not in _ALWAYS_SET and entry.key in by_key
        )
    return found
```

- [x] **Step 4: Run, expect pass**

Run: `T packages/mendel-compiler/tests/test_facts_read.py -q` → PASS.

- [x] **Step 5: Lint, then commit**

```bash
uv run ruff check packages/mendel-compiler
git add packages/mendel-compiler
git commit -m "feat(compiler): facts_read, which facts each tool's code reads (#338)"
```

---

### Task 3: The resolver records an unknown fact as tier 4, and the build passes the mapping

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py` (`resolve()` signature; after the params loop in `for step in plan.steps`)
- Modify: `packages/mendel-compiler/src/mendel_compiler/orchestrate.py:113` (the `resolve(` call)
- Test: `tests/guards/test_unknown_facts.py` (create)
- Test: `packages/mendel-resolver/tests/test_unknown_facts.py` (create)

**Interfaces:**
- Consumes: `FactDecision` (Task 1), `conformance.facts_read` (Task 2).
- Produces: `resolve(..., facts_read: Mapping[str, frozenset[str] | None] | None = None)`; records keyed `f"{node.id}.fact.{measurement}"`.

- [x] **Step 1: Write the guard (it must fail against today's code)**

```python
"""Whatever a chosen tool reads comes from somewhere, or is tier 4 (#338, #340).

featureCounts reads `meta.strandedness`; with the fact unknown the label was absent and the
module counted unstranded (`-s 0`) with nothing flagged. This holds for every label-carried
fact the example goal states, removed one at a time."""

import pytest
from comeni_core import yaml_strict
from mendel_compiler import conformance, orchestrate
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from mendel_resolver.ports import FlagOnlyResolver
from support.paths import ROOT

LOADED = layers.load(ROOT / "registry")
READ = conformance.facts_read(LOADED.registry, LOADED.modules, LOADED.measurements)
EXAMPLE = yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml")
CARRIED = sorted(
    m for m in LOADED.measurements.ids()
    if LOADED.measurements.get(m).meta_key and m in EXAMPLE["profile"]
)


def test_the_example_states_label_carried_facts():
    assert CARRIED == ["paired", "strandedness"]


@pytest.mark.parametrize("fact", CARRIED)
def test_a_tool_reading_an_unknown_fact_is_flagged(fact):
    goal = Goal.model_validate({**EXAMPLE, "profile": {
        k: v for k, v in EXAMPLE["profile"].items() if k != fact}})
    built = orchestrate.build(goal, registry_roots=[ROOT / "registry"],
                              resolver=FlagOnlyResolver())
    readers = [n for n in built.ir.nodes if fact in (READ.get(n.contract_id) or ())]
    assert readers, f"something on the spine reads {fact}"
    for node in readers:
        assert f"{node.id}.fact.{fact}" in built.ir.needs_review(), node.contract_id
```

The goal is loaded as the API's own tests load it (`test_blueprint.py`): `Goal.model_validate(yaml_strict.load(...))`, with the profile as the YAML mapping.

- [x] **Step 2: Run, expect failure**

Run: `T tests/guards/test_unknown_facts.py -q`
Expected: the two parametrised cases FAIL with `assert 'featurecounts….fact.strandedness' in [...]`: today nothing is flagged. Record this in the ledger in Step 7.

- [x] **Step 3: Write the resolver's pure test**

```python
"""The resolver's half: unknown facts a chosen tool reads become tier-4 records (#338)."""

from comeni_core import yaml_strict
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from mendel_resolver.resolve import resolve
from support.paths import ROOT

LOADED = layers.load(ROOT / "registry")
EXAMPLE = yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml")


def _resolve(profile, facts_read):
    goal = Goal.model_validate({**EXAMPLE, "profile": profile})
    return resolve(goal, LOADED.registry, LOADED.rules, LOADED.measurements,
                   vocabulary=LOADED.vocabulary, facts_read=facts_read)


def test_an_unknown_fact_is_one_record_per_reader_with_the_declared_values():
    profile = {k: v for k, v in EXAMPLE["profile"].items() if k != "strandedness"}
    ir = _resolve(profile, {c.id: frozenset({"strandedness"}) for c in LOADED.registry.all()
                            if "featurecounts" in c.id})
    [record] = [d for d in ir.decisions if getattr(d, "kind", "") == "fact"]
    assert record.unknown == ["strandedness"]
    assert record.candidates == ["forward", "reverse", "unstranded"]


def test_a_known_fact_or_no_mapping_changes_nothing():
    stated = _resolve(EXAMPLE["profile"], {c.id: frozenset({"strandedness"})
                                           for c in LOADED.registry.all()})
    assert not [d for d in stated.decisions if getattr(d, "kind", "") == "fact"]
    unread = _resolve({k: v for k, v in EXAMPLE["profile"].items() if k != "strandedness"},
                      None)
    assert not [d for d in unread.decisions if getattr(d, "kind", "") == "fact"]


def test_an_unreadable_tool_records_nothing():
    profile = {k: v for k, v in EXAMPLE["profile"].items() if k != "strandedness"}
    ir = _resolve(profile, {c.id: None for c in LOADED.registry.all()})
    assert not [d for d in ir.decisions if getattr(d, "kind", "") == "fact"]
```

Run: `T packages/mendel-resolver/tests/test_unknown_facts.py -q` → FAIL, `unexpected keyword argument 'facts_read'`.

- [x] **Step 4: Implement in `resolve()`**

Add the keyword to the signature (after `prior`) and document it in the docstring in one sentence. After `for param in contract.params: …` inside the step loop:

```python
        # **What a tool reads comes from somewhere** (#338): a fact its code reads off the
        # sample's label, and nobody supplied, is tier 4, as an unsupplied setting is.
        known = {entry.measurement for entry in goal.profile.measurements}
        for fact in sorted((facts_read or {}).get(contract.id) or ()):
            if fact in known:
                continue
            declared = measurements.get(fact)
            ir.decisions.append(
                FactDecision(
                    key=f"{node.id}.fact.{fact}",
                    subject=fact,
                    reason=f"{contract.id} reads {fact}, and it is not known",
                    resolved_by="flag-only",
                    candidates=_values_of(declared),
                    unknown=[fact],
                )
            )
```

with, beside `_roles_in`:

```python
def _values_of(measurement) -> list:
    """The answers a person can give: an enum's values, or true and false."""
    if measurement.kind is MeasurementKind.BOOLEAN:
        return [True, False]
    return list(measurement.values)
```

`"flag-only"` is what `FlagOnlyResolver` (`mendel_resolver/ports.py`) writes as `by`. Add `from comeni_core.declared.measurement import MeasurementKind` (beside the existing `MeasurementRegistry` import) and `FactDecision` to the existing `comeni_core.plan.decision` import.

- [x] **Step 5: Pass it from the build**

In `orchestrate.build`, at the `resolve(` call: `facts_read=conformance.facts_read(loaded.registry, loaded.modules, loaded.measurements),`.

- [x] **Step 6: Run both, expect pass; then everything that resolves**

Run: `T packages/mendel-resolver/tests/test_unknown_facts.py tests/guards/test_unknown_facts.py -q` → PASS.
Run: `T packages/mendel-resolver packages/mendel-compiler tests/emit tests/artifact tests/regressions -q`. Any golden that changed is a goal without `strandedness` or `paired` gaining a flagged record: list each one, check that is the only change in it, regenerate it the way that suite documents, and name them in the commit.

- [x] **Step 7: Ledger, lint, commit**

Ledger row: the guard RED with today's code (quote the message), GREEN after. Then:

```bash
uv run ruff check packages tests
git add packages/mendel-resolver packages/mendel-compiler tests
git commit -m "feat(resolver): an unknown fact a tool reads is tier 4, not the module's default (#338, #340)"
```

---

### Task 4: The walk asks for it on the step that reads it

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/needs.py` (`need_of`, module docstring)
- Test: `packages/mendel-authoring/tests/test_needs.py` (extend; create if absent, following the nearest existing `need_of` test)
- Test: `packages/mendel-api/tests/authoring/test_authoring_building.py` (extend the file whose tests answer a `fact_` option; find it with `git grep -n "fact_read_length" packages/mendel-api/tests`)

**Interfaces:**
- Consumes: `FactDecision.unknown` (Task 1); the resolver records (Task 3).
- Produces: `need_of` returns `NeedKind.FACT` with `facts` including a `FactDecision`'s `unknown`.

- [x] **Step 1: The failing unit test**

Mirror the existing `need_of` test that builds a `Step` and a `ProducerDecision` with `unknown=["read_length"]`; replace the record with:

```python
FactDecision(key=f"{step.id}.fact.strandedness", subject="strandedness", reason="r",
             resolved_by="flag-only", candidates=["forward", "reverse", "unstranded"],
             unknown=["strandedness"])
```

and assert `need.kind is NeedKind.FACT and need.facts == ["strandedness"]`.

Run: `T packages/mendel-authoring/tests -q -k need` → FAIL (`NeedKind.CHOICE`, empty `facts`).

- [x] **Step 2: Implement**

In `need_of`, read facts from both kinds:

```python
    facts = sorted(
        {fact for r in open_ if isinstance(r, ProducerDecision | FactDecision)
         for fact in r.unknown}
    )
```

and keep a `FactDecision` out of `choices` (its answer is the fact, offered as *tell me*): build `choices` from `[r for r in open_ if not isinstance(r, FactDecision)]`. Add one bullet to the module docstring: *a fact a chosen tool reads and nobody supplied (`FactDecision`, #338)*.

Run: `T packages/mendel-authoring/tests -q` → PASS.

- [x] **Step 3: The failing walk test, two readers settled by one answer**

In the API building tests, with a session resolved from a goal lacking strandedness (use the helper that builds a walk from a goal; pass the example profile without `strandedness`): walk until the pending step offers `fact_strandedness`; answer it `reverse` through the same command the existing `fact_read_length` test uses; then assert the decisions read back have `strandedness == "reverse"`, and that no later step offers `fact_strandedness`.

Run it → FAIL before Step 2 is in (if Step 2 is in already, revert it locally to see it fail, then restore). Then → PASS.

- [x] **Step 4: Lint, commit**

```bash
uv run ruff check packages
git add packages/mendel-authoring packages/mendel-api/tests
git commit -m "feat(authoring): a step asks for the unknown fact its tool reads (#338)"
```

---

### Task 5: Gathering does not ask what only a tool reads and no file can measure

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/gaps.py` (`gaps()`, the measurement list)
- Test: `packages/mendel-api/tests/authoring/samples/test_gaps.py` (extend)
- Modify: the tests that walk to the strandedness question (`git grep -n '"strandedness"' packages/mendel-api/tests`): `test_authoring_gathering.py`, `test_heard_replies.py`, `test_gaps.py`, `test_authoring_samples.py`, `test_drafts_service.py`, `mendel_api_tests/http.py`, `forge/test_attention.py`.

**Interfaces:**
- Consumes: `measurers.usable_pieces(stack).measures` (`.measures` is the measurement id each measure piece fills).

- [x] **Step 1: The failing test**

```python
def test_a_fact_only_a_tool_reads_and_no_sample_measures_is_not_asked():
    """#338: strandedness is read by featureCounts and HISAT2 off the label, no rule reads it,
    and no inspector measures it. It is left unknown and the step stops for it."""
    found = gaps.gaps(["counts.matrix"], [], registry.stack())
    subjects = [g.subject for g in found]
    assert "strandedness" not in subjects
    assert "read_length" in subjects  # a rule reads it
    assert "paired" in subjects       # a sample measures it
```

Run: `T packages/mendel-api/tests/authoring/samples/test_gaps.py -q` → FAIL (`strandedness` is in the list).

- [x] **Step 2: Implement**

In `gaps()`, where `measurements` is built:

```python
    from mendel_api.services import measurers

    measurable = {piece.measures for piece in measurers.usable_pieces(stack).measures.values()}
    # **Not asked: what only a tool reads and no sample can measure** (#338). It is left
    # unknown, and each step whose tool reads it stops for it on the board, as tier 4.
    measurements = set(premises) | {
        m.id
        for m in stack.measurements.measurements.values()
        if m.meta_key and m.describes in leaves and m.id in measurable
    }
```

Update `gaps()`'s docstring with the same sentence.

- [x] **Step 3: Run the gap tests, then fix the tests that walked to strandedness**

Run: `T packages/mendel-api/tests -q -x`. Each failure that waited for the strandedness question: point it at another subject that is still asked (`paired`, `quality_encoding`, `read_length`), or, where the test is *about* strandedness (`test_heard_replies.py` quoting *"reverse-stranded"*), keep it, since the chat can still state it. `forge/test_attention.py` uses strandedness as an example measurement name: change nothing there unless it fails. List every test changed and why in the commit.

- [x] **Step 4: Lint, commit**

```bash
uv run ruff check packages
git add packages/mendel-api
git commit -m "feat(api): gathering does not ask what only a tool reads and no sample measures (#338)"
```

---

### Task 6: The chat model cannot approve a step (#336, operator: C)

**Files:**
- Create: `packages/mendel-api/src/mendel_api/authoring/prompts/builder.chat.v5.md` (copy of v4 without the `proceed` line)
- Modify: `packages/mendel-api/src/mendel_api/authoring/prompts.py` (`CHAT = "builder.chat.v5"`, retire v4, docstring)
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (`ChatReply`: remove `proceed`)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_jobs.py` (remove `if reply.proceed: _proceed(...)` and `_proceed`)
- Test: `packages/mendel-api/tests/authoring/test_authoring_chat_changes.py`

- [x] **Step 1: The failing test**

```python
def test_the_model_cannot_settle_a_waiting_step(clean, monkeypatch):
    """#336, from the second walk: the model's `proceed` settled TrimGalore and STAR_ALIGN, read
    as *you chose*. Continue is the person's button; the field no longer exists."""
    from mendel_api.authoring.types import ChatReply

    assert "proceed" not in ChatReply.model_fields
```

and replace the existing `test_go_on_settles_the_waiting_step_and_does_nothing_at_a_question` with one asserting a reply carrying `"proceed": true` from an in-prompt provider is refused by the shape (extra field), so nothing is settled.

Run → FAIL.

- [x] **Step 2: Implement** — delete the field, the call, `_proceed`; write `builder.chat.v5.md` as v4 minus the `proceed` bullet; `CHAT = "builder.chat.v5"`, add `"builder.chat.v4"` to `RETIRED`, one paragraph in `CHAT`'s docstring (*v5 (2026-10-15, #336): no `proceed`; Continue is the person's*). Update `test_authoring_prompts.py` only if it pins v4's text.

- [x] **Step 3: Run, lint, commit**

Run: `T packages/mendel-api/tests/authoring -q` → PASS.

```bash
uv run ruff check packages
git add packages/mendel-api
git commit -m "fix(api): the chat model cannot approve a step; Continue is the person's (#336)"
```

---

### Task 7: A chat change quotes only the turn it answers (#337, operator: A)

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_jobs.py` (`_follow_up`, the `turns=` passed to `replies.issue`)
- Test: `packages/mendel-api/tests/authoring/test_authoring_chat_changes.py`

- [x] **Step 1: The failing test**

```python
def test_a_quote_from_an_earlier_turn_is_not_heard(clean, monkeypatch):
    """#337, from the second walk: the DE sentence, typed two turns earlier, made a read-length
    retraction read as *you said*. Only the turn being answered can be quoted."""
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "read_length")
    _typed(monkeypatch, sid, "they are 150 bp", {"say": "Noted."})
    _typed(monkeypatch, sid, "and paired-end",
           {"facts": [{"subject": "read_length", "value": 150, "quote": "150 bp"}]})
    assert _value(sid, "read_length") != 150
    assert [v.change.subject for v in suggestions.pending(sid)] == ["read_length"]
```

Run → FAIL (the old quote is heard and recorded).

- [x] **Step 2: Implement** — in `_follow_up`:

```python
    # **Only the turn being answered** (#337): earlier words were read when they were said.
    answered = [t for t in replies.person_turns(session_id) if t[0] < seq][-1:]
```

and pass `turns=answered` to `replies.issue`.

- [x] **Step 3: Run, lint, commit**

Run: `T packages/mendel-api/tests/authoring -q` → PASS.

```bash
uv run ruff check packages
git add packages/mendel-api
git commit -m "fix(api): a chat change quotes only the turn it answers (#337)"
```

---

### Task 8: Docs, verify, and the walk

**Files:**
- Modify: `docs/explanation/authoring-protocol.md` (the tier table: a fact *a chosen tool reads* that is open → 4; one decision-log row, 2026-10-15)
- Modify: `docs/notes/now.md`, a journal entry under `docs/notes/journal/`
- Modify: this plan's checkboxes and execution record

- [x] **Step 1: Protocol** — in *How a fact's source reaches the tiers*, change the open row to *"open: nobody knows, and a rule or a chosen tool reads it"*, and the last row to *"no rule and no chosen tool reads it"*. Decision-log row: *2026-10-15 | whatever a tool reads comes from somewhere, or is tier 4; strandedness left to the board until a profiler measures it | operator, #338*.

- [x] **Step 2: `make verify`** (Docker). Expected: PASS. Name any failure.

- [x] **Step 3: The walk (spec §11)** — `make ai-up OLLAMA_GPU=rocm`, `make dev`, Chrome. Sentence: *Gene counts from paired-end RNA-seq of yeast.* Upload `SRR6357070_1.fastq.gz` and `_2` (scratchpad `walk-data/`) on the reads question; *I have it* for the genome and annotation; confirm; *Set it up, stop only where you need me*. Expected: read length, pairing, quality not asked; strandedness not asked; one stop for strandedness; answer `reverse`; the build completes; *Keep*; the emitted `.nf` passes `-s 2` to featureCounts. Screenshot each; every defect is an issue first.

- [x] **Step 4: Notes, commit**

```bash
git add docs
git commit -m "docs: what a tool reads comes from somewhere, walked (#338)"
```

## Execution record

Executed inline (2026-10-15/16) on `facts-a-step-needs`, `346fbbf` through `de879f5`, from
`fix/i0-walk-findings` (#332). `make verify` green (4170, the 19 real-tool tests, 96 guards).

Deviations, each a ruling:

- **Task 1:** two declaration lists needed the new record, not only the egress count:
  `tests/support/egress.py` (`FactDecision.reason`) and `tests/support/pipeline.py`
  (`_GOAL_MODELS`). That is what those guards demand of a new record.
- **Task 2:** the test lives in `tests/registry/test_facts_read.py`: it reads the shipped
  registry, which `tests/README.md` puts in the repository suite.
- **Task 3:** Review Focus 4 (a yes/no fact offers `[True, False]`) is pinned in the resolver
  test, where candidates are made. No golden changed: every goal the suite resolves states both
  label-carried facts.
- **Task 4:** the RED was an `AttributeError` in `need_of._answered` (a `FactDecision` has no
  `human_override`), not the predicted wrong kind; `_answered` returns False for it first. The
  API test checks that no later card asks for strandedness, rather than walking to a
  featureCounts card: with the fact known, featureCounts needs nothing and is placed quietly.
- **Task 5:** `test_a_measurement_no_inspector_measures_keeps_not_sure` became
  `…_and_no_rule_reads_is_not_asked` (its only example is no longer asked for counts);
  `test_a_direct_edit_writes_a_receipt_the_server_composed` now answers the strandedness stop
  through the decide route before editing. Three phrasing and chat tests use `read_length`, now
  the last question asked.
- **Task 6:** the retired `AuthoringIntent` keeps its `proceed`; only `ChatReply`'s went.
  `_proceed` had settled the step as `"person"`, which is why the walk read *you chose*.
- **Task 8 walk:** the browser tool cannot upload files outside the session's shared folders,
  so the sample went to the card's own endpoint (`POST …/samples`) with curl, and the page was
  reloaded. Everything else was clicked. Result: from *"Gene counts from paired-end RNA-seq of
  yeast."* plus `SRR6357070_1/_2.fastq.gz`, the only questions were the three input files;
  read length (101), pairing and quality (phred33) were measured; the build under *Set it up*
  stopped once, at featureCounts, for strandedness; `reverse` completed it, and the emitted
  pipeline carries `strandedness: reverse` on the reads' label. The card's tier, reason wording
  and free-text answer are #341.
