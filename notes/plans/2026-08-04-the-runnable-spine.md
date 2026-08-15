# The Runnable Spine Implementation Plan

> **Plan 1.5.** Execute **before** Plan 2, Plan 1.7 and Plan 3 — see the execution order in
> [`notes/README.md`](../README.md). This finishes what Plan 1 started: Plan 1 shipped a
> verified *compiler* and left a pipeline that could not run.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax for
> tracking. Do **not** farm the tasks out with subagent-driven-development — subagents are for
> review and design only. This matches the execution decision recorded in `CLAUDE.md`.

**Goal:** Make the emitted RNA-seq spine produce a counts matrix that is *correct*, by giving a
resolved decision somewhere to go: structural flags reach `ext.args`, and measured facts reach the
`meta` map that nf-core modules already read.

**Architecture:** Two mechanisms, both declared data, neither of them new machinery. A contract
gains `ext_args` — a constant string of flags, sitting beside `nf_inputs`, because both answer
"how is this module called?" rather than "what should be decided?". And the measured profile
travels into the channel's `meta` map, where `SUBREAD_FEATURECOUNTS` already contains the code to
translate it. Mendel stops trying to translate on the tools' behalf.

**Tech Stack:** Python 3.12, Pydantic v2, Jinja2, pytest, ruff, `uv` workspace, Nextflow + Docker
for the gates. No AI, no network in any pure package, no new dependency.

## Why this plan exists

`gate stub: PASS` proved the DAG executes. It could not prove more, because **nf-core stubs never
read their inputs** — so a process handed `Channel.value([[:], []])` where a genome belongs is
exactly as green as one handed a genome. Running the spine on real data on 2026-08-04 found three
things, in increasing order of seriousness:

1. `genome.fasta` was not a declared type. Both index builders were called with an empty tuple in
   the reference slot. **Fixed in `53642bc`.**
2. `STAR_ALIGN` was handed an empty GTF while `ch_annotation_gtf` sat in the same workflow feeding
   featureCounts. **Fixed in `53642bc`.**
3. **A resolved parameter reaches no tool at all.** `params.subread_featurecounts_strandedness = 2`
   is emitted and read by nothing. nf-core modules take configuration through `task.ext.args` and
   through `meta`, and Mendel emitted neither.

The third is what this plan is for. Its consequence today is not a crash — it is that the spine
would emit a counts matrix computed with `-s 0` for a reverse-stranded library. **A pipeline that
fails is fine; a pipeline that confidently produces wrong numbers is the failure this product
exists to prevent**, and it would pass every gate we have.

### Emptiness and deadness are different problems

Worth stating because they were conflated while diagnosing this, and only one of them is in scope.

- **Empty** — the registry has three parameters and no defaults, so tier 2 for parameters has
  never fired. Cause: nobody has populated a registry, because hand-authoring one was never the
  plan. `examples/` is fixtures and says so. **Fix: build the forge. Out of scope here.**
- **Dead** — a resolved value reaches no tool. **Fix: this plan.**

The forge does not touch the second. It could draft eight hundred perfect parameter declarations
and every one would still evaporate at emission.

### Why the strandedness rule is deleted rather than wired

```yaml
- decides: {param: strandedness}
  cite: "Liao et al. 2014"          # the featureCounts paper
  rows:
    - {when: {strandedness: reverse}, then: 2}
```

Given the measurement `reverse`, is `-s 2` a decision? No — it is the only correct answer, and the
citation is the tool's own manual. `2` is not a semantic value; it is featureCounts' encoding, and
STAR spells the same fact `--outSAMstrandField intronMotif`. **That rule is a translation wearing
a tier-3 badge**, and `SUBREAD_FEATURECOUNTS` already contains the translation:

```groovy
def strandedness = 0
if (meta.strandedness == 'forward') { strandedness = 1 }
else if (meta.strandedness == 'reverse') { strandedness = 2 }
```

So Mendel carries the *fact* and the module keeps its *encoding*. After this plan the registry has
one tier-3 rule, `producer_of: alignment.bam`, which is a genuine decision between two defensible
aligners with a real citation. That is the honest outcome.

### What this plan does not do

**Parameters that are genuinely chosen** — `seq_platform` is the only one, sits at tier 4, and
still will not reach its tool when this plan is done. Giving `Param` a domain and an expression
needs a corpus to design against: `nf-core/rnaseq` 3.14.0's `conf/modules.config` is 1167 lines,
78 `withName` blocks and 44 `ext.args`, many of them Groovy ternaries that are *decision tables
that have been compiled and lost their provenance*. That is a forge ingestion problem, and
designing it from the one example in this registry is how the last three plans produced steps that
did not survive contact with the code. Recorded as a new task on Plan 2.

## Global Constraints

- `comeni-core` and `mendel-resolver` are under a **closed allowlist** in `tests/test_purity.py`.
  Nothing in this plan needs a new import; if you reach for one, stop.
