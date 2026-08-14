# Plan 1.14 — the explanation

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task, driven yourself, sequentially. Subagents are for review and design only —
> that is the operator's instruction in `CLAUDE.md`, not a suggestion. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Make *"nothing was guessed silently"* true — every value that reaches a tool carries a
reason, and no reason outlives the value it was written about.

**Architecture:** Six fields and one precedence fix, across the three pure packages. The pattern
is the same every time: a fact the artifact already carries gains the justification it was always
supposed to have, refused at load or at emit rather than left to a reviewer's attention. This
plan bumps `pipeline.yml` to `version: 2`; Plan 1.13 deliberately held every schema change back
so that it lands in one reviewable step.

**Tech Stack:** Python 3.12, Pydantic v2, Jinja2, pytest, `uv`.

**Spec:** [`docs/internal/audits/2026-08-14-design-audit.md`](../audits/2026-08-14-design-audit.md)
— roots 1, 2 and 3, plus A91 from root 4. Read the *philosophy question* section before starting:
this plan is the one the operator's 2026-08-14 decision promotes from legibility to correctness,
because the artifact's primary reader is an agent, and **a person reading a blank asks while a
model reading a blank fills it.**

## Global Constraints

- **Python floor 3.12.12 exactly.** Line length 100. `uv run ruff check .` clean. `ruff format`
  is not a gate.
- **The three pure packages do not reach the network.** No new transport, `ctypes`, `subprocess`,
  or dynamic import.
- **`make verify`, not `make check`**, at every verification step. Every task touches
  `pipeline.py`, `emit.py`, `rules.py` or `router.py`.
- **`pipeline.yml` goes to `version: 2` in Task 1 and stays there.** A `version: 1` file must
  still load and still emit — archived pipelines are the artifact's whole point. Every task that
  adds a required field states its version-1 behaviour explicitly.
- **A code is never renumbered.** `MD0223` onward in the pipeline-file band; `MD0301` onward in
  routing (Plan 1.13 opened that band with `MD0300`). Register each in
  `packages/comeni-core/src/comeni_core/diagnostics.yml` and run `make docs`.
- **Every task ends with a recorded revert** in `docs/internal/audits/guard-ledger.md`. That is
  A14's closure condition and this plan adds seven guards; a guard never watched failing may be
  inert rather than merely weak.
- **Do not weaken the egress guard.** `Why` is reachable from door 4's payload, so every field
  added here widens the publication boundary. `tests/test_egress.py` holds the field list
  literally and must be edited deliberately, never to make a test pass.

---

## Task 1: `Why.for_value` — a reason cannot outlive its value

**The defect (A104, critical; A105).** A hand-edited `settings[].value` keeps the `why:` written
for the value it replaced. Reproduced: `min_mqs` edited `0 → 30` emits `ext.args = '-Q 30'` while
the record still reads `tier: 2 / source: resolver / reason: contract default for min_mqs` — all
three false — and `mendel publish --gate lint` certified it at exit 0. `MD0218`/`MD0220` do this
cross-check already, but only for tier-4 `ParamDecision`s, and only in the *safe* direction.

Under the engine decision this stops being a legibility defect: a human leaves a stale reason
occasionally and may notice; an agent tuning settings does it systematically and does not.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py:73-90` — `Why.for_value`
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py:333-350` — `version: 2`
- Modify: wherever a `Why` is constructed in `mendel_resolver/router.py` and `resolve.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/pipeline_file.py` — the `MD0223` check
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`
- Test: `tests/test_pipeline_file.py`

**Interfaces:**
- Produces: `Why.for_value: ParamValue = None` — the value this reason was written about.
  Every later task's `Why` construction must set it.

- [ ] **Step 1: Write the failing test**

```python
def test_editing_a_value_without_its_reason_is_refused(tmp_path):
    """A104. The edit reached the tool; the reason beside it still described the old value.

    This is deliberately a diagnostic and not a parse error: the file says "Read it; edit it",
    so a person who changes a number must be *told* to update the reason, not handed a stack
    trace.
    """
    built = build_spine(tmp_path)
    edit_setting(built, "subread_featurecounts.min_mqs", value=30)

    with pytest.raises(DiagnosticError) as caught:
        emit(Pipeline.model_validate(yaml.safe_load((built / "pipeline.yml").read_text())),
             out=tmp_path / "out")
    assert caught.value.code == "MD0223"
    assert "0" in str(caught.value) and "30" in str(caught.value)