- **`PipelineIR` is reachable from `PublishBundle`.** Anything added to it must satisfy
  `tests/test_egress.py`: no `Any`, no mapping, no bare `str`, `extra="forbid"`. Task 2 adds a
  field to it, and `DataProfile` already satisfies the guard.
- **A `DataProfile` is built in exactly one place** — `MeasurementRegistry.profile()`, enforced by
  `tests/test_construction.py`. Task 2 must not construct one.
- Determinism is a test: same goal → byte-identical `.nf`, across `PYTHONHASHSEED` values.
- Ruff line length 100. `make check` passes before every commit.
- **Read process names, containers and flags out of `vendor/modules/**/main.nf`, never out of this
  plan.** Every Groovy fragment quoted here was read from the vendored tree on 2026-08-04 and
  should be re-read rather than trusted.

## Prerequisites, already landed

On branch `runnable-spine`, not merged:

- `53642bc` — `genome.fasta` as a declared type with an entry channel; both index builders consume
  it; `STAR_ALIGN` consumes the annotation; `NfInput.because` required whenever `empty` is set;
  `Vocabulary.test_data` and an emitted `test` profile so `Gate.TEST` can run at all.
- `59f3f0e` — `test_data` may be a list, because Nextflow refuses a glob pattern over https and
  `fromFilePairs` cannot brace-expand a URL.

Both are prerequisites for Task 4's verification run. Do not start this plan on `main`.

---

## File Structure

```
packages/comeni-core/src/comeni_core/
├─ contract.py       MODIFY — ModuleContract.ext_args
├─ ir.py             MODIFY — PipelineIR.profile
├─ measurement.py    MODIFY — Measurement.describes, meta_key, meta_values
packages/mendel-resolver/src/mendel_resolver/
├─ resolve.py        MODIFY — carry goal.profile onto the IR
packages/mendel-compiler/src/mendel_compiler/
├─ emit.py           MODIFY — withName/ext.args block; meta injection on entry channels
examples/
├─ contracts/nf-core/star-align.yml          MODIFY — ext_args
├─ measurements/strandedness.yml             MODIFY — describes, meta_key
├─ measurements/paired.yml                   MODIFY — describes, meta_key, meta_values
├─ contracts/nf-core/subread-featurecounts.yml  MODIFY — drop the strandedness param
├─ rules/rnaseq.yml                          MODIFY — drop the strandedness decision
tests/
├─ test_runnable.py  MODIFY — extend; it already exists from 53642bc
├─ test_counts.py    NEW — the run produced a matrix, and the matrix is right
```

**Ordering rationale.** `ext_args` first because it is what makes the pipeline execute at all, and
every later task wants to run it. `PipelineIR.profile` before the meta injection that reads it.
The deletion last among the code tasks, because removing the rule while parameters are still the
only path would leave strandedness unset in both mechanisms at once.

---

### Task 1: `ext_args` — flags a module always needs

`STAR_ALIGN` fails on real data with `wrong read ID line format: the read ID lines should start
with @ or >` and a binary offending line, because TrimGalore emits `.fq.gz` and STAR was not told
to decompress. That is not a decision anybody makes; it is a fact about how this module must be
called, which is what `nf_inputs` already is.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/contract.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`
- Modify: `examples/contracts/nf-core/star-align.yml`
- Test: `tests/test_runnable.py`

**Interfaces:**
- Consumes: `ModuleContract`, `emit_config`
- Produces: `ModuleContract.ext_args: str`; a `process { withName: … { ext.args = … } }` block in
  the emitted `nextflow.config`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_runnable.py`:

```python
def test_a_contract_can_declare_flags_its_module_always_needs(loaded):
    """Not a decision, so it carries no tier. `nf_inputs` says which channels a module
    takes; this says which flags it takes. Both are "how is this called", and neither is
    "what should be decided" — giving it a tier would dilute what a tier means."""
    star = loaded.registry.get("nf-core/star/align@1.11.0")
    assert "--readFilesCommand zcat" in star.ext_args


def test_ext_args_reaches_the_emitted_config(spine, loaded):
    """STAR died on real data with 'wrong read ID line format' and a binary offending
    line: TrimGalore emits .fq.gz and nothing told STAR to decompress."""
    from mendel_compiler.emit import emit_config

    config = emit_config(spine, loaded.registry, loaded.vocabulary)
    assert "process {" in config
    assert "withName: STAR_ALIGN" in config
    assert "ext.args = '--readFilesCommand zcat'" in config


def test_a_module_with_no_ext_args_gets_no_withname_block(spine, loaded):
    """An empty block is noise, and noise in generated config is how nobody reads it."""
    from mendel_compiler.emit import emit_config

    config = emit_config(spine, loaded.registry, loaded.vocabulary)
    assert "withName: TRIMGALORE" not in config


def test_ext_args_is_escaped_like_any_other_literal(loaded):
    """These reach Groovy. An unescaped quote is a syntax error and a crafted value runs."""
    from comeni_core.contract import ModuleContract

    contract = loaded.registry.get("nf-core/star/align@1.11.0")
    assert isinstance(contract, ModuleContract)
    with_quote = contract.model_copy(update={"ext_args": "--x 'it's'"})
    from mendel_compiler.emit import _render_literal

    assert "\\'" in _render_literal(with_quote.ext_args)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runnable.py -v -k "ext_args or always_needs"`
Expected: FAIL — `ModuleContract` has no attribute `ext_args`.

- [ ] **Step 3: Add the field**

In `packages/comeni-core/src/comeni_core/contract.py`, add to `ModuleContract`, immediately after
`nf_inputs`:

```python
    ext_args: str = ""
    """Flags this module always needs, regardless of any decision.

    Sits beside `nf_inputs` because both answer the same question — *how is this module
    called?* — rather than *what should be decided?*. `--readFilesCommand zcat` is not a
    judgement anybody makes; it is forced by TrimGalore emitting `.fq.gz`.

    **Carries no tier, deliberately.** A tier is for a decision. Labelling this tier 1
    would be defensible and would dilute what a tier means, which is the one thing this
    project sells.

    Emitted into `process { withName: <nf_process> { ext.args = ... } }`, which is where
    every nf-core module reads its arguments from: `def args = task.ext.args ?: ''`.
    """
```

- [ ] **Step 4: Emit the process scope**

In `packages/mendel-compiler/src/mendel_compiler/emit.py`, add above `emit_config`:

```python
def _process_scope(ir: PipelineIR, registry: Registry) -> list[str]:
    """`ext.args` per process, for modules that declare flags they always need.

    Every nf-core module opens its script with `def args = task.ext.args ?: ''`, so this
    is the only channel by which a flag reaches a tool. Emitting nothing for a module with
    no `ext_args` keeps the generated config readable; an empty block is noise, and noise
    is how a generated file stops being read.
    """
    blocks = []
    for node in ir.nodes:
        contract = registry.get(node.contract_id)
        if not contract.ext_args:
            continue
        blocks.append(
            f"    withName: {contract.nf_process} "
            f"{{ ext.args = {_render_literal(contract.ext_args)} }}"
        )
    if not blocks:
        return []
    # Sorted and deduplicated: a contract used twice must not emit its block twice, and
    # byte-identical output is a hard requirement.
    return ["process {", *sorted(set(blocks)), "}", ""]
```

and call it in `emit_config`, between the `params` block and `profiles`:

```python
    lines += [f"    {name} = null" for name in params]
    lines += ["}", ""]
    lines += _process_scope(ir, registry)
    lines += ["profiles {", "    stub_data {"]
```

> Note the existing code writes `lines += ["}", "", "profiles {", "    stub_data {"]` as one
> statement. Split it exactly as shown or the process scope lands inside `profiles`.

- [ ] **Step 5: Declare it on the contract**

In `examples/contracts/nf-core/star-align.yml`, add after `nf_inputs`:

```yaml
# TrimGalore emits .fq.gz and STAR reads plain text unless told otherwise. Not a
# decision — a fact about the upstream module's output format.
ext_args: "--readFilesCommand zcat"
```

- [ ] **Step 6: Run tests and lint**

Run: `make check`
Expected: PASS. The golden file `tests/golden/spine/main.nf` is unaffected — this changes
`nextflow.config`, not `main.nf`. If a config golden exists and fails, **read the diff before
regenerating it**: a generated file committed unread is how two include statements ended up on one
line once already.

- [ ] **Step 7: Commit**

```bash
git add packages/comeni-core packages/mendel-compiler examples/contracts tests/test_runnable.py
git commit -m "feat(core): a contract may declare flags its module always needs"
```

---

### Task 2: The IR records the profile it was built from

The emitter needs the measured profile to put it in `meta`, and cannot see it — `emit(ir, registry,
vocab)` takes no goal. It belongs on the IR regardless: the profile is part of what this pipeline
was built from, the same reason Plan 1.7 puts `registry_layers` there.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/ir.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Test: `packages/comeni-core/tests/test_ir_profile.py`

**Interfaces:**
- Consumes: `DataProfile`
- Produces: `PipelineIR.profile: DataProfile`

- [ ] **Step 1: Write the failing test**

```python
import pathlib

from comeni_core.ir import PipelineIR
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve

ROOT = pathlib.Path(__file__).parents[3]


def test_an_ir_defaults_to_an_empty_profile():
    assert PipelineIR().profile.measurements == []


def test_a_resolved_ir_carries_the_profile_it_was_built_from():
    loaded = layers.load(ROOT / "examples")
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["qc.report"],
        profile=loaded.measurements.profile({"strandedness": "reverse", "paired": True}),
    )
    ir = resolve(goal, loaded.registry, loaded.rules)
    assert ir.profile.get("strandedness") == "reverse"
    assert ir.profile.get("paired") is True


def test_the_profile_survives_serialisation():
    """It reaches the emitter through pipeline.ir.json in the CLI, not through memory."""
    loaded = layers.load(ROOT / "examples")
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["qc.report"],
        profile=loaded.measurements.profile({"strandedness": "reverse"}),
    )
    ir = resolve(goal, loaded.registry, loaded.rules)
    round_tripped = PipelineIR.model_validate_json(ir.model_dump_json())
    assert round_tripped.profile.get("strandedness") == "reverse"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_ir_profile.py -v`