def test_editing_a_value_and_its_reason_together_is_accepted(tmp_path):
    built = build_spine(tmp_path)
    edit_setting(built, "subread_featurecounts.min_mqs", value=30,
                 reason="lab SOP BIOINF-014 requires MAPQ >= 30", for_value=30)

    emit(Pipeline.model_validate(yaml.safe_load((built / "pipeline.yml").read_text())),
         out=tmp_path / "out")

    assert "-Q 30" in (tmp_path / "out" / "nextflow.config").read_text()


def test_a_version_1_file_still_emits(tmp_path):
    """`for_value: null` means "written before 1.14" and must not fire MD0223."""
    built = build_spine(tmp_path)
    strip_for_value(built)          # delete every `for_value:` line, as a v1 file has none

    emit(Pipeline.model_validate(yaml.safe_load((built / "pipeline.yml").read_text())),
         out=tmp_path / "out")

    assert (tmp_path / "out" / "main.nf").exists()
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_pipeline_file.py -k for_value -v`
Expected: FAIL — `TypeError: Why() got an unexpected keyword argument 'for_value'`.

- [ ] **Step 3: Add the field**

```python
    for_value: ParamValue = None
    """The value this reason was written about.

    A `Why` is written once at resolution and never re-derived, so nothing noticed when the
    value moved underneath it — a hand-edited `min_mqs` reached the tool as 30 while the
    record still said "contract default", and `publish` stamped it. Audit A104.

    **`None` means "written before 1.14"**, not "explains nothing": a `version: 1` file has no
    such field and must still emit. `MD0223` therefore fires only when this is set and
    disagrees, which is the honest check — it can be false, and a check that can only pass is
    not a check.
    """