Expected: FAIL — `PipelineIR` has no attribute `profile`.

- [ ] **Step 3: Add the field**

In `packages/comeni-core/src/comeni_core/ir.py`, import `DataProfile` and add to `PipelineIR`:

```python
from comeni_core.profile import DataProfile
```

```python
    profile: DataProfile = Field(default_factory=DataProfile)
    """What was measured about the data this pipeline was built for.

    On the IR rather than passed to the emitter separately, because it is part of what the
    pipeline was built *from* — the same reason Plan 1.7 puts `registry_layers` here. The
    emitter needs it to populate the `meta` map, and a reviewer reading
    `pipeline.ir.json` needs it to know which measurement a tier-3 decision rested on.
    """
```

> **`DataProfile` construction.** `Field(default_factory=DataProfile)` is a reference, not a call,
> so `tests/test_construction.py` does not flag it — the AST guard looks for `ast.Call`. This is
> the same shape `Goal.profile` already uses. Do not write `default=DataProfile()`.

- [ ] **Step 4: Carry it in `resolve`**

In `packages/mendel-resolver/src/mendel_resolver/resolve.py`, change the IR construction:

```python
    ir = PipelineIR(profile=goal.profile)
```

- [ ] **Step 5: Run the full suite and lint**

Run: `make check`
Expected: PASS. `pipeline.ir.json` gains a `profile` key, so any golden asserting the whole
document needs regenerating — read the diff.

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core packages/mendel-resolver
git commit -m "feat(core): the IR carries the profile it was built from"
```

---

### Task 3: Measured facts reach the tools through `meta`

`SUBREAD_FEATURECOUNTS` already contains the translation:

```groovy
def paired_end   = meta.single_end ? '' : '-p'
def strandedness = 0
if (meta.strandedness == 'forward')      { strandedness = 1 }
else if (meta.strandedness == 'reverse') { strandedness = 2 }
```

With `meta.strandedness` unset it computes `-s 0`. For a reverse-stranded library that is a
counts matrix full of wrong numbers, produced silently, passing every gate.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/measurement.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`
- Modify: `examples/measurements/strandedness.yml`, `examples/measurements/paired.yml`
- Test: `tests/test_runnable.py`

**Interfaces:**
- Consumes: `PipelineIR.profile` (Task 2), `Measurement`
- Produces: `MetaValue(when, then)`; `Measurement.describes: TypeId | None`,
  `Measurement.meta_key: str | None`, `Measurement.meta_values: list[MetaValue]`;
  `MeasurementRegistry.meta_for(type_id, profile) -> dict[str, ParamValue]`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_runnable.py`:

```python
def test_a_measurement_can_declare_how_it_appears_in_meta(loaded):
    strandedness = loaded.measurements.get("strandedness")
    assert strandedness.describes == "fastq.reads"
    assert strandedness.meta_key == "strandedness"


def test_a_measurement_can_declare_a_value_translation(loaded):
    """We ask whether the library is paired; nf-core asks whether it is single-end.
    The same fact, spelled inside out, and the translation is declared rather than known
    by the compiler."""
    paired = loaded.measurements.get("paired")
    assert paired.meta_key == "single_end"
    assert loaded.measurements.meta_for(
        "fastq.reads", loaded.measurements.profile({"paired": True})
    ) == {"single_end": False}


def test_measurements_without_a_meta_key_are_not_carried(loaded):
    """`n_samples` is a property of the study, not of a read. Opt-in, so nothing lands in
    a meta map by accident."""
    meta = loaded.measurements.meta_for(
        "fastq.reads", loaded.measurements.profile({"n_samples": 12, "strandedness": "reverse"})
    )
    assert meta == {"strandedness": "reverse"}


def test_meta_is_only_built_for_the_type_a_measurement_describes(loaded):
    """Putting strandedness on the genome channel would be meaningless and would read as a
    bug to anyone inspecting the emitted workflow."""
    profile = loaded.measurements.profile({"strandedness": "reverse"})
    assert loaded.measurements.meta_for("genome.fasta", profile) == {}


def test_the_emitted_entry_channel_carries_the_meta(spine_with_profile, loaded):
    from mendel_compiler.emit import emit

    source = emit(spine_with_profile, loaded.registry, loaded.vocabulary)
    line = next(ln for ln in source.splitlines() if "ch_fastq_reads =" in ln)
    assert "strandedness: 'reverse'" in line, line
    assert "single_end: false" in line, line


def test_an_unmeasured_profile_emits_no_meta_wrapper(spine, loaded):
    """No profile, no `.map`. The pipeline should not gain a no-op that a reader has to
    understand before dismissing."""
    from mendel_compiler.emit import emit

    source = emit(spine, loaded.registry, loaded.vocabulary)
    line = next(ln for ln in source.splitlines() if "ch_fastq_reads =" in ln)
    assert "meta +" not in line, line
```

Add the fixture beside the existing `spine` fixture in `tests/test_runnable.py`:

```python
@pytest.fixture
def spine_with_profile(loaded):
    goal = Goal(
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile(
            {"read_length": 150, "strandedness": "reverse", "paired": True}
        ),
    )
    return resolve(goal, loaded.registry, loaded.rules)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runnable.py -v -k "meta"`
Expected: FAIL — `Measurement` has no attribute `describes`.

- [ ] **Step 3: Add the declaration fields**

In `packages/comeni-core/src/comeni_core/measurement.py`, add above `Measurement`:

```python
class MetaValue(BaseModel):
    """One value translation between our vocabulary and a module's.

    A list of records rather than a mapping, matching `ParamBinding` and `Measured`: a
    typed key does not prove a declared key, and `Measurement` is one field away from
    being reachable from a publish bundle.
    """

    model_config = ConfigDict(extra="forbid")

    when: ParamValue
    then: ParamValue
```

and to `Measurement`, after `edam`:

```python
    describes: MeasurementId | None = None
    """Which type this is a property of, e.g. `fastq.reads`.

    Only measurements that describe something can be carried into that thing's `meta` map.
    `n_samples` describes the study rather than a read, so it has no `describes` and is
    never carried.
    """

    meta_key: str | None = None
    """How a module spells this in `meta`, if any. Absent means never carried.

    Opt-in, so nothing lands in a meta map by accident. nf-core modules read
    `meta.strandedness` and `meta.single_end` directly and do their own translation into
    flags — which is why Mendel carries the *fact* and lets the module keep its encoding.
    """

    meta_values: list[MetaValue] = Field(default_factory=list)
    """Value translations, when our vocabulary and the module's disagree.

    We ask whether a library is `paired`; nf-core asks whether it is `single_end`. The same
    fact spelled inside out. Declared here rather than known by the compiler, for the same
    reason `entry_channel` is declared: this has to work for a module nobody has seen.
    """
```

- [ ] **Step 4: Build the meta map**

Append to `MeasurementRegistry` in the same file:

```python
    def meta_for(self, type_id: str, profile: DataProfile) -> dict[str, ParamValue]:
        """The `meta` entries a channel of `type_id` should carry, from this profile.

        Only measurements that declare both `describes` and `meta_key`, and that the
        profile actually measured. Everything else is silence, which is the honest default:
        a `meta` key with a made-up value is worse than an absent one, because the module
        will use it.
        """
        found: dict[str, ParamValue] = {}
        for measurement_id in self.ids():
            measurement = self.get(measurement_id)
            if measurement.describes != type_id or not measurement.meta_key:
                continue
            value = profile.get(measurement_id)
            if value is None:
                continue
            for translation in measurement.meta_values:
                if translation.when == value:
                    value = translation.then
                    break
            found[measurement.meta_key] = value
        return found
```

- [ ] **Step 5: Declare it on the two measurements**

`examples/measurements/strandedness.yml` — append:

```yaml
describes: fastq.reads
meta_key: strandedness
```

`examples/measurements/paired.yml` — append:

```yaml
describes: fastq.reads
# We ask whether the library is paired; nf-core asks whether it is single-end. Same fact,
# spelled inside out. featureCounts reads it as `meta.single_end ? '' : '-p'`.
meta_key: single_end
meta_values:
  - {when: true, then: false}
  - {when: false, then: true}
```

- [ ] **Step 6: Wrap the entry channel**

In `packages/mendel-compiler/src/mendel_compiler/emit.py`, the entry-channel expression comes from
the vocabulary and already produces `[meta, files]`. Wrap rather than replace it, so the
vocabulary keeps owning arrival:

```python
def _render_meta(entries: dict[str, object]) -> str:
    """A Groovy map literal, keys sorted so emission stays byte-identical."""
    rendered = ", ".join(f"{key}: {_render_literal(entries[key])}" for key in sorted(entries))
    return "[" + rendered + "]"


def _with_meta(expression: str, entries: dict[str, object]) -> str:
    """Merge measured facts into the channel's meta map.

    `meta + [...]` rather than replacing it: the entry channel already put an `id` there,
    and losing it would break `tag "$meta.id"` in every module.
    """
    if not entries:
        return expression
    return (
        f"({expression}).map {{ meta, files -> [ meta + {_render_meta(entries)}, files ] }}"
    )