```

- [ ] **Step 4: Set it everywhere a `Why` is built**

Search for `Why(` across `mendel-resolver` and `comeni-core` and add `for_value=<the value>` at
each site. **Every one of them has the value in scope** — that is why this repair is cheap. Bump
`Pipeline.version` default to `2` in the same step.

- [ ] **Step 5: Add `MD0223`**

In `pipeline_file.py`, where settings are checked before emission:

```python
for step in pipeline.steps:
    for setting in step.settings:
        if setting.why.for_value is None or setting.why.for_value == setting.value:
            continue
        found.append(Diagnostic(
            code="MD0223",
            where=f"{step.id}.{setting.name}",
            summary="the value changed and the reason beside it did not",
            detail=(f"    value      {setting.value!r}\n"
                    f"    reason for {setting.why.for_value!r}: {setting.why.reason}"),
            fix=("update `why.reason` to explain the new value and set `why.for_value` to it, "
                 "or revert the value. A reason that describes a number the pipeline no "
                 "longer uses is worse than no reason."),
        ))
```

Register `MD0223` in `diagnostics.yml` (`fires_on: [emit, upgrade, publish]`, `refuses: true`) and
run `make docs`.

- [ ] **Step 6: Run the tests, verify, watch it fail, record it, commit**

Run: `uv run pytest tests/test_pipeline_file.py -k for_value -v` — expected 3 passed.
Run: `make verify` — expected exit 0. Golden `pipeline.yml` files will move (a new field on every
`why:`); **read the diff before regenerating** — that is what caught the Jinja loop-collapse bug.

Revert the `MD0223` append, confirm the first test fails, restore, append the ledger row.

```bash
git commit -m "feat(core): a reason names the value it explains; MD0223 (A104, A105)"
```

---

## Task 2: `MetaEntry.why` — the measured facts carry their citation

**The defect (A80, A106).** `channels[].meta` carries `strandedness: reverse` — the value that
becomes featureCounts' `-s 2`, the flag `CLAUDE.md` advertises as proof the system works — with no
`why` of any kind. `MetaEntry` is `key` + `value`. The `cite` the measurement declares in
`registry/measurements/` never reaches the artifact.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py:151-158` — `MetaEntry.why`
- Modify: materialisation, where `MetaEntry` is built from the profile
- Test: `tests/test_pipeline_file.py`, `tests/test_profiling.py`

**Interfaces:**
- Consumes: `Why` with `for_value` from Task 1; `MeasurementRegistry`'s declared `cite`.
- Produces: `MetaEntry.why: Why` — **required, no default**, on the A48 principle: a record that
  cannot be constructed without answering the question is the fix that lasts.

- [ ] **Step 1: Write the failing test**

```python
def test_a_measured_fact_carries_its_citation(spine_pipeline):
    """A80. `-s 2` is this project's worked example of the system working, and it arrived
    at the tool with nothing attached."""
    meta = {e.key: e for c in spine_pipeline.channels for e in c.meta}
    assert meta["strandedness"].why.tier is Tier.STRUCTURAL
    assert meta["strandedness"].why.source is ValueSource.MEASURED
    assert meta["strandedness"].why.reason
    assert meta["strandedness"].why.for_value == "reverse"


def test_meta_cannot_be_built_without_a_why():
    with pytest.raises(ValidationError):
        MetaEntry(key="strandedness", value="reverse")
```

- [ ] **Step 2: Run it — expect `AttributeError: 'MetaEntry' object has no attribute 'why'`**

- [ ] **Step 3: Add the field and fill it at materialisation**

```python
    why: Why
    """Where this fact came from. **Required, no default.**

    A measured fact is a decision the pipeline rests on — `strandedness` becomes featureCounts'
    `-s`, and getting it wrong is the classic way to a matrix of zeroes. It reached the tool
    with nothing attached, and the measurement's own declared citation stopped at the registry.
    Audit A80.
    """
```

At the materialisation site, build it from the `DataProfile` entry: `source` is
`ValueSource.MEASURED` when the measurement declares `source: measured` and
`ValueSource.ASSERTED` when the goal simply stated it — **that distinction is A108 and it starts
here.** `reason` is the measurement's declared `cite` where one exists, and
`f"declared in the goal; {measurement.description}"` where it does not.

- [ ] **Step 4: Run, verify, watch it fail, record, commit**

`make verify` — golden files move again. Read the diff.

```bash
git commit -m "feat(core): a measured fact carries where it came from (A80, A106)"
```

---

## Task 3: `CallArg.why` — positional literals stop being anonymous

**The defect (A81, A90, A106).** `SAMTOOLS_SORT(…, 'bai')` chooses BAI over CSI, which constrains
which genomes the pipeline works on. `STAR_ALIGN(…, false)` decides whether alignment is
GTF-guided. Both reach the tools with `why: null`, in no `decisions:` block and no review queue.
`docs/reference/pipeline-schema.md` documents a `literal` + `why` pair the registry cannot
produce. The mechanism already exists — `NfInput.because` → `CallArg.why` is wired — and only the
data is missing.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/contract.py` — `NfInput.because` required for
  `literal` as it already is for `empty`
- Modify: materialisation — `CallArg.why` built from `NfInput.because`
- Modify: `registry/contracts/nf-core/samtools-sort.yml`, `star-align.yml`
- Test: `tests/test_runnable.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a_positional_literal_must_say_why():
    """A81. `'bai'` and `false` are analysis decisions wearing the costume of plumbing."""
    with pytest.raises(ValidationError, match="because"):
        NfInput(literal="bai")


def test_every_shipped_literal_carries_a_reason(spine_pipeline):
    literals = [a for s in spine_pipeline.steps for a in s.call if a.literal is not None]
    assert literals, "the spine has literals; if this is empty the query is wrong"
    assert all(a.why and a.why.reason for a in literals)
```

- [ ] **Step 2: Run it — expect `DID NOT RAISE`**

- [ ] **Step 3: Require `because` beside a literal**

Extend the existing validator that enforces `because` for `empty`. The docstring on
`NfInput.because` already argues the case for `empty`; add the parallel sentence:

```python
    A `literal` needs one for the same reason and was missed: `empty` was the placeholder
    everyone worried about, and the *values* went unexamined. `'bai'` picks an index format
    and `false` turns off GTF-guided alignment — neither is plumbing. Audit A81.
```

- [ ] **Step 4: Fill the two shipped contracts**

`registry/contracts/nf-core/samtools-sort.yml`:

```yaml
nf_inputs:
  - {ports: [bam]}
  - {empty: 3, because: "no reference is needed to sort; samtools takes one for CRAM output"}
  - literal: bai
    because: >
      BAI, not CSI. BAI is what every downstream tool in this spine reads and it is the
      nf-core default; CSI is required only for chromosomes above 512 Mbp, which no
      supported reference has. Revisit for genomes that do.
```

Read the existing file first and preserve the entries that are already there — the `empty: 3`
above is illustrative of the shape, not necessarily the current text.

`registry/contracts/nf-core/star-align.yml`, the trailing `{literal: false}`:

```yaml
  - literal: false
    because: >
      `star_ignore_sjdbgtf = false` — align *with* the annotation. The GTF is routed into this
      module and ignoring it would waste it. Task 7 turns this into a routed parameter; until
      then it is a contract constant with a stated reason rather than a bare `false`.
```

- [ ] **Step 5: Run, verify, watch it fail, record, commit**

```bash
git commit -m "feat(core): a positional literal carries its reason (A81, A90, A106)"
```

---

## Task 4: `Step.ext_args` carries a reason, and the reason is checked

**The defect (A82, A106).** `ext_args` reaches the tool with no `why` — recorded as deliberate,
and the recorded argument conflates *tier* with *reason*. Worse, the premise is graph-contingent:
one goal edit (`states: [trimmed]`) removes TrimGalore entirely and `--readFilesCommand zcat`
survives on STAR, justified by *"TrimGalore emits .fq.gz… a fact about the upstream module's
output format."* **A recorded reason that has stopped being true** — and stated as a fact when it
is contingent, so a lab supplying uncompressed trimmed reads gets an actively wrong flag with
nothing to catch it.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/contract.py` — `ext_args` becomes a record
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py` — `Step.ext_args` likewise
- Modify: `registry/contracts/nf-core/star-align.yml`
- Test: `tests/test_pipeline_file.py`

- [ ] **Step 1: Write the failing test**

```python
def test_ext_args_carries_a_reason(spine_pipeline):
    star = next(s for s in spine_pipeline.steps if s.id == "star_align")
    assert star.ext_args.template == "--readFilesCommand zcat"
    assert star.ext_args.why.reason
```

- [ ] **Step 2: Run it — expect `AttributeError: 'str' object has no attribute 'template'`**

- [ ] **Step 3: Make `ext_args` a record rather than a bare string**

```python
class ExtArgs(BaseModel):
    """Flags a module always needs, and why it needs them.

    Was a bare `NfTemplate`. The recorded argument for it carrying no `why` was that it is a
    contract fact rather than a decision — which conflates *tier* with *reason*: a tier-1 fact
    still has a reason, and `NfInput.empty` proves the point by carrying a tier-1 `Why` for a
    structurally identical thing. Audit A82.
    """

    model_config = _NO_EXTRAS

    template: NfTemplate = ""
    why: Why
```

Keep a `model_validator(mode="before")` accepting a bare string so every existing contract still
parses — the same ergonomic-form-versus-safe-representation split `Constraints._accept_mapping`
already uses. A bare string materialises with a `Why` whose reason is
`"declared by the contract with no stated reason (pre-1.14)"`, which is honest and greppable.

- [ ] **Step 4: State the real premise on the one contract that has one**

`registry/contracts/nf-core/star-align.yml`:

```yaml
ext_args:
  template: "--readFilesCommand zcat"
  why:
    tier: 1
    source: contract
    reason: >
      The reads reaching STAR in this registry are gzipped — TrimGalore emits `.fq.gz`, and a
      goal declaring `fastq.reads[trimmed]` directly is gzipped by convention too. Stated as
      a premise rather than a fact about TrimGalore, because one goal edit removes TrimGalore
      and this flag survives it (audit A82). If a laboratory supplies uncompressed reads this
      is wrong and nothing here will catch it — that is issue #39's `when`-expressiveness
      problem, not this field's.
```

**That last sentence is the deliverable of this task**, not the field. The premise is now
inspectable and its limit is written down.

- [ ] **Step 5: Run, verify, watch it fail, record, commit**

```bash
git commit -m "feat(core): ext_args states its premise, contingency and all (A82, A106)"
```

---

## Task 5: `Pin.because()` — precedence, and the axis/row split

**The defect (A79, A107, A78).** The function's docstring says *"row before block"*; the code is
`row.cite or decision.cite or row.because or decision.because`, which is cite-before-because. Two
consequences, found from opposite ends by two reviewers:

- the **shipped** registry cites the STAR paper as the reason **HISAT2** was chosen, reachable by
  changing one number in `examples/rnaseq-goal.yml`;
- authoring a `cite` **deletes** the plain-English sentence, so the registry's only prose
  explanation of its only tier-3 decision never reaches the artifact.

Reproduction sharpened the finding: the rule author's own comment shows the block `cite` was
written to justify the **decision axis** — "read length determines which aligner is appropriate",
for which Dobin et al. is a fair citation — not either row's choice. So the repair is not a
reordering. **The field is answering two questions and must become two.**

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules.py:137-145` — `because()`
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules.py:272+` — `_validate`
- Modify: `registry/rules/rnaseq.yml`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` — `MD0301`
- Test: `tests/test_audit_regressions.py`

- [ ] **Step 1: Write the failing test**

```python
def test_the_row_that_won_explains_itself_and_the_axis_is_separate():
    """A79 + A107. Dobin et al. justifies *asking about read length*, not *choosing HISAT2*."""
    pipeline = build_with_read_length(50)
    step = next(s for s in pipeline.steps if "hisat2" in s.id)
    assert "Dobin" not in step.why.reason
    assert "read length" in step.why.axis_reason
    assert step.why.reason


def test_a_rule_with_neither_reason_is_refused(tmp_path):
    """A78: it loaded, fired, and emitted a reason ending in a bare colon."""
    with pytest.raises(DiagnosticError) as caught:
        load(layer_roots=[REGISTRY, rule_layer(tmp_path, NO_CITE_NO_BECAUSE)])
    assert caught.value.code == "MD0301"
```

- [ ] **Step 2: Run it — expect `AttributeError: 'Why' object has no attribute 'axis_reason'`**

- [ ] **Step 3: Split the two questions**

```python
    def because(self) -> str:
        """Why *this row* won — the specific choice, never the axis.

        Was `row.cite or decision.cite or row.because or decision.because`, under a docstring
        claiming "row before block". Two bugs in one line: the precedence was cite-first, and
        a block-level `cite` justifies the *decision* ("read length determines which aligner
        is appropriate") while being printed as the reason for a *row* ("HISAT2 was chosen").
        The shipped registry therefore cited the STAR paper as the reason HISAT2 was picked.
        Audit A79, A107.
        """
        return self.row.because or self.row.cite or ""

    def axis_because(self) -> str:
        """Why this decision is made this way at all. The block's justification."""
        return self.decision.because or self.decision.cite or ""
```

Add `Why.axis_reason: Line = ""` and set it from `axis_because()` wherever a rule-sourced `Why`
is built.

- [ ] **Step 4: Give the shipped rows their own reasons**

`registry/rules/rnaseq.yml` — the block keeps the axis, each row gains its own choice:

```yaml
decisions:
  - decides: {producer_of: alignment.bam}
    because: "read length determines which aligner is appropriate"
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - when: {read_length: ">= 70"}
        then: nf-core/star/align@1.11.0
        because: "STAR's seed-and-extend suits long reads and it is nf-core/rnaseq's default"
        cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
      - when: {read_length: "< 70"}
        then: nf-core/hisat2/align@2.2.2
        because: "HISAT2 handles short reads with a far smaller index and memory footprint"
        cite: "Kim et al. 2019, doi:10.1038/s41587-019-0201-4"
```

**The HISAT2 row's citation is the point of the task.** It was wrong in the shipped registry and
nothing could have noticed, because the field it was wrong in did not exist.

- [ ] **Step 5: Refuse a row that justifies nothing (`MD0301`)**

In `_validate`, require `row.because or row.cite or decision.because or decision.cite`. Register
`MD0301` (`fires_on: [build, upgrade]`, `refuses: true`).

- [ ] **Step 6: Run, verify, watch it fail, record, commit**

```bash
git commit -m "fix(resolver): a row explains its own choice; the axis is separate (A79, A107, A78)"
```

---

## Task 6: `priority` carries its justification

**The defect (A76, critical; A128).** Tier 2 is *"a documented default exists"* and the design has
nowhere to put the document. Reproduced: a lab overlay raising featureCounts' `-Q` from 0 to 30 —
reads below MAPQ 30 now discarded — produces a **byte-identical** `why:` block, `from_layer: null`
included, while the step above it correctly attributes its layer. `ModuleContract.priority` is the
same defect one field over: a bare int whose justification is a YAML comment the loader discards.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/contract.py` — `Param.because`, `priority` record
- Modify: materialisation — a contract-default `Why` carries the param's `because` and its layer
- Modify: every contract in `registry/contracts/` that declares a `default:`
- Test: `tests/test_registry_layer.py`

- [ ] **Step 1: Write the failing test**

```python
def test_an_overlay_default_is_distinguishable_from_the_base_default(tmp_path):
    """A76: value 0 and value 30 produced byte-identical justifications."""
    base = build_spine(tmp_path / "base")
    lab = build_spine(tmp_path / "lab", registries=[REGISTRY, mapq_overlay(tmp_path)])

    base_why = setting_of(base, "subread_featurecounts.min_mqs").why
    lab_why = setting_of(lab, "subread_featurecounts.min_mqs").why

    assert base_why != lab_why
    assert lab_why.from_layer == "acme-lab"
    assert "SOP" in lab_why.reason
```

**Hand-write `mapq_overlay` inline** — `.audit-artifacts/` is untracked and may be pruned. The
overlay is one contract sharing featureCounts' module key with a different default:

```python
def _mapq_overlay(tmp_path: pathlib.Path) -> pathlib.Path:
    """A lab that discards reads below MAPQ 30, and says why. Audit A76.

    Shares the module key `nf-core/subread/featurecounts`, so it displaces the base contract
    rather than tying with it — invariant 11. Copy the base contract and change two things:
    the default, and the reason.
    """
    layer = tmp_path / "acme-lab"
    (layer / "contracts" / "nf-core").mkdir(parents=True)
    base = (REGISTRY / "contracts" / "nf-core" / "subread-featurecounts.yml").read_text()
    (layer / "contracts" / "nf-core" / "subread-featurecounts.yml").write_text(
        base.replace("default: 0", "default: 30").replace(
            "because: >", "because: 'lab SOP BIOINF-014 requires MAPQ >= 30'\n    _old: >", 1
        )
    )
    (layer / "registry.yml").write_text("name: acme-lab\nversion: 0\n")
    return layer
```

The `_old:` trick above will not survive `extra="forbid"` — **read the base contract and write the
overlay's `params:` block out in full instead**. It is four lines, and a fixture that fails to
load reads exactly like the test failing for the right reason.

- [ ] **Step 2: Run it — expect `assert Why(...) != Why(...)` to fail; they are equal**

- [ ] **Step 3: Give a default a stated reason and a layer**

Add `Param.because: str = ""`. At materialisation, a tier-2 `Why` takes `reason` from
`param.because` (falling back to today's `f"contract default for {name}"` with the suffix
`" — no reason was declared"`, so the gap is visible rather than invisible) and **`from_layer`
from the layer the contract was loaded from**, which the loader already knows and currently drops
for parameter defaults.

- [ ] **Step 4: Fill the shipped defaults**

Every `default:` in `registry/contracts/` gains a `because:`. The prose already exists as comments
above each one — move it into the field. `registry/contracts/nf-core/subread-featurecounts.yml`:

```yaml
params:
  - name: min_mqs
    default: 0
    because: >
      featureCounts' own documented default. Declared rather than left to the tool so the
      threshold is part of the record, not part of the binary — a laboratory comparing two
      runs needs it written down. Changing it changes which reads are counted.
```

- [ ] **Step 5: Extend the same treatment to `priority`**

```yaml
priority: 10
priority_because: "nf-core/rnaseq's default aligner, so this registry prefers it by convention"
```

A bare int stays legal and materialises with `" — no reason was declared"`, matching Step 3.

- [ ] **Step 6: Run, verify, watch it fail, record, commit**

```bash
git commit -m "feat(core): a default states its reason and its layer (A76, A128)"
```

---

## Task 7: A91 — the fourth `Via`, a positional route

**The defect (A91, critical).** `Via` has three members and none emits into a call position. Three
of ten vendored modules take a bare `val` input — `star_ignore_sjdbgtf`, `index_format`,
`save_unaligned` — each a real analysis decision. Reproduced: routing STAR's own parameter the
only way the design permits produced **one call with two values of the same name, disagreeing** —
the documented, tier-4, human-answered one in `meta` where STAR never looks, and the one STAR
reads (`main.nf:47`) being the undocumented trailing `false`. `pipeline.yml` said the GTF was
ignored; the pipeline used it.

**This is the task that needs the `version: 2` bump most**, and it is last among the routing
repairs for that reason.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/routes.py` — `Via.POSITIONAL`
- Modify: `packages/comeni-core/src/comeni_core/contract.py` — `Param.slot`
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` — `_argument` reads a setting
- Modify: `packages/mendel-compiler/src/mendel_compiler/conformance.py` — extend `MD0108`
- Modify: `registry/contracts/nf-core/star-align.yml`, `samtools-sort.yml`, `hisat2-align.yml`
- Test: `tests/test_conformance.py`, `tests/test_pipeline_file.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a_positional_parameter_reaches_the_call_and_nothing_else(tmp_path):
    """A91: the answered value went to `meta`, and STAR read a different one from the call."""
    built = build_spine(tmp_path, registries=[REGISTRY, positional_star_layer(tmp_path)])
    answer(built, "star_align.star_ignore_sjdbgtf", True)
    emitted = (built / "main.nf").read_text()

    assert "STAR_ALIGN(" in emitted
    assert emitted.count("star_ignore_sjdbgtf") == 0, "it is positional; no name is emitted"
    assert re.search(r"STAR_ALIGN\(.*,\s*true\)", emitted)


def test_a_meta_route_to_a_key_the_module_never_reads_is_refused():
    """MD0108 covered `ext` only, and its docstring said so. A91's other half."""
    with pytest.raises(DiagnosticError) as caught:
        check_contract(star_contract_with(via=Via.META, name="star_ignore_sjdbgtf"))
    assert caught.value.code == "MD0108"
```

- [ ] **Step 2: Run it — expect the emitted call to end in `false` regardless of the answer**

- [ ] **Step 3: Add the member and the slot**

```python
    POSITIONAL = "positional"
    """A bare `val` in the module's input block — a value with no name at the call site.

    Three of ten vendored modules take one and each is an analysis decision:
    `star_ignore_sjdbgtf` turns off GTF-guided alignment, `index_format` picks BAI or CSI,
    `save_unaligned` decides whether unmapped reads survive. None could be routed, so all
    three lived as contract constants — outside the tier ladder, with no reason and no review.
    Audit A91.
    """
```

`Param.slot: int | None = None` names the `nf_inputs` index this parameter fills; required when
`via is Via.POSITIONAL`, refused otherwise.

- [ ] **Step 4: Emit the resolved value into the call position**

In `_argument`, before the literal branch:

```python
    if arg.from_setting is not None:
        setting = _setting(step, arg.from_setting)
        return _render_literal(setting.value)
```

`CallArg.from_setting: PortName | None` is set at materialisation when a `Param` declares that
slot. An unanswered tier-4 positional (`value: null`) must **refuse** rather than emit `null` —
add `MD0224` for it, because `STAR_ALIGN(..., null)` is a runtime failure with a confusing message
and the artifact already knows the answer is missing.

- [ ] **Step 5: Extend `MD0108` to meta routes it can check**

`_dead_ext_routes` gates on `param.via is not Via.EXT`. A `via: meta` key that the module's script
never mentions is checkable by the same substring the parser already extracts. Rename the function
`_dead_routes`, keep the code `MD0108` — **a code is never renumbered** — and add the meta arm.

- [ ] **Step 6: Route the three real parameters**

`registry/contracts/nf-core/star-align.yml`:

```yaml
  - name: star_ignore_sjdbgtf
    via: positional
    slot: 3
    default: false
    because: >
      Align with the annotation. The GTF is routed into this module; ignoring it discards
      splice-junction information that the whole point of a spliced aligner is to use.
```

And remove the `{literal: false}` entry from `nf_inputs` — the slot is now filled by the
parameter. Do the same for `samtools/sort`'s `index_format` and `hisat2/align`'s `save_unaligned`.

- [ ] **Step 7: Run, verify, watch it fail, record, commit**

`make verify` **and** `uv run pytest -m slow` — this changes an emitted call in the spine, which
is precisely what `test_counts.py` exists to catch.

```bash
git commit -m "feat: a positional route, so a val input can be decided (A91)"
```

---

## Task 8: A77 — a human's reason survives `upgrade`

**The defect (A77, critical).** Tier 4 is the honesty mechanism and the declared difference from a
chat window, and it is the one tier where a *person* supplies the answer. There is no field in
which that person can say why. Reproduced in four documented steps: a hand-written
`why.reason` — *"our sequencer is an Illumina NovaSeq X; lab SOP BIOINF-014"* — is **deleted** by
`mendel upgrade`, restored to *"selected the first of 1 candidates without judgement — please
review"* under `source: human`. `upgrade` reported `1 decisions replayed, 0 newly asked` and said
nothing, because every axis it compares is generated code.

Task 1 gave a `Why` the value it explains. This gives a *person* somewhere to write one, and makes
`upgrade` preserve it.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/decision.py` — `ParamDecision.override_reason`
- Modify: `packages/mendel-resolver/src/mendel_resolver/replay.py` — carry it through
- Modify: `packages/mendel-resolver/src/mendel_resolver/diff.py` — report its loss
- Modify: `docs/reference/pipeline-schema.md` — document how to answer *and explain*
- Test: `tests/test_upgrade.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a_human_reason_survives_upgrade(tmp_path):
    """A77, end to end, in the four steps the reference documents."""
    built = build_spine(tmp_path)
    answer(built, "star_align.seq_platform", "illumina",
           reason="our sequencer is an Illumina NovaSeq X; lab SOP BIOINF-014")

    upgraded = upgrade(built, out=tmp_path / "up")

    why = setting_of(upgraded, "star_align.seq_platform").why
    assert why.source is ValueSource.HUMAN
    assert why.reason == "our sequencer is an Illumina NovaSeq X; lab SOP BIOINF-014"
    assert "without judgement" not in why.reason


def test_an_answered_question_does_not_ask_for_review_of_itself(tmp_path):
    """`source: human` and "selected without judgement" coexisted in the shipped path."""
    built = build_spine(tmp_path)
    answer(built, "star_align.seq_platform", "illumina")
    why = setting_of(upgrade(built, out=tmp_path / "up"), "star_align.seq_platform").why
    assert "please review" not in why.reason
```

- [ ] **Step 2: Run it — expect the machine text back in both**

- [ ] **Step 3: Give the answer a reason of its own**

`ParamDecision.override_reason: Line = ""`, beside the existing `human_override`. `replay.py`
carries it into the rebuilt `Why.reason` when an override is replayed, and where it is empty the
reason becomes `"answered by a human; no reason was given"` — **not** the flag-only text, which
describes something that happened before the person arrived.

- [ ] **Step 4: Report the loss rather than performing it silently**

`diff_pipeline` compares module ids, settings and wiring. Add `override_reason` to
`_setting_changes` so that dropping one is a reported `Change`, not a silent restore. The
docstring's argument for the blind-spot verdict stands and is not replaced by this — a diff that
compares every field still cannot see the compiler changing.

- [ ] **Step 5: Document the round trip that now works**

In `docs/reference/pipeline-schema.md`, under *Answering a tier-4 question is editing this file*,
add the second half: write the value **and** the reason, and both survive `upgrade`. Note the
A112 contradiction while here — the schema doc says `human_override` "is not where you write one"
and `MD0220`'s message says to set it. Make the two agree; state which one is right in the commit
message.

- [ ] **Step 6: Run, verify, watch it fail, record, commit**

```bash
git commit -m "feat: a human's answer carries a human's reason, and upgrade keeps it (A77)"
```

---

## Finishing

- [ ] **Run everything**

`make verify && uv run pytest -m slow` — exit 0 on both.

- [ ] **Rebuild the example and read it as a stranger**

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --out build/ --gate stub
```

Open `build/pipeline.yml` and check the claim this plan exists to make true: **every value that
reaches the generated Nextflow carries a reason a stranger could act on.** Count them the way the
audit did — the six are `star_align.ext_args`, two `call[].literal`s, two `channels[].meta`
entries, and `subread_featurecounts.min_mqs`. Five of six carried nothing before this plan.

- [ ] **Update the artifact's own header**

`pipeline.yml`'s header says *"Every value carries a `why:`"*. It was false when written. Confirm
it is now true, and if any case remains, **change the header rather than the claim** — a document
that overstates its file is how A106 stayed invisible.

- [ ] **Close the findings in `CLAUDE.md` and write the journal entry**

A76, A77, A78, A79, A80, A81, A82, A90, A91, A104, A105, A106, A107, A128 close here. A108
(tier 3 carries no premise) and A130 (nothing marks a model-authored reason) are **not** closed by
this plan — Task 2's `MEASURED` vs `ASSERTED` split is A108's foundation and nothing more. Say so.

---

## Self-review notes

Predictions in this plan that are about code I read but did not run — correct them in place rather
than making the code match the plan:

1. **`ValueSource` may not have `MEASURED`/`ASSERTED`/`CONTRACT` members** (Tasks 2, 4). Read
   `comeni_core/tiers.py` first. If they are absent, adding them is part of Task 2 and the egress
   guard's allowlist needs the new enum.
2. **The materialisation sites are described, not located.** `Why(`, `MetaEntry(` and `CallArg(`
   construction all live in `comeni_core/pipeline.py`'s materialiser; find them by grep before
   Task 1, because every subsequent task edits the same function and a wrong first edit compounds.
3. **Task 7 removes an `nf_inputs` entry and adds a `Param` with a `slot`.** `MD0102` checks that
   the contract declares as many channels as the module takes — confirm a positional parameter
   still counts toward that arity, or `MD0102` will fire on all three contracts.
4. **Golden files move in six of eight tasks.** Read every golden diff before regenerating. That
   habit is what caught the Jinja `{%- endfor %}` collapse, and regenerating without reading is
   how a wrong emission ships green.

**Expect to correct this plan while executing it.**