```

and use it where entry channels are built. In `_entry_channels`, which currently returns
`[(channel_name, expression)]`, thread the profile through:

```python
def _entry_channels(
    ir: PipelineIR, registry: Registry, vocab: Vocabulary, measurements=None
) -> list[tuple[str, str]]:
    """Declarations for every type consumed but not produced inside the pipeline."""
    needed = _entry_expressions(ir, registry, vocab)
    return [
        (
            _channel_name(type_id),
            _with_meta(
                needed[type_id],
                measurements.meta_for(type_id, ir.profile) if measurements else {},
            ),
        )
        for type_id in sorted(needed)
    ]
```

`emit` gains an optional `measurements` argument and passes it through. The CLI passes
`loaded.measurements`.

**`entry_params` must be repointed at `_entry_expressions` first.** It currently reads
`_entry_channels`, and after this change that string contains the meta wrapper — so
`re.findall(r"params\.(\w+)")` would scan generated Groovy that has nothing to do with how a
type arrives. It happens to still find `params.input` today, which is worse than breaking,
because it would keep working until a meta value contained the word `params`:

```python
def entry_params(ir: PipelineIR, registry: Registry, vocab: Vocabulary) -> list[str]:
    found: set[str] = set()
    for expression in _entry_expressions(ir, registry, vocab).values():
        found.update(re.findall(r"params\.(\w+)", expression))
    return sorted(found)
```

A parameter comes from how a type *arrives*, never from what was merged into its meta.

> **Why optional.** `emit(ir, registry, vocab)` is called from several tests with no measurement
> registry, and a required argument would be churn across all of them for no benefit. Absent means
> no meta, which is what an unmeasured pipeline should emit anyway.

- [ ] **Step 7: Run the full suite and lint**

Run: `make check`
Expected: PASS. `tests/golden/spine/main.nf` changes only if that golden's IR carries a profile —
it does not, so it should be untouched. **Read the diff if it is not.**

- [ ] **Step 8: Commit**

```bash
git add packages/ examples/measurements tests/test_runnable.py
git commit -m "feat: measured facts reach the tools through the meta map"
```

---

### Task 4: Delete the translation, and prove the matrix is right

**Files:**
- Modify: `examples/rules/rnaseq.yml`, `examples/contracts/nf-core/subread-featurecounts.yml`
- Test: `tests/test_counts.py`

**Interfaces:**
- Consumes: everything above
- Produces: a verified counts matrix

- [ ] **Step 1: Write the failing test**

```python
"""The spine produces a counts matrix, and the matrix is right.

`gate stub: PASS` proves the DAG executes. This proves the analysis ran with the
parameters that were decided — which is a different claim, and the one a biologist reads.

Marked `slow`: it needs Docker, Nextflow and about ten minutes. CI runs it nightly.
"""

import pathlib
import subprocess

import pytest
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent
pytestmark = pytest.mark.slow


def test_the_registry_has_one_tier_three_rule_and_it_is_the_aligner():
    """The strandedness block was a translation the module already performs. What remains
    is a genuine decision between two defensible aligners, with a real citation."""
    table = layers.load(ROOT / "examples").rules
    assert [d.decides.key() for d in table.decisions] == ["producer_of:alignment.bam"]


def test_featurecounts_declares_no_parameters():
    """Strandedness arrives through meta now. A `Param` for it would resolve to a value
    that reaches nothing, which is what this whole plan is about removing."""
    registry = layers.load(ROOT / "examples").registry
    assert registry.get("nf-core/subread/featurecounts@2.0.6").params == []


def test_the_spine_produces_a_counts_matrix(tmp_path):
    out = tmp_path / "spine"
    build = subprocess.run(
        ["uv", "run", "mendel", "build", "--goal", str(ROOT / "examples/rnaseq-goal.yml"),
         "--out", str(out), "--root", str(ROOT), "--gate", "test"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert build.returncode == 0, build.stderr[-4000:]

    matrices = list(out.rglob("*.featureCounts.tsv"))
    assert matrices, "no counts matrix was produced"
    rows = [ln for ln in matrices[0].read_text().splitlines() if not ln.startswith("#")]
    assert len(rows) > 1, "the counts matrix has a header and no genes"


def test_featurecounts_ran_with_the_strandedness_that_was_measured(tmp_path):
    """The point of the whole plan. `examples/rnaseq-goal.yml` declares reverse, and
    featureCounts must therefore have run with `-s 2`. Before this plan it ran with `-s 0`
    and produced a matrix full of wrong numbers, silently, passing every gate."""
    out = tmp_path / "spine"
    subprocess.run(
        ["uv", "run", "mendel", "build", "--goal", str(ROOT / "examples/rnaseq-goal.yml"),
         "--out", str(out), "--root", str(ROOT), "--gate", "test"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    commands = list((out / "work").rglob(".command.sh"))
    featurecounts = [c for c in commands if "featureCounts" in c.read_text()]
    assert featurecounts, "featureCounts never ran"
    script = featurecounts[0].read_text()
    assert "-s 2" in script, script
    assert "-p" in script, "paired-end reads must be counted as fragments"
```

- [ ] **Step 2: Register the marker**

In root `pyproject.toml`, under `[tool.pytest.ini_options]`:

```toml
markers = ["slow: needs Docker and Nextflow; run nightly, not on a pull request"]
addopts = "-m 'not slow'"
```

`make check` then skips it and stays a one-minute gate. The nightly workflow runs
`uv run pytest -m slow -v`.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_counts.py -m slow -v -k "tier_three or no_parameters"`
Expected: FAIL — the rule table still has two decisions and featureCounts still declares
`strandedness`.

- [ ] **Step 4: Delete the translation**

In `examples/rules/rnaseq.yml`, remove the entire `param: strandedness` block, leaving:

```yaml
version: 1
decisions:
  - decides: {producer_of: alignment.bam}
    because: "read length determines which aligner is appropriate"
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@1.11.0}
      - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2}
```

In `examples/contracts/nf-core/subread-featurecounts.yml`, replace the `params` block:

```yaml
# Strandedness arrives through `meta.strandedness`, which this module already translates
# into `-s`. A Param here would resolve to a value that reaches nothing.
params: []
```

- [ ] **Step 5: Run the fast suite**

Run: `make check`
Expected: PASS. Several tests assert on the strandedness decision and must be updated rather than
deleted — `test_strandedness_resolves_at_tier_3_from_the_profile` in `tests/test_end_to_end.py`
asserted the behaviour this plan removes. Replace it with an assertion that the emitted workflow
carries `strandedness: 'reverse'` in the reads channel's meta, which is the same guarantee at the
place it now lives.

- [ ] **Step 6: Run it for real**

Run: `uv run pytest tests/test_counts.py -m slow -v`
Expected: PASS, about ten minutes on a warm container cache.

**If featureCounts ran with `-s 0`**, the meta did not reach it. Check in this order: the entry
channel's `.map` in `main.nf`; whether `SAMTOOLS_SORT.out.bam` preserved the meta (it does —
nf-core modules pass `meta` through); and `.command.sh` in the featureCounts work directory, which
is the ground truth.

- [ ] **Step 7: Commit**

```bash
git add examples tests pyproject.toml
git commit -m "feat: delete the strandedness translation; the spine counts correctly"
```

---

### Task 5: Record it

**Files:**
- Modify: `notes/README.md` — execution order
- Modify: `notes/plans/2026-08-02-mendel-ai-and-forge.md` — the parameters task
- Modify: `CLAUDE.md`, `CHANGELOG.md`, `.github/workflows/nightly.yml`
- Create: `notes/journal/<today>.md`

- [ ] **Step 1: Give the plans directory an execution order**

Filenames are a log, not an order — two plans share the date `2026-08-04`. In
`notes/README.md`, replace the plans table:

```markdown
| Order | Plan | Status |
|---|---|---|
| 1 | `2026-08-02-mendel-deterministic-spine.md` | complete |
| 2 | `2026-08-03-measurements-rules-and-profiling.md` | complete |
| 3 | `2026-08-04-the-runnable-spine.md` | **next** — Plan 1.5, finishes Plan 1's business |
| 4 | `2026-08-04-publication-and-the-registry-split.md` | Plan 1.7 — written, unimplemented |
| 5 | `2026-08-02-mendel-ai-and-forge.md` | Plan 2 — predates the types it references |
| 6 | `2026-08-02-mendel-api-and-dashboard.md` | Plan 3 — predates the types it references |

**Execute in this order.** Plan 1.5 comes before Plan 1.7 because publishing a bundle built on an
unverified spine would push a wrong pipeline through the door with no undo.
```

- [ ] **Step 2: Add the parameters task to Plan 2**

Plan 2's forge half is Tasks 8–10 and has nothing about parameters, because when it was written
nobody had looked at `conf/modules.config`. Append to that plan, before its Self-Review:

```markdown
### Task 11: Parameters, drafted from the corpus

Added 2026-08-04, after `mendel build` was found to emit resolved parameters that reach no
tool and the registry was found to hold three parameters and no defaults.

`nf-core/rnaseq` 3.14.0's `conf/modules.config` is 1167 lines, 78 `withName` blocks and 44
`ext.args`. Many are Groovy closures:

    ext.args = { [ params.gencode ? '--gencode' : '',
                   params.pseudo_aligner_kmer_size ? "-k ${params.pseudo_aligner_kmer_size}" : ''
                 ].join(' ').trim() }

That is a decision table which has been compiled into Groovy and lost its provenance. Across
nf-core's pipelines it is thousands of parameter decisions made by domain experts, reviewed in
pull requests and released under DOIs — the tier-2 corpus, sitting in public repositories.

The task: ingest `conf/modules.config` from pipelines named in the layer's config, classify
each `ext.args` as static, conditional or computed, recover conditionals as `DecisionRow`s,
and draft `Param` declarations with a domain and an attribution. A human approves them, as
with every other forge output.

**Design `Param`'s domain and expression here, against that corpus — not from the single
example in `examples/`.** Plan 1.5 deliberately left `Param` untouched for this reason.
```

- [ ] **Step 3: Run the slow tests nightly**

In `.github/workflows/nightly.yml`, after the stub gate step:

```yaml
      - name: The spine counts correctly on the test dataset
        run: uv run pytest -m slow -v
        # `make check` excludes these; they need Docker and about ten minutes. This is the
        # only gate that can catch a pipeline which runs and computes the wrong numbers.
```

- [ ] **Step 4: Update `CLAUDE.md`**

The v1 criterion block currently says the criterion is unreachable and the spine has never
produced a counts matrix. Replace with what is true after this plan, and add two gotchas:

```markdown
- **`-stub-run` cannot see a hollow input.** nf-core stubs never read their inputs, so a
  process handed `Channel.value([[:], []])` where a genome belongs is exactly as green as one
  handed a genome. `NfInput.empty` therefore requires a `because`, and only `--gate test`
  catches the rest.
- **A resolved value needs somewhere to go.** nf-core modules read `task.ext.args` and `meta`.
  A `params.<x>` in the emitted workflow is read by nothing. `ext_args` covers flags a module
  always needs; measured facts go through `meta`, where the module does its own translation.
```

- [ ] **Step 5: Update `CHANGELOG.md`**

An `Unreleased` entry: the genome type, the GTF wiring, `ext_args`, meta, the deleted
translation, and — stated plainly — that the spine previously emitted a counts matrix computed
with the wrong strandedness.

- [ ] **Step 6: Write the journal entry**

Follow `notes/journal/README.md`. Record the emptiness/deadness distinction, why the
strandedness rule was deleted rather than wired, and that `Param` was deliberately left alone
for Plan 2 Task 11.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "docs: the runnable spine, and where parameters get designed"
```

---

## Self-Review

**Coverage.**

| Finding | Task |
|---|---|
| no reference genome in the type system | **done**, `53642bc` |
| `STAR_ALIGN` handed an empty GTF | **done**, `53642bc` |
| no `test` profile emitted, so `Gate.TEST` could not pass | **done**, `53642bc` |
| glob pattern refused over https | **done**, `59f3f0e` |
| STAR needs `--readFilesCommand zcat` | 1 |
| resolved values reach no tool | 1 (flags) and 3 (measured facts) |
| featureCounts computed `-s 0` for a reverse-stranded library | 3, verified in 4 |
| the strandedness rule is a translation, not a decision | 4 |
| ten processes against a 15–20 target | **not addressed** — see below |
| parameter coverage: three parameters, no defaults | **Plan 2 Task 11**, added in 5 |

**The module count is deliberately untouched.** The remaining canonical processes —
`samtools stats`/`flagstat`/`idxstats`, duplicate marking, RNA-specific QC — are breadth, not
correctness. A pipeline with twenty modules that ignores every parameter is worse than one with
ten that does not. Revisit the v1 criterion's "~15–20 modules" clause after this plan, when the
ten that exist are known to be right.

**Placeholder scan.** No TBDs. Every code step contains runnable code. Task 3 Step 6 shows the
changed signature of `_entry_channels` rather than the whole file, and gives `entry_params` in
full because it is the one function in that file this plan requires you to rewrite.

**Type consistency.** `meta_for(type_id, profile)` takes the same two arguments in Task 3's tests
and its implementation. `MetaValue(when, then)` matches `DecisionRow`'s vocabulary deliberately —
both are "when this, then that", and a reader who has met one has met the other.
`PipelineIR.profile` is a `DataProfile`, matching `Goal.profile`, so `resolve` assigns it without
conversion. `_with_meta` and `_render_meta` are used only by `_entry_channels`.

**One error found by this review, and fixed inline.** The first draft asserted that
`entry_params` calls `_entry_expressions` and was unaffected by Task 3. It does not — it reads
`_entry_channels` (`emit.py:182`), and I had confused it with `_params_by_type` (`emit.py:197`),
which does. Left unfixed, the meta wrapper would have been scanned by the `params.<name>` regex.
It would not have failed a test: `params.input` is still inside the wrapped string, so it keeps
working right up until a meta value contains the word `params`. Task 3 Step 6 now repoints it
first.

That is the second plan in two days to assert something about code that was not true, and both
were caught by running a two-line check rather than by reading. **Verify claims about existing
code with a command, not with recollection.**

---

## Verification

```bash
uv sync
make check                       # fast; excludes the slow marker
uv run pytest -m slow -v         # needs Docker and Nextflow, ~10 min
make stub                        # gate stub: PASS
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate test
find build -name '*.featureCounts.tsv' -exec head -3 {} \;
grep -o '\-s [0-9]' $(grep -rl featureCounts build/work --include='.command.sh' | head -1)
```

Complete when the last command prints `-s 2`, the matrix has genes in it, `make check` stays under
a minute, and `examples/rules/rnaseq.yml` contains exactly one decision.
